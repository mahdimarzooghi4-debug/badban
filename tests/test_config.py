from __future__ import annotations

import pytest
from pydantic import ValidationError

from badban.config import EnvironmentSecretProvider, SecretRef, SecretUnavailableError, Settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BADBAN_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


async def test_environment_secret_provider_requires_explicit_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = EnvironmentSecretProvider()
    monkeypatch.delenv("BADBAN_SECRET_PROVIDER_API_KEY", raising=False)
    with pytest.raises(SecretUnavailableError):
        await provider.get(SecretRef("provider_api_key"))


@pytest.mark.parametrize(
    ("issuer", "discovery"),
    [
        ("http://issuer.example", None),
        ("https://issuer.example", "http://issuer.example/.well-known/openid-configuration"),
        ("https://issuer.example", "https://different.example/.well-known/openid-configuration"),
        ("https://user:password@issuer.example", None),
        ("https://issuer.example/#fragment", None),
        ("https://issuer.example:broken", None),
    ],
)
def test_stage_rejects_insecure_or_untrusted_oidc_endpoints(
    issuer: str, discovery: str | None
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="stage",
            secret_provider="vault",
            vault_address="https://test-vault.example",
            database_url="postgresql+asyncpg://test-host/test",
            oidc_issuer=issuer,
            oidc_audience="badban-api",
            oidc_discovery_url=discovery,
        )


def test_stage_accepts_valid_same_origin_https_discovery() -> None:
    config = Settings(
        app_env="stage",
        secret_provider="vault",
        vault_address="https://test-vault.example",
        database_url="postgresql+asyncpg://test-host/test",
        oidc_issuer="https://issuer.example/realms/badban",
        oidc_audience="badban-api",
        oidc_discovery_url="https://issuer.example/custom-discovery",
    )
    assert config.resolved_oidc_discovery_url == "https://issuer.example/custom-discovery"


def test_development_can_use_explicit_same_origin_http_oidc() -> None:
    config = Settings(
        app_env="development",
        database_url="postgresql+asyncpg://test-host/test",
        oidc_issuer="http://localhost:8080/realms/badban",
        oidc_audience="badban-api",
    )
    assert config.resolved_oidc_discovery_url.startswith("http://localhost:8080/")
