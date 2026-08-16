from moneyman_shared.services.llm.base import ClassificationResult, ExtractionResult


class DryRunProvider:
    """Returns canned results instead of calling any LLM — lets the Gmail fetch/store
    pipeline be exercised without real provider credentials (GMAIL_SYNC_DRY_RUN=true)."""

    def classify_email(
        self, subject: str | None, sender: str | None, snippet: str | None
    ) -> ClassificationResult:
        return ClassificationResult(
            is_transaction_email=True,
            confidence=0.99,
            reason="dry run: canned classification, no LLM call made",
        )

    def extract_transaction(
        self, subject: str | None, sender: str | None, body_text: str | None
    ) -> ExtractionResult:
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
            ambiguity_notes="dry run: canned extraction, no LLM call made",
            raw={"dry_run": True},
        )
