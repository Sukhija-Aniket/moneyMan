import anthropic

from moneyman_shared.config import get_settings
from moneyman_shared.services.llm.base import ClassificationResult, ExtractionResult
from moneyman_shared.services.llm.tools import (
    CLASSIFICATION_SYSTEM_PROMPT,
    CLASSIFY_TOOL,
    EXTRACT_TOOL,
    EXTRACTION_SYSTEM_PROMPT,
)


class AnthropicProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._classification_model = settings.GMAIL_CLASSIFICATION_MODEL
        self._extraction_model = settings.GMAIL_EXTRACTION_MODEL

    def classify_email(
        self, subject: str | None, sender: str | None, snippet: str | None
    ) -> ClassificationResult:
        user_content = f"Sender: {sender or ''}\nSubject: {subject or ''}\nSnippet: {snippet or ''}"

        response = self._client.messages.create(
            model=self._classification_model,
            max_tokens=256,
            system=CLASSIFICATION_SYSTEM_PROMPT,
            tools=[CLASSIFY_TOOL],
            tool_choice={"type": "tool", "name": "classify_transaction_email"},
            messages=[{"role": "user", "content": user_content}],
        )

        for block in response.content:
            if block.type == "tool_use":
                data = block.input
                return ClassificationResult(
                    is_transaction_email=bool(data["is_transaction_email"]),
                    confidence=float(data["confidence"]),
                    reason=str(data.get("reason", "")),
                )

        return ClassificationResult(is_transaction_email=False, confidence=0.0, reason="no tool_use block returned")

    def extract_transaction(
        self, subject: str | None, sender: str | None, body_text: str | None
    ) -> ExtractionResult:
        user_content = (
            f"Sender: {sender or ''}\nSubject: {subject or ''}\nBody:\n{body_text or ''}"
        )

        response = self._client.messages.create(
            model=self._extraction_model,
            max_tokens=1024,
            system=EXTRACTION_SYSTEM_PROMPT,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "extract_transaction"},
            messages=[{"role": "user", "content": user_content}],
        )

        for block in response.content:
            if block.type == "tool_use":
                data = block.input
                return ExtractionResult(
                    is_transaction=bool(data.get("is_transaction", False)),
                    is_bank_or_card_txn=data.get("is_bank_or_card_txn"),
                    amount=data.get("amount"),
                    currency=data.get("currency"),
                    txn_type=data.get("txn_type"),
                    merchant_or_counterparty=data.get("merchant_or_counterparty"),
                    txn_date=data.get("txn_date"),
                    account_last4=data.get("account_last4"),
                    issuer_or_bank_name=data.get("issuer_or_bank_name"),
                    account_type=data.get("account_type"),
                    category_hint=data.get("category_hint"),
                    confidence=float(data.get("confidence", 0.0)),
                    ambiguity_notes=data.get("ambiguity_notes"),
                    raw=data,
                )

        return ExtractionResult(
            is_transaction=False,
            is_bank_or_card_txn=None,
            amount=None,
            currency=None,
            txn_type=None,
            merchant_or_counterparty=None,
            txn_date=None,
            account_last4=None,
            issuer_or_bank_name=None,
            account_type=None,
            category_hint=None,
            confidence=0.0,
            ambiguity_notes="no tool_use block returned",
            raw={},
        )
