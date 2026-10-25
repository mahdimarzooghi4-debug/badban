from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import AssetType, ExternalEvidenceSource
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/evidence-sources", tags=["external-evidence-sources"])
EvidencePurpose = Literal["VALUATION", "RESTRICTION", "ENCUMBRANCE"]


class SourceRegistrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_type_id: UUID
    evidence_purpose: EvidencePurpose
    source_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=255)
    adapter_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    contract_version: str = Field(min_length=1, max_length=80)
    schema_version: str = Field(min_length=1, max_length=80)
    configuration_reference: str | None = Field(
        default=None,
        min_length=12,
        max_length=255,
        pattern=r"^secret-ref:[a-z0-9][a-z0-9/_-]{0,230}$",
    )


class SourceRegistrationView(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    asset_type_id: UUID
    evidence_purpose: EvidencePurpose
    source_key: str
    display_name: str
    adapter_key: str
    contract_version: str
    schema_version: str
    configuration_reference_configured: bool
    lifecycle_status: Literal["DRAFT", "ACTIVE", "SUSPENDED"]
    version: int
    created_by: UUID
    created_at: datetime


class SourceRegistrationPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: datetime
    items: list[SourceRegistrationView]


def _view(source: ExternalEvidenceSource) -> SourceRegistrationView:
    return SourceRegistrationView(
        id=source.id,
        asset_type_id=source.asset_type_id,
        evidence_purpose=source.evidence_purpose,  # type: ignore[arg-type]
        source_key=source.source_key,
        display_name=source.display_name,
        adapter_key=source.adapter_key,
        contract_version=source.contract_version,
        schema_version=source.schema_version,
        configuration_reference_configured=source.configuration_reference is not None,
        lifecycle_status=source.lifecycle_status,  # type: ignore[arg-type]
        version=source.version,
        created_by=source.created_by,
        created_at=source.created_at,
    )


async def _authorize_registry(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
    action: str,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_GOVERNANCE_APPROVER},
            scope_type=SCOPE_GLOBAL,
            scope_id=None,
            allow_global=False,
            action=action,
            target_type="ExternalEvidenceSource",
            target_id="GLOBAL",
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


@router.post("", response_model=SourceRegistrationView, status_code=status.HTTP_201_CREATED)
async def register_source(
    body: SourceRegistrationCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> SourceRegistrationView:
    await _authorize_registry(
        session,
        principal=principal,
        correlation_id=correlation_id,
        action="EXTERNAL_EVIDENCE_SOURCE_REGISTER",
    )
    asset_type = await session.get(AssetType, body.asset_type_id)
    if asset_type is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset Type was not found")

    record, replay = await acquire_idempotency(
        session,
        scope="external-evidence-source:register",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return SourceRegistrationView.model_validate(replay)

    existing = await session.scalar(
        select(ExternalEvidenceSource).where(
            ExternalEvidenceSource.asset_type_id == body.asset_type_id,
            ExternalEvidenceSource.evidence_purpose == body.evidence_purpose,
            ExternalEvidenceSource.source_key == body.source_key,
            ExternalEvidenceSource.version == 1,
        )
    )
    if existing is not None:
        raise ApiError(409, "SOURCE_ALREADY_REGISTERED", "Source key is already registered")

    source = ExternalEvidenceSource(
        asset_type_id=body.asset_type_id,
        evidence_purpose=body.evidence_purpose,
        source_key=body.source_key,
        display_name=body.display_name,
        adapter_key=body.adapter_key,
        contract_version=body.contract_version,
        schema_version=body.schema_version,
        configuration_reference=body.configuration_reference,
        lifecycle_status="DRAFT",
        created_by=principal.identity_id,
    )
    session.add(source)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "SOURCE_ALREADY_REGISTERED", "Source key is already registered") from exc
    view = _view(source)
    append_audit(
        session,
        aggregate_type="ExternalEvidenceSource",
        aggregate_id=str(source.id),
        aggregate_version=source.version,
        action="EXTERNAL_EVIDENCE_SOURCE_REGISTER",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=view.model_dump(mode="json"),
        evidence_reference=None,
        scope={"scope_type": SCOPE_GLOBAL},
    )
    complete_idempotency(record, status_code=201, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.get("", response_model=SourceRegistrationPage)
async def list_sources(
    asset_type_id: UUID | None = None,
    evidence_purpose: EvidencePurpose | None = Query(default=None),
    lifecycle_status: Literal["DRAFT", "ACTIVE", "SUSPENDED"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SourceRegistrationPage:
    await _authorize_registry(
        session,
        principal=principal,
        correlation_id=correlation_id,
        action="EXTERNAL_EVIDENCE_SOURCE_READ",
    )
    filters = []
    if asset_type_id is not None:
        filters.append(ExternalEvidenceSource.asset_type_id == asset_type_id)
    if evidence_purpose is not None:
        filters.append(ExternalEvidenceSource.evidence_purpose == evidence_purpose)
    if lifecycle_status is not None:
        filters.append(ExternalEvidenceSource.lifecycle_status == lifecycle_status)
    rows = (
        await session.scalars(
            select(ExternalEvidenceSource)
            .where(*filters)
            .order_by(ExternalEvidenceSource.created_at, ExternalEvidenceSource.id)
            .limit(limit)
        )
    ).all()
    return SourceRegistrationPage(
        observed_at=datetime.now(UTC),
        items=[_view(row) for row in rows],
    )
