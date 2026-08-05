import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.account import AccountOut
from app.schemas.category import CategoryOut


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    currency: str
    txn_type: str
    merchant_raw: str | None = None
    merchant_normalized: str | None = None
    txn_date: date | None = None
    confidence_score: Decimal | None = None
    needs_review: bool
    ambiguity_notes: str | None = None
    category: CategoryOut | None = None
    account: AccountOut | None = None
    created_at: datetime


class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    merchant_normalized: str | None = None
    needs_review: bool | None = None


class TransactionListResponse(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int
