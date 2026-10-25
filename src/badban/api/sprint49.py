from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import (
    CreditProductVersion,
    CreditProvider,
    ExternalLoanMirror,
    GuaranteeCase,
    Identity,
    RoleGrant,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    HUMAN_IDENTITY_TYPES,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LENDER_OPERATOR,
    SCOPE_GLOBAL,
    SCOPE_PROVIDER,
    AuthorizationDenied,
    Principal,
    authorize,
)

admin_router = APIRouter(prefix="/api/v1/admin/lender-access", tags=["admin-lender-access"])
lender_router = APIRouter(prefix="/api/v1/lender", tags=["lender-workspace"])


class LenderRoleGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: UUID
    provider_id: UUID
    valid_from: datetime
    valid_until: datetime | None = None
    reason_reference: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_window(self) -> LenderRoleGrantCreate:
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise ValueError("valid_from must be timezone-aware")
        if self.valid_until is not None:
            if self.valid_until.tzinfo is None or self.valid_until.utcoffset() is None:
                raise ValueError("valid_until must be timezone-aware")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be later than valid_from")
        return self


class LenderRoleGrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_reference: str = Field(min_length=1, max_length=255)


class LenderRoleGrantView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identity_id: UUID
    role_code: str
    scope_type: str
    scope_id: UUID | None
    valid_from: datetime
    valid_until: datetime | None
    status: str
    granted_by: UUID | None
    reason_ref: str | None
    version: int


class LenderRoleGrantPage(BaseModel):
    items: list[LenderRoleGrantView]
    status: str
    limit: int
    offset: int


class LenderProviderView(BaseModel):
    provider_id: UUID
    provider_code: str
    display_name: str


class LenderProvidersPage(BaseModel):
    items: list[LenderProviderView]
    limit: int
    offset: int


class LenderGuaranteeView(BaseModel):
    guarantee_case_id: UUID
    external_guarantee_reference: str | None
    case_state: str
    requested_principal: str
    reserved_guarantee_amount: str | None
    issued_guarantee_amount: str | None
    current_guarantee_exposure: str
    guarantee_mode: str
    reservation_expires_at: datetime | None
    currency: str
    external_loan_id: str | None
    loan_state: str | None
    original_principal: str | None
    outstanding_principal: str | None
    loan_currency: str | None
    disbursed_at: datetime | None
    settled_at: datetime | None
    delinquency_state: str | None
    last_synced_at: datetime | None


class LenderGuaranteesPage(BaseModel):
    provider_id: UUID
    items: list[LenderGuaranteeView]
    limit: int
    offset: int


async def _authorize_governance(
    session: AsyncSession,
    principal: Principal,
    correlation_id: UUID,
    action: str,
    target_id: str,
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
            target_type="LenderRoleGrant",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


@admin_router.get("/grants", response_model=LenderRoleGrantPage)
async def list_lender_role_grants(
    grant_status: Literal["REQUESTED", "ACTIVE", "REVOKED"] = Query(
        default="REQUESTED", alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderRoleGrantPage:
    await _authorize_governance(
        session, principal, correlation_id, "LENDER_ROLE_GRANT_LIST", grant_status
    )
    grants = (
        await session.scalars(
            select(RoleGrant)
            .where(
                RoleGrant.role_code == ROLE_LENDER_OPERATOR,
                RoleGrant.scope_type == SCOPE_PROVIDER,
                RoleGrant.status == grant_status,
            )
            .order_by(RoleGrant.created_at.desc(), RoleGrant.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="LenderRoleGrantQueue",
        aggregate_id=grant_status,
        aggregate_version=None,
        action="LENDER_ROLE_GRANT_LIST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={
            "status": grant_status,
            "returned_count": len(grants),
            "limit": limit,
            "offset": offset,
        },
    )
    await session.commit()
    return LenderRoleGrantPage(
        items=[LenderRoleGrantView.model_validate(grant) for grant in grants],
        status=grant_status,
        limit=limit,
        offset=offset,
    )


@admin_router.post(
    "/grants",
    response_model=LenderRoleGrantView,
    status_code=status.HTTP_201_CREATED,
)
async def request_lender_role_grant(
    body: LenderRoleGrantCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderRoleGrantView:
    await _authorize_governance(
        session,
        principal,
        correlation_id,
        "LENDER_ROLE_GRANT_REQUEST",
        str(body.identity_id),
    )
    identity = await session.get(Identity, body.identity_id)
    if (
        identity is None
        or identity.status != "ACTIVE"
        or identity.identity_type not in HUMAN_IDENTITY_TYPES
    ):
        raise ApiError(404, "HUMAN_IDENTITY_NOT_FOUND", "Active human identity was not found")
    provider = await session.get(CreditProvider, body.provider_id)
    if provider is None or provider.lifecycle_status != "ACTIVE":
        raise ApiError(404, "ACTIVE_LENDER_NOT_FOUND", "Active lender provider was not found")
    existing = await session.scalar(
        select(RoleGrant.id).where(
            RoleGrant.identity_id == body.identity_id,
            RoleGrant.role_code == ROLE_LENDER_OPERATOR,
            RoleGrant.scope_type == SCOPE_PROVIDER,
            RoleGrant.scope_id == body.provider_id,
            RoleGrant.status.in_(["REQUESTED", "ACTIVE"]),
        )
    )
    if existing is not None:
        raise ApiError(409, "LENDER_ROLE_GRANT_EXISTS", "A pending or active grant already exists")
    grant = RoleGrant(
        identity_id=body.identity_id,
        role_code=ROLE_LENDER_OPERATOR,
        scope_type=SCOPE_PROVIDER,
        scope_id=body.provider_id,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        status="REQUESTED",
        granted_by=principal.identity_id,
        reason_ref=body.reason_reference,
    )
    session.add(grant)
    await session.flush()
    append_audit(
        session,
        aggregate_type="LenderRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="LENDER_ROLE_GRANT_REQUEST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"provider_id": str(body.provider_id), "identity_id": str(body.identity_id)},
    )
    await session.commit()
    return LenderRoleGrantView.model_validate(grant)


@admin_router.post("/grants/{grant_id}/approve", response_model=LenderRoleGrantView)
async def approve_lender_role_grant(
    grant_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderRoleGrantView:
    await _authorize_governance(
        session,
        principal,
        correlation_id,
        "LENDER_ROLE_GRANT_APPROVE",
        str(grant_id),
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    if (
        grant is None
        or grant.role_code != ROLE_LENDER_OPERATOR
        or grant.scope_type != SCOPE_PROVIDER
        or grant.scope_id is None
    ):
        raise ApiError(404, "LENDER_ROLE_GRANT_NOT_FOUND", "Lender role grant was not found")
    if grant.status != "REQUESTED":
        raise ApiError(
            409, "LENDER_ROLE_GRANT_NOT_REQUESTED", "Only a requested grant can be approved"
        )
    if grant.granted_by == principal.identity_id:
        raise ApiError(
            403, "MAKER_CHECKER_REQUIRED", "The requester cannot approve the lender grant"
        )
    target_identity = await session.get(Identity, grant.identity_id)
    if (
        target_identity is None
        or target_identity.status != "ACTIVE"
        or target_identity.identity_type not in HUMAN_IDENTITY_TYPES
    ):
        raise ApiError(409, "HUMAN_IDENTITY_UNAVAILABLE", "The lender identity is no longer active")
    provider = await session.get(CreditProvider, grant.scope_id)
    if provider is None or provider.lifecycle_status != "ACTIVE":
        raise ApiError(409, "ACTIVE_LENDER_UNAVAILABLE", "The lender provider is no longer active")
    grant.status = "ACTIVE"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="LenderRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="LENDER_ROLE_GRANT_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=grant.reason_ref,
        scope={"provider_id": str(grant.scope_id), "role_code": grant.role_code},
    )
    await session.commit()
    return LenderRoleGrantView.model_validate(grant)


@admin_router.post("/grants/{grant_id}/revoke", response_model=LenderRoleGrantView)
async def revoke_lender_role_grant(
    grant_id: UUID,
    body: LenderRoleGrantRevoke,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderRoleGrantView:
    await _authorize_governance(
        session,
        principal,
        correlation_id,
        "LENDER_ROLE_GRANT_REVOKE",
        str(grant_id),
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    if (
        grant is None
        or grant.role_code != ROLE_LENDER_OPERATOR
        or grant.scope_type != SCOPE_PROVIDER
    ):
        raise ApiError(404, "LENDER_ROLE_GRANT_NOT_FOUND", "Lender role grant was not found")
    if grant.status not in {"REQUESTED", "ACTIVE"}:
        raise ApiError(
            409, "LENDER_ROLE_GRANT_NOT_REVOCABLE", "Grant is no longer pending or active"
        )
    grant.status = "REVOKED"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="LenderRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="LENDER_ROLE_GRANT_REVOKE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"provider_id": str(grant.scope_id), "role_code": grant.role_code},
    )
    await session.commit()
    return LenderRoleGrantView.model_validate(grant)


@lender_router.get("/providers", response_model=LenderProvidersPage)
async def list_lender_providers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderProvidersPage:
    now = datetime.now(UTC)
    if principal.identity_type not in HUMAN_IDENTITY_TYPES:
        append_audit(
            session,
            aggregate_type="LenderWorkspace",
            aggregate_id=str(principal.identity_id),
            aggregate_version=None,
            action="LENDER_PROVIDER_LIST_READ",
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
            outcome="DENIED",
            reason_code="AUTHORIZATION_DENIED",
            scope={"scope_type": SCOPE_PROVIDER},
        )
        await session.commit()
        raise ApiError(403, "AUTHORIZATION_DENIED", "Human lender operator identity required")
    providers = (
        await session.scalars(
            select(CreditProvider)
            .join(RoleGrant, RoleGrant.scope_id == CreditProvider.id)
            .where(
                RoleGrant.identity_id == principal.identity_id,
                RoleGrant.role_code == ROLE_LENDER_OPERATOR,
                RoleGrant.scope_type == SCOPE_PROVIDER,
                RoleGrant.status == "ACTIVE",
                RoleGrant.valid_from <= now,
                (RoleGrant.valid_until.is_(None) | (RoleGrant.valid_until > now)),
                CreditProvider.lifecycle_status == "ACTIVE",
            )
            .distinct()
            .order_by(CreditProvider.display_name, CreditProvider.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="LenderWorkspace",
        aggregate_id=str(principal.identity_id),
        aggregate_version=None,
        action="LENDER_PROVIDER_LIST_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(providers), "limit": limit, "offset": offset},
    )
    await session.commit()
    return LenderProvidersPage(
        items=[
            LenderProviderView(
                provider_id=provider.id,
                provider_code=provider.provider_code,
                display_name=provider.display_name,
            )
            for provider in providers
        ],
        limit=limit,
        offset=offset,
    )


@lender_router.get(
    "/providers/{provider_id}/guarantees",
    response_model=LenderGuaranteesPage,
)
async def list_lender_guarantees(
    provider_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderGuaranteesPage:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_LENDER_OPERATOR},
            scope_type=SCOPE_PROVIDER,
            scope_id=provider_id,
            allow_global=False,
            action="LENDER_GUARANTEES_READ",
            target_type="LenderProvider",
            target_id=str(provider_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Provider-scoped lender access is required") from exc

    provider = await session.get(CreditProvider, provider_id)
    if provider is None or provider.lifecycle_status != "ACTIVE":
        raise ApiError(404, "ACTIVE_LENDER_NOT_FOUND", "Active lender provider was not found")
    rows = (
        await session.execute(
            select(GuaranteeCase, CreditProductVersion, ExternalLoanMirror)
            .join(
                CreditProductVersion,
                CreditProductVersion.id == GuaranteeCase.credit_product_version_id,
            )
            .outerjoin(
                ExternalLoanMirror,
                and_(
                    ExternalLoanMirror.guarantee_case_id == GuaranteeCase.id,
                    ExternalLoanMirror.provider_id == provider_id,
                ),
            )
            .where(
                GuaranteeCase.provider_id == provider_id,
                CreditProductVersion.provider_id == provider_id,
            )
            .order_by(GuaranteeCase.created_at.desc(), GuaranteeCase.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="LenderProvider",
        aggregate_id=str(provider_id),
        aggregate_version=None,
        action="LENDER_GUARANTEES_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(rows), "limit": limit, "offset": offset},
    )
    await session.commit()
    return LenderGuaranteesPage(
        provider_id=provider_id,
        items=[
            LenderGuaranteeView(
                guarantee_case_id=case.id,
                external_guarantee_reference=case.legal_guarantee_external_id,
                case_state=case.state,
                requested_principal=_amount(case.requested_principal),
                reserved_guarantee_amount=_optional_amount(case.reserved_guarantee_amount),
                issued_guarantee_amount=_optional_amount(case.issued_guarantee_amount),
                current_guarantee_exposure=_amount(case.current_guarantee_exposure),
                guarantee_mode=case.guarantee_mode,
                reservation_expires_at=case.reservation_expires_at,
                currency=product.currency,
                external_loan_id=loan.external_loan_id if loan else None,
                loan_state=loan.state if loan else None,
                original_principal=_optional_amount(loan.original_principal) if loan else None,
                outstanding_principal=_optional_amount(loan.outstanding_principal)
                if loan
                else None,
                loan_currency=loan.currency if loan else None,
                disbursed_at=loan.disbursed_at if loan else None,
                settled_at=loan.settled_at if loan else None,
                delinquency_state=loan.delinquency_state if loan else None,
                last_synced_at=loan.last_synced_at if loan else None,
            )
            for case, product, loan in rows
        ],
        limit=limit,
        offset=offset,
    )


def _amount(value: Decimal) -> str:
    return format(value, "f")


def _optional_amount(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None
