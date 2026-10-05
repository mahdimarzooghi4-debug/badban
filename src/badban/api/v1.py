from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    AuditEvent,
    Participant,
    ParticipationEpisode,
    Program,
    RoleGrant,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_OPERATIONS,
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1")


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeView(BaseModel):
    identity_id: UUID
    external_subject: str
    identity_type: str


class GrantView(OrmModel):
    id: UUID
    role_code: str
    scope_type: str
    scope_id: UUID | None
    valid_from: datetime
    valid_until: datetime | None
    status: str
    version: int


class ProgramCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"
    legal_entity_id: UUID | None = None


class ProgramView(OrmModel):
    id: UUID
    code: str
    name: str
    status: str
    legal_entity_id: UUID | None
    version: int
    created_by: UUID


class ParticipantCreate(BaseModel):
    external_reference: str | None = Field(default=None, max_length=255)


class ParticipantView(OrmModel):
    id: UUID
    external_reference: str | None
    lifecycle_status: str


class ParticipationCreate(BaseModel):
    participant_id: UUID
    eligibility_reference: str | None = Field(default=None, max_length=255)
    consent_state: str = Field(min_length=1, max_length=80)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ParticipationView(OrmModel):
    id: UUID
    participant_id: UUID
    program_id: UUID
    status: str
    eligibility_reference: str | None
    consent_state: str
    started_at: datetime
    ended_at: datetime | None
    version: int
    created_by: UUID


class AssetTypeCreate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    status: Literal["DRAFT", "ACTIVE", "INACTIVE"] = "DRAFT"
    unit_code: str = Field(min_length=1, max_length=40)
    quantity_scale: int = Field(ge=0, le=18)
    currency_or_valuation_currency: str | None = Field(default=None, max_length=16)
    valuation_source_reference: str | None = Field(default=None, max_length=255)
    eligibility_metadata: dict[str, Any] = Field(default_factory=dict)
    custody_restriction_metadata: dict[str, Any] = Field(default_factory=dict)


class AssetTypeView(OrmModel):
    id: UUID
    asset_code: str
    name: str
    status: str
    unit_code: str
    quantity_scale: int
    currency_or_valuation_currency: str | None
    valuation_source_reference: str | None
    eligibility_metadata: dict[str, Any]
    custody_restriction_metadata: dict[str, Any]
    version: int
    created_by: UUID


class AssetPositionCreate(BaseModel):
    participation_episode_id: UUID
    asset_type_id: UUID
    ownership_funding_type: Literal["PARTICIPANT_OWNED", "PROGRAM_ATTRIBUTED"]
    legal_owner_entity_id: UUID | None = None
    legal_owner_participant_id: UUID | None = None
    custodian_legal_entity_id: UUID | None = None
    quantity: Decimal = Field(ge=0)
    unit_code: str = Field(min_length=1, max_length=40)
    source_reference: str | None = Field(default=None, max_length=255)
    evidence_reference: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_owner_pattern(self) -> AssetPositionCreate:
        if self.ownership_funding_type == "PARTICIPANT_OWNED":
            if self.legal_owner_participant_id is None or self.legal_owner_entity_id is not None:
                raise ValueError(
                    "PARTICIPANT_OWNED requires participant owner and no entity owner"
                )
        elif self.legal_owner_entity_id is None or self.legal_owner_participant_id is not None:
            raise ValueError(
                "PROGRAM_ATTRIBUTED requires entity owner and no participant owner"
            )
        return self


class AssetPositionView(OrmModel):
    id: UUID
    participation_episode_id: UUID
    program_id: UUID
    asset_type_id: UUID
    ownership_funding_type: str
    legal_owner_entity_id: UUID | None
    legal_owner_participant_id: UUID | None
    custodian_legal_entity_id: UUID | None
    quantity: Decimal
    unit_code: str
    lifecycle_status: str
    source_reference: str | None
    version: int
    created_by: UUID


async def _authorized(
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
    try:
        return await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=scope_type,
            scope_id=scope_id,
            allow_global=allow_global,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for requested scope") from exc


def _response(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _validate_quantity_scale(quantity: Decimal, scale: int) -> None:
    quantum = Decimal(1).scaleb(-scale)
    if quantity.quantize(quantum) != quantity:
        raise ApiError(
            422,
            "ASSET_QUANTITY_SCALE_INVALID",
            "Quantity exceeds configured Asset Type precision",
            {"quantity_scale": scale},
        )


@router.get("/me", response_model=MeView)
async def me(principal: Principal = Depends(get_current_principal)) -> MeView:
    return MeView(
        identity_id=principal.identity_id,
        external_subject=principal.external_subject,
        identity_type=principal.identity_type,
    )


@router.get("/me/grants", response_model=list[GrantView])
async def my_grants(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[GrantView]:
    now = datetime.now(UTC)
    rows = (
        await session.scalars(
            select(RoleGrant).where(
                RoleGrant.identity_id == principal.identity_id,
                RoleGrant.status == "ACTIVE",
                RoleGrant.valid_from <= now,
                (RoleGrant.valid_until.is_(None) | (RoleGrant.valid_until > now)),
            )
        )
    ).all()
    return [GrantView.model_validate(row) for row in rows]


@router.post("/programs", response_model=ProgramView, status_code=status.HTTP_201_CREATED)
async def create_program(
    body: ProgramCreate,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramView:
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="PROGRAM_CREATE",
        target_type="Program",
        target_id=body.code,
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope="program:create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return ProgramView.model_validate(replay)

    program = Program(
        code=body.code,
        name=body.name,
        status=body.status,
        legal_entity_id=body.legal_entity_id,
        created_by=principal.identity_id,
    )
    session.add(program)
    await session.flush()
    view = ProgramView.model_validate(program)
    append_audit(
        session,
        aggregate_type="Program",
        aggregate_id=str(program.id),
        aggregate_version=program.version,
        action="PROGRAM_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=_response(view),
        scope={"scope_type": SCOPE_GLOBAL},
    )
    complete_idempotency(record, status_code=201, response_payload=_response(view))
    await session.commit()
    return view


@router.get("/programs/{program_id}", response_model=ProgramView)
async def get_program(
    program_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramView:
    program = await session.get(Program, program_id)
    if program is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Program was not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS, ROLE_AUDITOR, ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_PROGRAM,
        scope_id=program.id,
        allow_global=True,
        action="PROGRAM_READ",
        target_type="Program",
        target_id=str(program.id),
        correlation_id=correlation_id,
    )
    return ProgramView.model_validate(program)


@router.post("/participants", response_model=ParticipantView, status_code=status.HTTP_201_CREATED)
async def create_participant(
    body: ParticipantCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ParticipantView:
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="PARTICIPANT_CREATE",
        target_type="Participant",
        target_id=body.external_reference or "new",
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope="participant:create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return ParticipantView.model_validate(replay)
    participant = Participant(external_reference=body.external_reference, lifecycle_status="ACTIVE")
    session.add(participant)
    await session.flush()
    view = ParticipantView.model_validate(participant)
    append_audit(
        session,
        aggregate_type="Participant",
        aggregate_id=str(participant.id),
        aggregate_version=None,
        action="PARTICIPANT_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=_response(view),
        scope={"scope_type": SCOPE_GLOBAL},
    )
    complete_idempotency(record, status_code=201, response_payload=_response(view))
    await session.commit()
    return view


@router.post(
    "/programs/{program_id}/participation-episodes",
    response_model=ParticipationView,
    status_code=status.HTTP_201_CREATED,
)
async def create_participation_episode(
    program_id: UUID,
    body: ParticipationCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ParticipationView:
    program = await session.get(Program, program_id)
    participant = await session.get(Participant, body.participant_id)
    if program is None or participant is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Program or participant was not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS},
        scope_type=SCOPE_PROGRAM,
        scope_id=program.id,
        allow_global=True,
        action="PARTICIPATION_EPISODE_CREATE",
        target_type="ParticipationEpisode",
        target_id=str(program.id),
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"participation:create:{program.id}",
        key=idempotency_key,
        payload={"program_id": str(program.id), **body.model_dump(mode="json")},
    )
    if replay is not None:
        return ParticipationView.model_validate(replay)
    episode = ParticipationEpisode(
        participant_id=participant.id,
        program_id=program.id,
        status="ACTIVE",
        eligibility_reference=body.eligibility_reference,
        consent_state=body.consent_state,
        started_at=body.started_at,
        created_by=principal.identity_id,
    )
    session.add(episode)
    await session.flush()
    view = ParticipationView.model_validate(episode)
    append_audit(
        session,
        aggregate_type="ParticipationEpisode",
        aggregate_id=str(episode.id),
        aggregate_version=episode.version,
        action="PARTICIPATION_EPISODE_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=_response(view),
        scope={"scope_type": SCOPE_PROGRAM, "scope_id": str(program.id)},
    )
    complete_idempotency(record, status_code=201, response_payload=_response(view))
    await session.commit()
    return view


@router.get("/participation-episodes/{episode_id}", response_model=ParticipationView)
async def get_participation_episode(
    episode_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ParticipationView:
    episode = await session.get(ParticipationEpisode, episode_id)
    if episode is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Participation Episode was not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS, ROLE_AUDITOR},
        scope_type=SCOPE_PROGRAM,
        scope_id=episode.program_id,
        allow_global=True,
        action="PARTICIPATION_EPISODE_READ",
        target_type="ParticipationEpisode",
        target_id=str(episode.id),
        correlation_id=correlation_id,
    )
    return ParticipationView.model_validate(episode)


@router.post("/asset-types", response_model=AssetTypeView, status_code=status.HTTP_201_CREATED)
async def create_asset_type(
    body: AssetTypeCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AssetTypeView:
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="ASSET_TYPE_CREATE",
        target_type="AssetType",
        target_id=body.asset_code,
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope="asset_type:create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return AssetTypeView.model_validate(replay)
    asset_type = AssetType(**body.model_dump(), created_by=principal.identity_id)
    session.add(asset_type)
    await session.flush()
    view = AssetTypeView.model_validate(asset_type)
    append_audit(
        session,
        aggregate_type="AssetType",
        aggregate_id=str(asset_type.id),
        aggregate_version=asset_type.version,
        action="ASSET_TYPE_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=_response(view),
        scope={"scope_type": SCOPE_GLOBAL},
    )
    complete_idempotency(record, status_code=201, response_payload=_response(view))
    await session.commit()
    return view


@router.get("/asset-types", response_model=list[AssetTypeView])
async def list_asset_types(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[AssetTypeView]:
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS, ROLE_AUDITOR, ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="ASSET_TYPE_LIST",
        target_type="AssetType",
        target_id="registry",
        correlation_id=correlation_id,
    )
    rows = (await session.scalars(select(AssetType).order_by(AssetType.asset_code))).all()
    return [AssetTypeView.model_validate(row) for row in rows]


@router.get("/asset-types/{asset_type_id}", response_model=AssetTypeView)
async def get_asset_type(
    asset_type_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AssetTypeView:
    asset_type = await session.get(AssetType, asset_type_id)
    if asset_type is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset Type was not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS, ROLE_AUDITOR, ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="ASSET_TYPE_READ",
        target_type="AssetType",
        target_id=str(asset_type.id),
        correlation_id=correlation_id,
    )
    return AssetTypeView.model_validate(asset_type)


@router.post(
    "/asset-positions",
    response_model=AssetPositionView,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset_position(
    body: AssetPositionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AssetPositionView:
    episode = await session.get(ParticipationEpisode, body.participation_episode_id)
    asset_type = await session.get(AssetType, body.asset_type_id)
    if episode is None or asset_type is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Participation Episode or Asset Type not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS},
        scope_type=SCOPE_PROGRAM,
        scope_id=episode.program_id,
        allow_global=True,
        action="ASSET_POSITION_CREATE",
        target_type="AssetPosition",
        target_id=str(episode.id),
        correlation_id=correlation_id,
    )
    if episode.status != "ACTIVE":
        raise ApiError(422, "PARTICIPATION_EPISODE_NOT_ACTIVE", "Participation Episode is not active")
    if asset_type.status != "ACTIVE":
        raise ApiError(422, "ASSET_TYPE_NOT_ACTIVE", "Asset Type is not active/approved")
    if body.unit_code != asset_type.unit_code:
        raise ApiError(
            422,
            "ASSET_UNIT_MISMATCH",
            "Asset Position unit does not match Asset Type",
            {"expected_unit_code": asset_type.unit_code},
        )
    _validate_quantity_scale(body.quantity, asset_type.quantity_scale)
    if (
        body.ownership_funding_type == "PARTICIPANT_OWNED"
        and body.legal_owner_participant_id != episode.participant_id
    ):
        raise ApiError(
            422,
            "ASSET_OWNER_MISMATCH",
            "Participant-owned position must belong to the Participation Episode participant",
        )

    record, replay = await acquire_idempotency(
        session,
        scope=f"asset_position:create:{episode.program_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return AssetPositionView.model_validate(replay)

    position = AssetPosition(
        participation_episode_id=episode.id,
        program_id=episode.program_id,
        asset_type_id=asset_type.id,
        ownership_funding_type=body.ownership_funding_type,
        legal_owner_entity_id=body.legal_owner_entity_id,
        legal_owner_participant_id=body.legal_owner_participant_id,
        custodian_legal_entity_id=body.custodian_legal_entity_id,
        quantity=body.quantity,
        unit_code=body.unit_code,
        lifecycle_status="ACTIVE",
        source_reference=body.source_reference,
        created_by=principal.identity_id,
    )
    session.add(position)
    await session.flush()
    view = AssetPositionView.model_validate(position)
    append_audit(
        session,
        aggregate_type="AssetPosition",
        aggregate_id=str(position.id),
        aggregate_version=position.version,
        action="ASSET_POSITION_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=_response(view),
        evidence_reference=body.evidence_reference,
        scope={"scope_type": SCOPE_PROGRAM, "scope_id": str(episode.program_id)},
    )
    complete_idempotency(record, status_code=201, response_payload=_response(view))
    await session.commit()
    return view


@router.get("/asset-positions/{position_id}", response_model=AssetPositionView)
async def get_asset_position(
    position_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AssetPositionView:
    position = await session.get(AssetPosition, position_id)
    if position is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset Position was not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS, ROLE_AUDITOR},
        scope_type=SCOPE_PROGRAM,
        scope_id=position.program_id,
        allow_global=True,
        action="ASSET_POSITION_READ",
        target_type="AssetPosition",
        target_id=str(position.id),
        correlation_id=correlation_id,
    )
    return AssetPositionView.model_validate(position)


@router.get(
    "/participation-episodes/{episode_id}/asset-positions",
    response_model=list[AssetPositionView],
)
async def list_episode_asset_positions(
    episode_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[AssetPositionView]:
    episode = await session.get(ParticipationEpisode, episode_id)
    if episode is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Participation Episode was not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_OPERATIONS, ROLE_AUDITOR},
        scope_type=SCOPE_PROGRAM,
        scope_id=episode.program_id,
        allow_global=True,
        action="ASSET_POSITION_LIST",
        target_type="ParticipationEpisode",
        target_id=str(episode.id),
        correlation_id=correlation_id,
    )
    rows = (
        await session.scalars(
            select(AssetPosition)
            .where(AssetPosition.participation_episode_id == episode.id)
            .order_by(AssetPosition.created_at)
        )
    ).all()
    return [AssetPositionView.model_validate(row) for row in rows]


@router.get("/audit/events/{event_id}")
async def get_audit_event(
    event_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> dict[str, Any]:
    event = await session.get(AuditEvent, event_id)
    if event is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Audit event was not found")
    await _authorized(
        session,
        principal=principal,
        roles={ROLE_AUDITOR},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="AUDIT_EVENT_READ",
        target_type="AuditEvent",
        target_id=str(event.id),
        correlation_id=correlation_id,
    )
    return {
        "id": str(event.id),
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "aggregate_version": event.aggregate_version,
        "action": event.action,
        "actor_type": event.actor_type,
        "actor_id": str(event.actor_id),
        "reason_code": event.reason_code,
        "evidence_reference": event.evidence_reference,
        "correlation_id": str(event.correlation_id),
        "outcome": event.outcome,
        "scope": event.scope,
        "occurred_at": event.occurred_at.isoformat(),
    }
