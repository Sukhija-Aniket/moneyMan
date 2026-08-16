from moneyman_shared.services.llm import ClassificationResult, get_provider


def classify_email(
    subject: str | None, sender: str | None, snippet: str | None, provider: str = "anthropic"
) -> ClassificationResult:
    return get_provider(provider).classify_email(subject, sender, snippet)
