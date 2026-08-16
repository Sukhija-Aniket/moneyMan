import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base

# Backend-owned: the parent record for one POST /gmail/sync call. A request fans out into
# zero or more sync_segments (one per gap in [date_from, date_to] not yet covered by
# synced_ranges) — status here is derived from the children, not written independently.


class SyncRequest(Base):
    __tablename__ = "sync_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    # "in_progress" | "success" | "partial_failure" | "failed"
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    segments: Mapped[list["SyncSegment"]] = relationship(
        back_populates="sync_request", cascade="all, delete-orphan"
    )
