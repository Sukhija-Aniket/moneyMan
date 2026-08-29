import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy import select

from moneyman_shared.db.models.fetched_range import FetchedRange
from moneyman_shared.db.models.user import User
from moneyman_shared.db.session import AsyncSessionLocal
from moneyman_shared.messaging.client import get_pulsar_client
from moneyman_shared.messaging.schemas import (
    EmailExtractionEvent,
    EmailExtractionJob,
    GmailSyncFetchEvent,
    GmailSyncJob,
)
from moneyman_shared.messaging.topics import (
    EMAIL_EXTRACTION_EVENTS_SUBSCRIPTION,
    EMAIL_EXTRACTION_EVENTS_TOPIC,
    EMAIL_EXTRACTION_JOBS_TOPIC,
    GMAIL_SYNC_FETCH_EVENTS_TOPIC,
    GMAIL_SYNC_JOBS_SUBSCRIPTION,
    GMAIL_SYNC_JOBS_TOPIC,
)
from moneyman_shared.services.coverage import merge_insert_range
from moneyman_shared.services.gmail_sync import GmailSyncError, fetch_and_queue_candidates

logger = logging.getLogger(__name__)

# Worker 1 (fetch stage) — see docs/design.md "Stage 1: Fetch". Runs two consumer loops
# concurrently in this one process: GMAIL_SYNC_JOBS_TOPIC (one message per gap segment) and
# EMAIL_EXTRACTION_EVENTS_TOPIC (one message per email, reported back by the extraction
# stage). This process is the only one that knows a segment's total_candidates count and
# tracks how many have settled, so it — not the backend — decides when a segment is fully
# drained and emits the single GmailSyncFetchEvent for it.
#
# fetched_ranges pre-check: before calling Gmail's list API at all, check whether this
# segment's date range is already in fetched_ranges (meaning raw_emails were already written
# for it on a prior attempt, even if extraction later failed for some of them — see
# moneyman_shared.db.models.fetched_range). If fully covered, skip Gmail entirely and derive
# candidates straight from the existing raw_emails rows. Gmail's list/get_message calls are
# the genuinely expensive, rate-limited part of this pipeline — a classify_failed/
# extract_failed retry should never re-pay that cost.
#
# Ack discipline: a GmailSyncJob message is NOT acked when fetch_and_queue_candidates
# returns — only once the segment reaches a truly terminal state (every EmailExtractionEvent
# for its candidates has arrived and GmailSyncFetchEvent has been published, or the fetch
# itself failed outright). This can be long after the job was received — extraction happens
# asynchronously via Worker 2. Holding the ack this long is deliberate: the alternative (ack
# right after dispatching EmailExtractionJobs) means the only record of "how many candidates
# this segment has / how many have reported back" lives in this process's memory — a crash
# anywhere in that window orphans the segment forever (confirmed in practice: a worker
# restart mid-segment left it stuck in_progress with no way to recover, since nothing told
# Pulsar the GmailSyncJob was still unfinished work). Not acking until truly done means a
# crash simply leaves the message unacked, so Pulsar redelivers the whole GmailSyncJob to
# the next consumer, which safely re-derives everything via fetch_and_queue_candidates's
# existing dedup/idempotency (already-candidate raw_emails rows get re-queued, already-
# terminal ones don't).

_stop = False


def _receive_one(consumer, timeout_millis: int):
    try:
        return consumer.receive(timeout_millis=timeout_millis)
    except Exception:
        return None


class _SegmentState:
    __slots__ = (
        "total",
        "received",
        "extracted",
        "not_transaction",
        "classify_failed",
        "extract_failed",
        "msg",
    )

    def __init__(self, total: int, msg):
        self.total = total
        self.received = 0
        self.extracted = 0
        self.not_transaction = 0
        self.classify_failed = 0
        self.extract_failed = 0
        self.msg = msg  # the original GmailSyncJob Pulsar message — acked only once done

    def record(self, outcome: str) -> None:
        self.received += 1
        if outcome == "extracted":
            self.extracted += 1
        elif outcome == "not_transaction":
            self.not_transaction += 1
        elif outcome == "classify_failed":
            self.classify_failed += 1
        elif outcome == "extract_failed":
            self.extract_failed += 1

    @property
    def done(self) -> bool:
        return self.received >= self.total

    @property
    def has_failures(self) -> bool:
        return self.classify_failed > 0 or self.extract_failed > 0


class FetchStage:
    def __init__(self) -> None:
        self._segments: dict[str, _SegmentState] = {}
        self._lock = asyncio.Lock()
        self._fetch_meta: dict[str, dict] = {}  # segment_id -> {"fetched": int, "gate1_rejected": int}

    async def _publish_fetch_event(
        self, producer, jobs_consumer, segment_id: str, status: str, error: str | None = None
    ) -> None:
        state = self._segments.pop(segment_id, None)
        meta = self._fetch_meta.pop(segment_id, None) or {}
        event = GmailSyncFetchEvent(
            segment_id=segment_id,
            status=status,
            fetched=meta.get("fetched", 0),
            gate1_rejected=meta.get("gate1_rejected", 0),
            total_candidates=state.total if state else 0,
            extracted=state.extracted if state else 0,
            not_transaction=state.not_transaction if state else 0,
            classify_failed=state.classify_failed if state else 0,
            extract_failed=state.extract_failed if state else 0,
            error=error,
        )
        producer.send(event.model_dump_json().encode("utf-8"))
        if state is not None:
            jobs_consumer.acknowledge(state.msg)

    async def handle_sync_job(self, msg, job: GmailSyncJob, extraction_producer, fetch_events_producer, jobs_consumer) -> None:
        """Processes one GmailSyncJob. Never acks/nacks `msg` itself on the happy path — the
        message is only acked once the segment is fully drained (see _publish_fetch_event) or
        an outright fetch failure is reported. The caller (run_fetch_stage_forever) only
        negative_acknowledges on an unexpected exception escaping this function."""
        segment_id = job.segment_id
        date_from = date.fromisoformat(job.date_from) if job.date_from else None
        date_to = date.fromisoformat(job.date_to) if job.date_to else None

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == uuid.UUID(job.user_id)))
            user = result.scalar_one_or_none()
            if user is None:
                async with self._lock:
                    self._segments[segment_id] = _SegmentState(total=0, msg=msg)
                await self._publish_fetch_event(
                    fetch_events_producer, jobs_consumer, segment_id, "failed", error="User not found."
                )
                return

            try:
                fetch_result = await fetch_and_queue_candidates(
                    db, user, date_from, date_to, skip_gmail_if_already_fetched=True
                )
            except GmailSyncError as exc:
                logger.warning("Segment %s fetch failed: %s", segment_id, exc)
                async with self._lock:
                    self._segments[segment_id] = _SegmentState(total=0, msg=msg)
                await self._publish_fetch_event(
                    fetch_events_producer, jobs_consumer, segment_id, "failed", error=str(exc)
                )
                return
            except Exception as exc:
                logger.exception("Segment %s fetch failed unexpectedly", segment_id)
                async with self._lock:
                    self._segments[segment_id] = _SegmentState(total=0, msg=msg)
                await self._publish_fetch_event(
                    fetch_events_producer, jobs_consumer, segment_id, "failed", error=str(exc)
                )
                return

            # Fetch itself succeeded — merge-insert into fetched_ranges now, regardless of
            # what extraction later does with these candidates. Gmail must never be
            # re-listed for these dates again, even if some candidates end up
            # classify_failed/extract_failed.
            if date_from is not None and date_to is not None:
                await merge_insert_range(db, FetchedRange, user.id, date_from, date_to)
                await db.commit()

        async with self._lock:
            self._fetch_meta[segment_id] = {
                "fetched": fetch_result.fetched,
                "gate1_rejected": fetch_result.gate1_rejected,
            }
            self._segments[segment_id] = _SegmentState(total=len(fetch_result.candidate_raw_email_ids), msg=msg)

        if not fetch_result.candidate_raw_email_ids:
            await self._publish_fetch_event(fetch_events_producer, jobs_consumer, segment_id, "extraction_complete")
            return

        for raw_email_id in fetch_result.candidate_raw_email_ids:
            extraction_job = EmailExtractionJob(
                segment_id=segment_id, user_id=job.user_id, raw_email_id=str(raw_email_id)
            )
            extraction_producer.send(extraction_job.model_dump_json().encode("utf-8"))
        # `msg` stays unacked here — handle_extraction_event acks it once every candidate's
        # EmailExtractionEvent has arrived and is_done becomes true.

    async def discard_segment(self, segment_id: str) -> None:
        """Drops any in-memory state for a segment without acking/publishing anything —
        used when a GmailSyncJob is being nacked mid-processing, so a stale _SegmentState
        can't linger and be mistaken for the state of the eventual redelivered attempt."""
        async with self._lock:
            self._segments.pop(segment_id, None)
            self._fetch_meta.pop(segment_id, None)

    async def handle_extraction_event(self, event: EmailExtractionEvent, fetch_events_producer, jobs_consumer) -> None:
        async with self._lock:
            state = self._segments.get(event.segment_id)
            if state is None:
                # This segment's GmailSyncJob was redelivered to a different/restarted
                # process (or this is a genuine duplicate EmailExtractionEvent) — either way
                # this process has no state for it and nothing more to do here; the process
                # that owns the still-unacked GmailSyncJob will eventually re-fetch and
                # re-derive total_candidates itself.
                return
            state.record(event.outcome)
            is_done = state.done
            has_failures = state.has_failures

        if is_done:
            # classify_failed/extract_failed are transient LLM-call failures (see
            # extract_one_email), not verdicts. fetched_ranges already has this range
            # covered (merged in handle_sync_job once fetch itself succeeded) — but
            # "extraction_complete" (which feeds synced_ranges) requires every candidate to
            # have reached a GENUINE verdict, so any failure here reports
            # "extraction_failed" instead: fetch is done (never re-list Gmail for these
            # dates), but the range stays an open gap for synced_ranges purposes, so a
            # later sync request will pick these emails up again for reclassification.
            if has_failures:
                error = (
                    f"{state.classify_failed} email(s) failed classification, "
                    f"{state.extract_failed} failed extraction (of {state.total} candidates)."
                )
                await self._publish_fetch_event(
                    fetch_events_producer, jobs_consumer, event.segment_id, "extraction_failed", error=error
                )
            else:
                await self._publish_fetch_event(
                    fetch_events_producer, jobs_consumer, event.segment_id, "extraction_complete"
                )


async def run_fetch_stage_forever(stage: FetchStage) -> None:
    client = get_pulsar_client()
    jobs_consumer = client.subscribe(GMAIL_SYNC_JOBS_TOPIC, GMAIL_SYNC_JOBS_SUBSCRIPTION)
    events_consumer = client.subscribe(EMAIL_EXTRACTION_EVENTS_TOPIC, EMAIL_EXTRACTION_EVENTS_SUBSCRIPTION)
    extraction_producer = client.create_producer(EMAIL_EXTRACTION_JOBS_TOPIC)
    fetch_events_producer = client.create_producer(GMAIL_SYNC_FETCH_EVENTS_TOPIC)

    logger.info("Fetch stage started, listening on %s and %s", GMAIL_SYNC_JOBS_TOPIC, EMAIL_EXTRACTION_EVENTS_TOPIC)

    async def _consume_jobs():
        while not _stop:
            msg = await asyncio.to_thread(_receive_one, jobs_consumer, 2000)
            if msg is None:
                continue
            segment_id = None
            try:
                job = GmailSyncJob.model_validate_json(msg.data())
                segment_id = job.segment_id
                logger.info("Fetch stage processing segment %s (%s -> %s)", job.segment_id, job.date_from, job.date_to)
                await stage.handle_sync_job(msg, job, extraction_producer, fetch_events_producer, jobs_consumer)
            except Exception:
                logger.exception("Failed to process gmail-sync-jobs message")
                # Drop any partially-registered state for this segment before nacking, so a
                # stray EmailExtractionEvent for the aborted dispatch can't be misattributed
                # once Pulsar redelivers this GmailSyncJob and fetch_and_queue_candidates
                # re-derives everything from scratch.
                if segment_id is not None:
                    await stage.discard_segment(segment_id)
                jobs_consumer.negative_acknowledge(msg)

    async def _consume_extraction_events():
        while not _stop:
            msg = await asyncio.to_thread(_receive_one, events_consumer, 2000)
            if msg is None:
                continue
            try:
                event = EmailExtractionEvent.model_validate_json(msg.data())
                await stage.handle_extraction_event(event, fetch_events_producer, jobs_consumer)
                events_consumer.acknowledge(msg)
            except Exception:
                logger.exception("Failed to process email-extraction-events message")
                events_consumer.negative_acknowledge(msg)

    try:
        await asyncio.gather(_consume_jobs(), _consume_extraction_events())
    finally:
        extraction_producer.close()
        fetch_events_producer.close()
        jobs_consumer.close()
        events_consumer.close()
