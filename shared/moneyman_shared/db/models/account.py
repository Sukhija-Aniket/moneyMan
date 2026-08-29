import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base

if TYPE_CHECKING:
    from moneyman_shared.db.models.transaction import Transaction
    from moneyman_shared.db.models.user import User


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        # Grouped by last4 alone (not issuer_name/account_type, both LLM-extracted and
        # inconsistent across emails for the same real account — e.g. "Axis Bank" vs "Axis
        # Bank Ltd.", debit_card vs credit_card for the same card) — see
        # _get_or_create_account in shared/services/gmail_sync.py. last4 collisions across
        # genuinely different accounts are possible but rare; accepted tradeoff for now.
        UniqueConstraint("user_id", "last4", name="uq_accounts_user_last4"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    issuer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")
