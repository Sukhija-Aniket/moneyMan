import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base

if TYPE_CHECKING:
    from moneyman_shared.db.models.user import User


class BlacklistedSender(Base):
    """A sender address or bare domain (e.g. 'newsletter@x.com' or '@x.com') excluded from
    Gmail fetch entirely via a '-from:' search term — the email is never retrieved or stored,
    not just filtered after the fact. Read by both the backend (plain sync) and the worker
    (range sync); only the backend exposes CRUD routes for managing entries."""

    __tablename__ = "blacklisted_senders"
    __table_args__ = (UniqueConstraint("user_id", "sender", name="uq_blacklisted_senders_user_sender"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="blacklisted_senders")
