from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.sprint46 import SERVICE_ROLE_MATRIX, _service_scope_id
from badban.infrastructure.persistence.models import RoleGrant
from badban.security.audit import append_audit
from badban.security.authorization import ROLE_GOVERNANCE_APPROVER, SCOPE_GLOBAL, SCOPE_SERVICE, Principal

router = APIRouter(prefix="/api/v1/admin", tags=["admin-workspace"])


class AdminWorkspaceEntry(BaseModel):
    workspace_code: str
    scope_type: Literal["GLOBAL", "SERVICE"]
    scope_id: UUID | None
    service_code: str | None
    role_codes: list[str]
    capabilities: list[str]


class AdminWorkspaceIndex(BaseModel):
    generated_at: datetime
    items: list[AdminWorkspaceEntry]


@router.get("/workspace", response_model=AdminWorkspaceIndex)
async def read_admin_workspace_index(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AdminWorkspaceIndex:
    observed_at = datetime.now(UTC)
    grants = (
        await session.scalars(
            select(RoleGrant).where(
                RoleGrant.identity_id == principal.identity_id,
                RoleGrant.status == "ACTIVE",
                RoleGrant.valid_from <= observed_at,
                or_(RoleGrant.valid_until.is_(None), RoleGrant.valid_until > observed_at),
            )
        )
    ).all()

    entries: list[AdminWorkspaceEntry] = []
    grant_by_service_scope: dict[UUID, set[str]] = {}
    for grant in grants:
        if grant.scope_type == SCOPE_SERVICE and grant.scope_id is not None:
            grant_by_service_scope.setdefault(grant.scope_id, set()).add(grant.role_code)

    for service_code, allowed_roles in SERVICE_ROLE_MATRIX.items():
        scope_id = _service_scope_id(service_code)
        active_roles = sorted(grant_by_service_scope.get(scope_id, set()) & allowed_roles)
        if active_roles:
            entries.append(
                AdminWorkspaceEntry(
                    workspace_code="ADMIN_SERVICE_OPERATIONS",
                    scope_type=SCOPE_SERVICE,
                    scope_id=scope_id,
                    service_code=service_code,
                    role_codes=active_roles,
                    capabilities=["READ_WORK_QUEUE"],
                )
            )

    has_global_governance = any(
        grant.role_code == ROLE_GOVERNANCE_APPROVER
        and grant.scope_type == SCOPE_GLOBAL
        and grant.scope_id is None
        for grant in grants
    )
    if has_global_governance:
        entries.append(
            AdminWorkspaceEntry(
                workspace_code="ADMIN_ACCESS_GOVERNANCE",
                scope_type=SCOPE_GLOBAL,
                scope_id=None,
                service_code=None,
                role_codes=[ROLE_GOVERNANCE_APPROVER],
                capabilities=[
                    "MANAGE_SERVICE_ROLE_GRANTS",
                    "MANAGE_SUPPORT_INSTITUTION_GRANTS",
                    "MANAGE_LENDER_GRANTS",
                ],
            )
        )

    append_audit(
        session,
        aggregate_type="AdminWorkspace",
        aggregate_id=str(principal.identity_id),
        aggregate_version=None,
        action="ADMIN_WORKSPACE_INDEX_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"entry_count": len(entries)},
    )
    await session.commit()
    return AdminWorkspaceIndex(generated_at=observed_at, items=entries)
