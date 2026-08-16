import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base

if TYPE_CHECKING:
    from moneyman_shared.db.models.user import User


class GmailWatchState(Base):
    """Created in Phase 1 for schema completeness; unused until Phase 2 Pub/Sub push ingestion."""

    __tablename__ = "gmail_watch_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    gmail_history_id: Mapped[str | None] = mapped_column(String, nullable=True)
    watch_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    topic_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="inactive")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="gmail_watch_state")
