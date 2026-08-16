import uuid
from datetime import date, datetime

from pydantic import BaseModel


class GmailSyncRequest(BaseModel):
    date_from: date | None = None
    date_to: date | None = None


class GmailSyncResult(BaseModel):
    fetched: int
    gate1_rejected: int
    classify_failed: int
    classified_non_transaction: int
    extracted_accepted: int
    extracted_needs_review: int
    extracted_discarded: int
    extract_failed: int


class GmailSyncTriggerOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    date_from: date
    date_to: date
    status: str
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class GmailStatus(BaseModel):
    connected: bool
    scope: str | None = None
    token_expiry: str | None = None
    earliest_synced_at: str | None = None
    latest_synced_at: str | None = None
