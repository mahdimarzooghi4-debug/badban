from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.business_readiness import (
    BusinessReadinessError,
    BusinessReadinessResult,
    activate_stop_control,
    clear_stop_control,
    evaluate_business_readiness,
)
from badban.application.lender_adapter import LenderAdapterError
from badban.infrastructure.persistence.models import OperationalStopControl
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_OPERATIONS,
    ROLE_RISK,
    SCOPE_ASSET_TYPE,
    SCOPE_GLOBAL,
    SCOPE_PROVIDER,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1", tags=["business-readiness"])

_MUTATION_ROLES = {ROLE_OPERATIONS, ROLE_GOVERNANCE_APPROVER}
_READ_ROLES = {
    ROLE_OPERATIONS,
    ROLE_RISK,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_AUDITOR,
}


class StopControlCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_type: Literal[
        "STOP_NEW_GUARANTEE_RESERVATIONS",
        "STOP_GUARANTEE_ACTIVATION",
        "SUSPEND_PROVIDER_FOR_NEW_ACTIONS",
        "SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS",
        "STOP_CLAIM_SETTLEMENT",
        "STOP_COLLATERAL_RELEASE",
    ]
    scope_type: Literal["GLOBAL", "PROVIDER", "ASSET_TYPE"]
    scope_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=1000)
    evidence_reference: str | None = Field(default=None, min_length=1, max_length=500)


class StopControlView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    control_type: str
    scope_type: str
    scope_id: UUID | None
    active: bool
    reason: str
    evidence_reference: str | None
    activated_by: UUID
    activated_at: datetime
    cleared_by: UUID | None
    cleared_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class BusinessReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_scope_definition: dict[str, Any]
    provider_id: UUID | None = None
    asset_type_id: UUID | None = None

    @model_validator(mode="after")
    def single_optional_target(self) -> BusinessReadinessRequest:
        if self.provider_id is not None and self.asset_type_id is not None:
            raise ValueError("provider_id and asset_type_id cannot be evaluated together")
        return self


class BusinessReadinessReasonView(BaseModel):
    code: str
    source_type: str
    source_reference: str | None
    details: dict[str, Any]


class BusinessReadinessView(BaseModel):
    status: Literal["READY", "NOT_READY"]
    evaluated_at: datetime
    policy_pack_id: UUID | None
    risk_snapshot_id: UUID | None
    reasons: list[BusinessReadinessReasonView]


def _raise_readiness_error(exc: BusinessReadinessError) -> NoReturn:
    if exc.code in {"STOP_CONTROL_NOT_FOUND", "STOP_CONTROL_TARGET_NOT_FOUND"}:
        raise ApiError(404, exc.code, str(exc)) from exc
    if exc.code in {"STOP_CONTROL_ALREADY_ACTIVE", "STOP_CONTROL_ACTIVE"}:
        raise ApiError(409, exc.code, str(exc)) from exc
    raise ApiError(422, exc.code, str(exc)) from exc


async def _authorize_scope(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    scope_type: str,
    scope_id: UUID | None,
    action: str,
    target_id: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=scope_type,
            scope_id=scope_id,
            allow_global=scope_type != SCOPE_GLOBAL,
            action=action,
            target_type="OperationalControl",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for requested scope") from exc


def _assert_generic_scope(scope_type: str, scope_id: UUID | None) -> None:
    if scope_type == SCOPE_GLOBAL and scope_id is not None:
        raise ApiError(422, "STOP_CONTROL_SCOPE_INVALID", "GLOBAL scope must not include scope_id")
    if scope_type != SCOPE_GLOBAL and scope_id is None:
        raise ApiError(422, "STOP_CONTROL_SCOPE_INVALID", "Scoped query requires scope_id")


def _readiness_view(result: BusinessReadinessResult) -> BusinessReadinessView:
    return BusinessReadinessView(
        status=result.status,
        evaluated_at=result.evaluated_at,
        policy_pack_id=result.policy_pack_id,
        risk_snapshot_id=result.risk_snapshot_id,
        reasons=[
            BusinessReadinessReasonView(
                code=reason.code,
                source_type=reason.source_type,
                source_reference=reason.source_reference,
                details=reason.details,
            )
            for reason in result.reasons
        ],
    )


@router.post(
    "/operational-stop-controls",
    response_model=StopControlView,
    status_code=status.HTTP_201_CREATED,
)
async def create_operational_stop_control(
    body: StopControlCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> StopControlView:
    await _authorize_scope(
        session,
        principal=principal,
        roles=_MUTATION_ROLES,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        action="STOP_CONTROL_ACTIVATE",
        target_id=body.control_type,
        correlation_id=correlation_id,
    )
    try:
        control = await activate_stop_control(
            session,
            control_type=body.control_type,
            scope_type=body.scope_type,
            scope_id=body.scope_id,
            reason=body.reason,
            evidence_reference=body.evidence_reference,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    except BusinessReadinessError as exc:
        _raise_readiness_error(exc)
    await session.commit()
    await session.refresh(control)
    return StopControlView.model_validate(control)


@router.post(
    "/operational-stop-controls/{control_id}/clear",
    response_model=StopControlView,
)
async def clear_operational_stop_control(
    control_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> StopControlView:
    control = await session.get(OperationalStopControl, control_id)
    if control is None:
        raise ApiError(404, "STOP_CONTROL_NOT_FOUND", "Stop control was not found")
    await _authorize_scope(
        session,
        principal=principal,
        roles=_MUTATION_ROLES,
        scope_type=control.scope_type,
        scope_id=control.scope_id,
        action="STOP_CONTROL_CLEAR",
        target_id=str(control.id),
        correlation_id=correlation_id,
    )
    try:
        cleared = await clear_stop_control(
            session,
            control_id=control.id,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    except BusinessReadinessError as exc:
        _raise_readiness_error(exc)
    await session.commit()
    await session.refresh(cleared)
    return StopControlView.model_validate(cleared)


@router.get(
    "/operational-stop-controls",
    response_model=list[StopControlView],
)
async def list_operational_stop_controls(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    scope_type: Literal["GLOBAL", "PROVIDER", "ASSET_TYPE"] = Query(default="GLOBAL"),
    scope_id: UUID | None = Query(default=None),
    active_only: bool = Query(default=True),
) -> list[StopControlView]:
    _assert_generic_scope(scope_type, scope_id)
    await _authorize_scope(
        session,
        principal=principal,
        roles=_READ_ROLES,
        scope_type=scope_type,
        scope_id=scope_id,
        action="STOP_CONTROL_LIST",
        target_id="collection",
        correlation_id=correlation_id,
    )
    statement = select(OperationalStopControl).where(
        OperationalStopControl.scope_type == scope_type,
        OperationalStopControl.scope_id.is_(None)
        if scope_id is None
        else OperationalStopControl.scope_id == scope_id,
    )
    if active_only:
        statement = statement.where(OperationalStopControl.active.is_(True))
    rows = (
        await session.scalars(
            statement.order_by(
                OperationalStopControl.activated_at.desc(),
                OperationalStopControl.id.desc(),
            )
        )
    ).all()
    return [StopControlView.model_validate(row) for row in rows]


@router.post(
    "/business-readiness/evaluate",
    response_model=BusinessReadinessView,
)
async def business_readiness(
    body: BusinessReadinessRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> BusinessReadinessView:
    if body.provider_id is not None:
        scope_type = SCOPE_PROVIDER
        scope_id = body.provider_id
    elif body.asset_type_id is not None:
        scope_type = SCOPE_ASSET_TYPE
        scope_id = body.asset_type_id
    else:
        scope_type = SCOPE_GLOBAL
        scope_id = None

    await _authorize_scope(
        session,
        principal=principal,
        roles=_READ_ROLES,
        scope_type=scope_type,
        scope_id=scope_id,
        action="BUSINESS_READINESS_READ",
        target_id=str(scope_id) if scope_id is not None else "GLOBAL",
        correlation_id=correlation_id,
    )

    provider_health: str | None = None
    if body.provider_id is not None:
        try:
            adapter = request.app.state.lender_adapter_registry.resolve(body.provider_id)
            provider_health = await adapter.health_check()
        except (LenderAdapterError, Exception):
            provider_health = None

    result = await evaluate_business_readiness(
        session,
        policy_scope_definition=body.policy_scope_definition,
        provider_id=body.provider_id,
        asset_type_id=body.asset_type_id,
        provider_health=provider_health,
    )
    return _readiness_view(result)
