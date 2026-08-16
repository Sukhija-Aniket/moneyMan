from moneyman_shared.services.llm import ExtractionResult, get_provider


def extract_transaction(
    subject: str | None, sender: str | None, body_text: str | None, provider: str = "anthropic"
) -> ExtractionResult:
    return get_provider(provider).extract_transaction(subject, sender, body_text)
