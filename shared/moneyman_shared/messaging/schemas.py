from pydantic import BaseModel


class GmailSyncJob(BaseModel):
    """Published by the backend to GMAIL_SYNC_JOBS_TOPIC, one per gap segment; consumed by
    the worker's fetch stage. date_from/date_to are omitted only for a plain "Sync now"
    (most recent N messages)."""

    segment_id: str
    user_id: str
    date_from: str | None = None  # ISO date, e.g. "2026-07-01"
    date_to: str | None = None


class EmailExtractionJob(BaseModel):
    """Published once per candidate email by the fetch stage to EMAIL_EXTRACTION_JOBS_TOPIC;
    consumed by the extraction stage. Only acked after that email's outcome is fully
    committed — a crash before ack means Pulsar redelivers this exact message, so a single
    email's failure is never silently lost."""

    segment_id: str
    user_id: str
    raw_email_id: str


class EmailExtractionEvent(BaseModel):
    """Published once per email by the extraction stage to EMAIL_EXTRACTION_EVENTS_TOPIC;
    consumed by the fetch stage (not the backend) to track how many of a segment's
    candidates have settled."""

    segment_id: str
    raw_email_id: str
    outcome: str  # "extracted" | "not_transaction" | "classify_failed" | "extract_failed"


class GmailSyncFetchEvent(BaseModel):
    """Published once per segment by the fetch stage to GMAIL_SYNC_FETCH_EVENTS_TOPIC —
    either immediately on a whole-segment fetch failure, or after every EmailExtractionEvent
    for this segment's candidates has been received. Consumed by the backend to mark the
    segment terminal and merge-insert into fetched_ranges/synced_ranges as appropriate.

    status is a 3-state outcome, not a flat success/failed pair:
      "failed"              - the fetch itself failed outright (Gmail API error, user not
                               found). Nothing usable was written — no fetched_ranges or
                               synced_ranges entry for this segment's range.
      "extraction_failed"   - fetch succeeded (raw_emails were written — merge into
                               fetched_ranges so Gmail is never re-listed for these dates),
                               but at least one candidate ended in classify_failed/
                               extract_failed. Those are transient LLM-call failures, not
                               verdicts, so this range must NOT be merged into synced_ranges
                               — a later sync request should still pick these emails up for
                               reclassification.
      "extraction_complete" - fetch succeeded AND every candidate reached a genuine verdict
                               (extracted/not_transaction). Merge into both fetched_ranges
                               and synced_ranges.
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
