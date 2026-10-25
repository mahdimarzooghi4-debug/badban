from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_current_principal, get_session
from badban.api.errors import ApiError
from badban.api.sprint44 import get_linked_participant
from badban.infrastructure.persistence.models import (
    CreditProductVersion,
    ExternalLoanMirror,
    GuaranteeCase,
    JournalEntry,
    JournalPosting,
    MonthlyPensionEntitlement,
    MonthlyPensionFundingAllocation,
    ParticipationEpisode,
    PostExitSupportCase,
    PostExitSupportEntitlement,
    PostExitSupportFundingAllocation,
)
from badban.security.authorization import Principal

router = APIRouter(prefix="/api/v1/applicant", tags=["applicant"])


class GuaranteeCaseSummary(BaseModel):
    id: UUID
    status: str
    requested_principal: Decimal
    guarantee_exposure: Decimal
    lender_evidence_status: Literal["AVAILABLE", "NOT_RECORDED"]
    loan_state: str | None
    outstanding_principal: Decimal | None
    currency: str


class EntitlementSummary(BaseModel):
    id: UUID
    period_reference: str
    amount: Decimal
    currency: str
    status: str
    payment_status: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"


class PostExitCaseSummary(BaseModel):
    id: UUID
    status: str
    exit_at: datetime
    support_start_at: datetime
    duration_months: int
    entitlements: list[EntitlementSummary]


class FinancialBalanceSummary(BaseModel):
    currency: str
    outstanding_principal: Decimal | None
    guarantee_exposure: Decimal | None
    realized_return_allocated_to_support: Decimal | None
    allocated_support: Decimal | None
    paid_amount: Decimal | None = None
    payment_status: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"


class ApplicantFinancialCaseView(BaseModel):
    participant_id: UUID
    guarantee_cases: list[GuaranteeCaseSummary]
    monthly_entitlements: list[EntitlementSummary]
    post_exit_cases: list[PostExitCaseSummary]
    balances: list[FinancialBalanceSummary]
    external_price_source_status: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"
    external_payment_status: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"


@router.get("/financial-case", response_model=ApplicantFinancialCaseView)
async def get_financial_case(
    limit: int = Query(default=100, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ApplicantFinancialCaseView:
    linked = await get_linked_participant(principal=principal, session=session)
    participant_id = linked.participant_id

    guarantee_rows = (
        await session.execute(
            select(GuaranteeCase, CreditProductVersion, ExternalLoanMirror)
            .join(
                ParticipationEpisode,
                GuaranteeCase.participation_episode_id == ParticipationEpisode.id,
            )
            .join(
                CreditProductVersion,
                GuaranteeCase.credit_product_version_id == CreditProductVersion.id,
            )
            .outerjoin(
                ExternalLoanMirror,
                ExternalLoanMirror.guarantee_case_id == GuaranteeCase.id,
            )
            .where(ParticipationEpisode.participant_id == participant_id)
            .order_by(GuaranteeCase.created_at, GuaranteeCase.id)
            .limit(limit)
        )
    ).all()
    guarantee_cases = [
        GuaranteeCaseSummary(
            id=case.id,
            status=case.state,
            requested_principal=case.requested_principal,
            guarantee_exposure=case.current_guarantee_exposure,
            lender_evidence_status="AVAILABLE" if loan is not None else "NOT_RECORDED",
            loan_state=loan.state if loan is not None else None,
            outstanding_principal=loan.outstanding_principal if loan is not None else None,
            currency=product.currency,
        )
        for case, product, loan in guarantee_rows
    ]

    monthly_rows = (
        await session.scalars(
            select(MonthlyPensionEntitlement)
            .where(MonthlyPensionEntitlement.participant_id == participant_id)
            .order_by(MonthlyPensionEntitlement.created_at, MonthlyPensionEntitlement.id)
            .limit(limit)
        )
    ).all()
    monthly_entitlements = [
        EntitlementSummary(
            id=item.id,
            period_reference=item.period_reference,
            amount=item.amount,
            currency=item.currency,
            status=item.lifecycle_status,
        )
        for item in monthly_rows
    ]

    support_cases = (
        await session.scalars(
            select(PostExitSupportCase)
            .where(PostExitSupportCase.participant_id == participant_id)
            .order_by(PostExitSupportCase.created_at, PostExitSupportCase.id)
            .limit(limit)
        )
    ).all()
    support_ids = [case.id for case in support_cases]
    support_entitlements = (
        (
            await session.scalars(
                select(PostExitSupportEntitlement)
                .where(PostExitSupportEntitlement.support_case_id.in_(support_ids))
                .order_by(PostExitSupportEntitlement.period_sequence)
                .limit(limit)
            )
        ).all()
        if support_ids
        else []
    )
    by_case: dict[UUID, list[EntitlementSummary]] = {}
    for item in support_entitlements:
        by_case.setdefault(item.support_case_id, []).append(
            EntitlementSummary(
                id=item.id,
                period_reference=item.period_reference,
                amount=item.amount,
                currency=item.currency,
                status=item.lifecycle_status,
            )
        )
    post_exit_cases = [
        PostExitCaseSummary(
            id=case.id,
            status=case.lifecycle_status,
            exit_at=case.exit_at,
            support_start_at=case.support_start_at,
            duration_months=case.duration_months,
            entitlements=by_case.get(case.id, []),
        )
        for case in support_cases
    ]

    totals: dict[str, dict[str, Decimal]] = {}

    def add(currency: str, key: str, amount: Decimal | None) -> None:
        bucket = totals.setdefault(currency, {})
        bucket[key] = bucket.get(key, Decimal("0")) + (amount or Decimal("0"))

    for case, product, loan in guarantee_rows:
        add(product.currency, "guarantee_exposure", case.current_guarantee_exposure)
        if loan is not None:
            add(loan.currency, "outstanding_principal", loan.outstanding_principal)

    return_rows = (
        await session.execute(
            select(JournalPosting.currency, func.sum(JournalPosting.credit_amount))
            .join(JournalEntry, JournalPosting.journal_entry_id == JournalEntry.id)
            .where(
                JournalPosting.participant_id == participant_id,
                JournalPosting.account_code.in_(
                    {"2010.LIVELIHOOD_PAYABLE", "2020.FUTURE_FINANCIAL_ENTITLEMENT"}
                ),
                JournalEntry.state == "POSTED",
                JournalEntry.posting_template_reference == "RETURN_ALLOCATION@1",
            )
            .group_by(JournalPosting.currency)
        )
    ).all()
    for currency, amount in return_rows:
        add(currency, "realized_return_allocated_to_support", amount)

    monthly_funded = (
        await session.execute(
            select(MonthlyPensionFundingAllocation.currency, func.sum(MonthlyPensionFundingAllocation.amount))
            .join(
                MonthlyPensionEntitlement,
                MonthlyPensionFundingAllocation.entitlement_id == MonthlyPensionEntitlement.id,
            )
            .where(MonthlyPensionEntitlement.participant_id == participant_id)
            .group_by(MonthlyPensionFundingAllocation.currency)
        )
    ).all()
    future_funded = (
        await session.execute(
            select(PostExitSupportFundingAllocation.currency, func.sum(PostExitSupportFundingAllocation.amount))
            .join(
                PostExitSupportEntitlement,
                PostExitSupportFundingAllocation.entitlement_id == PostExitSupportEntitlement.id,
            )
            .join(
                PostExitSupportCase,
                PostExitSupportEntitlement.support_case_id == PostExitSupportCase.id,
            )
            .where(PostExitSupportCase.participant_id == participant_id)
            .group_by(PostExitSupportFundingAllocation.currency)
        )
    ).all()
    for currency, amount in [*monthly_funded, *future_funded]:
        add(currency, "allocated_support", amount)

    balances = [
        FinancialBalanceSummary(
            currency=currency,
            outstanding_principal=values.get("outstanding_principal"),
            guarantee_exposure=values.get("guarantee_exposure"),
            realized_return_allocated_to_support=values.get(
                "realized_return_allocated_to_support"
            ),
            allocated_support=values.get("allocated_support"),
        )
        for currency, values in sorted(totals.items())
    ]
    return ApplicantFinancialCaseView(
        participant_id=participant_id,
        guarantee_cases=guarantee_cases,
        monthly_entitlements=monthly_entitlements,
        post_exit_cases=post_exit_cases,
        balances=balances,
    )
