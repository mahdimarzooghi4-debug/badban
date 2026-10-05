from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import Identity, RoleGrant

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "OPERATIONS": frozenset(
        {
            "program:create",
            "program:read",
            "participation:create",
            "participation:read",
            "asset-type:read",
            "asset-position:create",
            "asset-position:read",
        }
    ),
    "GOVERNANCE_APPROVER": frozenset({"asset-type:create", "asset-type:read"}),
    "AUDITOR": frozenset(
        {
            "program:read",
            "participation:read",
            "asset-type:read",
            "asset-position:read",
            "audit:read",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class Actor:
    identity_id: UUID
    external_subject: str
    identity_type: str


async def find_active_identity(session: AsyncSession, subject: str) -> Identity | None:
    return await session.scalar(
        select(Identity).where(Identity.external_subject == subject, Identity.status == "ACTIVE")
    )


def _scope_matches(grant: RoleGrant, scope_type: str, scope_id: str) -> bool:
    if grant.scope_type == "SYSTEM" and grant.scope_id == "badban":
        return scope_type == "SYSTEM" and scope_id == "badban"
    return grant.scope_type == scope_type and grant.scope_id == scope_id


async def is_authorized(
    session: AsyncSession,
    actor: Actor,
    permission: str,
    scope_type: str,
    scope_id: str,
) -> bool:
    now = datetime.now(UTC)
    grants = (
        await session.scalars(
            select(RoleGrant).where(
                RoleGrant.identity_id == actor.identity_id,
                RoleGrant.status == "ACTIVE",
                RoleGrant.valid_from <= now,
                or_(RoleGrant.valid_until.is_(None), RoleGrant.valid_until > now),
            )
        )
    ).all()
    return any(
        permission in ROLE_PERMISSIONS.get(grant.role_code, frozenset())
        and _scope_matches(grant, scope_type, scope_id)
        for grant in grants
    )
