import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from moneyman_shared.db.base import Base
from moneyman_shared.db.models.review_status import REVIEW_STATUSES, ReviewStatus
from moneyman_shared.db.models.reviewed_by import REVIEWED_BY_VALUES, ReviewedBy

if TYPE_CHECKING:
    from moneyman_shared.db.models.account import Account
    from moneyman_shared.db.models.category import Category
    from moneyman_shared.db.models.raw_email import RawEmail
    from moneyman_shared.db.models.user import User


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "raw_email_id", name="uq_transactions_user_raw_email"),
        CheckConstraint(
            f"review_status IN ({', '.join(repr(s) for s in REVIEW_STATUSES)})",
            name="ck_transactions_review_status",
        ),
        CheckConstraint(
            f"reviewed_by IN ({', '.join(repr(s) for s in REVIEWED_BY_VALUES)})",
            name="ck_transactions_reviewed_by",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_emails.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    duplicate_of_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    txn_type: Mapped[str] = mapped_column(String, nullable=False)  # debit | credit

    merchant_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    merchant_normalized: Mapped[str | None] = mapped_column(String, nullable=True)

    txn_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(String, nullable=False, default="pending", index=True)
    # Set to "human" whenever review_status is changed via PATCH /transactions/{id} (the
    # only place a person/API caller can act) — "system" when the extraction pipeline
    # auto-confirms a high-confidence transaction without it ever going through "pending".
    # Lets the UI hide "Move to review" for transactions the user already vetted themself.
    reviewed_by: Mapped[ReviewedBy | None] = mapped_column(String, nullable=True)
    ambiguity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    raw_email: Mapped["RawEmail"] = relationship(back_populates="transaction")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
    account: Mapped["Account | None"] = relationship(back_populates="transactions")
