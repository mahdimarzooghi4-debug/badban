from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from badban.security.auth import AuthenticationError, OidcAuthenticator, StaticJwksProvider


@pytest.fixture(scope="module")
def oidc_material():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "test-key"
    jwk["alg"] = "RS256"
    jwks = {"keys": [jwk]}
    return private_key, jwks


def issue_token(private_key, **overrides):
    now = datetime.now(UTC)
    claims = {
        "sub": "ops-user",
        "iss": "https://issuer.example/realms/badban",
        "aud": "badban-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.mark.asyncio
async def test_oidc_accepts_valid_signed_token(oidc_material) -> None:
    private_key, jwks = oidc_material
    authenticator = OidcAuthenticator(
        "https://issuer.example/realms/badban",
        "badban-api",
        StaticJwksProvider(jwks),
    )

    principal = await authenticator.authenticate(issue_token(private_key))

    assert principal.subject == "ops-user"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "wrong-audience"},
        {"iss": "https://wrong.example"},
        {"exp": 1},
        {"nbf": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())},
    ],
)
async def test_oidc_rejects_invalid_registered_claims(oidc_material, claims) -> None:
    private_key, jwks = oidc_material
    authenticator = OidcAuthenticator(
        "https://issuer.example/realms/badban",
        "badban-api",
        StaticJwksProvider(jwks),
    )

    with pytest.raises(AuthenticationError):
        await authenticator.authenticate(issue_token(private_key, **claims))


@pytest.mark.asyncio
async def test_oidc_rejects_unknown_signing_key(oidc_material) -> None:
    private_key, _ = oidc_material
    authenticator = OidcAuthenticator(
        "https://issuer.example/realms/badban",
        "badban-api",
        StaticJwksProvider({"keys": []}),
    )

    with pytest.raises(AuthenticationError):
        await authenticator.authenticate(issue_token(private_key))
