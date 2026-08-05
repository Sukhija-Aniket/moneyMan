import uuid
from decimal import Decimal

from pydantic import BaseModel


class OverviewSummary(BaseModel):
    total_income: Decimal
    total_spend: Decimal
    net: Decimal
    transaction_count: int
    needs_review_count: int
    currency: str


class CategorySummaryItem(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    total_amount: Decimal
    transaction_count: int


class AccountSummaryItem(BaseModel):
    account_id: uuid.UUID | None
    display_name: str
    total_amount: Decimal
    transaction_count: int


class BankSummaryItem(BaseModel):
    issuer_name: str
    total_amount: Decimal
    transaction_count: int


class TrendPoint(BaseModel):
    period: str
    total_income: Decimal
    total_spend: Decimal
    transaction_count: int
