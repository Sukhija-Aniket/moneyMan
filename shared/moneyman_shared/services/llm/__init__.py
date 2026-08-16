from functools import lru_cache

from moneyman_shared.config import get_settings
from moneyman_shared.services.llm.base import ClassificationResult, ExtractionResult, LLMProvider
from moneyman_shared.services.llm.dry_run_provider import DryRunProvider

_PROVIDERS: dict[str, type] = {}


def _load_providers() -> dict[str, type]:
    global _PROVIDERS
    if not _PROVIDERS:
        from moneyman_shared.services.llm.anthropic_provider import AnthropicProvider
        from moneyman_shared.services.llm.ollama_provider import OllamaProvider

        _PROVIDERS = {"anthropic": AnthropicProvider, "ollama": OllamaProvider}
    return _PROVIDERS


@lru_cache
def get_provider(name: str) -> LLMProvider:
    settings = get_settings()
    if settings.GMAIL_SYNC_DRY_RUN:
        return DryRunProvider()

    providers = _load_providers()
    provider_cls = providers.get(name)
    if provider_cls is None:
        raise ValueError(f"Unknown LLM provider: {name!r}. Available: {sorted(providers)}")

    return provider_cls()


__all__ = ["ClassificationResult", "ExtractionResult", "LLMProvider", "get_provider"]
