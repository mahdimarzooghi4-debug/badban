from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.decision_snapshot import get_decision_snapshot
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.application.policy_lifecycle import (
    activate_policy,
    approve_policy,
    assert_policy_pack_manifest_exact,
    retire_policy,
    review_policy,
)
from badban.infrastructure.persistence.models import DecisionSnapshot, PolicyVersion
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/admin")


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PolicyPackCreate(BaseModel):
    policy_code: str = Field(min_length=1, max_length=120)
    version_number: int = Field(gt=0)
    scope_definition: dict[str, Any]
    component_version_ids: list[UUID] = Field(default_factory=list)
    schema_version: str = Field(min_length=1, max_length=40)
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def validate_effective_window(self) -> PolicyPackCreate:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must be later than effective_from")
        return self


class PolicyTransitionApproval(BaseModel):
    approval_id: UUID


class PolicyPackView(OrmModel):
    id: UUID
    policy_code: str
    version_number: int
    lifecycle_status: str
    scope_definition: dict[str, Any]
    payload: dict[str, Any]
    payload_hash: str | None
    schema_version: str
    effective_from: datetime | None
    effective_to: datetime | None
    approved_at: datetime | None
    activated_at: datetime | None
    superseded_at: datetime | None
    created_by: UUID
    approved_by: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class PolicyPackListView(BaseModel):
    items: list[PolicyPackView]
    next_cursor: UUID | None


class DecisionSnapshotView(OrmModel):
    id: UUID
    business_entity_type: str
    business_entity_id: str
    decision_type: str
    policy_pack_id: UUID
    policy_pack_version: int
    component_version_ids: list[str]
    algorithm_code: str
    algorithm_version: str
    material_input_payload: dict[str, Any]
    material_output_payload: dict[str, Any]
    input_hash: str
    output_hash: str
    valuation_observation_ids: list[str]
    authoritative_external_references: list[str]
    risk_snapshot_id: UUID | None
    effective_at: datetime
    actor_type: str
    actor_id: UUID
    created_at: datetime


async def _authorize_admin(
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
        raise ApiError(403, exc.code, "Authorization denied for requested admin operation") from exc


async def _get_policy_pack(session: AsyncSession, policy_id: UUID) -> PolicyVersion:
    policy = await session.scalar(
        select(PolicyVersion).where(
            PolicyVersion.id == policy_id,
            PolicyVersion.policy_type == "PILOT_POLICY_PACK",
        )
    )
    if policy is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Pilot Policy Pack was not found")
    return policy


@router.get("/policy-packs", response_model=PolicyPackListView)
async def list_policy_packs(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    cursor: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> PolicyPackListView:
    await _authorize_admin(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER, ROLE_AUDITOR},
        action="POLICY_PACK_LIST",
        target_type="PolicyVersion",
        target_id="policy-pack-collection",
        correlation_id=correlation_id,
    )
    statement = (
        select(PolicyVersion)
        .where(PolicyVersion.policy_type == "PILOT_POLICY_PACK")
        .order_by(PolicyVersion.id)
        .limit(limit)
    )
    if cursor is not None:
        statement = statement.where(PolicyVersion.id > cursor)
    policies = (await session.scalars(statement)).all()
    next_cursor = policies[-1].id if len(policies) == limit else None
    return PolicyPackListView(
        items=[PolicyPackView.model_validate(policy) for policy in policies],
        next_cursor=next_cursor,
    )


@router.get("/policy-packs/{policy_id}", response_model=PolicyPackView)
async def get_policy_pack(
    policy_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> PolicyPackView:
    await _authorize_admin(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER, ROLE_AUDITOR},
        action="POLICY_PACK_READ",
        target_type="PolicyVersion",
        target_id=str(policy_id),
        correlation_id=correlation_id,
    )
    policy = await _get_policy_pack(session, policy_id)
    return PolicyPackView.model_validate(policy)


@router.post(
    "/policy-packs",
    response_model=PolicyPackView,
    status_code=status.HTTP_201_CREATED,
)
async def create_policy_pack(
    body: PolicyPackCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> PolicyPackView:
    await _authorize_admin(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER},
        action="POLICY_PACK_CREATE",
        target_type="PolicyVersion",
        target_id=body.policy_code,
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"policy_pack:create:{principal.identity_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return PolicyPackView.model_validate(replay)

    existing = await session.scalar(
        select(PolicyVersion.id).where(
            PolicyVersion.policy_type == "PILOT_POLICY_PACK",
            PolicyVersion.policy_code == body.policy_code,
            PolicyVersion.version_number == body.version_number,
        )
    )
    if existing is not None:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Pilot Policy Pack version already exists",
        )

    policy = PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code=body.policy_code,
        version_number=body.version_number,
        lifecycle_status="DRAFT",
        scope_definition=body.scope_definition,
        payload={
            "component_version_ids": [
                str(component_id) for component_id in body.component_version_ids
            ]
        },
        schema_version=body.schema_version,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        created_by=principal.identity_id,
        version=1,
    )
    assert_policy_pack_manifest_exact(policy)
    session.add(policy)
    await session.flush()
    view = PolicyPackView.model_validate(policy)
    append_audit(
        session,
        aggregate_type="PolicyVersion",
        aggregate_id=str(policy.id),
        aggregate_version=policy.version,
        action="POLICY_PACK_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=view.model_dump(mode="json"),
        scope=policy.scope_definition,
    )
    complete_idempotency(record, status_code=201, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


async def _transition_command(
    *,
    command: str,
    policy_id: UUID,
    principal: Principal,
    session: AsyncSession,
    correlation_id: UUID,
    idempotency_key: str,
    approval_id: UUID | None = None,
) -> PolicyPackView:
    await _authorize_admin(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER},
        action=f"POLICY_PACK_{command.upper()}",
        target_type="PolicyVersion",
        target_id=str(policy_id),
        correlation_id=correlation_id,
    )
    request_payload = {
        "policy_id": str(policy_id),
        "command": command,
        "approval_id": str(approval_id) if approval_id is not None else None,
    }
    record, replay = await acquire_idempotency(
        session,
        scope=f"policy_pack:{command}:{policy_id}:{principal.identity_id}",
        key=idempotency_key,
        payload=request_payload,
    )
    if replay is not None:
        return PolicyPackView.model_validate(replay)

    policy = await _get_policy_pack(session, policy_id)
    if command == "review":
        policy = await review_policy(
            session,
            policy_id=policy.id,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    elif command == "approve":
        assert approval_id is not None
        policy = await approve_policy(
            session,
            policy_id=policy.id,
            approval_id=approval_id,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    elif command == "activate":
        assert approval_id is not None
        policy = await activate_policy(
            session,
            policy_id=policy.id,
            approval_id=approval_id,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    elif command == "retire":
        policy = await retire_policy(
            session,
            policy_id=policy.id,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    else:
        raise RuntimeError(f"Unsupported policy transition command: {command}")

    view = PolicyPackView.model_validate(policy)
    complete_idempotency(record, status_code=200, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.post("/policy-packs/{policy_id}/review", response_model=PolicyPackView)
async def review_policy_pack(
    policy_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> PolicyPackView:
    return await _transition_command(
        command="review",
        policy_id=policy_id,
        principal=principal,
        session=session,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@router.post("/policy-packs/{policy_id}/approve", response_model=PolicyPackView)
async def approve_policy_pack(
    policy_id: UUID,
    body: PolicyTransitionApproval,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> PolicyPackView:
    return await _transition_command(
        command="approve",
        policy_id=policy_id,
        principal=principal,
        session=session,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        approval_id=body.approval_id,
    )


@router.post("/policy-packs/{policy_id}/activate", response_model=PolicyPackView)
async def activate_policy_pack(
    policy_id: UUID,
    body: PolicyTransitionApproval,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> PolicyPackView:
    return await _transition_command(
        command="activate",
        policy_id=policy_id,
        principal=principal,
        session=session,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        approval_id=body.approval_id,
    )


@router.post("/policy-packs/{policy_id}/retire", response_model=PolicyPackView)
async def retire_policy_pack(
    policy_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> PolicyPackView:
    return await _transition_command(
        command="retire",
        policy_id=policy_id,
        principal=principal,
        session=session,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@router.get("/decision-snapshots/{snapshot_id}", response_model=DecisionSnapshotView)
async def read_decision_snapshot(
    snapshot_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> DecisionSnapshotView:
    await _authorize_admin(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER, ROLE_AUDITOR},
        action="DECISION_SNAPSHOT_READ",
        target_type="DecisionSnapshot",
        target_id=str(snapshot_id),
        correlation_id=correlation_id,
    )
    snapshot = await get_decision_snapshot(session, snapshot_id)
    return DecisionSnapshotView.model_validate(snapshot)
