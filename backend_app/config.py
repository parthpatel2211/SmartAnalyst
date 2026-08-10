from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Deliberately contains no API key. Callers supply their own OpenAI key per
    request via the ``X-OpenAI-Key`` header, so the server never holds a
    credential, never persists one, and cannot leak one it does not have.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SMARTANALYST_",
        extra="ignore",
    )

    #: Model used for question-to-SQL translation.
    openai_model: str = "gpt-4o-mini"

    #: Origins permitted by CORS. Set to the deployed frontend URL in production.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    #: Upload bounds, enforced before the file is fully parsed.
    max_upload_bytes: int = 10 * 1024 * 1024
    max_rows: int = 200_000

    #: Session lifetime and capacity. State is process-local by design; see README.
    session_ttl_seconds: int = 1800
    max_sessions: int = 25

    #: Query bounds.
    query_timeout_seconds: int = 15
    default_row_limit: int = 5000


@lru_cache
def get_settings() -> Settings:
    return Settings()
