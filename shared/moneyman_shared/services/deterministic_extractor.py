import re
from dataclasses import dataclass
from datetime import date, datetime

# Bank/card transaction notification emails are templated, not free-form prose — amount,
# currency, and date almost always appear in one of a handful of recognizable formats.
# LLMs (especially smaller local models) are unreliable at extracting these precisely: they
# can pick up unrelated digit sequences from footers/reference codes (e.g. document IDs like
# "E001001528_07_2023") and hallucinate a plausible-looking but wrong date. A regex pass over
# the same structured formats gets amount/currency/date right deterministically, with no
# hallucination risk — so we prefer it over the LLM's values whenever it finds a match,
# falling back to the LLM only when the deterministic pass comes up empty.

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}

# Matches "INR 1,234.56", "Rs.297.00", "Rs 45", "$12.34", "1234.56 INR", etc. Currency
# codes are \b-bounded so they can't match as a substring of an unrelated longer token
# (e.g. a base64 tracking-URL fragment that happens to contain the letters "USD").
_AMOUNT_PATTERN = re.compile(
    r"\b(?P<prefix_code>USD|INR|EUR|GBP)\b\.?\s?(?P<prefix_amount>\d[\d,]*(?:\.\d{1,2})?)\b"
    r"|(?P<prefix_symbol>[$€£₹])\s?(?P<prefix_sym_amount>\d[\d,]*(?:\.\d{1,2})?)\b"
    r"|\bRs\.?\s?(?P<rs_amount>\d[\d,]*(?:\.\d{1,2})?)\b"
    r"|\b(?P<suffix_amount>\d[\d,]*(?:\.\d{1,2})?)\s?(?P<suffix_code>USD|INR|EUR|GBP)\b",
    re.IGNORECASE,
)

# Day-first dates (Indian bank convention): DD-MM-YYYY, DD-MM-YY, DD/MM/YYYY, DD/MM/YY.
_DATE_PATTERN = re.compile(
    r"\b(?P<day>[0-3]?\d)[-/](?P<month>[01]?\d)[-/](?P<year>\d{2}|\d{4})\b"
)

# "A/c no. XX1516", "ending 9961", "card ending in 4263" — digits directly preceded by
# masking characters or an "ending"-style word, so we don't grab an unrelated number.
_LAST4_PATTERN = re.compile(
    r"(?:ending\s*(?:in|with)?\s*|[Xx*]{2,}\s*)(\d{4})\b"
)

# Debit/credit direction keywords. Boilerplate footers mention "credit"/"debit" constantly
# ("Credit/Debit Card number", "RuPay Credit Card") with nothing to do with the transaction's
# actual direction, so these are only checked in a window immediately around the amount match
# (see _TXN_TYPE_WINDOW below) rather than anywhere in the email.
_CREDIT_KEYWORDS = re.compile(r"\b(credited|received|deposit(?:ed)?)\b", re.IGNORECASE)
_DEBIT_KEYWORDS = re.compile(r"\b(debited|spent|charged|withdr(?:awn|awal)|purchase)\b", re.IGNORECASE)
_TXN_TYPE_WINDOW = 80  # chars on each side of the amount match to search for direction keywords


@dataclass
class DeterministicResult:
    amount: float | None
    currency: str | None
    txn_date: date | None
    account_last4: str | None
    txn_type: str | None


def _parse_amount(text: str) -> tuple[float | None, str | None, re.Match | None]:
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return None, None, None

    groups = match.groupdict()
    if groups["prefix_code"]:
        return float(groups["prefix_amount"].replace(",", "")), groups["prefix_code"].upper(), match
    if groups["prefix_symbol"]:
        return float(groups["prefix_sym_amount"].replace(",", "")), _CURRENCY_SYMBOLS[groups["prefix_symbol"]], match
    if groups["rs_amount"]:
        return float(groups["rs_amount"].replace(",", "")), "INR", match
    if groups["suffix_code"]:
        return float(groups["suffix_amount"].replace(",", "")), groups["suffix_code"].upper(), match
    return None, None, None


def _parse_txn_type(text: str, amount_match: re.Match | None) -> str | None:
    """Looks for an explicit debit/credit direction keyword near where the amount was found —
    not just anywhere in the email, since boilerplate footers mention "credit"/"debit" in
    unrelated contexts (e.g. "Credit/Debit Card number", "RuPay Credit Card") constantly."""
    if amount_match is None:
        return None

    start = max(0, amount_match.start() - _TXN_TYPE_WINDOW)
    end = amount_match.end() + _TXN_TYPE_WINDOW
    window = text[start:end]

    is_credit = _CREDIT_KEYWORDS.search(window) is not None
    is_debit = _DEBIT_KEYWORDS.search(window) is not None

    if is_credit and not is_debit:
        return "credit"
    if is_debit and not is_credit:
        return "debit"
    return None  # ambiguous (both or neither found) — let the LLM's guess stand


def _normalize_year(year_str: str) -> int:
    if len(year_str) == 4:
        return int(year_str)
    # 2-digit year: templated bank emails are near-real-time, so "assume current century" is safe.
    return 2000 + int(year_str)


def _parse_date(text: str, received_at: datetime | None) -> date | None:
    """Finds a day-first date in the text and sanity-checks it against received_at (bank
    notification emails describe a transaction that just happened, so the extracted date
    should be within a few days of when the email actually arrived) — this is what catches
    an LLM-style hallucinated year; a regex match can still land on a footer reference number
    that happens to look like a date, so the received_at check guards against that too."""
    candidates: list[date] = []
    for match in _DATE_PATTERN.finditer(text):
        day, month, year_str = int(match["day"]), int(match["month"]), match["year"]
        if not (1 <= day <= 31 and 1 <= month <= 12):
            continue
        try:
            candidates.append(date(_normalize_year(year_str), month, day))
        except ValueError:
            continue

    if not candidates:
        return None

    if received_at is None:
        return candidates[0]

    received_date = received_at.date()
    plausible = [d for d in candidates if abs((d - received_date).days) <= 3]
    return plausible[0] if plausible else None


def _parse_last4(text: str) -> str | None:
    match = _LAST4_PATTERN.search(text)
    return match.group(1) if match else None


def extract_deterministic(
    subject: str | None, body_text: str | None, received_at: datetime | None
) -> DeterministicResult:
    text = f"{subject or ''}\n{body_text or ''}"
    amount, currency, amount_match = _parse_amount(text)
    return DeterministicResult(
        amount=amount,
        currency=currency,
        txn_date=_parse_date(text, received_at),
        account_last4=_parse_last4(text),
        txn_type=_parse_txn_type(text, amount_match),
    )
