import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base

# Backend-owned: one row per unsynced gap segment computed for a sync_requests row. The
# worker never writes here — it only publishes GmailSyncFetchEvent, which the backend
# applies here. total_candidates/processed_candidates exist purely for progress display.
#
# status is a small state machine, not a flat success/failed pair:
#   in_progress          -> Worker 1 is still listing/fetching from Gmail.
#   failed                -> the fetch itself failed outright (Gmail API error, user not
#                            found) — nothing usable was written, fetched_ranges/
#                            synced_ranges get no entry for this segment's range.
#   extraction_complete   -> fetch succeeded AND every candidate reached a genuine verdict
#                            (extracted/not_transaction) — the only status that feeds
#                            synced_ranges (see sync_fetch_events_consumer.py).
#   extraction_failed     -> fetch succeeded (so fetched_ranges DOES get an entry — Gmail
#                            never needs to be re-listed for these dates), but at least one
#                            candidate ended in classify_failed/extract_failed, which are
#                            transient LLM-call failures, not verdicts. A later sync request
#                            covering these dates will see the range missing from
#                            synced_ranges, recompute it as a gap, and Worker 1's fetch stage
#                            will find it already in fetched_ranges — skipping Gmail
#                            entirely and going straight to re-dispatching extraction for
#                            the still-non-terminal raw_emails rows.


class SyncSegment(Base):
    __tablename__ = "sync_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sync_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")

    total_candidates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sync_request: Mapped["SyncRequest"] = relationship(back_populates="segments")
