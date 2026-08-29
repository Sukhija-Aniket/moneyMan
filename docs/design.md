# Design: Async range sync via two-stage Pulsar pipeline

## Context

A sync request (an explicit `[date_from, date_to]` range — the earlier plain
"Sync now", most-recent-N-messages mode has been removed) fetches Gmail
messages in that range, and for each one runs classification +
extraction to produce a `Transaction`. This must not block the HTTP request
that triggers it — a wide date range means hundreds of emails run serially
against the LLM, which can take minutes. The backend must stay lightweight:
it only validates the request, figures out what actually still needs
fetching, enqueues work, and reports status; a separate worker pipeline does
all the actual work.

Goals:

- The triggering HTTP request returns immediately regardless of range size.
- Re-requesting a range that's partly (or fully) already synced only
  re-fetches the still-unsynced days — never re-processes days already done.
- A single sync request/segment can't run unboundedly long — enforced by
  capping the requestable range itself (`MAX_SYNC_RANGE_DAYS`, see
  Validation) rather than by chunking a segment's fetch internally.
- No email is ever silently dropped on a crash/redelivery.
- Only one sync can be `in_progress` per user for a given date at a time; an
  overlapping request is rejected for the overlapping part, not silently
  double-processed.
- A partial failure (e.g. Gmail errors out on days 15-20 of a 30-day
  request) only leaves days 15-20 unsynced — it doesn't force a re-sync of
  the whole 30-day request.

Related: `~/.claude/plans/fuzzy-tumbling-moon.md` (original architecture
plan), `docs/todo.md` (Phase 2 checklist this design fulfills).

## Range splitting: gap splitting only

The only range-splitting in this design is **gap splitting**: given a
requested range and the user's sync history, the backend computes which
sub-ranges are *not yet synced* (a DB-driven diff against `synced_ranges`,
below) and publishes one `GmailSyncJob` per gap segment. There is no
separate worker-side chunking of a segment's fetch — `MAX_SYNC_RANGE_DAYS`
(see Validation) caps how wide a single request (and therefore any single
segment) can ever be, so one Gmail `list` + pagination call per segment is
bounded enough on its own; an additional internal chunking step inside the
fetch stage would add complexity without a problem left to solve.

## Sync coverage: `fetched_ranges` and `synced_ranges`

Two coverage tables, tracking two genuinely different things — conflating
them was an earlier design/implementation mistake (a range that fetched
successfully but whose extraction entirely failed against a bad LLM
provider config got merged into a single "synced" table, permanently
hiding those emails from ever being retried, since a later sync request
saw zero gaps and never touched Gmail or those raw_emails rows again):

- **`fetched_ranges`** (shared — Worker 1 writes this directly, not just
  the backend): which date ranges have already had their Gmail messages
  **listed and written to `raw_emails`**, regardless of what later happened
  during classification/extraction. Gmail's `list`/`get_message` calls are
  the expensive, rate-limited part of this pipeline — once a range is in
  here, Worker 1 never calls Gmail for it again, even on a retry driven by
  `classify_failed`/`extract_failed` rows.
- **`synced_ranges`** (backend-owned): which date ranges are **fully**
  done — every candidate email reached a genuine verdict (`extracted` or
  `not_transaction`). Only this table feeds the backend's gap computation
  for `POST /gmail/sync/range` — a range with real extraction failures
  stays a "gap" here (and gets recomputed as such on a future request) even
  though it's fully covered in `fetched_ranges`.

Both tables have the identical shape and gap-computation/merge logic
(`moneyman_shared.services.coverage`, used by both the worker and the
backend against their respective table):

```
fetched_ranges / synced_ranges
  id          uuid primary key
  user_id     uuid, fk users, indexed
  date_from   date
  date_to     date
```

A `fetched_ranges` row is inserted by Worker 1 the moment a segment's fetch
(listing + Gate 1 + `raw_emails` write) completes — independent of
extraction outcome. A `synced_ranges` row is inserted by the backend only
when a segment's `GmailSyncFetchEvent` reports `status="extraction_complete"`
(see "Stage 1: Fetch" and the `GmailSyncFetchEvent` schema below). Rows in
either table start out **disjoint but not merged** — e.g. syncing `[20,50]`
then `[54,70]` leaves two rows; a later request for `[40,60]` diffs against
both and finds `[51,53]` as the only gap (day 50→54 gap, intersected with
the query range). Gap computation always diffs against the full row set for
the user, so correctness never depends on rows being merged — but the row
count per user grows unboundedly with repeated small syncs, so merging is a
required maintenance step, not optional cleanup (see "Merging coverage
ranges" below).

**Gap computation** (`date_from, date_to, user_id, table` → `list[(date_from, date_to)]`) —
identical algorithm against either table:

1. Load all rows of the table for the user overlapping the requested range.
2. Sort by `date_from`, merge any that touch/overlap into a coalesced
   "already covered" interval list.
3. Subtract the coalesced list from the requested range → the remaining
   pieces are the gaps. Zero gaps means the whole request is already
   covered by that table.

## Merging coverage ranges

Two points where merging matters, handled identically for both
`fetched_ranges` and `synced_ranges`:

- **On insert (eager, required for correctness of adjacency, not just
  tidiness)**: when a row is about to be inserted, first check for existing
  rows of the same table that touch or overlap it
  (`existing.date_to >= new.date_from - 1 day` and
  `existing.date_from <= new.date_to + 1 day`). If any are found, delete
  them and insert a single row spanning the union instead of adding a third
  disjoint row. Continuing the running example: `[20,50]` and `[54,70]`
  already exist; a `[51,53]` insert arrives; since `50` and `54` are each
  within 1 day of `51`/`53`, all three collapse into one `[20,70]` row. This
  is a normal part of handling the insert, not a separate job — it keeps
  the common "fill in a gap" case from ever fragmenting.
- **Periodic compaction (best-effort maintenance)**: even with eager
  merge-on-insert, concurrent segments from different in-flight requests
  can each insert a row that turns out to be adjacent to another only after
  both land (a race the eager step alone can't fully close). A periodic job
  (e.g. hourly, per user or globally) re-scans each table, merges any rows
  that touch/overlap, and replaces them with their union. This is pure
  cleanup — gap computation is correct against an unmerged row set too —
  but keeps row counts from growing unboundedly for users who sync often in
  small increments.

Only a genuinely successful outcome ever gets merge-inserted into either
table — `fetched_ranges` only from a fetch that didn't error outright,
`synced_ranges` only from `status="extraction_complete"`. `in_progress`,
`failed`, and `extraction_failed` segments insert nothing into
`synced_ranges` (though `extraction_failed` still inserts into
`fetched_ranges`), for debuggability and correctness — see the
`GmailSyncFetchEvent` schema below for the full status semantics.

## Segment tracking: `sync_requests` + `sync_segments`

A request can fan out into multiple gap segments, each independently
succeeding or failing, so tracking needs a parent/child shape instead of
the one-row-per-request model:

```
sync_requests
  id                 uuid primary key
  user_id            uuid, fk users, indexed
  date_from          date
  date_to            date
  status             text   -- "in_progress" | "success" | "partial_failure" | "failed"
  created_at         timestamptz

sync_segments
  id                     uuid primary key
  sync_request_id        uuid, fk sync_requests, indexed
  user_id                uuid, indexed
  date_from              date
  date_to                date
  status                 text  -- "in_progress" | "success" | "failed"
  total_candidates       int nullable
  processed_candidates   int default 0
  error                  text nullable
  started_at             timestamptz
  completed_at           timestamptz nullable
```

- One `sync_segments` row per gap segment computed for the request (could
  be zero, if the whole range was already covered — the parent goes
  straight to `success`).
- On a segment reaching `success`, the backend inserts a `synced_ranges` row
  for exactly that segment's `[date_from, date_to]`. Failed segments insert
  nothing — so a later request covering the same dates naturally computes
  them as still a gap and retries them. No separate retry mechanism is
  needed; re-running "Sync range" for the same dates is the retry path.

**In-progress overlap check**: before computing gaps, reject (409) if any
`sync_segments` row for this user with `status="in_progress"` overlaps the
requested range — this is what prevents two concurrent requests from
racing to fetch the same still-unsynced days.

## Architecture

```
Backend                                  Worker 1 (fetch)          Worker 2 (extraction)
  │                                           │                           │
  │  POST /gmail/sync (date_from, date_to)    │                           │
  │  1. validate range                        │                           │
  │  2. reject if full overlapping segment    │                           │
  │     already in_progress (409)             │                           │
  │  3. compute gaps vs. synced_ranges        │                           │
  │  4. create sync_requests row              │                           │
  │     + one sync_segments row per gap       │                           │
  │  5. publish one GmailSyncJob per segment  │                           │
  │─────────────────────────────────────────► │                           │
  │  6. respond 202 {request_id} immediately  │                           │
  │                                           ▼                           │
  │                                   for its segment:                    │
  │                                   - list msg ids in segment range     │
  │                                   - skip ids with an existing         │
  │                                     terminal raw_emails row           │
  │                                   - Gate 1 filter                     │
  │                                   - write raw_emails                  │
  │                                   - publish 1x EmailExtractionJob     │
  │                                     per candidate                     │
  │                                            │                          │
  │                                            │ EMAIL_EXTRACTION_JOBS    │
  │                                            ├─────────────────────────►│
  │                                            │                          │ classify → extract →
  │                                            │                          │ dedupe → write Transaction
  │                                            │                          │ ack only after commit
  │                                            │◄─────────────────────────┤
  │                                            │  EmailExtractionEvent    │
  │                                            │  (per email, to Worker1) │
  │                                            │                          │
  │       GmailSyncFetchEvent (per segment,    │                          │
  │       once all its emails are processed)   │                          │
  │◄───────────────────────────────────────────┤                          │
  │  7. mark segment success/failed            │                          │
  │  8. on success: insert synced_ranges row    │                          │
  │  9. once all segments terminal, derive      │                          │
  │     sync_requests.status                    │                          │
```

Note the event flow: `EmailExtractionEvent` goes **extraction stage →
fetch stage** (Worker 2 → Worker 1), not directly to the backend. Worker 1
owns the segment and is the one tracking "have all this segment's
candidates finished," so it aggregates per-email events itself and emits a
single `GmailSyncFetchEvent` per segment to the backend only once that
segment is fully drained. This keeps the backend's job to exactly two
writes per segment (mark terminal, insert `synced_ranges`) instead of
counting individual email events itself.

**Single writer principle**: only the backend writes `sync_requests`,
`sync_segments`, and `synced_ranges`. Workers never touch these tables —
they only publish events. The in-progress overlap check therefore can never
race with a worker-side write.

## API

### `POST /gmail/sync`

Request:

```json
{ "date_from": "2026-07-01", "date_to": "2026-08-01" }
```

`date_from`/`date_to` are both required.

Validation (range given):

- `date_to >= date_from`.
- `date_to` not in the future.
- `date_to - date_from <= MAX_SYNC_RANGE_DAYS` (e.g. 90 days).
- `date_to - date_from >= MIN_SYNC_RANGE_DAYS` (e.g. 1 day) — i.e. reject a
  zero-length or inverted range.

A validation failure responds `422` with the specific violated constraint.

Behavior (range given, passes validation):

1. Reject `409` if any `sync_segments` row for this user with
   `status="in_progress"` overlaps the requested range.
2. Compute gap segments against `synced_ranges`.
3. If no gaps: create a `sync_requests` row with `status="success"` directly
   (no segments, nothing published) and respond `202`.
4. Otherwise: create the `sync_requests` row (`status="in_progress"`), one
   `sync_segments` row per gap (`status="in_progress"`), publish one
   `GmailSyncJob` per segment, and respond `202`.

Response (`202`):

```json
{ "request_id": "…", "status": "in_progress", "segments": [
  { "segment_id": "…", "date_from": "2026-07-01", "date_to": "2026-07-15", "status": "in_progress" }
] }
```

Response (`409`):

```json
{ "conflicting_segment_id": "…", "date_from": "…", "date_to": "…" }
```

Response (`422`):

```json
{ "error": "date_to must not be more than 90 days after date_from" }
```

### `GET /gmail/sync/{request_id}`

Poll a request's aggregate status plus its per-segment breakdown.

```json
{
  "request_id": "…",
  "status": "in_progress",
  "date_from": "2026-07-01",
  "date_to": "2026-08-01",
  "segments": [
    {
      "segment_id": "…",
      "date_from": "2026-07-01",
      "date_to": "2026-07-15",
      "status": "success",
      "total_candidates": 22,
      "processed_candidates": 22
    },
    {
      "segment_id": "…",
      "date_from": "2026-07-16",
      "date_to": "2026-08-01",
      "status": "in_progress",
      "total_candidates": 31,
      "processed_candidates": 12
    }
  ]
}
```

### `GET /gmail/sync/current`

Convenience lookup for the frontend: does this user have any segment
`in_progress` right now? Used to disable/hide "Sync range" and show a
progress indicator without the frontend having to track a `request_id`
across page loads.

```json
{ "in_progress": true, "request_id": "…", "date_from": "…", "date_to": "…" }
```

## Messages

```python
class GmailSyncJob(BaseModel):
    """Published by the backend to GMAIL_SYNC_JOBS_TOPIC, one per gap
    segment; consumed by the worker's fetch stage."""
    segment_id: str
    user_id: str
    date_from: str | None = None  # ISO date
    date_to: str | None = None


class EmailExtractionJob(BaseModel):
    """Published once per candidate email by the fetch stage to
    EMAIL_EXTRACTION_JOBS_TOPIC; consumed by the extraction stage. Only
    acked after that email's outcome is fully committed — a crash before
    ack means Pulsar redelivers this exact message, so a single email's
    failure is never silently lost."""
    segment_id: str
    user_id: str
    raw_email_id: str


class EmailExtractionEvent(BaseModel):
    """Published once per email by the extraction stage to
    EMAIL_EXTRACTION_EVENTS_TOPIC; consumed by the fetch stage (not the
    backend) to track how many of this segment's candidates have settled."""
    segment_id: str
    raw_email_id: str
    outcome: str  # "extracted" | "not_transaction" | "classify_failed" | "extract_failed"


class GmailSyncFetchEvent(BaseModel):
    """Published once per segment by the fetch stage to
    GMAIL_SYNC_FETCH_EVENTS_TOPIC — either immediately on a whole-segment
    fetch failure, or after every EmailExtractionEvent for this segment's
    candidates has been received. Consumed by the backend to mark the
    segment terminal and merge-insert into fetched_ranges/synced_ranges as
    appropriate.

    status is a 3-state outcome, not a flat success/failed pair:
      "failed"              - the fetch itself failed outright (Gmail API
                               error, user not found). Nothing usable was
                               written — no fetched_ranges or synced_ranges
                               entry for this segment's range.
      "extraction_failed"   - fetch succeeded (raw_emails were written —
                               Worker 1 already merged this range into
                               fetched_ranges directly, so Gmail is never
                               re-listed for these dates), but at least one
                               candidate ended in classify_failed/
                               extract_failed. Those are transient LLM-call
                               failures, not verdicts (see extract_one_email)
                               — this range must NOT be merged into
                               synced_ranges, so a later sync request still
                               picks these emails up for reclassification.
      "extraction_complete" - fetch succeeded AND every candidate reached a
                               genuine verdict (extracted/not_transaction).
                               The backend merges this range into
                               synced_ranges.
    """
    segment_id: str
    status: str  # "failed" | "extraction_failed" | "extraction_complete"
    fetched: int = 0
    gate1_rejected: int = 0
    total_candidates: int = 0
    extracted: int = 0
    not_transaction: int = 0
    classify_failed: int = 0
    extract_failed: int = 0
    error: str | None = None
```

Topics:

```
GMAIL_SYNC_JOBS_TOPIC                  persistent://public/default/gmail-sync-jobs
EMAIL_EXTRACTION_JOBS_TOPIC            persistent://public/default/email-extraction-jobs
EMAIL_EXTRACTION_EVENTS_TOPIC          persistent://public/default/email-extraction-events
GMAIL_SYNC_FETCH_EVENTS_TOPIC          persistent://public/default/gmail-sync-fetch-events

GMAIL_SYNC_JOBS_SUBSCRIPTION           gmail-sync-worker
EMAIL_EXTRACTION_JOBS_SUBSCRIPTION     email-extraction-worker
EMAIL_EXTRACTION_EVENTS_SUBSCRIPTION   gmail-sync-worker
GMAIL_SYNC_FETCH_EVENTS_SUBSCRIPTION   gmail-sync-backend
```

Note `EMAIL_EXTRACTION_EVENTS_SUBSCRIPTION` is consumed by Worker 1
(`gmail-sync-worker`), not the backend — only `GMAIL_SYNC_FETCH_EVENTS_TOPIC`
reaches the backend.

## Stage 1: Fetch (Worker 1)

**Consumes**: `GMAIL_SYNC_JOBS_TOPIC`, `EMAIL_EXTRACTION_EVENTS_TOPIC`
**Publishes**: `EMAIL_EXTRACTION_JOBS_TOPIC` (one per candidate email),
`GMAIL_SYNC_FETCH_EVENTS_TOPIC` (once per segment)

On a `GmailSyncJob` (one per segment):

1. Look up the user; refresh the OAuth token if expired.
2. **`fetched_ranges` pre-check**: if `[date_from, date_to]` is fully
   covered by `fetched_ranges` already, skip straight to step 3.5 below —
   Gmail's `list`/`get_message` calls are the expensive, rate-limited part
   of this pipeline, and a range that's already been fetched must never pay
   that cost again just because some of its candidates later failed
   classification/extraction.
3. Otherwise, list Gmail message ids for the segment's `[date_from,
   date_to]` in one call (paginating as needed) — `MAX_SYNC_RANGE_DAYS`
   keeps this bounded, so no further internal splitting is needed. For each
   message id: skip if a `raw_emails` row already exists with a genuine-verdict
   classification for it; otherwise fetch the full message, run Gate 1, and
   write a `raw_emails` row (`classification="pending"` if it passes Gate
   1, `"not_transaction"` if Gate 1 rejects it). Once done, merge-insert
   `[date_from, date_to]` into `fetched_ranges` — regardless of what
   extraction later does with these candidates.
3.5. Derive the candidate list: either the ids just written/re-queued in
   step 3, or (if step 2 skipped Gmail entirely) every existing `raw_emails`
   row in this date range whose classification isn't yet a genuine verdict
   (`pending`/`candidate`/`classify_failed`/`extract_failed`).
4. Record, in memory/local state keyed by `segment_id`, the expected count
   of candidates — this is `total_candidates` for the segment.
5. For every candidate, publish one
   `EmailExtractionJob{segment_id, user_id, raw_email_id}`.
6. As `EmailExtractionEvent`s arrive back (from Worker 2) for this
   `segment_id`, track how many of `total_candidates` have settled. Once
   every candidate has a terminal event (or immediately, if
   `total_candidates == 0`), publish one `GmailSyncFetchEvent{segment_id,
   ...aggregated counters}` — `status="extraction_complete"` only if none
   of the candidates ended in `classify_failed`/`extract_failed`;
   `status="extraction_failed"` otherwise, even though every candidate did
   reach a terminal outcome (see the `GmailSyncFetchEvent` docstring above
   for why — this only affects `synced_ranges`, not `fetched_ranges`,
   which is already covered as of step 3).
7. Ack the originating `GmailSyncJob` only once its `GmailSyncFetchEvent`
   has been published. On a crash mid-segment, Pulsar redelivers the whole
   `GmailSyncJob` — safe to reprocess because both `raw_emails` writes
   (step 3) and `fetched_ranges` merge-inserts (idempotent — merging the
   same range twice is a no-op) are dedupe-checked, and republishing an
   `EmailExtractionJob` for an already-terminal email is a no-op downstream
   (Stage 2 is idempotent per `raw_email_id`).

If listing/fetching from Gmail fails outright for the whole segment (not a
single message), publish `GmailSyncFetchEvent{status="failed", error,
total_candidates=0}` immediately instead of waiting on extraction events
that will never be published — nothing is merged into `fetched_ranges`
either, since nothing was actually fetched.

Tracking per-segment in-flight counts (step 4/6) needs to survive a Worker 1
restart — persist it (e.g. a small `segment_id → total_candidates` +
received-count record, either in the worker's own lightweight store or
recomputable by re-querying `raw_emails` for the segment's candidates on
startup) rather than keeping it purely in process memory.

## Stage 2: Extraction (Worker 2)

**Consumes**: `EMAIL_EXTRACTION_JOBS_TOPIC`
**Publishes**: `EMAIL_EXTRACTION_EVENTS_TOPIC` (once per email, to Worker 1)

For each `EmailExtractionJob`:

1. Load the `raw_emails` row by `raw_email_id`.
2. Classify (Stage A) → extract (Stage B) → deterministic field extraction →
   duplicate check → write the `Transaction` row.
3. Publish `EmailExtractionEvent{segment_id, raw_email_id, outcome}`, where
   `outcome` is one of `extracted | not_transaction | classify_failed |
   extract_failed`.
4. Ack only after both the DB commit in step 2 and the publish in step 3
   succeed. If the consumer crashes between receiving the message and
   acking it, Pulsar redelivers this exact `EmailExtractionJob` — a single
   email's failure or crash can never silently vanish from the count Worker
   1 is waiting on.

Re-running steps 1-3 for the same `raw_email_id` on redelivery is safe: the
duplicate-detection pass and `Transaction` uniqueness constraints prevent a
second insert, so at worst there's a harmless re-classification.

## Backend responsibilities

- `POST /gmail/sync`: validate → overlap check → gap computation → create
  `sync_requests`/`sync_segments` → publish one `GmailSyncJob` per segment
  → respond immediately (see API section above).
- Consume `GMAIL_SYNC_FETCH_EVENTS_TOPIC`: mark the corresponding
  `sync_segments` row with the reported status (`failed` /
  `extraction_failed` / `extraction_complete`); only on
  `extraction_complete`, merge-insert a `synced_ranges` row for that
  segment's exact `[date_from, date_to]` (see "Merging coverage ranges") —
  note `fetched_ranges` is merge-inserted by the worker directly, not here.
  Once every segment under a `sync_requests` row is terminal, derive and
  set the parent's `status` (`success` if every segment is
  `extraction_complete`, `failed` if every segment is `failed`,
  `partial_failure` otherwise — which covers both a genuine mix and the
  "fetched fine, some emails still need reclassification" case).
- Run the periodic `fetched_ranges`/`synced_ranges` compaction job (see
  "Merging coverage ranges") so per-user row counts stay bounded over time.
- Serve `GET /gmail/sync/{request_id}` and `GET /gmail/sync/current` so the
  frontend can poll status and block a second concurrent sync from the UI
  side too (in addition to the backend's own overlap check).
- Segments that aren't `extraction_complete` are **not** retried
  automatically — they simply aren't written to `synced_ranges`, so the
  next `POST /gmail/sync` covering those dates naturally recomputes them as
  a gap and retries them. No separate retry/backoff mechanism. Critically,
  this retry is cheap for an `extraction_failed` segment: `fetched_ranges`
  already covers it, so Worker 1 skips Gmail entirely and goes straight to
  re-dispatching extraction for the still-non-terminal `raw_emails` rows.

## Open questions

1. **Segment granularity vs. request-level UX**: should the frontend surface
   per-segment progress (as in the `GET /gmail/sync/{request_id}` response
   above), or only the aggregate `sync_requests.status`? Per-segment is more
   informative but exposes an implementation detail (gap splitting) the user
   didn't ask for.
2. **Compaction job cadence/ownership**: "Merging synced_ranges" specifies
   eager merge-on-insert plus a periodic compaction sweep for the race case
   — need to decide the sweep's schedule (hourly? daily?) and whether it
   runs as a backend cron endpoint, a worker cron job, or a one-off script,
   consistent with however the rest of this codebase runs scheduled
   maintenance (nothing like that exists yet, per current repo state).
3. **`MAX_SYNC_RANGE_DAYS`/`MIN_SYNC_RANGE_DAYS` exact values**: doc uses 90
   / 1 as placeholders per your "3 months"/"not less than 1 day" — confirm
   exact bounds.
4. ~~**Worker 1 restart mid-segment**~~ — resolved: Worker 1 defers acking a
   `GmailSyncJob` until its segment is fully drained (step 7 of "Stage 1:
   Fetch" above), not right after dispatching `EmailExtractionJob`s. A crash
   or restart at any point before that leaves the message unacked, so Pulsar
   redelivers the whole segment and `fetch_and_queue_candidates` safely
   re-derives `total_candidates` from `raw_emails` — no separate persistence
   layer needed. (An earlier implementation acked right after dispatch,
   relying on in-memory per-segment counters alone; a worker restart in that
   window silently orphaned the segment with no way to recover — this is
   what the deferred-ack fix actually addresses.)
