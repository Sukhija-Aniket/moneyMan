from dataclasses import dataclass
from typing import Protocol


@dataclass
class ClassificationResult:
    is_transaction_email: bool
    confidence: float
    reason: str


@dataclass
class ExtractionResult:
    is_transaction: bool
    is_bank_or_card_txn: bool | None
    amount: float | None
    currency: str | None
    txn_type: str | None
    merchant_or_counterparty: str | None
    txn_date: str | None
    account_last4: str | None
    issuer_or_bank_name: str | None
    account_type: str | None
    category_hint: str | None
    confidence: float
    ambiguity_notes: str | None
    raw: dict


class LLMProvider(Protocol):
    def classify_email(
        self, subject: str | None, sender: str | None, snippet: str | None
    ) -> ClassificationResult: ...

    def extract_transaction(
        self, subject: str | None, sender: str | None, body_text: str | None
    ) -> ExtractionResult: ...
