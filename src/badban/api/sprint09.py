from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.application.policy_resolution import resolve_active_policy_pack
from badban.application.risk import RiskEvaluationError, evaluate_and_snapshot_portfolio_risk
from badban.infrastructure.persistence.models import PortfolioRiskSnapshot
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_RISK,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/risk", tags=["portfolio-risk"])


class RiskEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_definition: dict[str, Any]
    reserve_requirement: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^\d+(?:\.\d+)?$",
        json_schema_extra={"format": "decimal"},
    )
    reserve_available: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^\d+(?:\.\d+)?$",
        json_schema_extra={"format": "decimal"},
    )
    reserve_metrics_reference: str = Field(min_length=1, max_length=500)
    concentration_state: Literal["GREEN", "AMBER", "RED"]
    concentration_metrics_reference: str = Field(min_length=1, max_length=500)
    stress_state: Literal["GREEN", "AMBER", "RED"] | None = None
    stress_result_reference: str | None = Field(default=None, min_length=1, max_length=500)
    authoritative_input_references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stress_pair(self) -> RiskEvaluateRequest:
        if (self.stress_state is None) != (self.stress_result_reference is None):
            raise ValueError("stress_state and stress_result_reference must be supplied together")
        if any(not reference.strip() for reference in self.authoritative_input_references):
            raise ValueError("authoritative_input_references cannot contain blank values")
        return self


class RiskSnapshotView(BaseModel):
    id: UUID
    policy_pack_id: UUID
    policy_pack_version: int
    risk_policy_version_id: UUID
    risk_policy_code: str
    risk_policy_version_number: int
    risk_state: Literal["GREEN", "AMBER", "RED"]
    total_active_exposure: str = Field(json_schema_extra={"format": "decimal"})
    total_reserved_exposure: str = Field(json_schema_extra={"format": "decimal"})
    committed_exposure: str = Field(json_schema_extra={"format": "decimal"})
    approved_portfolio_limit: str = Field(json_schema_extra={"format": "decimal"})
    reserve_requirement: str = Field(json_schema_extra={"format": "decimal"})
    reserve_available: str = Field(json_schema_extra={"format": "decimal"})
    reserve_metrics_reference: str
    concentration_metrics_reference: str
    stress_result_reference: str | None
    evaluated_inputs: dict[str, Any]
    input_hash: str
    algorithm_code: str
    algorithm_version: str
    actor_type: str
    actor_id: UUID
    correlation_id: UUID
    evaluated_at: datetime
    created_at: datetime


def _decimal(value: str, *, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ApiError(422, "RISK_INPUT_INVALID", f"{field} must be a decimal string") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ApiError(422, "RISK_INPUT_INVALID", f"{field} must be finite and non-negative")
    return parsed


def _view(snapshot: PortfolioRiskSnapshot) -> RiskSnapshotView:
    return RiskSnapshotView(
        id=snapshot.id,
        policy_pack_id=snapshot.policy_pack_id,
        policy_pack_version=snapshot.policy_pack_version,
        risk_policy_version_id=snapshot.risk_policy_version_id,
        risk_policy_code=snapshot.risk_policy_code,
        risk_policy_version_number=snapshot.risk_policy_version_number,
        risk_state=snapshot.risk_state,
        total_active_exposure=format(snapshot.total_active_exposure, "f"),
        total_reserved_exposure=format(snapshot.total_reserved_exposure, "f"),
        committed_exposure=format(snapshot.committed_exposure, "f"),
        approved_portfolio_limit=format(snapshot.approved_portfolio_limit, "f"),
        reserve_requirement=format(snapshot.reserve_requirement, "f"),
        reserve_available=format(snapshot.reserve_available, "f"),
        reserve_metrics_reference=snapshot.reserve_metrics_reference,
        concentration_metrics_reference=snapshot.concentration_metrics_reference,
        stress_result_reference=snapshot.stress_result_reference,
        evaluated_inputs=snapshot.evaluated_inputs,
        input_hash=snapshot.input_hash,
        algorithm_code=snapshot.algorithm_code,
        algorithm_version=snapshot.algorithm_version,
        actor_type=snapshot.actor_type,
        actor_id=snapshot.actor_id,
        correlation_id=snapshot.correlation_id,
        evaluated_at=snapshot.evaluated_at,
        created_at=snapshot.created_at,
    )


async def _authorize(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    action: str,
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
            target_type="PortfolioRiskSnapshot",
            target_id="portfolio",
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for portfolio risk") from exc


@router.get("/portfolio", response_model=RiskSnapshotView)
async def get_current_portfolio_risk(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> RiskSnapshotView:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_RISK, ROLE_AUDITOR},
        action="PORTFOLIO_RISK_READ",
        correlation_id=correlation_id,
    )
    snapshot = await session.scalar(
        select(PortfolioRiskSnapshot)
        .order_by(
            PortfolioRiskSnapshot.evaluated_at.desc(),
            PortfolioRiskSnapshot.created_at.desc(),
            PortfolioRiskSnapshot.id.desc(),
        )
        .limit(1)
    )
    if snapshot is None:
        raise ApiError(
            404,
            "PORTFOLIO_RISK_SNAPSHOT_NOT_FOUND",
            "No portfolio risk snapshot exists",
        )
    return _view(snapshot)


@router.post(
    "/portfolio/evaluate",
    response_model=RiskSnapshotView,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_portfolio_risk(
    body: RiskEvaluateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> RiskSnapshotView:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_RISK},
        action="PORTFOLIO_RISK_EVALUATE",
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope="portfolio-risk:evaluate",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return RiskSnapshotView.model_validate(replay)

    evaluated_at = datetime.now(UTC)
    resolved_pack = await resolve_active_policy_pack(
        session,
        scope_definition=body.scope_definition,
        effective_at=evaluated_at,
    )
    try:
        snapshot = await evaluate_and_snapshot_portfolio_risk(
            session,
            resolved_policy_pack=resolved_pack,
            reserve_requirement=_decimal(body.reserve_requirement, field="reserve_requirement"),
            reserve_available=_decimal(body.reserve_available, field="reserve_available"),
            reserve_metrics_reference=body.reserve_metrics_reference,
            concentration_state=body.concentration_state,
            concentration_metrics_reference=body.concentration_metrics_reference,
            stress_state=body.stress_state,
            stress_result_reference=body.stress_result_reference,
            authoritative_input_references=tuple(body.authoritative_input_references),
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
            evaluated_at=evaluated_at,
        )
    except RiskEvaluationError as exc:
        status_code = (
            409 if exc.code in {"RISK_POLICY_INVALID", "RISK_EXPOSURE_SOURCE_INVALID"} else 422
        )
        raise ApiError(status_code, exc.code, str(exc)) from exc

    await session.refresh(snapshot)
    view = _view(snapshot)
    complete_idempotency(
        record,
        status_code=status.HTTP_201_CREATED,
        response_payload=view.model_dump(mode="json"),
    )
    await session.commit()
    return view
