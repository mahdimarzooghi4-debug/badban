from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import (
    Identity,
    Participant,
    ParticipationEpisode,
    Program,
    RoleGrant,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    HUMAN_IDENTITY_TYPES,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_SUPPORT_INSTITUTION_OPERATOR,
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

admin_router = APIRouter(
    prefix="/api/v1/admin/support-institution",
    tags=["admin-support-institution"],
)
institution_router = APIRouter(
    prefix="/api/v1/support-institution",
    tags=["support-institution"],
)

class ProgramRoleGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: UUID
    program_id: UUID
    valid_from: datetime
    valid_until: datetime | None = None
    reason_reference: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_window(self) -> ProgramRoleGrantCreate:
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise ValueError("valid_from must be timezone-aware")
        if self.valid_until is not None:
            if self.valid_until.tzinfo is None or self.valid_until.utcoffset() is None:
                raise ValueError("valid_until must be timezone-aware")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be later than valid_from")
        return self


class ProgramRoleGrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_reference: str = Field(min_length=1, max_length=255)


class ProgramRoleGrantView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identity_id: UUID
    role_code: str
    scope_type: str
    scope_id: UUID | None
    valid_from: datetime
    valid_until: datetime | None
    status: str
    granted_by: UUID | None
    reason_ref: str | None
    version: int


class SupportingProgramView(BaseModel):
    program_id: UUID
    code: str
    name: str
    status: str


class SupportingProgramsView(BaseModel):
    items: list[SupportingProgramView]
    limit: int
    offset: int


class SupportedPersonView(BaseModel):
    participant_id: UUID
    episode_id: UUID
    participation_status: str
    consent_state: str
    started_at: datetime
    ended_at: datetime | None


class SupportedPeopleView(BaseModel):
    program_id: UUID
    items: list[SupportedPersonView]
    limit: int
    offset: int


async def _authorize_global_governance(
    session: AsyncSession,
    principal: Principal,
    correlation_id: UUID,
    action: str,
    target_id: str,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_GOVERNANCE_APPROVER},
            scope_type=SCOPE_GLOBAL,
            scope_id=None,
            allow_global=False,
            action=action,
            target_type="SupportingInstitutionRoleGrant",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


@admin_router.post(
    "/grants",
    response_model=ProgramRoleGrantView,
    status_code=status.HTTP_201_CREATED,
)
async def request_supporting_institution_access(
    body: ProgramRoleGrantCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramRoleGrantView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "SUPPORT_INSTITUTION_ROLE_GRANT_REQUEST",
        str(body.identity_id),
    )
    identity = await session.get(Identity, body.identity_id)
    if (
        identity is None
        or identity.status != "ACTIVE"
        or identity.identity_type not in HUMAN_IDENTITY_TYPES
    ):
        raise ApiError(404, "HUMAN_IDENTITY_NOT_FOUND", "Active human identity was not found")
    program = await session.get(Program, body.program_id)
    if program is None or program.status != "ACTIVE" or program.legal_entity_id is None:
        raise ApiError(
            404,
            "SUPPORTING_PROGRAM_NOT_FOUND",
            "Active supporting institution program was not found",
        )
    existing = await session.scalar(
        select(RoleGrant.id).where(
            RoleGrant.identity_id == body.identity_id,
            RoleGrant.role_code == ROLE_SUPPORT_INSTITUTION_OPERATOR,
            RoleGrant.scope_type == SCOPE_PROGRAM,
            RoleGrant.scope_id == body.program_id,
            RoleGrant.status.in_(["REQUESTED", "ACTIVE"]),
        )
    )
    if existing is not None:
        raise ApiError(
            409,
            "SUPPORT_INSTITUTION_ROLE_GRANT_EXISTS",
            "A pending or active grant already exists",
        )
    grant = RoleGrant(
        identity_id=body.identity_id,
        role_code=ROLE_SUPPORT_INSTITUTION_OPERATOR,
        scope_type=SCOPE_PROGRAM,
        scope_id=body.program_id,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        status="REQUESTED",
        granted_by=principal.identity_id,
        reason_ref=body.reason_reference,
    )
    session.add(grant)
    await session.flush()
    append_audit(
        session,
        aggregate_type="SupportingInstitutionRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SUPPORT_INSTITUTION_ROLE_GRANT_REQUEST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"program_id": str(body.program_id), "identity_id": str(body.identity_id)},
    )
    await session.commit()
    return ProgramRoleGrantView.model_validate(grant)


@admin_router.post("/grants/{grant_id}/approve", response_model=ProgramRoleGrantView)
async def approve_supporting_institution_access(
    grant_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramRoleGrantView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "SUPPORT_INSTITUTION_ROLE_GRANT_APPROVE",
        str(grant_id),
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    if (
        grant is None
        or grant.scope_type != SCOPE_PROGRAM
        or grant.role_code != ROLE_SUPPORT_INSTITUTION_OPERATOR
        or grant.scope_id is None
    ):
        raise ApiError(
            404, "SUPPORT_INSTITUTION_GRANT_NOT_FOUND", "Supporting institution grant was not found"
        )
    if grant.status != "REQUESTED":
        raise ApiError(
            409,
            "SUPPORT_INSTITUTION_GRANT_NOT_REQUESTED",
            "Only a requested grant can be approved",
        )
    if grant.granted_by == principal.identity_id:
        raise ApiError(
            403,
            "MAKER_CHECKER_REQUIRED",
            "The requester cannot approve the supporting institution grant",
        )
    program = await session.get(Program, grant.scope_id)
    if program is None or program.status != "ACTIVE" or program.legal_entity_id is None:
        raise ApiError(
            409,
            "SUPPORTING_PROGRAM_UNAVAILABLE",
            "The supporting institution program is no longer active",
        )
    grant.status = "ACTIVE"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="SupportingInstitutionRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SUPPORT_INSTITUTION_ROLE_GRANT_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=grant.reason_ref,
        scope={"program_id": str(grant.scope_id), "role_code": grant.role_code},
    )
    await session.commit()
    return ProgramRoleGrantView.model_validate(grant)


@admin_router.post("/grants/{grant_id}/revoke", response_model=ProgramRoleGrantView)
async def revoke_supporting_institution_access(
    grant_id: UUID,
    body: ProgramRoleGrantRevoke,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramRoleGrantView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "SUPPORT_INSTITUTION_ROLE_GRANT_REVOKE",
        str(grant_id),
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    if (
        grant is None
        or grant.scope_type != SCOPE_PROGRAM
        or grant.role_code != ROLE_SUPPORT_INSTITUTION_OPERATOR
    ):
        raise ApiError(
            404, "SUPPORT_INSTITUTION_GRANT_NOT_FOUND", "Supporting institution grant was not found"
        )
    if grant.status not in {"REQUESTED", "ACTIVE"}:
        raise ApiError(
            409,
            "SUPPORT_INSTITUTION_GRANT_NOT_REVOCABLE",
            "Grant is no longer active or pending",
        )
    grant.status = "REVOKED"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="SupportingInstitutionRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SUPPORT_INSTITUTION_ROLE_GRANT_REVOKE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"program_id": str(grant.scope_id), "role_code": grant.role_code},
    )
    await session.commit()
    return ProgramRoleGrantView.model_validate(grant)


@institution_router.get("/programs", response_model=SupportingProgramsView)
async def read_authorized_programs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportingProgramsView:
    now = datetime.now(UTC)
    programs = (
        await session.scalars(
            select(Program)
            .join(RoleGrant, RoleGrant.scope_id == Program.id)
            .where(
                RoleGrant.identity_id == principal.identity_id,
                RoleGrant.role_code == ROLE_SUPPORT_INSTITUTION_OPERATOR,
                RoleGrant.scope_type == SCOPE_PROGRAM,
                RoleGrant.status == "ACTIVE",
                RoleGrant.valid_from <= now,
                (RoleGrant.valid_until.is_(None) | (RoleGrant.valid_until > now)),
                Program.status == "ACTIVE",
                Program.legal_entity_id.is_not(None),
            )
            .distinct()
            .order_by(Program.name, Program.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="SupportingInstitutionWorkspace",
        aggregate_id=str(principal.identity_id),
        aggregate_version=None,
        action="SUPPORT_INSTITUTION_PROGRAM_LIST_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(programs), "limit": limit, "offset": offset},
    )
    await session.commit()
    return SupportingProgramsView(
        items=[
            SupportingProgramView(
                program_id=program.id,
                code=program.code,
                name=program.name,
                status=program.status,
            )
            for program in programs
        ],
        limit=limit,
        offset=offset,
    )


@institution_router.get(
    "/programs/{program_id}/beneficiaries",
    response_model=SupportedPeopleView,
)
async def read_program_beneficiaries(
    program_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportedPeopleView:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_SUPPORT_INSTITUTION_OPERATOR},
            scope_type=SCOPE_PROGRAM,
            scope_id=program_id,
            allow_global=False,
            action="SUPPORT_INSTITUTION_BENEFICIARIES_READ",
            target_type="SupportingInstitutionProgram",
            target_id=str(program_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Program-scoped supporting institution access is required") from exc

    rows: list[tuple[ParticipationEpisode, Participant]] = (
        await session.execute(
            select(ParticipationEpisode, Participant)
            .join(Participant, Participant.id == ParticipationEpisode.participant_id)
            .join(Program, Program.id == ParticipationEpisode.program_id)
            .where(
                ParticipationEpisode.program_id == program_id,
                Program.status == "ACTIVE",
                Program.legal_entity_id.is_not(None),
            )
            .order_by(ParticipationEpisode.started_at.desc(), ParticipationEpisode.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="SupportingInstitutionProgram",
        aggregate_id=str(program_id),
        aggregate_version=None,
        action="SUPPORT_INSTITUTION_BENEFICIARIES_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(rows), "limit": limit, "offset": offset},
    )
    await session.commit()
    return SupportedPeopleView(
        program_id=program_id,
        items=[
            SupportedPersonView(
                participant_id=participant.id,
                episode_id=episode.id,
                participation_status=episode.status,
                consent_state=episode.consent_state,
                started_at=episode.started_at,
                ended_at=episode.ended_at,
            )
            for episode, participant in rows
        ],
        limit=limit,
        offset=offset,
    )
