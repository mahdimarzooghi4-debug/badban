from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Protocol

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BADBAN_", extra="ignore")

    app_env: Literal["development", "test", "stage", "production"] = "development"
    database_url: str
    nats_url: str = "nats://localhost:4222"
    log_level: str = "INFO"
    otel_service_name: str = "badban-api"
    otel_exporter_otlp_endpoint: str | None = None
    secret_provider: Literal["environment", "vault"] = "environment"
    vault_address: str | None = None

    @model_validator(mode="after")
    def validate_secret_provider(self) -> "Settings":
        if self.secret_provider == "vault" and not self.vault_address:
            raise ValueError("BADBAN_VAULT_ADDRESS is required when secret_provider=vault")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@dataclass(frozen=True, slots=True)
class SecretRef:
    name: str


class SecretUnavailableError(RuntimeError):
    pass


class SecretProvider(Protocol):
    async def get(self, ref: SecretRef) -> str: ...


class EnvironmentSecretProvider:
    """Non-production secret seam. Values are supplied by process environment only."""

    def __init__(self, prefix: str = "BADBAN_SECRET_") -> None:
        self._prefix = prefix

    async def get(self, ref: SecretRef) -> str:
        key = f"{self._prefix}{ref.name.upper()}"
        value = os.getenv(key)
        if value is None:
            raise SecretUnavailableError(f"Secret reference is unavailable: {ref.name}")
        return value


def build_secret_provider(settings: Settings) -> SecretProvider:
    if settings.secret_provider == "environment":
        return EnvironmentSecretProvider()
    raise SecretUnavailableError(
        "Vault is the Stage/Production target, but the Vault client is not part of Sprint 01."
    )
