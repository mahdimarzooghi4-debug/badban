from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKSet

from badban.config import Settings, oidc_url_origin


class AuthenticationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OidcTokenVerifier:
    """Validate OIDC access tokens against issuer discovery and JWKS."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._cached_jwks: PyJWKSet | None = None
        self._cache_expires_at = 0.0
        self._cache_lock = asyncio.Lock()

    async def _fetch_jwks(self) -> PyJWKSet:
        now = time.monotonic()
        if self._cached_jwks is not None and now < self._cache_expires_at:
            return self._cached_jwks

        async with self._cache_lock:
            now = time.monotonic()
            if self._cached_jwks is not None and now < self._cache_expires_at:
                return self._cached_jwks

            owns_client = self._client is None
            client = self._client or httpx.AsyncClient(timeout=5.0, follow_redirects=False)
            try:
                discovery = await client.get(
                    self._settings.resolved_oidc_discovery_url, follow_redirects=False
                )
                discovery.raise_for_status()
                document = discovery.json()
                if not isinstance(document, dict):
                    raise AuthenticationError(
                        "OIDC_DISCOVERY_INVALID", "OIDC discovery document must be an object"
                    )
                if document.get("issuer") != self._settings.oidc_issuer:
                    raise AuthenticationError(
                        "OIDC_DISCOVERY_INVALID",
                        "OIDC discovery issuer does not match configured issuer",
                    )
                jwks_uri = document.get("jwks_uri")
                issuer_origin = oidc_url_origin(self._settings.oidc_issuer)
                if (
                    not isinstance(jwks_uri, str)
                    or issuer_origin is None
                    or oidc_url_origin(jwks_uri) != issuer_origin
                ):
                    raise AuthenticationError(
                        "OIDC_DISCOVERY_INVALID",
                        "OIDC JWKS URL must be an absolute URL on the trusted issuer origin",
                    )
                response = await client.get(jwks_uri, follow_redirects=False)
                response.raise_for_status()
                key_document = response.json()
                if not isinstance(key_document, dict) or not isinstance(
                    key_document.get("keys"), list
                ):
                    raise AuthenticationError(
                        "OIDC_JWKS_INVALID", "OIDC JWKS document is invalid"
                    )
                jwks = PyJWKSet.from_dict(key_document)
            except AuthenticationError:
                raise
            except (httpx.HTTPError, ValueError, TypeError, KeyError, jwt.PyJWTError) as exc:
                raise AuthenticationError(
                    "OIDC_PROVIDER_UNAVAILABLE",
                    "OIDC discovery/JWKS could not be validated",
                ) from exc
            finally:
                if owns_client:
                    await client.aclose()

            self._cached_jwks = jwks
            self._cache_expires_at = now + self._settings.oidc_jwks_cache_seconds
            return jwks

    async def verify(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("AUTHENTICATION_REQUIRED", "Malformed bearer token") from exc

        if header.get("alg") != "RS256":
            raise AuthenticationError(
                "AUTHENTICATION_REQUIRED",
                "Only RS256 access tokens are accepted",
            )
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise AuthenticationError("AUTHENTICATION_REQUIRED", "Token has no key identifier")

        jwks = await self._fetch_jwks()
        signing_key = next((item.key for item in jwks.keys if item.key_id == key_id), None)
        if signing_key is None:
            self._cached_jwks = None
            jwks = await self._fetch_jwks()
            signing_key = next((item.key for item in jwks.keys if item.key_id == key_id), None)
        if signing_key is None:
            raise AuthenticationError("AUTHENTICATION_REQUIRED", "Unknown token signing key")

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._settings.oidc_audience,
                issuer=self._settings.oidc_issuer,
                options={"require": ["sub", "exp"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("AUTHENTICATION_REQUIRED", "Access token is expired") from exc
        except jwt.ImmatureSignatureError as exc:
            raise AuthenticationError(
                "AUTHENTICATION_REQUIRED",
                "Access token is not yet valid",
            ) from exc
        except jwt.PyJWTError as exc:
            raise AuthenticationError("AUTHENTICATION_REQUIRED", "Access token is invalid") from exc

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("AUTHENTICATION_REQUIRED", "Token subject is invalid")
        return claims
