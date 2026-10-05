from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK


class AuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TokenPrincipal:
    subject: str
    claims: dict[str, Any]


class JwksProvider(Protocol):
    async def get_jwks(self, issuer: str) -> dict[str, Any]: ...


class OidcJwksProvider:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    async def get_jwks(self, issuer: str) -> dict[str, Any]:
        normalized = issuer.rstrip("/")
        if normalized in self._cache:
            return self._cache[normalized]
        timeout = httpx.Timeout(5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            discovery = await client.get(f"{normalized}/.well-known/openid-configuration")
            discovery.raise_for_status()
            jwks_uri = discovery.json()["jwks_uri"]
            response = await client.get(jwks_uri)
            response.raise_for_status()
            jwks = response.json()
        self._cache[normalized] = jwks
        return jwks


class StaticJwksProvider:
    def __init__(self, jwks: dict[str, Any]) -> None:
        self._jwks = jwks

    async def get_jwks(self, issuer: str) -> dict[str, Any]:
        _ = issuer
        return self._jwks


class OidcAuthenticator:
    def __init__(self, issuer: str, audience: str, jwks_provider: JwksProvider | None = None) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_provider = jwks_provider or OidcJwksProvider()

    async def authenticate(self, token: str) -> TokenPrincipal:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise AuthenticationError("Token is missing kid")
            jwks = await self._jwks_provider.get_jwks(self._issuer)
            raw_key = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)
            if raw_key is None:
                raise AuthenticationError("Signing key is unknown")
            key = PyJWK.from_dict(raw_key)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[key.algorithm_name],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
            subject = claims.get("sub")
            if not isinstance(subject, str) or not subject:
                raise AuthenticationError("Token subject is invalid")
            return TokenPrincipal(subject=subject, claims=claims)
        except AuthenticationError:
            raise
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Token validation failed") from exc
