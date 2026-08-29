"""Configuration that keeps provider access explicitly optional."""

from dataclasses import dataclass
from os import getenv
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    generation_provider_api_key: str | None
    llm_provider: str
    ollama_api_key: str | None
    ollama_base_url: str
    ollama_model: str
    openai_api_key: str | None
    openai_model: str
    model_timeout_seconds: float
    preference_database_path: Path

    @property
    def generation_is_configured(self) -> bool:
        return bool(self.generation_provider_api_key)


def load_settings() -> Settings:
    provider = getenv("ITL_LLM_PROVIDER", "deterministic")
    return Settings(
        generation_provider_api_key=getenv("GENERATION_PROVIDER_API_KEY"),
        llm_provider=provider,
        ollama_api_key=getenv("OLLAMA_API_KEY"),
        ollama_base_url=getenv("OLLAMA_BASE_URL", "https://ollama.com/v1"),
        ollama_model=getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud"),
        openai_api_key=getenv("OPENAI_API_KEY"),
        openai_model=getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        model_timeout_seconds=max(1, float(getenv("LLM_TIMEOUT_SECONDS", "120"))),
        preference_database_path=Path(getenv("PREFERENCE_DATABASE_PATH", "data/preferences.db")),
    )
