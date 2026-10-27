from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.external_evidence import (
    EvidenceAdapterRegistry,
    EvidenceContract,
    EvidencePurpose,
    EvidenceRequest,
    EvidenceSourceDefinition,
    acquire_from_sources,
)
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import (
    AssetPosition,
    ExternalEvidenceAcquisition,
    ExternalEvidenceObservation,
    ExternalEvidenceSource,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_OPERATIONS,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(
    prefix="/api/v1/asset-positions/{asset_position_id}/external-evidence",
    tags=["external-evidence-acquisitions"],
)
AcquisitionStatus = Literal["COMPLETED"]
EvidenceResultStatus = Literal["VALID", "UNAVAILABLE", "INVALID"]
RestrictionState = Literal["CLEAR", "BLOCKED", "UNKNOWN"]


class EvidenceAcquireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_purpose: EvidencePurpose


class EvidenceObservationView(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    source_id: UUID
    observed_at: datetime
    received_at: datetime
    status: EvidenceResultStatus
    evidence_reference: str | None
    contract_version: str
    schema_version: str
    source_value: str | None
    currency: str | None
    restriction_state: RestrictionState | None
    encumbrance_state: RestrictionState | None
    error_code: str | None


class EvidenceAcquisitionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    asset_position_id: UUID
    evidence_purpose: EvidencePurpose
    status: AcquisitionStatus
    requested_at: datetime
    completed_at: datetime
    source_count: int
    requested_by: UUID
    items: list[EvidenceObservationView]


class EvidenceAcquisitionPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: datetime
    items: list[EvidenceAcquisitionView]
    limit: int
    offset: int


def _observation_view(row: ExternalEvidenceObservation) -> EvidenceObservationView:
    return EvidenceObservationView(
        id=row.id,
        source_id=row.source_id,
        observed_at=row.observed_at,
        received_at=row.received_at,
        status=row.status,  # type: ignore[arg-type]
        evidence_reference=row.evidence_reference,
        contract_version=row.contract_version,
        schema_version=row.schema_version,
        source_value=str(row.source_value) if row.source_value is not None else None,
        currency=row.currency,
        restriction_state=row.restriction_state,  # type: ignore[arg-type]
        encumbrance_state=row.encumbrance_state,  # type: ignore[arg-type]
        error_code=row.error_code,
    )


def _acquisition_view(
    acquisition: ExternalEvidenceAcquisition,
    observations: list[ExternalEvidenceObservation],
) -> EvidenceAcquisitionView:
    return EvidenceAcquisitionView(
        id=acquisition.id,
        asset_position_id=acquisition.asset_position_id,
        evidence_purpose=acquisition.evidence_purpose,  # type: ignore[arg-type]
        status=acquisition.status,  # type: ignore[arg-type]
        requested_at=acquisition.requested_at,
        completed_at=acquisition.completed_at,
        source_count=acquisition.source_count,
        requested_by=acquisition.requested_by,
        items=[_observation_view(row) for row in observations],
    )


async def _authorize_position(
    session: AsyncSession,
    *,
    principal: Principal,
    position: AssetPosition,
    correlation_id: UUID,
    action: str,
    roles: set[str],
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=SCOPE_PROGRAM,
            scope_id=position.program_id,
            allow_global=True,
            action=action,
            target_type="AssetPosition",
            target_id=str(position.id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Program-scoped permission required") from exc


async def _observations_for(
    session: AsyncSession,
    acquisition_ids: list[UUID],
) -> dict[UUID, list[ExternalEvidenceObservation]]:
    if not acquisition_ids:
        return {}
    rows = (
        await session.scalars(
            select(ExternalEvidenceObservation)
            .where(ExternalEvidenceObservation.acquisition_id.in_(acquisition_ids))
            .order_by(ExternalEvidenceObservation.source_id)
        )
    ).all()
    result: dict[UUID, list[ExternalEvidenceObservation]] = {
        acquisition_id: [] for acquisition_id in acquisition_ids
    }
    for row in rows:
        result[row.acquisition_id].append(row)
    return result


@router.post(
    "/acquisitions",
    response_model=EvidenceAcquisitionView,
    status_code=status.HTTP_201_CREATED,
)
async def acquire_evidence(
    asset_position_id: UUID,
    body: EvidenceAcquireRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> EvidenceAcquisitionView:
    position = await session.get(AssetPosition, asset_position_id)
    if position is None:
        raise ApiError(404, "ASSET_POSITION_NOT_FOUND", "Asset Position was not found")
    await _authorize_position(
        session,
        principal=principal,
        position=position,
        correlation_id=correlation_id,
        action="EXTERNAL_EVIDENCE_ACQUIRE",
        roles={ROLE_OPERATIONS},
    )

    payload = {
        "asset_position_id": str(position.id),
        "evidence_purpose": body.evidence_purpose,
    }
    idempotency, replay = await acquire_idempotency(
        session,
        scope=f"external-evidence-acquire:{principal.identity_id}",
        key=idempotency_key,
        payload=payload,
    )
    if replay is not None:
        acquisition_id = UUID(str(replay["acquisition_id"]))
        acquisition = await session.get(ExternalEvidenceAcquisition, acquisition_id)
        if acquisition is None:
            raise ApiError(
                500,
                "EVIDENCE_ACQUISITION_RECORD_MISSING",
                "Completed evidence acquisition record was not found",
            )
        observations = await session.scalars(
            select(ExternalEvidenceObservation)
            .where(ExternalEvidenceObservation.acquisition_id == acquisition.id)
            .order_by(ExternalEvidenceObservation.source_id)
        )
        return _acquisition_view(acquisition, list(observations.all()))

    source_rows = (
        await session.scalars(
            select(ExternalEvidenceSource)
            .where(
                ExternalEvidenceSource.asset_type_id == position.asset_type_id,
                ExternalEvidenceSource.evidence_purpose == body.evidence_purpose,
                ExternalEvidenceSource.lifecycle_status == "ACTIVE",
            )
            .order_by(ExternalEvidenceSource.source_key, ExternalEvidenceSource.id)
        )
    ).all()
    source_definitions = tuple(EvidenceSourceDefinition.from_record(row) for row in source_rows)
    evidence_request = EvidenceRequest(
        asset_position_id=position.id,
        asset_type_id=position.asset_type_id,
        evidence_purpose=body.evidence_purpose,
    )
    registry: EvidenceAdapterRegistry = request.app.state.evidence_adapter_registry
    started_at = datetime.now(UTC)
    results = await acquire_from_sources(
        registry,
        sources=source_definitions,
        request=evidence_request,
    )
    completed_at = datetime.now(UTC)
    acquisition = ExternalEvidenceAcquisition(
        asset_position_id=position.id,
        evidence_purpose=body.evidence_purpose,
        status="COMPLETED",
        requested_at=started_at,
        completed_at=completed_at,
        source_count=len(results),
        requested_by=principal.identity_id,
        correlation_id=correlation_id,
    )
    session.add(acquisition)
    await session.flush()

    observation_rows: list[ExternalEvidenceObservation] = []
    for result in results:
        row = ExternalEvidenceObservation(
            acquisition_id=acquisition.id,
            source_id=result.source_id,
            observed_at=result.observed_at,
            received_at=result.received_at,
            status=result.status,
            evidence_reference=result.evidence_reference,
            contract_version=result.contract_version,
            schema_version=result.schema_version,
            source_value=result.source_value,
            currency=result.currency,
            restriction_state=result.restriction_state,
            encumbrance_state=result.encumbrance_state,
            error_code=result.error_code,
        )
        session.add(row)
        observation_rows.append(row)
    await session.flush()

    view = _acquisition_view(acquisition, observation_rows)
    append_audit(
        session,
        aggregate_type="ExternalEvidenceAcquisition",
        aggregate_id=str(acquisition.id),
        aggregate_version=None,
        action="EXTERNAL_EVIDENCE_ACQUIRE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={
            "asset_position_id": str(position.id),
            "evidence_purpose": body.evidence_purpose,
            "source_count": len(results),
            "result_statuses": [result.status for result in results],
            "error_codes": [result.error_code for result in results if result.error_code],
        },
    )
    complete_idempotency(
        idempotency,
        status_code=201,
        response_payload={"acquisition_id": str(acquisition.id)},
    )
    await session.commit()
    return view


@router.get("/acquisitions", response_model=EvidenceAcquisitionPage)
async def list_evidence_acquisitions(
    asset_position_id: UUID,
    evidence_purpose: EvidencePurpose | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> EvidenceAcquisitionPage:
    position = await session.get(AssetPosition, asset_position_id)
    if position is None:
        raise ApiError(404, "ASSET_POSITION_NOT_FOUND", "Asset Position was not found")
    await _authorize_position(
        session,
        principal=principal,
        position=position,
        correlation_id=correlation_id,
        action="EXTERNAL_EVIDENCE_ACQUISITION_LIST",
        roles={ROLE_OPERATIONS, ROLE_AUDITOR},
    )
    filters = [ExternalEvidenceAcquisition.asset_position_id == position.id]
    if evidence_purpose is not None:
        filters.append(ExternalEvidenceAcquisition.evidence_purpose == evidence_purpose)
    rows = (
        await session.scalars(
            select(ExternalEvidenceAcquisition)
            .where(*filters)
            .order_by(
                ExternalEvidenceAcquisition.requested_at.desc(),
                ExternalEvidenceAcquisition.id,
            )
            .offset(offset)
            .limit(limit)
        )
    ).all()
    by_id = await _observations_for(session, [row.id for row in rows])
    append_audit(
        session,
        aggregate_type="ExternalEvidenceAcquisitionQueue",
        aggregate_id=str(position.id),
        aggregate_version=None,
        action="EXTERNAL_EVIDENCE_ACQUISITION_LIST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(rows), "limit": limit, "offset": offset},
    )
    await session.commit()
    return EvidenceAcquisitionPage(
        observed_at=datetime.now(UTC),
        items=[_acquisition_view(row, by_id.get(row.id, [])) for row in rows],
        limit=limit,
        offset=offset,
    )
