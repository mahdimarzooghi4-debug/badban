from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.application.reconciliation import run_lender_reconciliation
from badban.application.reconciliation_multisource import run_source_reconciliation
from badban.application.reconciliation_sources import SourceTarget, SourceType
from badban.infrastructure.persistence.models import (
    CreditProvider,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    SCOPE_LEGAL_ENTITY,
    SCOPE_PROGRAM,
    SCOPE_PROVIDER,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reconciliation_type: Literal["LENDER"] = "LENDER"
    provider_id: UUID


class LegalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reconciliation_type: Literal["GUARANTEE_ISSUER", "CUSTODY", "SETTLEMENT", "COLLATERAL_REGISTRY"]
    source_legal_entity_id: UUID


class LedgerRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reconciliation_type: Literal["LEDGER"]
    program_id: UUID


def _legacy_lender(value: Any) -> Any:
    if isinstance(value, dict) and "reconciliation_type" not in value and "provider_id" in value:
        return {**value, "reconciliation_type": "LENDER"}
    return value


RunBody = Annotated[
    Annotated[
        RunRequest | LegalRunRequest | LedgerRunRequest, Field(discriminator="reconciliation_type")
    ],
    BeforeValidator(_legacy_lender),
]


def _target(body: RunRequest | LegalRunRequest | LedgerRunRequest) -> SourceTarget:
    return SourceTarget.model_validate(body.model_dump())


def _run_target(run: ReconciliationRun) -> SourceTarget:
    return SourceTarget.model_validate(
        {
            "reconciliation_type": run.reconciliation_type,
            "provider_id": run.provider_id,
            "source_legal_entity_id": run.source_legal_entity_id,
            "program_id": run.program_id,
        }
    )


def _scope_type(target: SourceTarget) -> str:
    return (
        SCOPE_PROVIDER
        if target.reconciliation_type == "LENDER"
        else (SCOPE_PROGRAM if target.reconciliation_type == "LEDGER" else SCOPE_LEGAL_ENTITY)
    )


async def _authorize(
    session: AsyncSession,
    principal: Principal,
    provider_id: UUID,
    correlation_id: UUID,
    *,
    write: bool,
    scope_type: str = SCOPE_PROVIDER,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_FINANCE_RECONCILIATION}
            if write
            else {ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            scope_type=scope_type,
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
        "provider_id": str(run.provider_id) if run.provider_id else None,
        "source_legal_entity_id": str(run.source_legal_entity_id)
        if run.source_legal_entity_id
        else None,
        "program_id": str(run.program_id) if run.program_id else None,
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
        "internal_cutoff": run.internal_cutoff.isoformat() if run.internal_cutoff else None,
        "external_cutoff": run.external_cutoff.isoformat() if run.external_cutoff else None,
        "source_snapshot_ref": run.source_snapshot_ref,
    }


@router.post("/runs", status_code=201)
async def create_run(
    body: RunBody,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> dict[str, Any]:
    target = _target(body)
    await _authorize(
        session,
        principal,
        target.identity,
        correlation_id,
        write=True,
        scope_type=_scope_type(target),
    )
    if (
        target.provider_id is not None
        and await session.get(CreditProvider, target.provider_id) is None
    ):
        raise ApiError(404, "PROVIDER_NOT_FOUND", "Lender provider not found")
    record, replay = await acquire_idempotency(
        session,
        scope=f"reconciliation:lender:{target.identity}"
        if target.reconciliation_type == "LENDER"
        else f"reconciliation:{target.reconciliation_type}:{target.identity}",
        key=idempotency_key,
        payload={"provider_id": str(target.identity)}
        if target.reconciliation_type == "LENDER"
        else body.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    if target.reconciliation_type == "LENDER":
        run = await run_lender_reconciliation(
            session,
            provider_id=target.identity,
            registry=request.app.state.lender_adapter_registry,
            actor_id=principal.identity_id,
            actor_type=principal.identity_type,
            correlation_id=correlation_id,
        )
    else:
        run = await run_source_reconciliation(
            session,
            target=target,
            registry=request.app.state.reconciliation_source_registry,
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
    target = _run_target(run)
    await _authorize(
        session,
        principal,
        target.identity,
        correlation_id,
        write=False,
        scope_type=_scope_type(target),
    )
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
    provider_id: UUID | None = None,
    source_legal_entity_id: UUID | None = None,
    program_id: UUID | None = None,
    reconciliation_type: SourceType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[dict[str, Any]]:
    try:
        target = SourceTarget.model_validate(
            {
                "reconciliation_type": reconciliation_type or ("LENDER" if provider_id else None),
                "provider_id": provider_id,
                "source_legal_entity_id": source_legal_entity_id,
                "program_id": program_id,
            }
        )
    except ValidationError as exc:
        raise ApiError(
            422, "RECON_TARGET_INVALID", "Specify exactly one typed source identity"
        ) from exc
    await _authorize(
        session,
        principal,
        target.identity,
        correlation_id,
        write=False,
        scope_type=_scope_type(target),
    )
    predicate = (
        ReconciliationRun.provider_id == target.identity
        if target.reconciliation_type == "LENDER"
        else (
            ReconciliationRun.program_id == target.identity
            if target.reconciliation_type == "LEDGER"
            else ReconciliationRun.source_legal_entity_id == target.identity
        )
    )
    cases = (
        await session.scalars(
            select(ReconciliationCase)
            .join(ReconciliationRun, ReconciliationCase.run_id == ReconciliationRun.id)
            .where(predicate, ReconciliationRun.reconciliation_type == target.reconciliation_type)
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
    target = _run_target(run)
    await _authorize(
        session,
        principal,
        target.identity,
        correlation_id,
        write=False,
        scope_type=_scope_type(target),
    )
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
