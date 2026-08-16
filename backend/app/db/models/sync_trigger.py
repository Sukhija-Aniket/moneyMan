import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from moneyman_shared.db.base import Base

# Backend-owned: tracks each Gmail sync trigger (plain "Sync now" or a date-range sync) and
# its outcome. The worker does the actual Gmail fetch / classify / extract / DB writes for
# raw_emails/transactions, but never writes to this table — only the backend updates status
# here, on trigger creation and again on consuming the worker's events. This keeps a single
# writer for "is this range currently being synced" so overlap checks can't race with worker
# writes.
#
# total_candidates/processed_candidates track completion across the async, per-email
# extraction pipeline: the fetch stage sets total_candidates once (how many emails passed
# Gate 1 and got queued for extraction); each extraction outcome increments
# processed_candidates. The trigger flips to "success" once processed_candidates reaches
# total_candidates — not when the fetch stage finishes, since extraction now happens later
# and independently per email.


class SyncTrigger(Base):
    __tablename__ = "sync_triggers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_candidates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
