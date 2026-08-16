from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    ANTHROPIC_API_KEY: str = ""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # Providers users are allowed to select in Settings. First entry is the default
    # for new users (also enforced by the users.llm_provider DB default).
    AVAILABLE_LLM_PROVIDERS: list[str] = ["anthropic", "ollama"]

    # Phase 1 stand-in for Cloud KMS envelope encryption (see services/token_crypto.py).
    TOKEN_ENCRYPTION_KEY: str

    SESSION_SECRET: str

    FRONTEND_URL: str = "http://localhost:5173"

    GMAIL_CLASSIFICATION_MODEL: str = "claude-haiku-4-5"
    GMAIL_EXTRACTION_MODEL: str = "claude-sonnet-4-5"

    GMAIL_SYNC_MAX_RESULTS: int = 25

    # When true, classification/extraction return canned results instead of calling Anthropic —
    # lets the Gmail fetch/store pipeline be exercised without a real ANTHROPIC_API_KEY.
    GMAIL_SYNC_DRY_RUN: bool = False

    SESSION_COOKIE_NAME: str = "moneyman_session"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 14

    PULSAR_SERVICE_URL: str = "pulsar://localhost:6650"


@lru_cache
def get_settings() -> Settings:
    return Settings()
