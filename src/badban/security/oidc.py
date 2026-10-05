from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKSet

from badban.config import Settings


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
            client = self._client or httpx.AsyncClient(timeout=5.0)
            try:
                discovery = await client.get(self._settings.resolved_oidc_discovery_url)
                discovery.raise_for_status()
                document = discovery.json()
                if document.get("issuer") != self._settings.oidc_issuer:
                    raise AuthenticationError(
                        "OIDC_DISCOVERY_INVALID",
                        "OIDC discovery issuer does not match configured issuer",
                    )
                jwks_uri = document.get("jwks_uri")
                if not isinstance(jwks_uri, str) or not jwks_uri.startswith(("https://", "http://")):
                    raise AuthenticationError(
                        "OIDC_DISCOVERY_INVALID",
                        "OIDC discovery document has no valid jwks_uri",
                    )
                response = await client.get(jwks_uri)
                response.raise_for_status()
                jwks = PyJWKSet.from_dict(response.json())
            except AuthenticationError:
                raise
            except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
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
