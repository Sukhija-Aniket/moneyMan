import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.transaction import Transaction
    from app.db.models.user import User


class RawEmail(Base):
    __tablename__ = "raw_emails"
    __table_args__ = (UniqueConstraint("user_id", "gmail_message_id", name="uq_raw_emails_user_gmail_message"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    gmail_message_id: Mapped[str] = mapped_column(String, nullable=False)
    history_id: Mapped[str | None] = mapped_column(String, nullable=True)

    sender: Mapped[str | None] = mapped_column(String, nullable=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # pending | not_transaction | candidate | extracted | extract_failed
    classification: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="raw_emails")
    transaction: Mapped["Transaction | None"] = relationship(back_populates="raw_email", uselist=False)
