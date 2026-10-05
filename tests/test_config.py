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
