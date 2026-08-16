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
        "required": ["is_transaction", "confidence"],
    },
}

EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured transaction data from bank and credit card notification emails. "
    "Use the extract_transaction tool for every response. If the email is not a real transaction "
    "notification, set is_transaction to false and confidence low."
)

CLASSIFICATION_SYSTEM_PROMPT = (
    "You classify whether an email is a bank/card transaction notification. "
    "Use the classify_transaction_email tool for every response."
)
