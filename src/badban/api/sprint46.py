from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import (
    ExternalLoanMirror,
    GuaranteeCase,
    Identity,
    MonthlyPensionEntitlement,
    Participant,
    ParticipationEpisode,
    PostExitSupportCase,
    PostExitSupportEntitlement,
    RoleGrant,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    HUMAN_IDENTITY_TYPES,
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_OPERATIONS,
    ROLE_RISK,
    SCOPE_GLOBAL,
    SCOPE_SERVICE,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/admin/service-operations", tags=["admin-service-operations"])
ServiceCode = Literal["LOAN_GUARANTEE", "MONTHLY_PENSION", "POST_EXIT_SUPPORT"]
RoleCode = Literal[
    "OPERATIONS",
    "RISK",
    "FINANCE_RECONCILIATION",
    "LEGAL_COMPLIANCE",
    "GOVERNANCE_APPROVER",
    "AUDITOR",
]

SERVICE_ROLE_MATRIX: dict[str, set[str]] = {
    "LOAN_GUARANTEE": {
        ROLE_OPERATIONS,
        ROLE_RISK,
        ROLE_LEGAL_COMPLIANCE,
        ROLE_GOVERNANCE_APPROVER,
        ROLE_AUDITOR,
    },
    "MONTHLY_PENSION": {
        ROLE_OPERATIONS,
        ROLE_FINANCE_RECONCILIATION,
        ROLE_GOVERNANCE_APPROVER,
        ROLE_AUDITOR,
    },
    "POST_EXIT_SUPPORT": {
        ROLE_OPERATIONS,
        ROLE_FINANCE_RECONCILIATION,
        ROLE_GOVERNANCE_APPROVER,
        ROLE_AUDITOR,
    },
}


def _service_scope_id(service_code: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"badban:service-scope:{service_code}")


def _service_code_for_scope(scope_id: UUID | None) -> str | None:
    if scope_id is None:
        return None
    return next((code for code in SERVICE_ROLE_MATRIX if _service_scope_id(code) == scope_id), None)


class ServiceRoleGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: UUID
    service_code: ServiceCode
    role_code: RoleCode
    valid_from: datetime
    valid_until: datetime | None = None
    reason_reference: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_window(self) -> ServiceRoleGrantCreate:
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise ValueError("valid_from must be timezone-aware")
        if self.valid_until is not None:
            if self.valid_until.tzinfo is None or self.valid_until.utcoffset() is None:
                raise ValueError("valid_until must be timezone-aware")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be later than valid_from")
        return self


class ServiceRoleGrantView(BaseModel):
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


class ServiceWorkQueue(BaseModel):
    service_code: ServiceCode
    items: list[dict[str, Any]]


async def _authorize_global_governance(
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
            target_type="ServiceRoleGrant",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


async def _authorize_service_read(
    session: AsyncSession,
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
            action="SERVICE_OPERATIONS_READ",
            target_type="ServiceOperations",
            target_id=service_code,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Role grant for this service is required") from exc


@router.post("/grants", response_model=ServiceRoleGrantView, status_code=status.HTTP_201_CREATED)
async def request_service_role_grant(
    body: ServiceRoleGrantCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ServiceRoleGrantView:
    await _authorize_global_governance(
        session, principal, correlation_id, "SERVICE_ROLE_GRANT_REQUEST", str(body.identity_id)
    )
    if body.role_code not in SERVICE_ROLE_MATRIX[body.service_code]:
        raise ApiError(422, "ROLE_NOT_ALLOWED_FOR_SERVICE", "Role is not valid for this service")
    target_identity = await session.get(Identity, body.identity_id)
    if target_identity is None or target_identity.status != "ACTIVE":
        raise ApiError(404, "IDENTITY_NOT_FOUND", "Identity was not found")
    if target_identity.identity_type not in HUMAN_IDENTITY_TYPES:
        raise ApiError(
            422, "HUMAN_IDENTITY_REQUIRED", "Service role grants require a human identity"
        )
    existing = await session.scalar(
        select(RoleGrant.id).where(
            RoleGrant.identity_id == body.identity_id,
            RoleGrant.role_code == body.role_code,
            RoleGrant.scope_type == SCOPE_SERVICE,
            RoleGrant.scope_id == _service_scope_id(body.service_code),
            RoleGrant.status.in_(["REQUESTED", "ACTIVE"]),
        )
    )
    if existing is not None:
        raise ApiError(409, "SERVICE_ROLE_GRANT_EXISTS", "A pending or active grant already exists")
    grant = RoleGrant(
        identity_id=body.identity_id,
        role_code=body.role_code,
        scope_type=SCOPE_SERVICE,
        scope_id=_service_scope_id(body.service_code),
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
        aggregate_type="ServiceRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SERVICE_ROLE_GRANT_REQUEST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"service_code": body.service_code, "role_code": body.role_code},
    )
    await session.commit()
    return ServiceRoleGrantView.model_validate(grant)


@router.post("/grants/{grant_id}/approve", response_model=ServiceRoleGrantView)
async def approve_service_role_grant(
    grant_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ServiceRoleGrantView:
    await _authorize_global_governance(
        session, principal, correlation_id, "SERVICE_ROLE_GRANT_APPROVE", str(grant_id)
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    service_code = _service_code_for_scope(grant.scope_id) if grant is not None else None
    if (
        grant is None
        or grant.scope_type != SCOPE_SERVICE
        or service_code is None
        or grant.role_code not in SERVICE_ROLE_MATRIX[service_code]
    ):
        raise ApiError(404, "SERVICE_ROLE_GRANT_NOT_FOUND", "Service role grant was not found")
    if grant.status != "REQUESTED":
        raise ApiError(
            409, "SERVICE_ROLE_GRANT_NOT_REQUESTED", "Only a requested grant can be approved"
        )
    if grant.granted_by == principal.identity_id:
        raise ApiError(
            403, "MAKER_CHECKER_REQUIRED", "The requester cannot approve the service role grant"
        )
    grant.status = "ACTIVE"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="ServiceRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SERVICE_ROLE_GRANT_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=grant.reason_ref,
        scope={"role_code": grant.role_code, "scope_id": str(grant.scope_id)},
    )
    await session.commit()
    return ServiceRoleGrantView.model_validate(grant)


class ServiceRoleGrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_reference: str = Field(min_length=1, max_length=255)


@router.post("/grants/{grant_id}/revoke", response_model=ServiceRoleGrantView)
async def revoke_service_role_grant(
    grant_id: UUID,
    body: ServiceRoleGrantRevoke,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ServiceRoleGrantView:
    await _authorize_global_governance(
        session, principal, correlation_id, "SERVICE_ROLE_GRANT_REVOKE", str(grant_id)
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    service_code = _service_code_for_scope(grant.scope_id) if grant is not None else None
    if (
        grant is None
        or grant.scope_type != SCOPE_SERVICE
        or service_code is None
        or grant.role_code not in SERVICE_ROLE_MATRIX[service_code]
    ):
        raise ApiError(404, "SERVICE_ROLE_GRANT_NOT_FOUND", "Service role grant was not found")
    if grant.status not in {"REQUESTED", "ACTIVE"}:
        raise ApiError(
            409, "SERVICE_ROLE_GRANT_NOT_REVOCABLE", "Grant is no longer active or pending"
        )
    grant.status = "REVOKED"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="ServiceRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SERVICE_ROLE_GRANT_REVOKE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"role_code": grant.role_code, "scope_id": str(grant.scope_id)},
    )
    await session.commit()
    return ServiceRoleGrantView.model_validate(grant)


@router.get("/{service_code}/work-queue", response_model=ServiceWorkQueue)
async def read_service_work_queue(
    service_code: ServiceCode,
    limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ServiceWorkQueue:
    await _authorize_service_read(session, principal, correlation_id, service_code)
    if service_code == "LOAN_GUARANTEE":
        rows = (
            await session.execute(
                select(GuaranteeCase, ParticipationEpisode, Participant, ExternalLoanMirror)
                .join(
                    ParticipationEpisode,
                    GuaranteeCase.participation_episode_id == ParticipationEpisode.id,
                )
                .join(Participant, ParticipationEpisode.participant_id == Participant.id)
                .outerjoin(
                    ExternalLoanMirror, ExternalLoanMirror.guarantee_case_id == GuaranteeCase.id
                )
                .order_by(GuaranteeCase.created_at, GuaranteeCase.id)
                .limit(limit)
            )
        ).all()
        items = [
            {
                "case_id": case.id,
                "participant_id": participant.id,
                "status": case.state,
                "requested_principal": case.requested_principal,
                "guarantee_exposure": case.current_guarantee_exposure,
                "lender_record_status": "RECORDED" if loan else "NOT_RECORDED",
                "loan_state": loan.state if loan else None,
                "outstanding_principal": loan.outstanding_principal if loan else None,
                "currency": loan.currency if loan else None,
            }
            for case, _, participant, loan in rows
        ]
    elif service_code == "MONTHLY_PENSION":
        rows = (
            await session.scalars(
                select(MonthlyPensionEntitlement)
                .order_by(MonthlyPensionEntitlement.created_at, MonthlyPensionEntitlement.id)
                .limit(limit)
            )
        ).all()
        items = [
            {
                "entitlement_id": item.id,
                "participant_id": item.participant_id,
                "period_reference": item.period_reference,
                "amount": item.amount,
                "currency": item.currency,
                "status": item.lifecycle_status,
                "policy_version_reference": item.policy_version_reference,
                "calculation_reference": item.calculation_reference,
                "eligibility_evidence_reference": item.eligibility_evidence_reference,
            }
            for item in rows
        ]
    else:
        rows = (
            await session.execute(
                select(PostExitSupportCase, PostExitSupportEntitlement)
                .outerjoin(
                    PostExitSupportEntitlement,
                    PostExitSupportEntitlement.support_case_id == PostExitSupportCase.id,
                )
                .order_by(
                    PostExitSupportCase.created_at,
                    PostExitSupportCase.id,
                    PostExitSupportEntitlement.period_sequence,
                )
                .limit(limit)
            )
        ).all()
        items = [
            {
                "case_id": case.id,
                "participant_id": case.participant_id,
                "case_status": case.lifecycle_status,
                "exit_event_reference": case.exit_event_reference,
                "exit_evidence_reference": case.exit_evidence_reference,
                "entitlement_id": entitlement.id if entitlement else None,
                "period_reference": entitlement.period_reference if entitlement else None,
                "period_at": entitlement.period_at if entitlement else None,
                "amount": entitlement.amount if entitlement else None,
                "currency": entitlement.currency if entitlement else None,
                "entitlement_status": entitlement.lifecycle_status if entitlement else None,
                "calculation_reference": entitlement.calculation_reference if entitlement else None,
                "eligibility_evidence_reference": entitlement.eligibility_evidence_reference
                if entitlement
                else None,
            }
            for case, entitlement in rows
        ]
    append_audit(
        session,
        aggregate_type="ServiceOperations",
        aggregate_id=service_code,
        aggregate_version=None,
        action="SERVICE_OPERATIONS_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"service_code": service_code, "returned_count": len(items)},
    )
    await session.commit()
    return ServiceWorkQueue(service_code=service_code, items=items)
