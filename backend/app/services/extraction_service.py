from dataclasses import dataclass

import anthropic

from app.config import get_settings

EXTRACT_TOOL = {
    "name": "extract_transaction",
    "description": "Extract structured transaction details from a bank/card notification email body.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_transaction": {
                "type": "boolean",
                "description": "True if this email describes an actual financial transaction.",
            },
            "amount": {
                "type": "number",
                "description": "The transaction amount as a positive number, or null if not present.",
            },
            "currency": {
                "type": "string",
                "description": "ISO 4217 currency code, e.g. USD, INR, EUR.",
            },
            "txn_type": {
                "type": "string",
                "enum": ["debit", "credit"],
                "description": "Whether money left (debit) or entered (credit) the account.",
            },
            "merchant_or_counterparty": {
                "type": "string",
                "description": "Merchant name or counterparty as it appears in the email.",
            },
            "txn_date": {
                "type": "string",
                "description": "Transaction date in YYYY-MM-DD format, or null if unavailable.",
            },
            "account_last4": {
                "type": "string",
                "description": "Last 4 digits of the account/card, or null if unavailable.",
            },
            "issuer_or_bank_name": {
                "type": "string",
                "description": "Name of the issuing bank or card network, e.g. Chase, HDFC Bank.",
            },
            "account_type": {
                "type": "string",
                "description": "Account type, e.g. credit_card, debit_card, checking, savings.",
            },
            "category_hint": {
                "type": "string",
                "description": "A best-guess spending category, e.g. groceries, dining, travel.",
            },
            "confidence": {
                "type": "number",
                "description": "Overall confidence in this extraction, between 0 and 1.",
            },
            "ambiguity_notes": {
                "type": "string",
                "description": "Notes on any ambiguity, missing fields, or uncertainty; empty string if none.",
            },
        },
        "required": ["is_transaction", "confidence"],
    },
}


@dataclass
class ExtractionResult:
    is_transaction: bool
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


def _client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured transaction data from bank and credit card notification emails. "
    "Use the extract_transaction tool for every response. If the email is not a real transaction "
    "notification, set is_transaction to false and confidence low."
)


def extract_transaction(subject: str | None, sender: str | None, body_text: str | None) -> ExtractionResult:
    settings = get_settings()

    if settings.GMAIL_SYNC_DRY_RUN:
        return ExtractionResult(
            is_transaction=True,
            amount=42.0,
            currency="USD",
            txn_type="debit",
            merchant_or_counterparty="Dry Run Merchant",
            txn_date=None,
            account_last4="0000",
            issuer_or_bank_name="Dry Run Bank",
            account_type="credit_card",
            category_hint="uncategorized",
            confidence=0.99,
            ambiguity_notes="dry run: canned extraction, no Anthropic call made",
            raw={"dry_run": True},
        )

    client = _client()

    user_content = (
        f"Sender: {sender or ''}\n"
        f"Subject: {subject or ''}\n"
        f"Body:\n{body_text or ''}"
    )

    response = client.messages.create(
        model=settings.GMAIL_EXTRACTION_MODEL,
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
