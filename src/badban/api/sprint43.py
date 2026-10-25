from __future__ import annotations

import calendar
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import (
    JournalEntry,
    JournalPosting,
    Participant,
    PostExitSupportCase,
    PostExitSupportEntitlement,
    PostExitSupportFundingAllocation,
    ServiceCatalogueVersion,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/admin/post-exit-support", tags=["post-exit-support"])


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


class SupportCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_catalogue_version_id: UUID
    participant_id: UUID
    exit_event_reference: str = Field(min_length=1, max_length=255)
    exit_evidence_reference: str = Field(min_length=1, max_length=500)
    exit_at: datetime
    support_start_at: datetime
    duration_months: int = Field(ge=1, le=36)
    policy_version_reference: str = Field(min_length=1, max_length=200)
    eligibility_decision_reference: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self) -> SupportCaseCreate:
        if any(
            value.tzinfo is None or value.utcoffset() is None
            for value in (self.exit_at, self.support_start_at)
        ):
            raise ValueError("exit and support start timestamps must be timezone-aware")
        if self.support_start_at < self.exit_at:
            raise ValueError("support cannot start before the recorded exit event")
        return self


class SupportCaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_catalogue_version_id: UUID
    participant_id: UUID
    exit_event_reference: str
    exit_evidence_reference: str
    exit_at: datetime
    support_start_at: datetime
    duration_months: int
    policy_version_reference: str
    eligibility_decision_reference: str
    lifecycle_status: Literal["DRAFT", "ACTIVE", "SUSPENDED", "COMPLETED", "CANCELLED"]
    created_by: UUID
    activated_by: UUID | None
    activated_at: datetime | None
    created_at: datetime
    version: int


class SupportEntitlementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_sequence: int = Field(ge=1, le=36)
    period_reference: str = Field(min_length=1, max_length=120)
    period_at: datetime
    amount: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    currency: str = Field(min_length=1, max_length=16)
    policy_version_reference: str = Field(min_length=1, max_length=200)
    calculation_reference: str = Field(min_length=1, max_length=500)
    eligibility_evidence_reference: str = Field(min_length=1, max_length=500)
    source_posting_ids: list[UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_period_at(self) -> SupportEntitlementCreate:
        if self.period_at.tzinfo is None or self.period_at.utcoffset() is None:
            raise ValueError("period_at must be timezone-aware")
        return self


class SupportEntitlementView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    support_case_id: UUID
    period_sequence: int
    period_reference: str
    period_at: datetime
    amount: Decimal
    currency: str
    policy_version_reference: str
    calculation_reference: str
    eligibility_evidence_reference: str
    lifecycle_status: Literal["DRAFT", "APPROVED", "CANCELLED"]
    created_by: UUID
    approved_by: UUID | None
    approved_at: datetime | None
    created_at: datetime
    version: int


async def _authorize(
    session: AsyncSession,
    principal: Principal,
    correlation_id: UUID,
    action: str,
    target_id: str = "GLOBAL",
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
            target_type="PostExitSupport",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


@router.post("/cases", response_model=SupportCaseView, status_code=status.HTTP_201_CREATED)
async def create_support_case(
    body: SupportCaseCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> SupportCaseView:
    await _authorize(session, principal, correlation_id, "POST_EXIT_SUPPORT_CASE_CREATE")
    service = await session.get(ServiceCatalogueVersion, body.service_catalogue_version_id)
    now = datetime.now(UTC)
    if (
        service is None
        or service.service_code != "POST_EXIT_SUPPORT"
        or service.lifecycle_status != "ACTIVE"
        or service.effective_from > now
        or (service.effective_to is not None and service.effective_to <= now)
    ):
        raise ApiError(
            409,
            "POST_EXIT_SERVICE_UNAVAILABLE",
            "An active, effective post-exit support service version is required",
        )
    if service.max_duration_months is None or body.duration_months > service.max_duration_months:
        raise ApiError(
            422,
            "SUPPORT_DURATION_EXCEEDS_POLICY",
            "Support duration exceeds the configured service maximum",
        )
    if body.policy_version_reference != service.policy_version_reference:
        raise ApiError(
            422,
            "POLICY_VERSION_MISMATCH",
            "Case policy reference must match the selected service version",
        )
    if await session.get(Participant, body.participant_id) is None:
        raise ApiError(404, "PARTICIPANT_NOT_FOUND", "Participant was not found")
    idem, replay = await acquire_idempotency(
        session,
        scope="post-exit-support:case-create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return SupportCaseView.model_validate(replay)
    case = PostExitSupportCase(
        service_catalogue_version_id=service.id,
        participant_id=body.participant_id,
        exit_event_reference=body.exit_event_reference,
        exit_evidence_reference=body.exit_evidence_reference,
        exit_at=body.exit_at,
        support_start_at=body.support_start_at,
        duration_months=body.duration_months,
        policy_version_reference=body.policy_version_reference,
        eligibility_decision_reference=body.eligibility_decision_reference,
        lifecycle_status="DRAFT",
        created_by=principal.identity_id,
    )
    session.add(case)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            409,
            "EXIT_EVENT_ALREADY_REGISTERED",
            "This participant exit-event reference is already registered",
        ) from exc
    view = SupportCaseView.model_validate(case)
    append_audit(
        session,
        aggregate_type="PostExitSupportCase",
        aggregate_id=str(case.id),
        aggregate_version=case.version,
        action="POST_EXIT_SUPPORT_CASE_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=case.exit_evidence_reference,
        scope={"participant_id": str(case.participant_id)},
    )
    complete_idempotency(idem, status_code=201, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.post("/cases/{case_id}/activate", response_model=SupportCaseView)
async def activate_support_case(
    case_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportCaseView:
    await _authorize(
        session, principal, correlation_id, "POST_EXIT_SUPPORT_CASE_ACTIVATE", str(case_id)
    )
    case = await session.scalar(
        select(PostExitSupportCase).where(PostExitSupportCase.id == case_id).with_for_update()
    )
    if case is None:
        raise ApiError(404, "SUPPORT_CASE_NOT_FOUND", "Post-exit support case was not found")
    if case.lifecycle_status != "DRAFT":
        raise ApiError(409, "SUPPORT_CASE_NOT_DRAFT", "Only a draft support case can be activated")
    if case.created_by == principal.identity_id:
        raise ApiError(403, "MAKER_CHECKER_REQUIRED", "The case creator cannot activate the case")
    case.lifecycle_status = "ACTIVE"
    case.activated_by = principal.identity_id
    case.activated_at = datetime.now(UTC)
    append_audit(
        session,
        aggregate_type="PostExitSupportCase",
        aggregate_id=str(case.id),
        aggregate_version=case.version,
        action="POST_EXIT_SUPPORT_CASE_ACTIVATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=case.eligibility_decision_reference,
    )
    await session.commit()
    return SupportCaseView.model_validate(case)


@router.post(
    "/cases/{case_id}/entitlements",
    response_model=SupportEntitlementView,
    status_code=status.HTTP_201_CREATED,
)
async def create_period_entitlement(
    case_id: UUID,
    body: SupportEntitlementCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> SupportEntitlementView:
    await _authorize(
        session, principal, correlation_id, "POST_EXIT_ENTITLEMENT_CREATE", str(case_id)
    )
    case = await session.scalar(
        select(PostExitSupportCase).where(PostExitSupportCase.id == case_id).with_for_update()
    )
    if case is None:
        raise ApiError(404, "SUPPORT_CASE_NOT_FOUND", "Post-exit support case was not found")
    if case.lifecycle_status != "ACTIVE":
        raise ApiError(
            409, "SUPPORT_CASE_NOT_ACTIVE", "Entitlements require an active support case"
        )
    now = datetime.now(UTC)
    if now < case.support_start_at:
        raise ApiError(
            409,
            "SUPPORT_WINDOW_NOT_STARTED",
            "Entitlements cannot be created before the policy-defined support start",
        )
    support_end_at = _add_months(case.support_start_at, case.duration_months)
    if not case.support_start_at <= body.period_at <= support_end_at:
        raise ApiError(
            422,
            "PERIOD_OUTSIDE_SUPPORT_WINDOW",
            "Period date must fall within the policy-defined support window",
        )
    if body.period_sequence > case.duration_months:
        raise ApiError(
            422, "PERIOD_OUTSIDE_SUPPORT_WINDOW", "Period sequence exceeds the support window"
        )
    if body.policy_version_reference != case.policy_version_reference:
        raise ApiError(
            422,
            "POLICY_VERSION_MISMATCH",
            "Entitlement policy reference must match its support case",
        )
    idem, replay = await acquire_idempotency(
        session,
        scope=f"post-exit-support:entitlement:{case_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return SupportEntitlementView.model_validate(replay)

    rows = (
        await session.execute(
            select(JournalPosting, JournalEntry)
            .join(JournalEntry, JournalPosting.journal_entry_id == JournalEntry.id)
            .where(
                JournalPosting.id.in_(body.source_posting_ids),
                JournalPosting.account_code == "2020.FUTURE_FINANCIAL_ENTITLEMENT",
                JournalPosting.participant_id == case.participant_id,
                JournalPosting.currency == body.currency,
                JournalEntry.state == "POSTED",
                JournalEntry.posting_template_reference == "RETURN_ALLOCATION@1",
            )
            .order_by(JournalPosting.id)
            .with_for_update(of=JournalPosting)
        )
    ).all()
    if len(rows) != len(set(body.source_posting_ids)):
        raise ApiError(
            422,
            "INVALID_FUNDING_SOURCE",
            "Every source must be a posted future-financial return allocation for this participant "
            "and currency",
        )
    existing = dict(
        (posting_id, amount)
        for posting_id, amount in (
            await session.execute(
                select(
                    PostExitSupportFundingAllocation.source_journal_posting_id,
                    func.sum(PostExitSupportFundingAllocation.amount),
                )
                .where(
                    PostExitSupportFundingAllocation.source_journal_posting_id.in_(
                        body.source_posting_ids
                    )
                )
                .group_by(PostExitSupportFundingAllocation.source_journal_posting_id)
            )
        ).all()
    )
    available = [
        (
            posting,
            max(
                Decimal("0"),
                (posting.credit_amount or Decimal("0"))
                - (existing.get(posting.id) or Decimal("0")),
            ),
        )
        for posting, _ in rows
    ]
    if sum((amount for _, amount in available), Decimal("0")) < body.amount:
        raise ApiError(
            422,
            "INSUFFICIENT_REALIZED_RETURN",
            "Posted and unallocated future-financial returns do not cover the requested amount",
        )

    entitlement = PostExitSupportEntitlement(
        support_case_id=case.id,
        period_sequence=body.period_sequence,
        period_reference=body.period_reference,
        period_at=body.period_at,
        amount=body.amount,
        currency=body.currency,
        policy_version_reference=body.policy_version_reference,
        calculation_reference=body.calculation_reference,
        eligibility_evidence_reference=body.eligibility_evidence_reference,
        lifecycle_status="DRAFT",
        created_by=principal.identity_id,
    )
    session.add(entitlement)
    await session.flush()
    remaining = body.amount
    for posting, available_amount in available:
        allocated = min(remaining, available_amount)
        if allocated > 0:
            session.add(
                PostExitSupportFundingAllocation(
                    entitlement_id=entitlement.id,
                    source_journal_posting_id=posting.id,
                    amount=allocated,
                    currency=body.currency,
                )
            )
            remaining -= allocated
        if remaining == 0:
            break
    view = SupportEntitlementView.model_validate(entitlement)
    append_audit(
        session,
        aggregate_type="PostExitSupportEntitlement",
        aggregate_id=str(entitlement.id),
        aggregate_version=entitlement.version,
        action="POST_EXIT_ENTITLEMENT_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.eligibility_evidence_reference,
        scope={
            "support_case_id": str(case.id),
            "period_sequence": body.period_sequence,
        },
    )
    complete_idempotency(idem, status_code=201, response_payload=view.model_dump(mode="json"))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            409,
            "ENTITLEMENT_CONFLICT",
            "Period entitlement or source allocation conflicts with an existing record",
        ) from exc
    return view


@router.post("/entitlements/{entitlement_id}/approve", response_model=SupportEntitlementView)
async def approve_period_entitlement(
    entitlement_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportEntitlementView:
    await _authorize(
        session, principal, correlation_id, "POST_EXIT_ENTITLEMENT_APPROVE", str(entitlement_id)
    )
    item = await session.scalar(
        select(PostExitSupportEntitlement)
        .where(PostExitSupportEntitlement.id == entitlement_id)
        .with_for_update()
    )
    if item is None:
        raise ApiError(404, "ENTITLEMENT_NOT_FOUND", "Post-exit period entitlement was not found")
    if item.lifecycle_status != "DRAFT":
        raise ApiError(409, "ENTITLEMENT_NOT_DRAFT", "Only a draft entitlement can be approved")
    if item.created_by == principal.identity_id:
        raise ApiError(403, "MAKER_CHECKER_REQUIRED", "The entitlement creator cannot approve it")
    funded = await session.scalar(
        select(func.coalesce(func.sum(PostExitSupportFundingAllocation.amount), 0)).where(
            PostExitSupportFundingAllocation.entitlement_id == item.id
        )
    )
    if (funded or Decimal("0")) < item.amount:
        raise ApiError(
            409,
            "FUNDING_INCOMPLETE",
            "Approved entitlement must be fully backed by allocated posted returns",
        )
    item.lifecycle_status = "APPROVED"
    item.approved_by = principal.identity_id
    item.approved_at = datetime.now(UTC)
    append_audit(
        session,
        aggregate_type="PostExitSupportEntitlement",
        aggregate_id=str(item.id),
        aggregate_version=item.version,
        action="POST_EXIT_ENTITLEMENT_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=item.eligibility_evidence_reference,
    )
    await session.commit()
    return SupportEntitlementView.model_validate(item)



class SupportCaseStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_status: Literal["ACTIVE", "SUSPENDED", "COMPLETED", "CANCELLED"]
    decision_reference: str = Field(min_length=1, max_length=500)


@router.post("/cases/{case_id}/status", response_model=SupportCaseView)
async def change_support_case_status(
    case_id: UUID,
    body: SupportCaseStatusChange,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportCaseView:
    await _authorize(
        session, principal, correlation_id, "POST_EXIT_SUPPORT_CASE_STATUS_CHANGE", str(case_id)
    )
    case = await session.scalar(
        select(PostExitSupportCase).where(PostExitSupportCase.id == case_id).with_for_update()
    )
    if case is None:
        raise ApiError(404, "SUPPORT_CASE_NOT_FOUND", "Post-exit support case was not found")
    allowed = {
        "ACTIVE": {"SUSPENDED", "COMPLETED", "CANCELLED"},
        "SUSPENDED": {"ACTIVE", "COMPLETED", "CANCELLED"},
    }
    if body.target_status not in allowed.get(case.lifecycle_status, set()):
        raise ApiError(
            409,
            "INVALID_SUPPORT_CASE_TRANSITION",
            "Requested support case status transition is not allowed",
        )
    if case.created_by == principal.identity_id:
        raise ApiError(
            403,
            "MAKER_CHECKER_REQUIRED",
            "The case creator cannot change the case status",
        )
    previous_status = case.lifecycle_status
    case.lifecycle_status = body.target_status
    append_audit(
        session,
        aggregate_type="PostExitSupportCase",
        aggregate_id=str(case.id),
        aggregate_version=case.version,
        action="POST_EXIT_SUPPORT_CASE_STATUS_CHANGE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.decision_reference,
        scope={"previous_status": previous_status, "new_status": body.target_status},
    )
    await session.commit()
    return SupportCaseView.model_validate(case)


class SupportCasePage(BaseModel):
    items: list[SupportCaseView]


class SupportEntitlementPage(BaseModel):
    items: list[SupportEntitlementView]


@router.get("/cases", response_model=SupportCasePage)
async def list_support_cases(
    participant_id: UUID | None = None,
    lifecycle_status: Literal["DRAFT", "ACTIVE", "SUSPENDED", "COMPLETED", "CANCELLED"]
    | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportCasePage:
    await _authorize(session, principal, correlation_id, "POST_EXIT_SUPPORT_CASE_READ")
    filters = []
    if participant_id is not None:
        filters.append(PostExitSupportCase.participant_id == participant_id)
    if lifecycle_status is not None:
        filters.append(PostExitSupportCase.lifecycle_status == lifecycle_status)
    rows = (
        await session.scalars(
            select(PostExitSupportCase)
            .where(*filters)
            .order_by(PostExitSupportCase.created_at, PostExitSupportCase.id)
            .limit(limit)
        )
    ).all()
    return SupportCasePage(items=[SupportCaseView.model_validate(row) for row in rows])


@router.get("/cases/{case_id}/entitlements", response_model=SupportEntitlementPage)
async def list_case_entitlements(
    case_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportEntitlementPage:
    await _authorize(session, principal, correlation_id, "POST_EXIT_ENTITLEMENT_READ", str(case_id))
    if await session.get(PostExitSupportCase, case_id) is None:
        raise ApiError(404, "SUPPORT_CASE_NOT_FOUND", "Post-exit support case was not found")
    rows = (
        await session.scalars(
            select(PostExitSupportEntitlement)
            .where(PostExitSupportEntitlement.support_case_id == case_id)
            .order_by(
                PostExitSupportEntitlement.period_sequence,
                PostExitSupportEntitlement.id,
            )
            .limit(limit)
        )
    ).all()
    return SupportEntitlementPage(
        items=[SupportEntitlementView.model_validate(row) for row in rows]
    )
