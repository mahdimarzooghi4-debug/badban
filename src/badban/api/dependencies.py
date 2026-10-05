from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import Identity
from badban.security.authorization import Principal
from badban.security.oidc import AuthenticationError

_bearer = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as session:
        yield session


def get_correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


async def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Bearer authentication is required")
    try:
        claims = await request.app.state.token_verifier.verify(credentials.credentials)
    except AuthenticationError as exc:
        raise ApiError(401, exc.code, str(exc)) from exc

    identity = await session.scalar(
        select(Identity).where(Identity.external_subject == claims["sub"])
    )
    if identity is None or identity.status != "ACTIVE":
        raise ApiError(403, "AUTHORIZATION_DENIED", "Identity is not active in Badban")

    return Principal(
        identity_id=identity.id,
        external_subject=identity.external_subject,
        identity_type=identity.identity_type,
    )
