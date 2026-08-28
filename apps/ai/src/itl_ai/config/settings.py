"""Configuration that keeps provider access explicitly optional."""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    generation_provider_api_key: str | None

    @property
    def generation_is_configured(self) -> bool:
        return bool(self.generation_provider_api_key)


def load_settings() -> Settings:
    return Settings(generation_provider_api_key=getenv("GENERATION_PROVIDER_API_KEY"))
