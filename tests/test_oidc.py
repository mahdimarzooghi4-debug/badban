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


@pytest.mark.parametrize(
    "jwks_uri",
    [
        "http://issuer.test/jwks",
        "https://issuer.test.evil.example/jwks",
        "https://127.0.0.1/jwks",
        "https://169.254.169.254/latest/meta-data",
        "https://attacker@issuer.test/jwks",
        "https://issuer.test:444/jwks",
        "https://issuer.test/jwks#injected",
        "javascript:alert(1)",
    ],
)
async def test_oidc_rejects_untrusted_jwks_before_outbound_request(
    settings: Settings, jwks_uri: str
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url) == settings.resolved_oidc_discovery_url:
            return httpx.Response(200, json={"issuer": settings.oidc_issuer, "jwks_uri": jwks_uri})
        raise AssertionError("Untrusted JWKS URI must not be fetched")

    verifier = OidcTokenVerifier(
        settings, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(AuthenticationError) as rejected:
        await verifier._fetch_jwks()
    assert rejected.value.code == "OIDC_DISCOVERY_INVALID"
    assert requested == [settings.resolved_oidc_discovery_url]


@pytest.mark.parametrize("discovery_document", [[], "not-an-object", None, {}])
async def test_oidc_invalid_discovery_document_fails_closed(
    settings: Settings, discovery_document: object
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json=discovery_document)

    verifier = OidcTokenVerifier(
        settings, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(AuthenticationError) as rejected:
        await verifier._fetch_jwks()
    assert rejected.value.code == "OIDC_DISCOVERY_INVALID"
    assert requested == [settings.resolved_oidc_discovery_url]


@pytest.mark.parametrize("jwks_document", [[], None, {}, {"keys": "not-an-array"}])
async def test_oidc_invalid_jwks_shape_fails_closed(
    settings: Settings, jwks_document: object
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url) == settings.resolved_oidc_discovery_url:
            return httpx.Response(
                200,
                json={"issuer": settings.oidc_issuer, "jwks_uri": "https://issuer.test/jwks"},
            )
        assert str(request.url) == "https://issuer.test/jwks"
        return httpx.Response(200, json=jwks_document)

    verifier = OidcTokenVerifier(
        settings, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(AuthenticationError) as rejected:
        await verifier._fetch_jwks()
    assert rejected.value.code == "OIDC_JWKS_INVALID"
    assert requested == [settings.resolved_oidc_discovery_url, "https://issuer.test/jwks"]


async def test_oidc_rejects_discovery_redirect_even_with_redirect_following_client(
    settings: Settings,
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url) == settings.resolved_oidc_discovery_url:
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest"})
        raise AssertionError("Redirect destination must not be accessed")

    verifier = OidcTokenVerifier(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True),
    )
    with pytest.raises(AuthenticationError) as rejected:
        await verifier._fetch_jwks()
    assert rejected.value.code == "OIDC_PROVIDER_UNAVAILABLE"
    assert requested == [settings.resolved_oidc_discovery_url]


async def test_oidc_refreshes_trusted_jwks_on_unknown_key_rotation(
    settings: Settings,
) -> None:
    old_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    new_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    counter = 0
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal counter
        requested.append(str(request.url))
        if str(request.url) == settings.resolved_oidc_discovery_url:
            return httpx.Response(
                200,
                json={"issuer": settings.oidc_issuer, "jwks_uri": "https://issuer.test/jwks"},
            )
        assert str(request.url) == "https://issuer.test/jwks"
        counter += 1
        key = old_private.public_key() if counter == 1 else new_private.public_key()
        jwk = RSAAlgorithm.to_jwk(key, as_dict=True)
        jwk["kid"] = "old" if counter == 1 else "new"
        jwk["use"] = "sig"
        jwk["alg"] = "RS256"
        return httpx.Response(200, json={"keys": [jwk]})

    verifier = OidcTokenVerifier(
        settings, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    first = jwt.encode(
        _issuer_payload(settings), old_private, algorithm="RS256", headers={"kid": "old"}
    )
    second = jwt.encode(
        _issuer_payload(settings), new_private, algorithm="RS256", headers={"kid": "new"}
    )
    assert (await verifier.verify(first))["sub"] == "subject-1"
    assert (await verifier.verify(second))["sub"] == "subject-1"
    assert counter == 2
    assert all(url.startswith("https://issuer.test/") for url in requested)
