from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.api.sprint07 import GuaranteeCaseView, _view as guarantee_view
from badban.application.backing_source_inventory import BackingInventoryError
from badban.application.request_bound_backing_evidence import (
    RequestEvidenceError,
    read_request_bound_backing_evidence,
)
from badban.infrastructure.persistence.models import GuaranteeCase, ParticipationEpisode
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_OPERATIONS,
    ROLE_RISK,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/guarantees", tags=["guarantee-reads"])


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValuationEvidenceView(EvidenceModel):
    observation_id: UUID
    asset_position_id: UUID
    valued_quantity: str = Field(json_schema_extra={"format": "decimal"})
    unit_price: str = Field(json_schema_extra={"format": "decimal"})
    valuation_currency: str
    fx_rate: str | None = Field(default=None, json_schema_extra={"format": "decimal"})
    gross_market_value: str = Field(json_schema_extra={"format": "decimal"})
    source_name: str
    source_reference: str
    source_version_reference: str | None
    observed_at: datetime
    received_at: datetime
    valid_until: datetime | None
    recorded_freshness_status: str
    evidence_reference: str | None


class AssetEvidenceView(EvidenceModel):
    position_id: UUID
    position_version: int
    asset_type_id: UUID
    asset_type_version: int
    asset_type_code: str
    asset_type_status: str
    episode_id: UUID
    program_id: UUID
    ownership_funding_type: str
    legal_owner_participant_id: UUID | None
    legal_owner_entity_id: UUID | None
    custodian_legal_entity_id: UUID | None
    quantity: str = Field(json_schema_extra={"format": "decimal"})
    unit_code: str
    lifecycle_status: str
    source_reference: str | None
    valuation_history: list[ValuationEvidenceView]


class BackingEvidenceView(EvidenceModel):
    episode_id: UUID
    episode_version: int
    episode_status: str
    participant_id: UUID
    program_id: UUID
    episode_consent_state: str
    sources: list[AssetEvidenceView]
    source_fingerprint: str


class RequestBoundEvidenceView(EvidenceModel):
    guarantee_case_id: UUID
    guarantee_version: int
    guarantee_state: str
    requested_principal: str = Field(json_schema_extra={"format": "decimal"})
    guarantee_mode: str
    episode_id: UUID
    program_id: UUID
    provider_id: UUID
    provider_version: int
    provider_code: str
    provider_lifecycle_status: str
    provider_legal_entity_id: UUID
    credit_product_version_id: UUID
    product_aggregate_version: int
    product_version_number: int
    product_code: str
    product_lifecycle_status: str
    product_currency: str
    product_guarantee_mode: str
    product_policy_version_reference: str
    product_lender_of_record_legal_entity_id: UUID
    product_min_principal: str = Field(json_schema_extra={"format": "decimal"})
    product_max_principal: str = Field(json_schema_extra={"format": "decimal"})
    backing: BackingEvidenceView
    evidence_fingerprint: str


def _decimal_to_string(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _decimal_to_string(inner) for key, inner in value.items()}
    if isinstance(value, (tuple, list)):
        return [_decimal_to_string(inner) for inner in value]
    return value


async def _authorized_guarantee(
    session: AsyncSession,
    *,
    principal: Principal,
    guarantee_id: UUID,
    correlation_id: UUID,
    action: str,
) -> GuaranteeCase:
    row = (
        await session.execute(
            select(GuaranteeCase, ParticipationEpisode)
            .join(
                ParticipationEpisode,
                ParticipationEpisode.id == GuaranteeCase.participation_episode_id,
            )
            .where(GuaranteeCase.id == guarantee_id)
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "GUARANTEE_NOT_FOUND", "Guarantee was not found")
    guarantee, episode = row
    try:
        await authorize(
            session,
            principal=principal,
            roles={
                ROLE_OPERATIONS,
                ROLE_RISK,
                ROLE_FINANCE_RECONCILIATION,
                ROLE_AUDITOR,
            },
            scope_type=SCOPE_PROGRAM,
            scope_id=episode.program_id,
            allow_global=True,
            action=action,
            target_type="GuaranteeCase",
            target_id=str(guarantee.id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for guarantee read") from exc
    return guarantee


@router.get(
    "/{guarantee_id}",
    response_model=GuaranteeCaseView,
    description=(
        "Scoped staff read of persisted GuaranteeCase state. No capacity calculation, "
        "reservation or provider decision. OPERATIONS, RISK, FINANCE_RECONCILIATION "
        "or AUDITOR within the Program; eligible global roles are accepted."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "GUARANTEE_NOT_FOUND"},
    },
)
async def get_guarantee_detail(
    guarantee_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> GuaranteeCaseView:
    guarantee = await _authorized_guarantee(
        session,
        principal=principal,
        guarantee_id=guarantee_id,
        correlation_id=correlation_id,
        action="GUARANTEE_DETAIL_READ",
    )
    return guarantee_view(guarantee)


@router.get(
    "/{guarantee_id}/request-evidence",
    response_model=RequestBoundEvidenceView,
    description=(
        "Scoped operational observation of REQUESTED guarantee, captured product/provider "
        "and recorded multi-asset backing sources. Data and fingerprints are NOT "
        "valuation acceptance, capacity, reserve eligibility, risk PASS or a reservation. "
        "Never used to infer an approved action. Staff-only; Program/global RBAC required."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "GUARANTEE_NOT_FOUND or REQUEST_EVIDENCE_NOT_FOUND"},
        409: {"description": "Contradictory request/source lineage or unsupported state"},
    },
)
async def get_guarantee_request_evidence(
    guarantee_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> RequestBoundEvidenceView:
    guarantee = await _authorized_guarantee(
        session,
        principal=principal,
        guarantee_id=guarantee_id,
        correlation_id=correlation_id,
        action="GUARANTEE_REQUEST_EVIDENCE_READ",
    )
    episode = await session.get(ParticipationEpisode, guarantee.participation_episode_id)
    if episode is None:
        raise ApiError(409, "REQUEST_EVIDENCE_SCOPE_CONFLICT", "Episode lineage is missing")
    try:
        evidence = await read_request_bound_backing_evidence(
            session,
            guarantee_case_id=guarantee.id,
            program_id=episode.program_id,
        )
    except (RequestEvidenceError, BackingInventoryError) as exc:
        status_code = 404 if exc.code == "REQUEST_EVIDENCE_NOT_FOUND" else 409
        raise ApiError(status_code, exc.code, str(exc)) from exc
    body = asdict(evidence)
    body["backing"]["source_fingerprint"] = evidence.backing.source_fingerprint
    body["evidence_fingerprint"] = evidence.evidence_fingerprint
    return RequestBoundEvidenceView.model_validate(_decimal_to_string(body))
