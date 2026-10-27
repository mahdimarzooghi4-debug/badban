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
from badban.infrastructure.persistence.models import (
    AssetType,
    ExternalEvidenceSource,
    ExternalEvidenceSourceLifecycleReview,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/external-evidence-sources", tags=["external-evidence-sources"])
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
        raise ApiError(
            409, "SOURCE_ALREADY_REGISTERED", "Source key is already registered"
        ) from exc
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


SourceLifecycleAction = Literal["ACTIVATE", "SUSPEND"]
SourceLifecycleReviewStatus = Literal["REQUESTED", "APPROVED", "REJECTED"]


class SourceLifecycleReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: SourceLifecycleAction
    reason_reference: str = Field(min_length=1, max_length=255)


class SourceLifecycleReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_reference: str = Field(min_length=1, max_length=255)


class SourceLifecycleReviewView(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    source_id: UUID
    requested_action: SourceLifecycleAction
    status: SourceLifecycleReviewStatus
    reason_reference: str
    requested_by: UUID
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_reason_reference: str | None
    created_at: datetime


class SourceLifecycleReviewPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    items: list[SourceLifecycleReviewView]
    limit: int
    offset: int


def _source_lifecycle_review_view(
    review: ExternalEvidenceSourceLifecycleReview,
) -> SourceLifecycleReviewView:
    return SourceLifecycleReviewView.model_validate(review)


@router.post(
    "/{source_id}/lifecycle-reviews",
    response_model=SourceLifecycleReviewView,
    status_code=status.HTTP_201_CREATED,
)
async def request_source_lifecycle_review(
    source_id: UUID,
    body: SourceLifecycleReviewCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> SourceLifecycleReviewView:
    await _authorize_registry(
        session,
        principal=principal,
        correlation_id=correlation_id,
        action="EXTERNAL_EVIDENCE_SOURCE_LIFECYCLE_REQUEST",
    )
    source = await session.scalar(
        select(ExternalEvidenceSource)
        .where(ExternalEvidenceSource.id == source_id)
        .with_for_update()
    )
    if source is None:
        raise ApiError(404, "EXTERNAL_EVIDENCE_SOURCE_NOT_FOUND", "Evidence source was not found")

    allowed_from = {"DRAFT", "SUSPENDED"} if body.action == "ACTIVATE" else {"ACTIVE"}
    if source.lifecycle_status not in allowed_from:
        raise ApiError(
            409,
            "EXTERNAL_EVIDENCE_SOURCE_INVALID_TRANSITION",
            "The requested action is not valid for the current source state",
        )

    payload = {"source_id": str(source_id), **body.model_dump(mode="json")}
    idempotency, replay = await acquire_idempotency(
        session,
        scope="external-evidence-source:lifecycle-request",
        key=idempotency_key,
        payload=payload,
    )
    if replay is not None:
        return SourceLifecycleReviewView.model_validate(replay)

    pending = await session.scalar(
        select(ExternalEvidenceSourceLifecycleReview.id).where(
            ExternalEvidenceSourceLifecycleReview.source_id == source_id,
            ExternalEvidenceSourceLifecycleReview.status == "REQUESTED",
        )
    )
    if pending is not None:
        raise ApiError(
            409,
            "EXTERNAL_EVIDENCE_SOURCE_REVIEW_PENDING",
            "A lifecycle review is already pending for this source",
        )

    review = ExternalEvidenceSourceLifecycleReview(
        source_id=source.id,
        requested_action=body.action,
        status="REQUESTED",
        reason_reference=body.reason_reference,
        requested_by=principal.identity_id,
    )
    session.add(review)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            409,
            "EXTERNAL_EVIDENCE_SOURCE_REVIEW_PENDING",
            "A lifecycle review is already pending for this source",
        ) from exc

    view = _source_lifecycle_review_view(review)
    append_audit(
        session,
        aggregate_type="ExternalEvidenceSourceLifecycleReview",
        aggregate_id=str(review.id),
        aggregate_version=None,
        action="EXTERNAL_EVIDENCE_SOURCE_LIFECYCLE_REQUEST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={
            "source_id": str(source.id),
            "source_key": source.source_key,
            "requested_action": body.action,
            "current_status": source.lifecycle_status,
        },
        new_state=view.model_dump(mode="json"),
    )
    complete_idempotency(
        idempotency,
        status_code=201,
        response_payload=view.model_dump(mode="json"),
    )
    await session.commit()
    return view


@router.get(
    "/{source_id}/lifecycle-reviews",
    response_model=SourceLifecycleReviewPage,
)
async def list_source_lifecycle_reviews(
    source_id: UUID,
    review_status: SourceLifecycleReviewStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SourceLifecycleReviewPage:
    await _authorize_registry(
        session,
        principal=principal,
        correlation_id=correlation_id,
        action="EXTERNAL_EVIDENCE_SOURCE_LIFECYCLE_LIST",
    )
    source_exists = await session.scalar(
        select(ExternalEvidenceSource.id).where(ExternalEvidenceSource.id == source_id)
    )
    if source_exists is None:
        raise ApiError(404, "EXTERNAL_EVIDENCE_SOURCE_NOT_FOUND", "Evidence source was not found")

    filters = [ExternalEvidenceSourceLifecycleReview.source_id == source_id]
    if review_status is not None:
        filters.append(ExternalEvidenceSourceLifecycleReview.status == review_status)
    rows = (
        await session.scalars(
            select(ExternalEvidenceSourceLifecycleReview)
            .where(*filters)
            .order_by(
                ExternalEvidenceSourceLifecycleReview.created_at.desc(),
                ExternalEvidenceSourceLifecycleReview.id,
            )
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="ExternalEvidenceSourceLifecycleReviewQueue",
        aggregate_id=str(source_id),
        aggregate_version=None,
        action="EXTERNAL_EVIDENCE_SOURCE_LIFECYCLE_LIST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(rows), "limit": limit, "offset": offset},
    )
    await session.commit()
    return SourceLifecycleReviewPage(
        source_id=source_id,
        items=[_source_lifecycle_review_view(row) for row in rows],
        limit=limit,
        offset=offset,
    )


async def _decide_source_lifecycle_review(
    *,
    source_id: UUID,
    review_id: UUID,
    body: SourceLifecycleReviewDecision,
    principal: Principal,
    session: AsyncSession,
    correlation_id: UUID,
    decision: Literal["APPROVED", "REJECTED"],
) -> SourceLifecycleReviewView:
    await _authorize_registry(
        session,
        principal=principal,
        correlation_id=correlation_id,
        action=f"EXTERNAL_EVIDENCE_SOURCE_LIFECYCLE_{decision}",
    )
    review = await session.scalar(
        select(ExternalEvidenceSourceLifecycleReview)
        .where(
            ExternalEvidenceSourceLifecycleReview.id == review_id,
            ExternalEvidenceSourceLifecycleReview.source_id == source_id,
        )
        .with_for_update()
    )
    if review is None:
        raise ApiError(
            404,
            "EXTERNAL_EVIDENCE_SOURCE_REVIEW_NOT_FOUND",
            "Evidence source lifecycle review was not found",
        )
    if review.status != "REQUESTED":
        raise ApiError(
            409,
            "EXTERNAL_EVIDENCE_SOURCE_REVIEW_NOT_PENDING",
            "Only a pending lifecycle review can be decided",
        )
    if review.requested_by == principal.identity_id:
        raise ApiError(
            403,
            "MAKER_CHECKER_REQUIRED",
            "The requester cannot decide the evidence source lifecycle review",
        )

    source = await session.scalar(
        select(ExternalEvidenceSource)
        .where(ExternalEvidenceSource.id == source_id)
        .with_for_update()
    )
    if source is None:
        raise ApiError(404, "EXTERNAL_EVIDENCE_SOURCE_NOT_FOUND", "Evidence source was not found")
    if decision == "APPROVED":
        allowed_from = {"DRAFT", "SUSPENDED"} if review.requested_action == "ACTIVATE" else {"ACTIVE"}
        if source.lifecycle_status not in allowed_from:
            raise ApiError(
                409,
                "EXTERNAL_EVIDENCE_SOURCE_INVALID_TRANSITION",
                "The source state changed before this review could be approved",
            )
        source.lifecycle_status = "ACTIVE" if review.requested_action == "ACTIVATE" else "SUSPENDED"

    review.status = decision
    review.reviewed_by = principal.identity_id
    review.reviewed_at = datetime.now(UTC)
    review.review_reason_reference = body.reason_reference
    view = _source_lifecycle_review_view(review)
    append_audit(
        session,
        aggregate_type="ExternalEvidenceSourceLifecycleReview",
        aggregate_id=str(review.id),
        aggregate_version=None,
        action=f"EXTERNAL_EVIDENCE_SOURCE_LIFECYCLE_{decision}",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={
            "source_id": str(source.id),
            "source_key": source.source_key,
            "requested_action": review.requested_action,
            "source_status": source.lifecycle_status,
        },
        previous_state={"review_status": "REQUESTED"},
        new_state={
            **view.model_dump(mode="json"),
            "source_lifecycle_status": source.lifecycle_status,
        },
    )
    await session.commit()
    return view


@router.post(
    "/{source_id}/lifecycle-reviews/{review_id}/approve",
    response_model=SourceLifecycleReviewView,
)
async def approve_source_lifecycle_review(
    source_id: UUID,
    review_id: UUID,
    body: SourceLifecycleReviewDecision,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SourceLifecycleReviewView:
    return await _decide_source_lifecycle_review(
        source_id=source_id,
        review_id=review_id,
        body=body,
        principal=principal,
        session=session,
        correlation_id=correlation_id,
        decision="APPROVED",
    )


@router.post(
    "/{source_id}/lifecycle-reviews/{review_id}/reject",
    response_model=SourceLifecycleReviewView,
)
async def reject_source_lifecycle_review(
    source_id: UUID,
    review_id: UUID,
    body: SourceLifecycleReviewDecision,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SourceLifecycleReviewView:
    return await _decide_source_lifecycle_review(
        source_id=source_id,
        review_id=review_id,
        body=body,
        principal=principal,
        session=session,
        correlation_id=correlation_id,
        decision="REJECTED",
    )
