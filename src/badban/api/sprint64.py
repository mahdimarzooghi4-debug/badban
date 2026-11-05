from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import (
    get_correlation_id,
    get_current_principal,
    get_session,
)
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import Identity, LegalEntity, Program
from badban.security.audit import append_audit
from badban.security.authorization import (
    HUMAN_IDENTITY_TYPES,
    ROLE_AUDITOR,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_OPERATIONS,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(
    prefix="/api/v1/admin/directory",
    tags=["admin-reference-directories"],
)


class HumanIdentityDirectoryItem(BaseModel):
    identity_id: UUID
    identity_type: str
    status: str
    created_at: datetime


class HumanIdentityDirectoryPage(BaseModel):
    observed_at: datetime
    items: list[HumanIdentityDirectoryItem]
    limit: int
    offset: int


class LegalEntityDirectoryItem(BaseModel):
    legal_entity_id: UUID
    legal_name: str
    entity_type: str
    status: str
    version: int
    created_at: datetime


class LegalEntityDirectoryPage(BaseModel):
    observed_at: datetime
    items: list[LegalEntityDirectoryItem]
    limit: int
    offset: int


class ProgramDirectoryItem(BaseModel):
    program_id: UUID
    code: str
    name: str
    status: str
    legal_entity_id: UUID | None
    version: int
    created_at: datetime


class ProgramDirectoryPage(BaseModel):
    observed_at: datetime
    items: list[ProgramDirectoryItem]
    limit: int
    offset: int


async def _authorize_directory(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    action: str,
    target_type: str,
    target_id: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=SCOPE_GLOBAL,
            scope_id=None,
            allow_global=False,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(
            403,
            exc.code,
            "Global directory read authorization required",
        ) from exc


@router.get("/identities", response_model=HumanIdentityDirectoryPage)
async def list_human_identity_directory(
    identity_type: Literal["STAFF", "GOVERNANCE", "AUDITOR"] | None = Query(
        default=None,
    ),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> HumanIdentityDirectoryPage:
    await _authorize_directory(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER},
        action="ADMIN_HUMAN_IDENTITY_DIRECTORY_READ",
        target_type="HumanIdentityDirectory",
        target_id="human-identities",
        correlation_id=correlation_id,
    )
    observed_at = datetime.now(UTC)
    statement = select(Identity).where(Identity.identity_type.in_(HUMAN_IDENTITY_TYPES))
    if identity_type is not None:
        statement = statement.where(Identity.identity_type == identity_type)
    identities = (
        await session.scalars(
            statement.order_by(Identity.created_at.desc(), Identity.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="HumanIdentityDirectory",
        aggregate_id="human-identities",
        aggregate_version=None,
        action="ADMIN_HUMAN_IDENTITY_DIRECTORY_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={
            "identity_type": identity_type,
            "returned_count": len(identities),
            "limit": limit,
            "offset": offset,
        },
    )
    await session.commit()
    return HumanIdentityDirectoryPage(
        observed_at=observed_at,
        items=[
            HumanIdentityDirectoryItem(
                identity_id=item.id,
                identity_type=item.identity_type,
                status=item.status,
                created_at=item.created_at,
            )
            for item in identities
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/legal-entities", response_model=LegalEntityDirectoryPage)
async def list_legal_entity_directory(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LegalEntityDirectoryPage:
    await _authorize_directory(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER, ROLE_LEGAL_COMPLIANCE, ROLE_AUDITOR},
        action="ADMIN_LEGAL_ENTITY_DIRECTORY_READ",
        target_type="LegalEntityDirectory",
        target_id="legal-entities",
        correlation_id=correlation_id,
    )
    observed_at = datetime.now(UTC)
    entities = (
        await session.scalars(
            select(LegalEntity)
            .order_by(LegalEntity.legal_name, LegalEntity.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="LegalEntityDirectory",
        aggregate_id="legal-entities",
        aggregate_version=None,
        action="ADMIN_LEGAL_ENTITY_DIRECTORY_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={
            "returned_count": len(entities),
            "limit": limit,
            "offset": offset,
        },
    )
    await session.commit()
    return LegalEntityDirectoryPage(
        observed_at=observed_at,
        items=[
            LegalEntityDirectoryItem(
                legal_entity_id=item.id,
                legal_name=item.legal_name,
                entity_type=item.entity_type,
                status=item.status,
                version=item.version,
                created_at=item.created_at,
            )
            for item in entities
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/programs", response_model=ProgramDirectoryPage)
async def list_program_directory(
    status: Literal["ACTIVE", "INACTIVE"] | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramDirectoryPage:
    await _authorize_directory(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER, ROLE_AUDITOR, ROLE_OPERATIONS},
        action="ADMIN_PROGRAM_DIRECTORY_READ",
        target_type="ProgramDirectory",
        target_id="programs",
        correlation_id=correlation_id,
    )
    observed_at = datetime.now(UTC)
    statement = select(Program).order_by(Program.code, Program.id)
    if status is not None:
        statement = statement.where(Program.status == status)
    programs = (
        await session.scalars(statement.offset(offset).limit(limit))
    ).all()
    append_audit(
        session,
        aggregate_type="ProgramDirectory",
        aggregate_id="programs",
        aggregate_version=None,
        action="ADMIN_PROGRAM_DIRECTORY_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={
            "status": status,
            "returned_count": len(programs),
            "limit": limit,
            "offset": offset,
        },
    )
    await session.commit()
    return ProgramDirectoryPage(
        observed_at=observed_at,
        items=[
            ProgramDirectoryItem(
                program_id=item.id,
                code=item.code,
                name=item.name,
                status=item.status,
                legal_entity_id=item.legal_entity_id,
                version=item.version,
                created_at=item.created_at,
            )
            for item in programs
        ],
        limit=limit,
        offset=offset,
    )
