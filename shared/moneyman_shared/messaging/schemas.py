from pydantic import BaseModel


class GmailSyncJob(BaseModel):
    """Published by the backend to GMAIL_SYNC_JOBS_TOPIC; consumed by the worker's fetch
    stage. date_from/date_to are omitted for a plain "Sync now" (most recent N messages)."""

    trigger_id: str
    user_id: str
    date_from: str | None = None  # ISO date, e.g. "2026-07-01"
    date_to: str | None = None


class GmailSyncFetchEvent(BaseModel):
    """Published once by the worker's fetch stage to GMAIL_SYNC_FETCH_EVENTS_TOPIC after
    listing Gmail messages, running Gate 1, and writing raw_emails rows — before any
    classify/extract has happened. Consumed by the backend to record how many candidate
    emails to expect (total_candidates) so it knows when the trigger is fully processed."""

    trigger_id: str
    status: str  # "fetched" | "failed" (failed = couldn't even list/fetch from Gmail)
    fetched: int = 0
    gate1_rejected: int = 0
    total_candidates: int = 0  # emails queued for extraction; trigger succeeds once this many EmailExtractionEvents arrive
    error: str | None = None


class EmailExtractionJob(BaseModel):
    """Published once per candidate email by the worker's fetch stage to
    EMAIL_EXTRACTION_JOBS_TOPIC; consumed by the extraction stage. Only acked after that
    email's outcome (classify/extract/write) is fully committed — a crash before ack means
    Pulsar redelivers this exact message, so a single email's failure is never silently lost."""

    trigger_id: str
    user_id: str
    raw_email_id: str


class EmailExtractionEvent(BaseModel):
    """Published once per email by the extraction stage to EMAIL_EXTRACTION_EVENTS_TOPIC
    after that email's processing settles (any outcome — extracted, discarded, failed).
    Consumed by the backend to increment sync_triggers.processed_candidates."""

    trigger_id: str
    raw_email_id: str
    outcome: str  # "extracted" | "not_transaction" | "classify_failed" | "extract_failed"
