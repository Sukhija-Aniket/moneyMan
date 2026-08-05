from pydantic import BaseModel


class GmailSyncResult(BaseModel):
    fetched: int
    gate1_rejected: int
    classified_non_transaction: int
    extracted_accepted: int
    extracted_needs_review: int
    extracted_discarded: int
    extract_failed: int


class GmailStatus(BaseModel):
    connected: bool
    scope: str | None = None
    token_expiry: str | None = None
