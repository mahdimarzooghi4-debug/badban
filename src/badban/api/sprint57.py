from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.api.sprint44 import ensure_individual_profile
from badban.api.sprint46 import SERVICE_ROLE_MATRIX, _service_scope_id
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import ApplicantServiceRequest
from badban.security.audit import append_audit
from badban.security.authorization import (
    SCOPE_SERVICE,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1", tags=["applicant-service-requests"])
ServiceCode = Literal["LOAN_GUARANTEE", "MONTHLY_PENSION", "POST_EXIT_SUPPORT"]
RequestStatus = Literal["RECEIVED"]


class ApplicantServiceRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: ServiceCode


class ApplicantServiceRequestView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    service_code: ServiceCode
    status: RequestStatus
    submitted_at: datetime


class ApplicantServiceRequestPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: datetime
    items: list[ApplicantServiceRequestView]
    limit: int
    offset: int


class AdminServiceRequestView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    participant_id: UUID
    service_code: ServiceCode
    status: RequestStatus
    submitted_at: datetime


class AdminServiceRequestPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: ServiceCode
    observed_at: datetime
    items: list[AdminServiceRequestView]
    limit: int
    offset: int


def _applicant_view(row: ApplicantServiceRequest) -> ApplicantServiceRequestView:
    return ApplicantServiceRequestView(
        id=row.id,
        service_code=row.service_code,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        submitted_at=row.submitted_at,
    )


def _admin_view(row: ApplicantServiceRequest) -> AdminServiceRequestView:
    return AdminServiceRequestView(
        id=row.id,
        participant_id=row.participant_id,
        service_code=row.service_code,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        submitted_at=row.submitted_at,
    )


async def _authorize_service_queue(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
    service_code: ServiceCode,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=SERVICE_ROLE_MATRIX[service_code],
            scope_type=SCOPE_SERVICE,
            scope_id=_service_scope_id(service_code),
            allow_global=False,
            action="APPLICANT_SERVICE_REQUEST_QUEUE_READ",
            target_type="ApplicantServiceRequestQueue",
            target_id=service_code,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Role grant for this service is required") from exc


@router.post(
    "/applicant/service-requests",
    response_model=ApplicantServiceRequestView,
    status_code=status.HTTP_201_CREATED,
)
async def submit_applicant_service_request(
    body: ApplicantServiceRequestCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ApplicantServiceRequestView:
    # Ensure the self profile from the verified OIDC claim; never accept a caller-supplied participant ID.
    await ensure_individual_profile(
        principal=principal,
        session=session,
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"applicant-service-request:{principal.identity_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        request_id = UUID(str(replay["id"]))
        existing = await session.get(ApplicantServiceRequest, request_id)
        if existing is None:
            raise ApiError(
                500,
                "APPLICANT_SERVICE_REQUEST_RECORD_MISSING",
                "Completed applicant service request was not found",
            )
        return _applicant_view(existing)

    if principal.national_id is None or not principal.national_id.strip():
        raise ApiError(
            403,
            "PARTICIPANT_LINK_UNAVAILABLE",
            "The authenticated account has no trusted participant reference",
        )
    participant_id = await session.scalar(
        select(ApplicantServiceRequest.participant_id)
        .where(ApplicantServiceRequest.created_by == principal.identity_id)
        .order_by(ApplicantServiceRequest.submitted_at.desc())
        .limit(1)
    )
    if participant_id is None:
        # The profile operation above is the authority for matching the verified claim.
        from badban.infrastructure.persistence.models import Participant

        participant_id = await session.scalar(
            select(Participant.id).where(
                Participant.external_reference == principal.national_id
            )
        )
    if participant_id is None:
        raise ApiError(
            404,
            "PARTICIPANT_RECORD_NOT_FOUND",
            "No Badban participant profile matches the authenticated account",
        )

    submitted_at = datetime.now(UTC)
    service_request = ApplicantServiceRequest(
        participant_id=participant_id,
        service_code=body.service_code,
        status="RECEIVED",
        submitted_at=submitted_at,
        created_by=principal.identity_id,
        correlation_id=correlation_id,
    )
    session.add(service_request)
    await session.flush()
    view = _applicant_view(service_request)
    append_audit(
        session,
        aggregate_type="ApplicantServiceRequest",
        aggregate_id=str(service_request.id),
        aggregate_version=None,
        action="APPLICANT_SERVICE_REQUEST_SUBMIT",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"service_code": body.service_code, "status": service_request.status},
    )
    response_payload = view.model_dump(mode="json")
    complete_idempotency(record, status_code=201, response_payload=response_payload)
    await session.commit()
    return view


@router.get("/applicant/service-requests", response_model=ApplicantServiceRequestPage)
async def list_applicant_service_requests(
    service_code: ServiceCode | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ApplicantServiceRequestPage:
    profile = await ensure_individual_profile(
        principal=principal,
        session=session,
        correlation_id=correlation_id,
    )
    filters = [ApplicantServiceRequest.participant_id == profile.participant_id]
    if service_code is not None:
        filters.append(ApplicantServiceRequest.service_code == service_code)
    rows = (
        await session.scalars(
            select(ApplicantServiceRequest)
            .where(*filters)
            .order_by(
                ApplicantServiceRequest.submitted_at.desc(),
                ApplicantServiceRequest.id,
            )
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="ApplicantServiceRequestQueue",
        aggregate_id=str(profile.participant_id),
        aggregate_version=None,
        action="APPLICANT_SERVICE_REQUESTS_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(rows), "limit": limit, "offset": offset},
    )
    await session.commit()
    return ApplicantServiceRequestPage(
        observed_at=datetime.now(UTC),
        items=[_applicant_view(row) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/admin/service-operations/{service_code}/applicant-requests",
    response_model=AdminServiceRequestPage,
)
async def list_admin_applicant_service_requests(
    service_code: ServiceCode,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AdminServiceRequestPage:
    await _authorize_service_queue(
        session,
        principal=principal,
        correlation_id=correlation_id,
        service_code=service_code,
    )
    rows = (
        await session.scalars(
            select(ApplicantServiceRequest)
            .where(ApplicantServiceRequest.service_code == service_code)
            .order_by(
                ApplicantServiceRequest.submitted_at,
                ApplicantServiceRequest.id,
            )
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="ApplicantServiceRequestQueue",
        aggregate_id=service_code,
        aggregate_version=None,
        action="APPLICANT_SERVICE_REQUEST_QUEUE_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(rows), "limit": limit, "offset": offset},
    )
    await session.commit()
    return AdminServiceRequestPage(
        service_code=service_code,
        observed_at=datetime.now(UTC),
        items=[_admin_view(row) for row in rows],
        limit=limit,
        offset=offset,
    )
