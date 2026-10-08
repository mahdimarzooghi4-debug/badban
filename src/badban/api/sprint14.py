from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.reconciliation import (
    LENDER_RECONCILIATION_TYPE,
    ReconciliationError,
    execute_lender_reconciliation,
)
from badban.infrastructure.persistence.models import (
    CreditProvider,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    SCOPE_GLOBAL,
    SCOPE_PROVIDER,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])


class ReconciliationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reconciliation_type: Literal["LENDER_EXTERNAL_LOAN"] = LENDER_RECONCILIATION_TYPE
    provider_id: UUID
    scope_definition: dict[str, Any]
    scope_reference: str | None = Field(default=None, min_length=1, max_length=500)


class ReconciliationRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reconciliation_type: str
    provider_id: UUID | None
    scope_definition: dict[str, Any]
    policy_pack_id: UUID
    policy_pack_version: int
    rule_policy_version_id: UUID
    rule_policy_code: str
    rule_policy_version_number: int
    rule_schema_version: str
    internal_cutoff: datetime
    external_cutoff: datetime
    source_snapshot_ref: str | None
    source_evidence_references: list[str]
    source_fingerprint: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    matched_count: int
    mismatch_count: int
    stale_count: int
    critical_count: int
    created_at: datetime


class ReconciliationObservationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reconciliation_case_id: UUID
    internal_value_reference: str
    external_value_reference: str
    difference_payload: dict[str, Any]
    evidence_reference: str | None
    observed_at: datetime
    created_at: datetime


class ReconciliationCaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    reconciliation_type: str
    internal_entity_type: str
    internal_entity_id: str | None
    external_provider_id: UUID | None
    external_reference: str | None
    status: str
    materiality: str
    mismatch_reason_code: str | None
    compared_at: datetime | None
    resolved_at: datetime | None
    resolution_reference: str | None
    rule_policy_version_id: UUID
    rule_policy_version_number: int
    first_detected_at: datetime
    last_observed_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime


class ReconciliationCaseDetailView(ReconciliationCaseView):
    observations: list[ReconciliationObservationView]


def _raise_reconciliation_error(exc: ReconciliationError) -> NoReturn:
    if exc.code == "PROVIDER_NOT_FOUND":
        raise ApiError(404, exc.code, str(exc)) from exc
    if exc.retryable or exc.code in {
        "LENDER_ADAPTER_NOT_CONFIGURED",
        "RECONCILIATION_SOURCE_NOT_CONFIGURED",
        "PROVIDER_TIMEOUT",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_OUTCOME_UNKNOWN",
    }:
        raise ApiError(503, exc.code, str(exc)) from exc
    if exc.code in {
        "POLICY_PACK_NOT_ACTIVE",
        "RECONCILIATION_POLICY_MISSING",
        "RECONCILIATION_POLICY_AMBIGUOUS",
        "RECONCILIATION_POLICY_INVALID",
        "RECONCILIATION_SCOPE_INVALID",
        "RECONCILIATION_SOURCE_CUTOFF_INVALID",
        "RECONCILIATION_EVIDENCE_REQUIRED",
    }:
        raise ApiError(409, exc.code, str(exc)) from exc
    raise ApiError(422, exc.code, str(exc)) from exc


async def _authorize_provider(
    session: AsyncSession,
    *,
    principal: Principal,
    provider_id: UUID,
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
            scope_type=SCOPE_PROVIDER,
            scope_id=provider_id,
            allow_global=True,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for reconciliation") from exc


async def _authorize_global(
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
        raise ApiError(403, exc.code, "Authorization denied for reconciliation") from exc


@router.post(
    "/runs",
    response_model=ReconciliationRunView,
    status_code=status.HTTP_201_CREATED,
)
async def create_reconciliation_run(
    body: ReconciliationRunRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ReconciliationRunView:
    provider = await session.get(CreditProvider, body.provider_id)
    if provider is None:
        raise ApiError(404, "PROVIDER_NOT_FOUND", "Lender provider was not found")
    await _authorize_provider(
        session,
        principal=principal,
        provider_id=provider.id,
        roles={ROLE_FINANCE_RECONCILIATION},
        action="RECONCILIATION_RUN_CREATE",
        target_type="CreditProvider",
        target_id=str(provider.id),
        correlation_id=correlation_id,
    )

    try:
        run_id = await execute_lender_reconciliation(
            request.app.state.database,
            request.app.state.lender_adapter_registry,
            provider_id=provider.id,
            scope_definition=body.scope_definition,
            scope_reference=body.scope_reference,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    except ReconciliationError as exc:
        _raise_reconciliation_error(exc)

    run = await session.get(ReconciliationRun, run_id)
    if run is None:
        raise ApiError(500, "RECONCILIATION_RUN_NOT_VISIBLE", "Created run could not be loaded")
    return ReconciliationRunView.model_validate(run)


@router.get("/runs/{run_id}", response_model=ReconciliationRunView)
async def get_reconciliation_run(
    run_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ReconciliationRunView:
    run = await session.get(ReconciliationRun, run_id)
    if run is None:
        raise ApiError(404, "RECONCILIATION_RUN_NOT_FOUND", "Reconciliation run was not found")
    if run.provider_id is None:
        await _authorize_global(
            session,
            principal=principal,
            roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            action="RECONCILIATION_RUN_READ",
            target_type="ReconciliationRun",
            target_id=str(run.id),
            correlation_id=correlation_id,
        )
    else:
        await _authorize_provider(
            session,
            principal=principal,
            provider_id=run.provider_id,
            roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            action="RECONCILIATION_RUN_READ",
            target_type="ReconciliationRun",
            target_id=str(run.id),
            correlation_id=correlation_id,
        )
    return ReconciliationRunView.model_validate(run)


@router.get("/cases", response_model=list[ReconciliationCaseView])
async def list_reconciliation_cases(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    reconciliation_type: str | None = Query(default=None, alias="type", max_length=80),
    case_status: str | None = Query(default=None, alias="status", max_length=40),
    materiality: str | None = Query(default=None, max_length=20),
    provider_id: UUID | None = Query(default=None, alias="provider"),
    min_age_seconds: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ReconciliationCaseView]:
    if provider_id is None:
        await _authorize_global(
            session,
            principal=principal,
            roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            action="RECONCILIATION_CASE_LIST",
            target_type="ReconciliationCase",
            target_id="collection",
            correlation_id=correlation_id,
        )
    else:
        await _authorize_provider(
            session,
            principal=principal,
            provider_id=provider_id,
            roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            action="RECONCILIATION_CASE_LIST",
            target_type="ReconciliationCase",
            target_id="collection",
            correlation_id=correlation_id,
        )

    statement = select(ReconciliationCase).order_by(
        ReconciliationCase.created_at.desc(),
        ReconciliationCase.id.desc(),
    )
    if reconciliation_type is not None:
        statement = statement.where(ReconciliationCase.reconciliation_type == reconciliation_type)
    if case_status is not None:
        statement = statement.where(ReconciliationCase.status == case_status)
    if materiality is not None:
        statement = statement.where(ReconciliationCase.materiality == materiality)
    if provider_id is not None:
        statement = statement.where(ReconciliationCase.external_provider_id == provider_id)
    if min_age_seconds is not None:
        cutoff = datetime.now(UTC) - timedelta(seconds=min_age_seconds)
        statement = statement.where(ReconciliationCase.created_at <= cutoff)
    rows = (await session.scalars(statement.limit(limit))).all()
    return [ReconciliationCaseView.model_validate(row) for row in rows]


@router.get("/cases/{case_id}", response_model=ReconciliationCaseDetailView)
async def get_reconciliation_case(
    case_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ReconciliationCaseDetailView:
    case = await session.get(ReconciliationCase, case_id)
    if case is None:
        raise ApiError(404, "RECONCILIATION_CASE_NOT_FOUND", "Reconciliation case was not found")
    if case.external_provider_id is None:
        await _authorize_global(
            session,
            principal=principal,
            roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            action="RECONCILIATION_CASE_READ",
            target_type="ReconciliationCase",
            target_id=str(case.id),
            correlation_id=correlation_id,
        )
    else:
        await _authorize_provider(
            session,
            principal=principal,
            provider_id=case.external_provider_id,
            roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            action="RECONCILIATION_CASE_READ",
            target_type="ReconciliationCase",
            target_id=str(case.id),
            correlation_id=correlation_id,
        )
    observations = (
        await session.scalars(
            select(ReconciliationObservation)
            .where(ReconciliationObservation.reconciliation_case_id == case.id)
            .order_by(
                ReconciliationObservation.observed_at,
                ReconciliationObservation.id,
            )
        )
    ).all()
    base = ReconciliationCaseView.model_validate(case).model_dump()
    return ReconciliationCaseDetailView(
        **base,
        observations=[
            ReconciliationObservationView.model_validate(observation)
            for observation in observations
        ],
    )
