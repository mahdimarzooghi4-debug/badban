from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from badban.config import Settings
from badban.security.oidc import AuthenticationError, OidcTokenVerifier


def _issuer_payload(settings: Settings, **overrides):
    now = datetime.now(UTC)
    payload = {
        "sub": "subject-1",
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    payload.update(overrides)
    return payload


def _verifier(settings: Settings, public_key) -> OidcTokenVerifier:
    jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = "key-1"
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == settings.resolved_oidc_discovery_url:
            return httpx.Response(
                200,
                json={
                    "issuer": settings.oidc_issuer,
                    "jwks_uri": "https://issuer.test/jwks",
                },
            )
        if str(request.url) == "https://issuer.test/jwks":
            return httpx.Response(200, json={"keys": [jwk]})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OidcTokenVerifier(settings, client=client)


async def test_oidc_valid_signature_issuer_and_audience(settings: Settings) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        _issuer_payload(settings),
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    verifier = _verifier(settings, private_key.public_key())
    claims = await verifier.verify(token)
    assert claims["sub"] == "subject-1"


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        ({"aud": "wrong-audience"}, "invalid"),
        ({"iss": "https://wrong-issuer.test"}, "invalid"),
        (
            {"exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())},
            "expired",
        ),
        (
            {"nbf": int((datetime.now(UTC) + timedelta(minutes=1)).timestamp())},
            "not yet valid",
        ),
    ],
)
async def test_oidc_rejects_invalid_registered_claims(
    settings: Settings,
    overrides: dict[str, object],
    expected_message: str,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        _issuer_payload(settings, **overrides),
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    verifier = _verifier(settings, private_key.public_key())
    with pytest.raises(AuthenticationError, match=expected_message):
        await verifier.verify(token)


async def test_oidc_rejects_invalid_signature(settings: Settings) -> None:
    trusted = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        _issuer_payload(settings),
        attacker,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    verifier = _verifier(settings, trusted.public_key())
    with pytest.raises(AuthenticationError, match="invalid"):
        await verifier.verify(token)
