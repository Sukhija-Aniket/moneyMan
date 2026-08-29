import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, PlainSerializer

# Pydantic serializes Decimal to a JSON string by default (precision-safe, but every
# frontend chart/table here expects a JS number for arithmetic and Recharts dataKey
# plotting) — serialize as float instead for all money fields in these summary responses.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float)]


class OverviewSummary(BaseModel):
    total_income: Money
    total_spend: Money
    net: Money
    transaction_count: int
    needs_review_count: int
    currency: str


class CategorySummaryItem(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    total_income: Money
    total_spend: Money
    transaction_count: int


class AccountSummaryItem(BaseModel):
    account_id: uuid.UUID | None
    display_name: str
    total_income: Money
    total_spend: Money
    transaction_count: int


class BankSummaryItem(BaseModel):
    issuer_name: str
    total_income: Money
    total_spend: Money
    transaction_count: int


class TrendPoint(BaseModel):
    period: str
    total_income: Money
    total_spend: Money
    transaction_count: int
