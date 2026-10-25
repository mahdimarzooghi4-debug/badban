from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import (
    JournalEntry,
    JournalPosting,
    MonthlyPensionEntitlement,
    MonthlyPensionFundingAllocation,
    Participant,
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

router = APIRouter(prefix="/api/v1/admin/monthly-pension-entitlements", tags=["monthly-pension"])


class EntitlementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_catalogue_version_id: UUID
    participant_id: UUID
    period_reference: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0, max_digits=38, decimal_places=18)
    currency: str = Field(min_length=1, max_length=16)
    policy_version_reference: str = Field(min_length=1, max_length=200)
    calculation_reference: str = Field(min_length=1, max_length=500)
    eligibility_evidence_reference: str = Field(min_length=1, max_length=500)
    source_posting_ids: list[UUID] = Field(min_length=1, max_length=100)


class EntitlementView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_catalogue_version_id: UUID
    participant_id: UUID
    period_reference: str
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
    session: AsyncSession, principal: Principal, correlation_id: UUID, action: str
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
            target_type="MonthlyPensionEntitlement",
            target_id="GLOBAL",
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


@router.post("", response_model=EntitlementView, status_code=status.HTTP_201_CREATED)
async def create_entitlement(
    body: EntitlementCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> EntitlementView:
    await _authorize(session, principal, correlation_id, "MONTHLY_PENSION_ENTITLEMENT_CREATE")
    service = await session.get(ServiceCatalogueVersion, body.service_catalogue_version_id)
    now = datetime.now(UTC)
    if (
        service is None
        or service.service_code != "MONTHLY_PENSION"
        or service.lifecycle_status != "ACTIVE"
        or service.effective_from > now
        or (service.effective_to is not None and service.effective_to <= now)
    ):
        raise ApiError(
            409,
            "MONTHLY_PENSION_SERVICE_UNAVAILABLE",
            "An active, effective monthly pension service version is required",
        )
    if body.policy_version_reference != service.policy_version_reference:
        raise ApiError(
            422,
            "POLICY_VERSION_MISMATCH",
            "Entitlement policy reference must match the selected service version",
        )
    if await session.get(Participant, body.participant_id) is None:
        raise ApiError(404, "PARTICIPANT_NOT_FOUND", "Participant was not found")
    idem, replay = await acquire_idempotency(
        session,
        scope="monthly-pension-entitlement:create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return EntitlementView.model_validate(replay)
    if (
        await session.scalar(
            select(MonthlyPensionEntitlement.id).where(
                MonthlyPensionEntitlement.participant_id == body.participant_id,
                MonthlyPensionEntitlement.period_reference == body.period_reference,
            )
        )
        is not None
    ):
        raise ApiError(
            409,
            "ENTITLEMENT_EXISTS",
            "An entitlement already exists for this participant and period",
        )

    rows = (
        await session.execute(
            select(JournalPosting, JournalEntry)
            .join(JournalEntry, JournalPosting.journal_entry_id == JournalEntry.id)
            .where(
                JournalPosting.id.in_(body.source_posting_ids),
                JournalPosting.account_code == "2010.LIVELIHOOD_PAYABLE",
                JournalPosting.participant_id == body.participant_id,
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
            "Every funding source must be a posted return allocation for this participant "
            "and currency",
        )
    existing = dict(
        (posting_id, amount)
        for posting_id, amount in (
            await session.execute(
                select(
                    MonthlyPensionFundingAllocation.source_journal_posting_id,
                    func.sum(MonthlyPensionFundingAllocation.amount),
                )
                .where(
                    MonthlyPensionFundingAllocation.source_journal_posting_id.in_(
                        body.source_posting_ids
                    )
                )
                .group_by(MonthlyPensionFundingAllocation.source_journal_posting_id)
            )
        ).all()
    )
    available = [
        (
            p,
            max(
                Decimal("0"),
                (p.credit_amount or Decimal("0")) - (existing.get(p.id) or Decimal("0")),
            ),
        )
        for p, _ in rows
    ]
    if sum((a for _, a in available), Decimal("0")) < body.amount:
        raise ApiError(
            422,
            "INSUFFICIENT_REALIZED_RETURN",
            "Posted and unallocated return allocation does not cover the requested amount",
        )

    entitlement = MonthlyPensionEntitlement(
        service_catalogue_version_id=service.id,
        participant_id=body.participant_id,
        period_reference=body.period_reference,
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
                MonthlyPensionFundingAllocation(
                    entitlement_id=entitlement.id,
                    source_journal_posting_id=posting.id,
                    amount=allocated,
                    currency=body.currency,
                )
            )
            remaining -= allocated
        if remaining == 0:
            break
    view = EntitlementView.model_validate(entitlement)
    append_audit(
        session,
        aggregate_type="MonthlyPensionEntitlement",
        aggregate_id=str(entitlement.id),
        aggregate_version=entitlement.version,
        action="MONTHLY_PENSION_ENTITLEMENT_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.eligibility_evidence_reference,
        scope={
            "participant_id": str(body.participant_id),
            "period_reference": body.period_reference,
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
            "Entitlement or funding allocation conflicts with an existing record",
        ) from exc
    return view


@router.post("/{entitlement_id}/approve", response_model=EntitlementView)
async def approve_entitlement(
    entitlement_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> EntitlementView:
    await _authorize(session, principal, correlation_id, "MONTHLY_PENSION_ENTITLEMENT_APPROVE")
    item = await session.scalar(
        select(MonthlyPensionEntitlement)
        .where(MonthlyPensionEntitlement.id == entitlement_id)
        .with_for_update()
    )
    if item is None:
        raise ApiError(404, "ENTITLEMENT_NOT_FOUND", "Monthly pension entitlement was not found")
    if item.lifecycle_status != "DRAFT":
        raise ApiError(409, "ENTITLEMENT_NOT_DRAFT", "Only a draft entitlement can be approved")
    if item.created_by == principal.identity_id:
        raise ApiError(
            403, "MAKER_CHECKER_REQUIRED", "The creator cannot approve their own entitlement"
        )
    funded = await session.scalar(
        select(func.coalesce(func.sum(MonthlyPensionFundingAllocation.amount), 0)).where(
            MonthlyPensionFundingAllocation.entitlement_id == item.id
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
        aggregate_type="MonthlyPensionEntitlement",
        aggregate_id=str(item.id),
        aggregate_version=item.version,
        action="MONTHLY_PENSION_ENTITLEMENT_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=item.eligibility_evidence_reference,
    )
    await session.commit()
    return EntitlementView.model_validate(item)
