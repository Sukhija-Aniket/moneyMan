from dataclasses import dataclass

import anthropic

from app.config import get_settings

CLASSIFY_TOOL = {
    "name": "classify_transaction_email",
    "description": "Classify whether an email is a bank/card transaction notification.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_transaction_email": {
                "type": "boolean",
                "description": "True if this email notifies the user of a specific debit/credit/transaction.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in this classification, between 0 and 1.",
            },
            "reason": {
                "type": "string",
                "description": "One-sentence rationale for the classification.",
            },
        },
        "required": ["is_transaction_email", "confidence", "reason"],
    },
}


@dataclass
class ClassificationResult:
    is_transaction_email: bool
    confidence: float
    reason: str


def _client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def classify_email(subject: str | None, sender: str | None, snippet: str | None) -> ClassificationResult:
    settings = get_settings()

    if settings.GMAIL_SYNC_DRY_RUN:
        return ClassificationResult(
            is_transaction_email=True,
            confidence=0.99,
            reason="dry run: canned classification, no Anthropic call made",
        )

    client = _client()

    user_content = (
        f"Sender: {sender or ''}\n"
        f"Subject: {subject or ''}\n"
        f"Snippet: {snippet or ''}"
    )

    response = client.messages.create(
        model=settings.GMAIL_CLASSIFICATION_MODEL,
        max_tokens=256,
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
