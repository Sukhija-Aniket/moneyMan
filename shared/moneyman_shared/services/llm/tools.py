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
            "is_bank_or_card_txn": {
                "type": "boolean",
                "description": (
                    "True if this transaction moves money into/out of a bank account or "
                    "credit card (i.e. debit/credit applies). False for demat/brokerage/stock "
                    "trade confirmations (buy/sell orders, dividend credits inside a brokerage "
                    "account, etc.) -- those are securities activity, not a bank/card "
                    "transaction, even though cash value is involved."
                ),
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
                "description": (
                    "Whether money left (debit) or entered (credit) the account. Only "
                    "meaningful when is_bank_or_card_txn is true; still pick your best guess "
                    "when it is false (e.g. buy=debit, sell=credit for a securities trade) but "
                    "it will not be used to record a bank/card transaction."
                ),
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
                "pattern": "^[0-9]{4}$",
                "description": (
                    "EXACTLY the last 4 digits of the account/card, digits only — no masking "
                    "characters like 'X', '*', or spaces, and no other prefix/suffix. "
                    "E.g. if the email shows 'XX1516' or 'ending in 1516', extract '1516'. "
                    "Null if fewer than 4 digits are available."
                ),
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
        "required": ["is_transaction", "is_bank_or_card_txn", "confidence"],
    },
}

# Few-shot examples covering (a) txn_type (debit/credit) direction and (b) whether an email
# is a bank/card transaction at all vs. demat/brokerage securities activity, keyed by the
# confusing pattern each one teaches. Add new entries here as misclassified emails turn up —
# each becomes one more "Example" block appended to EXTRACTION_SYSTEM_PROMPT below.
# Keep each example anonymized (no real account/user names) and focused on the specific
# wording that made the classification non-obvious. is_bank_or_card_txn defaults to True
# when omitted, since most examples are ordinary bank/card transactions.
TXN_TYPE_EXAMPLES: list[dict] = [
    {
        "name": "credit_card_boilerplate_debit",
        "email": (
            "You have spent INR 1,200.00 using your Credit Card ending 4321 at "
            "ACME STORE. Avail up to 5% cashback credit on your next Credit Card "
            "statement."
        ),
        "txn_type": "debit",
        "reasoning": (
            "The transaction verb 'spent' next to the amount is the real signal. "
            "'Credit Card' and 'cashback credit' are product-name and marketing "
            "boilerplate, not direction indicators -- do not classify an email as "
            "'credit' just because the word 'credit' appears near the amount."
        ),
    },
    {
        "name": "ach_cr_explicit_credited",
        "email": (
            "We wish to inform you that your A/c no. XX1516 has been credited with "
            "INR 90.00 on 06-08-2026 at 14:31:57 IST by ACH-CR-LUPINLTD FNLDIV25 2."
        ),
        "txn_type": "credit",
        "reasoning": (
            "'has been credited with' stated directly against the named account is an "
            "explicit, unambiguous direction signal -- no need to look elsewhere in the "
            "email. The 'ACH-CR-' prefix in the reference/narration string is a further "
            "confirming signal: 'CR' here denotes a credit-type ACH transaction."
        ),
    },
    {
        "name": "demat_sell_order_not_bank_txn",
        "email": (
            "SELL order of Intuit Inc. for $500 is successful. "
            "(from Transactions INDmoney <transactions@transactions.indmoney.com>)"
        ),
        "txn_type": "credit",
        "is_bank_or_card_txn": False,
        "reasoning": (
            "This is a stock/securities SELL order confirmation from a demat/brokerage "
            "platform (INDmoney), not a bank or credit card transaction -- set "
            "is_bank_or_card_txn to false even though a dollar amount and 'successful' "
            "order language are present. Recognize this pattern from: a brokerage/demat "
            "sender domain, and BUY/SELL/order-execution language rather than "
            "debited/credited/spent language. Still give your best-guess txn_type "
            "(sell=credit, buy=debit) in case it's needed, but it will not be recorded "
            "as a bank/card transaction."
        ),
    },
]


def _render_txn_type_examples() -> str:
    blocks = []
    for ex in TXN_TYPE_EXAMPLES:
        is_bank_or_card_txn = ex.get("is_bank_or_card_txn", True)
        blocks.append(
            f"Email: \"{ex['email']}\"\n"
            f"-> is_bank_or_card_txn: {str(is_bank_or_card_txn).lower()}, txn_type: \"{ex['txn_type']}\"\n"
            f"Reasoning: {ex['reasoning']}"
        )
    return "\n\n".join(blocks)


EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured transaction data from bank and credit card notification emails. "
    "Use the extract_transaction tool for every response. If the email is not a real transaction "
    "notification, set is_transaction to false and confidence low.\n\n"
    "Determining txn_type (debit vs credit) can be subtle: bank templates often mention "
    "'credit'/'debit' in unrelated boilerplate (card product names, cashback offers, generic "
    "settlement-timing disclaimers). Look for the word that explicitly states which account "
    "is gaining or losing money, not just the nearest occurrence of 'credit'/'debit' to the "
    "amount.\n\n"
    "Also watch for emails that describe real money movement but are NOT a bank/card "
    "transaction -- e.g. demat/brokerage securities trades (buy/sell order confirmations, "
    "dividend credits inside a brokerage account). Set is_bank_or_card_txn to false for "
    "these, based on signals like a brokerage/demat sender domain or buy/sell/order-execution "
    "language, rather than debited/credited/spent language.\n\n"
    "Examples of this kind of ambiguity:\n\n"
    f"{_render_txn_type_examples()}"
)

# Few-shot examples for Stage A classification (is_transaction_email), keyed by the
# confusing pattern each one teaches. Add new entries here as misclassified emails turn up.
CLASSIFY_EXAMPLES: list[dict] = [
    {
        "name": "otp_not_a_completed_transaction",
        "email": (
            "The One Time Password (OTP) for your transaction at ZEPTO MARK of INR 297.00 "
            "with your SBI Credit Card ending 9961 is 616362. This OTP is valid for 10 "
            "minutes or 1 successful attempt, whichever is earlier."
        ),
        "is_transaction_email": False,
        "reasoning": (
            "An OTP email only means a transaction was initiated/attempted -- it does not "
            "confirm the transaction actually completed (the user might cancel, mistype the "
            "OTP, or the OTP might expire unused). Even though it has a specific amount, "
            "merchant, and card last4 that look like real transaction data, this is not a "
            "transaction notification. Only classify an email as a transaction when it "
            "confirms money already moved (e.g. 'debited', 'credited', 'payment successful')."
        ),
    },
]


def _render_classify_examples() -> str:
    blocks = []
    for ex in CLASSIFY_EXAMPLES:
        blocks.append(
            f"Email: \"{ex['email']}\"\n"
            f"-> is_transaction_email: {str(ex['is_transaction_email']).lower()}\n"
            f"Reasoning: {ex['reasoning']}"
        )
    return "\n\n".join(blocks)


CLASSIFICATION_SYSTEM_PROMPT = (
    "You classify whether an email is a bank/card transaction notification. "
    "Use the classify_transaction_email tool for every response.\n\n"
    "A transaction notification confirms money already moved (debited/credited/payment "
    "successful) -- it is not enough for an email to merely mention an amount, merchant, or "
    "account in the context of a transaction being attempted or in progress. Examples:\n\n"
    f"{_render_classify_examples()}"
)
