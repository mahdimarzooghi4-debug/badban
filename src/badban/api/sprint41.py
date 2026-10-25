from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import ServiceCatalogueVersion
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(tags=["service-catalogue"])
ServiceCode = Literal["LOAN_GUARANTEE", "MONTHLY_PENSION", "POST_EXIT_SUPPORT"]


class ServiceCatalogueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: ServiceCode
    version_number: int = Field(gt=0)
    display_name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    policy_version_reference: str = Field(min_length=1, max_length=200)
    policy_definition: dict[str, Any] = Field(min_length=1)
    max_duration_months: int | None = Field(default=None, ge=1, le=36)
    effective_from: datetime
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def validate_policy(self) -> ServiceCatalogueCreate:
        timestamps = [self.effective_from]
        if self.effective_to is not None:
            timestamps.append(self.effective_to)
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise ValueError("effective timestamps must be timezone-aware")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")
        if self.service_code == "POST_EXIT_SUPPORT" and self.max_duration_months is None:
            raise ValueError("post-exit support requires a policy-bounded duration")
        if self.service_code != "POST_EXIT_SUPPORT" and self.max_duration_months is not None:
            raise ValueError("max_duration_months applies only to post-exit support")
        required = {
            "LOAN_GUARANTEE": {"guarantee_policy_reference"},
            "MONTHLY_PENSION": {
                "eligibility_policy_reference",
                "amount_policy_reference",
                "period_definition_reference",
            },
            "POST_EXIT_SUPPORT": {
                "eligibility_policy_reference",
                "amount_policy_reference",
                "period_definition_reference",
            },
        }[self.service_code]
        if any(
            not isinstance(self.policy_definition.get(key), str)
            or not self.policy_definition[key].strip()
            for key in required
        ):
            raise ValueError("policy_definition is missing required policy references")
        return self


class ServiceCatalogueView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_code: str
    version_number: int
    display_name: str
    description: str
    policy_version_reference: str
    policy_definition: dict[str, Any]
    max_duration_months: int | None
    lifecycle_status: str
    effective_from: datetime
    effective_to: datetime | None
    created_by: UUID
    version: int
    created_at: datetime


class ServiceCatalogueList(BaseModel):
    items: list[ServiceCatalogueView]


async def _authorize_admin(
    session: AsyncSession,
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
            target_type="ServiceCatalogueVersion",
            target_id="GLOBAL",
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


def _view(record: ServiceCatalogueVersion) -> ServiceCatalogueView:
    return ServiceCatalogueView.model_validate(record)


@router.post(
    "/api/v1/admin/service-catalogue",
    response_model=ServiceCatalogueView,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_version(
    body: ServiceCatalogueCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ServiceCatalogueView:
    await _authorize_admin(
        session, principal, correlation_id, "SERVICE_CATALOGUE_VERSION_CREATE"
    )
    idem, replay = await acquire_idempotency(
        session,
        scope="service-catalogue:create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return ServiceCatalogueView.model_validate(replay)

    existing = await session.scalar(
        select(ServiceCatalogueVersion).where(
            ServiceCatalogueVersion.service_code == body.service_code,
            ServiceCatalogueVersion.version_number == body.version_number,
        )
    )
    if existing is not None:
        raise ApiError(409, "SERVICE_VERSION_EXISTS", "Service catalogue version already exists")

    record = ServiceCatalogueVersion(
        service_code=body.service_code,
        version_number=body.version_number,
        display_name=body.display_name,
        description=body.description,
        policy_version_reference=body.policy_version_reference,
        policy_definition=body.policy_definition,
        max_duration_months=body.max_duration_months,
        lifecycle_status="DRAFT",
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        created_by=principal.identity_id,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "SERVICE_VERSION_EXISTS", "Service catalogue version already exists") from exc

    view = _view(record)
    append_audit(
        session,
        aggregate_type="ServiceCatalogueVersion",
        aggregate_id=str(record.id),
        aggregate_version=record.version,
        action="SERVICE_CATALOGUE_VERSION_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCEEDED",
        reason_code=None,
        scope={"service_code": record.service_code, "lifecycle_status": "DRAFT"},
        evidence_references=[record.policy_version_reference],
    )
    await complete_idempotency(session, idem, view.model_dump(mode="json"))
    await session.commit()
    return view


@router.get(
    "/api/v1/admin/service-catalogue",
    response_model=ServiceCatalogueList,
)
async def list_admin_service_versions(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ServiceCatalogueList:
    await _authorize_admin(
        session, principal, correlation_id, "SERVICE_CATALOGUE_ADMIN_READ"
    )
    result = await session.scalars(
        select(ServiceCatalogueVersion).order_by(
            ServiceCatalogueVersion.service_code,
            ServiceCatalogueVersion.version_number.desc(),
        )
    )
    return ServiceCatalogueList(items=[_view(record) for record in result.all()])


@router.get("/api/v1/service-catalogue", response_model=ServiceCatalogueList)
async def list_applicant_service_catalogue(
    _: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ServiceCatalogueList:
    now = datetime.now(UTC)
    result = await session.scalars(
        select(ServiceCatalogueVersion)
        .where(
            ServiceCatalogueVersion.lifecycle_status == "ACTIVE",
            ServiceCatalogueVersion.effective_from <= now,
            (ServiceCatalogueVersion.effective_to.is_(None))
            | (ServiceCatalogueVersion.effective_to > now),
        )
        .order_by(ServiceCatalogueVersion.service_code)
    )
    return ServiceCatalogueList(items=[_view(record) for record in result.all()])
