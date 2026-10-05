from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import RoleGrant
from badban.security.audit import append_audit


ROLE_OPERATIONS = "OPERATIONS"
ROLE_RISK = "RISK"
ROLE_FINANCE_RECONCILIATION = "FINANCE_RECONCILIATION"
ROLE_LEGAL_COMPLIANCE = "LEGAL_COMPLIANCE"
ROLE_GOVERNANCE_APPROVER = "GOVERNANCE_APPROVER"
ROLE_AUDITOR = "AUDITOR"
ROLE_SYSTEM_OPERATOR = "SYSTEM_OPERATOR"

SCOPE_GLOBAL = "GLOBAL"
SCOPE_PROGRAM = "PROGRAM"
SCOPE_PARTICIPANT = "PARTICIPANT"
SCOPE_ASSET_TYPE = "ASSET_TYPE"
SCOPE_ASSET_POSITION = "ASSET_POSITION"


@dataclass(frozen=True, slots=True)
class Principal:
    identity_id: UUID
    external_subject: str
    identity_type: str


class AuthorizationDenied(RuntimeError):
    def __init__(self, code: str = "AUTHORIZATION_DENIED") -> None:
        super().__init__(code)
        self.code = code


async def authorize(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    scope_type: str,
    scope_id: UUID | None,
    allow_global: bool,
    action: str,
    target_type: str,
    target_id: str,
    correlation_id: UUID,
) -> RoleGrant:
    now = datetime.now(UTC)
    scope_predicate = (
        or_(
            (RoleGrant.scope_type == scope_type) & (RoleGrant.scope_id == scope_id),
            (RoleGrant.scope_type == SCOPE_GLOBAL) & (RoleGrant.scope_id.is_(None)),
        )
        if allow_global
        else (RoleGrant.scope_type == scope_type) & (RoleGrant.scope_id == scope_id)
    )
    statement = (
        select(RoleGrant)
        .where(
            RoleGrant.identity_id == principal.identity_id,
            RoleGrant.role_code.in_(roles),
            RoleGrant.status == "ACTIVE",
            RoleGrant.valid_from <= now,
            or_(RoleGrant.valid_until.is_(None), RoleGrant.valid_until > now),
            scope_predicate,
        )
        .order_by(RoleGrant.valid_from.desc())
        .limit(1)
    )
    grant = await session.scalar(statement)
    if grant is not None:
        return grant

    append_audit(
        session,
        aggregate_type=target_type,
        aggregate_id=target_id,
        aggregate_version=None,
        action=action,
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="DENIED",
        reason_code="AUTHORIZATION_DENIED",
        scope={"scope_type": scope_type, "scope_id": str(scope_id) if scope_id else None},
    )
    await session.commit()
    raise AuthorizationDenied()
