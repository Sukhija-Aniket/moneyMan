import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base

# Backend-owned: one row per unsynced gap segment computed for a sync_requests row. The
# worker never writes here — it only publishes GmailSyncFetchEvent, which the backend
# applies to mark a segment terminal. total_candidates/processed_candidates exist purely for
# progress display; a segment is terminal ("success"/"failed") the moment its single
# GmailSyncFetchEvent arrives, not by counting up to total_candidates itself (the fetch stage
# already did that counting before emitting the event).


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
