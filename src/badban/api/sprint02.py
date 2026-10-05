from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    AuditEvent,
    IdempotencyRecord,
    ParticipationEpisode,
    Program,
    RoleGrant,
)
from badban.security.auth import AuthenticationError
from badban.security.authorization import Actor, find_active_identity, is_authorized

router = APIRouter(prefix="/api/v1")
_bearer = HTTPBearer(auto_error=False)


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProgramCreate(ApiModel):
    code: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)


class ProgramView(ApiModel):
    id: UUID
    code: str
    name: str
    status: str
    version: int


class ParticipationCreate(ApiModel):
    participant_ref: str = Field(min_length=1, max_length=200)


class ParticipationView(ApiModel):
    id: UUID
    program_id: UUID
    participant_ref: str
    status: str
    version: int


class AssetTypeCreate(ApiModel):
    code: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    unit: str = Field(min_length=1, max_length=80)
    precision_scale: int = Field(ge=0, le=18)
    valuation_source_ref: str | None = Field(default=None, max_length=240)
    eligibility_metadata: dict[str, Any] = Field(default_factory=dict)
    custody_metadata: dict[str, Any] = Field(default_factory=dict)
    status: Literal["APPROVED", "INACTIVE"] = "APPROVED"


class AssetTypeView(ApiModel):
    id: UUID
    code: str
    name: str
    unit: str
    precision_scale: int
    valuation_source_ref: str | None
    eligibility_metadata: dict[str, Any]
    custody_metadata: dict[str, Any]
    status: str
    version: int


class AssetPositionCreate(ApiModel):
    program_id: UUID
    participation_episode_id: UUID
    asset_type_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    ownership_class: Literal["PARTICIPANT_OWNED", "PROGRAM_ATTRIBUTED"]
    owner_ref: str | None = Field(default=None, max_length=240)
    custody_ref: str | None = Field(default=None, max_length=240)


class AssetPositionView(ApiModel):
    id: UUID
    program_id: UUID
    participation_episode_id: UUID
    asset_type_id: UUID
    quantity: Decimal
    ownership_class: str
    owner_ref: str | None
    custody_ref: str | None
    version: int


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_actor(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Actor:
    authenticator = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTHENTICATION_UNAVAILABLE"},
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED"},
        )
    try:
        principal = await authenticator.authenticate(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED"},
        ) from exc
    identity = await find_active_identity(session, principal.subject)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUTHORIZATION_DENIED"},
        )
    return Actor(
        identity_id=identity.id,
        external_subject=identity.external_subject,
        identity_type=identity.identity_type,
    )


ActorDep = Annotated[Actor, Depends(get_actor)]


def _correlation_id(request: Request) -> UUID | None:
    value = getattr(request.state, "correlation_id", None)
    try:
        return UUID(value) if value else None
    except (TypeError, ValueError):
        return None


def _request_hash(model: BaseModel) -> str:
    canonical = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _existing_idempotent(
    session: AsyncSession,
    scope: str,
    key: str,
    request_hash: str,
) -> dict[str, Any] | None:
    record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if record is None:
        return None
    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "IDEMPOTENCY_CONFLICT"},
        )
    return record.response_payload


def _save_idempotent(
    session: AsyncSession,
    scope: str,
    key: str,
    request_hash: str,
    response: dict[str, Any],
    response_code: int = 201,
) -> None:
    session.add(
        IdempotencyRecord(
            scope=scope,
            idempotency_key=key,
            request_hash=request_hash,
            outcome_status="COMPLETED",
            response_code=response_code,
            response_payload=response,
        )
    )


def _audit(
    session: AsyncSession,
    request: Request,
    actor: Actor | None,
    action: str,
    target_type: str,
    target_id: str | None,
    outcome: str,
    scope_type: str | None,
    scope_id: str | None,
    reason_code: str | None = None,
    evidence_refs: list[str] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_identity_id=actor.identity_id if actor else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=_correlation_id(request),
            outcome=outcome,
            scope_type=scope_type,
            scope_id=scope_id,
            reason_code=reason_code,
            evidence_refs=evidence_refs or [],
        )
    )


async def _require(
    session: AsyncSession,
    request: Request,
    actor: Actor,
    permission: str,
    scope_type: str,
    scope_id: str,
    target_type: str,
    target_id: str | None = None,
) -> None:
    if await is_authorized(session, actor, permission, scope_type, scope_id):
        return
    _audit(
        session,
        request,
        actor,
        permission,
        target_type,
        target_id,
        "DENIED",
        scope_type,
        scope_id,
        "AUTHORIZATION_DENIED",
    )
    await session.commit()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "AUTHORIZATION_DENIED"},
    )


@router.get("/me")
async def me(actor: ActorDep) -> dict[str, str]:
    return {
        "identity_id": str(actor.identity_id),
        "external_subject": actor.external_subject,
        "identity_type": actor.identity_type,
    }


@router.get("/me/grants")
async def my_grants(actor: ActorDep, session: SessionDep) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    grants = (
        await session.scalars(
            select(RoleGrant).where(
                RoleGrant.identity_id == actor.identity_id,
                RoleGrant.status == "ACTIVE",
                RoleGrant.valid_from <= now,
            )
        )
    ).all()
    return [
        {
            "id": str(grant.id),
            "role_code": grant.role_code,
            "scope_type": grant.scope_type,
            "scope_id": grant.scope_id,
            "valid_until": grant.valid_until.isoformat() if grant.valid_until else None,
            "status": grant.status,
        }
        for grant in grants
        if grant.valid_until is None or grant.valid_until > now
    ]


@router.post("/programs", response_model=ProgramView, status_code=201)
async def create_program(
    payload: ProgramCreate,
    request: Request,
    actor: ActorDep,
    session: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ProgramView:
    await _require(session, request, actor, "program:create", "SYSTEM", "badban", "Program")
    scope = f"program:create:{actor.identity_id}"
    digest = _request_hash(payload)
    existing = await _existing_idempotent(session, scope, idempotency_key, digest)
    if existing is not None:
        return ProgramView.model_validate(existing)
    program = Program(code=payload.code, name=payload.name, created_by=actor.identity_id)
    async with session.begin():
        session.add(program)
        await session.flush()
        result = ProgramView.model_validate(program)
        _audit(session, request, actor, "program:create", "Program", str(program.id), "SUCCEEDED", "SYSTEM", "badban")
        _save_idempotent(session, scope, idempotency_key, digest, result.model_dump(mode="json"))
    return result


@router.get("/programs/{program_id}", response_model=ProgramView)
async def get_program(program_id: UUID, request: Request, actor: ActorDep, session: SessionDep) -> ProgramView:
    await _require(session, request, actor, "program:read", "PROGRAM", str(program_id), "Program", str(program_id))
    program = await session.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail={"code": "PROGRAM_NOT_FOUND"})
    return ProgramView.model_validate(program)


@router.post("/programs/{program_id}/participation-episodes", response_model=ParticipationView, status_code=201)
async def create_participation(
    program_id: UUID,
    payload: ParticipationCreate,
    request: Request,
    actor: ActorDep,
    session: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ParticipationView:
    await _require(session, request, actor, "participation:create", "PROGRAM", str(program_id), "ParticipationEpisode")
    if await session.get(Program, program_id) is None:
        raise HTTPException(status_code=404, detail={"code": "PROGRAM_NOT_FOUND"})
    scope = f"participation:create:{program_id}:{actor.identity_id}"
    digest = _request_hash(payload)
    existing = await _existing_idempotent(session, scope, idempotency_key, digest)
    if existing is not None:
        return ParticipationView.model_validate(existing)
    episode = ParticipationEpisode(
        program_id=program_id,
        participant_ref=payload.participant_ref,
        created_by=actor.identity_id,
    )
    async with session.begin():
        session.add(episode)
        await session.flush()
        result = ParticipationView.model_validate(episode)
        _audit(session, request, actor, "participation:create", "ParticipationEpisode", str(episode.id), "SUCCEEDED", "PROGRAM", str(program_id))
        _save_idempotent(session, scope, idempotency_key, digest, result.model_dump(mode="json"))
    return result


@router.get("/participation-episodes/{episode_id}", response_model=ParticipationView)
async def get_participation(episode_id: UUID, request: Request, actor: ActorDep, session: SessionDep) -> ParticipationView:
    episode = await session.get(ParticipationEpisode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail={"code": "PARTICIPATION_NOT_FOUND"})
    await _require(session, request, actor, "participation:read", "PROGRAM", str(episode.program_id), "ParticipationEpisode", str(episode_id))
    return ParticipationView.model_validate(episode)


@router.post("/asset-types", response_model=AssetTypeView, status_code=201)
async def create_asset_type(
    payload: AssetTypeCreate,
    request: Request,
    actor: ActorDep,
    session: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AssetTypeView:
    await _require(session, request, actor, "asset-type:create", "SYSTEM", "badban", "AssetType")
    scope = f"asset-type:create:{actor.identity_id}"
    digest = _request_hash(payload)
    existing = await _existing_idempotent(session, scope, idempotency_key, digest)
    if existing is not None:
        return AssetTypeView.model_validate(existing)
    asset_type = AssetType(**payload.model_dump(), created_by=actor.identity_id)
    async with session.begin():
        session.add(asset_type)
        await session.flush()
        result = AssetTypeView.model_validate(asset_type)
        _audit(session, request, actor, "asset-type:create", "AssetType", str(asset_type.id), "SUCCEEDED", "SYSTEM", "badban")
        _save_idempotent(session, scope, idempotency_key, digest, result.model_dump(mode="json"))
    return result


@router.get("/asset-types", response_model=list[AssetTypeView])
async def list_asset_types(request: Request, actor: ActorDep, session: SessionDep) -> list[AssetTypeView]:
    await _require(session, request, actor, "asset-type:read", "SYSTEM", "badban", "AssetType")
    rows = (await session.scalars(select(AssetType).order_by(AssetType.code))).all()
    return [AssetTypeView.model_validate(row) for row in rows]


@router.get("/asset-types/{asset_type_id}", response_model=AssetTypeView)
async def get_asset_type(asset_type_id: UUID, request: Request, actor: ActorDep, session: SessionDep) -> AssetTypeView:
    await _require(session, request, actor, "asset-type:read", "SYSTEM", "badban", "AssetType", str(asset_type_id))
    row = await session.get(AssetType, asset_type_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ASSET_TYPE_NOT_FOUND"})
    return AssetTypeView.model_validate(row)


@router.post("/asset-positions", response_model=AssetPositionView, status_code=201)
async def create_asset_position(
    payload: AssetPositionCreate,
    request: Request,
    actor: ActorDep,
    session: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AssetPositionView:
    await _require(session, request, actor, "asset-position:create", "PROGRAM", str(payload.program_id), "AssetPosition")
    episode = await session.get(ParticipationEpisode, payload.participation_episode_id)
    if episode is None or episode.program_id != payload.program_id:
        raise HTTPException(status_code=409, detail={"code": "PARTICIPATION_PROGRAM_MISMATCH"})
    asset_type = await session.get(AssetType, payload.asset_type_id)
    if asset_type is None:
        raise HTTPException(status_code=404, detail={"code": "ASSET_TYPE_NOT_FOUND"})
    if asset_type.status != "APPROVED":
        raise HTTPException(status_code=409, detail={"code": "ASSET_TYPE_NOT_ACTIVE"})
    scope = f"asset-position:create:{payload.program_id}:{actor.identity_id}"
    digest = _request_hash(payload)
    existing = await _existing_idempotent(session, scope, idempotency_key, digest)
    if existing is not None:
        return AssetPositionView.model_validate(existing)
    position = AssetPosition(**payload.model_dump(), created_by=actor.identity_id)
    async with session.begin():
        session.add(position)
        await session.flush()
        result = AssetPositionView.model_validate(position)
        _audit(session, request, actor, "asset-position:create", "AssetPosition", str(position.id), "SUCCEEDED", "PROGRAM", str(payload.program_id))
        _save_idempotent(session, scope, idempotency_key, digest, result.model_dump(mode="json"))
    return result


@router.get("/asset-positions/{position_id}", response_model=AssetPositionView)
async def get_asset_position(position_id: UUID, request: Request, actor: ActorDep, session: SessionDep) -> AssetPositionView:
    row = await session.get(AssetPosition, position_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ASSET_POSITION_NOT_FOUND"})
    await _require(session, request, actor, "asset-position:read", "PROGRAM", str(row.program_id), "AssetPosition", str(position_id))
    return AssetPositionView.model_validate(row)
