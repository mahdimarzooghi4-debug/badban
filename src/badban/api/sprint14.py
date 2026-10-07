from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.application.reconciliation import run_lender_reconciliation
from badban.infrastructure.persistence.models import (
    CreditProvider,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    SCOPE_PROVIDER,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: UUID


async def _authorize(
    session: AsyncSession,
    principal: Principal,
    provider_id: UUID,
    correlation_id: UUID,
    *,
    write: bool,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_FINANCE_RECONCILIATION}
            if write
            else {ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            scope_type=SCOPE_PROVIDER,
            scope_id=provider_id,
            allow_global=True,
            action="RECONCILIATION_RUN" if write else "RECONCILIATION_READ",
            target_type="ReconciliationRun",
            target_id=str(provider_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Reconciliation authorization denied") from exc


def _run_view(run: ReconciliationRun) -> dict[str, Any]:
    # Source metadata is intentionally not a generic API dump.
    return {
        "id": str(run.id),
        "provider_id": str(run.provider_id),
        "reconciliation_type": run.reconciliation_type,
        "policy_pack_id": str(run.policy_pack_id),
        "policy_pack_version": run.policy_pack_version,
        "reconciliation_policy_version_id": str(run.reconciliation_policy_version_id),
        "reconciliation_policy_version_number": run.reconciliation_policy_version_number,
        "policy_payload_hash": run.reconciliation_policy_payload_hash,
        "rule_schema_version": run.rule_schema_version,
        "algorithm_code": run.algorithm_code,
        "algorithm_version": run.algorithm_version,
        "status": run.status,
        "counts": run.counts,
        "internal_cutoff": run.internal_cutoff.isoformat(),
        "external_cutoff": run.external_cutoff.isoformat() if run.external_cutoff else None,
        "source_snapshot_ref": run.source_snapshot_ref,
    }


@router.post("/runs", status_code=201)
async def create_run(
    body: RunRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> dict[str, Any]:
    await _authorize(session, principal, body.provider_id, correlation_id, write=True)
    if await session.get(CreditProvider, body.provider_id) is None:
        raise ApiError(404, "PROVIDER_NOT_FOUND", "Lender provider not found")
    record, replay = await acquire_idempotency(
        session,
        scope=f"reconciliation:lender:{body.provider_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    run = await run_lender_reconciliation(
        session,
        provider_id=body.provider_id,
        registry=request.app.state.lender_adapter_registry,
        actor_id=principal.identity_id,
        actor_type=principal.identity_type,
        correlation_id=correlation_id,
    )
    result = _run_view(run)
    complete_idempotency(record, status_code=201, response_payload=result)
    await session.commit()
    return result


@router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> dict[str, Any]:
    run = await session.get(ReconciliationRun, run_id)
    if run is None:
        raise ApiError(404, "RECON_RUN_NOT_FOUND", "Run not found")
    await _authorize(session, principal, run.provider_id, correlation_id, write=False)
    return _run_view(run)


def _case_view(case: ReconciliationCase) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "run_id": str(case.run_id),
        "resource_type": case.internal_entity_type,
        "resource_id": case.internal_entity_id,
        "external_reference": case.external_reference,
        "status": case.status,
        "materiality": case.materiality,
        "reason_code": case.mismatch_reason_code,
        "version": case.version,
    }


@router.get("/cases")
async def list_cases(
    provider_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[dict[str, Any]]:
    await _authorize(session, principal, provider_id, correlation_id, write=False)
    cases = (
        await session.scalars(
            select(ReconciliationCase)
            .join(ReconciliationRun, ReconciliationCase.run_id == ReconciliationRun.id)
            .where(ReconciliationRun.provider_id == provider_id)
            .order_by(ReconciliationCase.compared_at.desc(), ReconciliationCase.id)
            .limit(limit)
        )
    ).all()
    return [_case_view(case) for case in cases]


@router.get("/cases/{case_id}")
async def get_case(
    case_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> dict[str, Any]:
    case = await session.get(ReconciliationCase, case_id)
    if case is None:
        raise ApiError(404, "RECON_CASE_NOT_FOUND", "Case not found")
    run = await session.get(ReconciliationRun, case.run_id)
    assert run is not None
    await _authorize(session, principal, run.provider_id, correlation_id, write=False)
    observations = (
        await session.scalars(
            select(ReconciliationObservation).where(
                ReconciliationObservation.reconciliation_case_id == case.id
            )
        )
    ).all()
    return {
        **_case_view(case),
        "observations": [
            {
                "id": str(o.id),
                "differences": o.difference_payload,
                "evidence_references": o.evidence_references,
            }
            for o in observations
        ],
    }
