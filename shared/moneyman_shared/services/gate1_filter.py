import re

# Gate 1 (free heuristic pre-filter, plan §3.3): reject obvious non-candidates using
# subject/snippet only, before spending any LLM call (Gate 2 / Stage A classification).

AMOUNT_PATTERN = re.compile(
    r"(?:USD|INR|EUR|GBP|Rs\.?|[$€£₹])\s?\d[\d,]*(?:\.\d{1,2})?|\d[\d,]*(?:\.\d{1,2})?\s?(?:USD|INR|EUR|GBP)",
    re.IGNORECASE,
)

TRANSACTION_KEYWORDS = [
    "debited",
    "credited",
    "debit",
    "credit",
    "transaction",
    "payment",
    "charged",
    "charge",
    "purchase",
    "spent",
    "withdrawn",
    "withdrawal",
    "deposit",
    "transfer",
    "balance",
    "statement",
    "account ending",
    "card ending",
    "available balance",
    "autopay",
    "invoice paid",
    "alert",
]

NEGATIVE_KEYWORDS = [
    "unsubscribe",
    "newsletter",
    "% off",
    "sale ends",
    "webinar",
    "job alert",
    "survey",
]


def passes_gate1(subject: str | None, snippet: str | None) -> bool:
    text = f"{subject or ''} {snippet or ''}"
    lowered = text.lower()

    if AMOUNT_PATTERN.search(text):
        return True

    if any(keyword in lowered for keyword in TRANSACTION_KEYWORDS):
        if any(neg in lowered for neg in NEGATIVE_KEYWORDS) and not AMOUNT_PATTERN.search(text):
            return False
        return True

    return False
