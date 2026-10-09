from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def oidc_url_origin(url: str) -> tuple[str, str, int] | None:
    """Parse a trusted HTTP(S) origin without credentials, fragments or control chars."""
    if not isinstance(url, str) or any(ord(char) <= 32 or char == "\\\\" for char in url):
        return None
    try:
        parts = urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.fragment
        ):
            return None
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None
    return (parts.scheme, parts.hostname.lower(), port)


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
    oidc_issuer: str
    oidc_audience: str
    oidc_discovery_url: str | None = None
    oidc_jwks_cache_seconds: int = 300

    @model_validator(mode="after")
    def validate_runtime_security(self) -> Settings:
        if self.secret_provider == "vault" and not self.vault_address:
            raise ValueError("BADBAN_VAULT_ADDRESS is required when secret_provider=vault")
        if self.app_env in {"stage", "production"} and self.secret_provider != "vault":
            raise ValueError("Stage/production requires BADBAN_SECRET_PROVIDER=vault")
        issuer_origin = oidc_url_origin(self.oidc_issuer)
        if issuer_origin is None:
            raise ValueError("BADBAN_OIDC_ISSUER must be a valid absolute HTTP(S) URL")
        if self.app_env in {"stage", "production"} and issuer_origin[0] != "https":
            raise ValueError("Stage/production OIDC issuer must use HTTPS")
        discovery_origin = oidc_url_origin(self.resolved_oidc_discovery_url)
        if discovery_origin is None or discovery_origin != issuer_origin:
            raise ValueError("OIDC discovery URL must share the configured issuer origin")
        if not self.oidc_audience.strip():
            raise ValueError("BADBAN_OIDC_AUDIENCE must not be empty")
        return self

    @property
    def resolved_oidc_discovery_url(self) -> str:
        if self.oidc_discovery_url:
            return self.oidc_discovery_url
        return f"{self.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"


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
        if settings.app_env in {"stage", "production"}:
            raise SecretUnavailableError("Environment secrets are forbidden in Stage/Production.")
        return EnvironmentSecretProvider()
    raise SecretUnavailableError(
        "Vault is the Stage/Production target, but the Vault client is not part of Sprint 02."
    )
