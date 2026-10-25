from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import (
    LegacyBenefitLineageReview,
    MonthlyPensionEntitlement,
    ParticipationEpisode,
    PostExitSupportCase,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(
    prefix="/api/v1/admin/benefit-lineage/reviews",
    tags=["benefit-lineage-governance"],
)

BenefitType = Literal["MONTHLY_PENSION", "POST_EXIT_SUPPORT"]
ReviewStatus = Literal["REQUESTED", "APPROVED", "REJECTED"]


class BenefitLineageReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benefit_type: BenefitType
    benefit_record_id: UUID
    program_id: UUID
    participation_episode_id: UUID
    evidence_reference: str = Field(min_length=1, max_length=500)
    reason_reference: str = Field(min_length=1, max_length=255)


class BenefitLineageReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_reference: str = Field(min_length=1, max_length=255)


class BenefitLineageReviewView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    benefit_type: BenefitType
    benefit_record_id: UUID
    participant_id: UUID
    program_id: UUID
    participation_episode_id: UUID
    evidence_reference: str
    reason_reference: str
    status: ReviewStatus
    requested_by: UUID
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_reason_reference: str | None
    created_at: datetime


class BenefitLineageReviewPage(BaseModel):
    items: list[BenefitLineageReviewView]
    status: ReviewStatus
    limit: int
    offset: int


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
            target_type="LegacyBenefitLineageReview",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


async def _load_benefit(
    session: AsyncSession,
    benefit_type: BenefitType,
    benefit_record_id: UUID,
    *,
    lock: bool = False,
) -> Any | None:
    model = MonthlyPensionEntitlement if benefit_type == "MONTHLY_PENSION" else PostExitSupportCase
    statement = select(model).where(model.id == benefit_record_id)
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement)


@router.get("", response_model=BenefitLineageReviewPage)
async def list_benefit_lineage_reviews(
    review_status: ReviewStatus = Query(default="REQUESTED", alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> BenefitLineageReviewPage:
    await _authorize_global_governance(
        session, principal, correlation_id, "LEGACY_BENEFIT_LINEAGE_REVIEW_LIST", review_status
    )
    reviews = (
        await session.scalars(
            select(LegacyBenefitLineageReview)
            .where(LegacyBenefitLineageReview.status == review_status)
            .order_by(LegacyBenefitLineageReview.created_at.desc(), LegacyBenefitLineageReview.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="LegacyBenefitLineageReviewQueue",
        aggregate_id=review_status,
        aggregate_version=None,
        action="LEGACY_BENEFIT_LINEAGE_REVIEW_LIST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(reviews), "limit": limit, "offset": offset},
    )
    await session.commit()
    return BenefitLineageReviewPage(
        items=[BenefitLineageReviewView.model_validate(review) for review in reviews],
        status=review_status,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=BenefitLineageReviewView, status_code=status.HTTP_201_CREATED)
async def request_benefit_lineage_review(
    body: BenefitLineageReviewCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> BenefitLineageReviewView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "LEGACY_BENEFIT_LINEAGE_REQUEST",
        str(body.benefit_record_id),
    )
    record = await _load_benefit(session, body.benefit_type, body.benefit_record_id, lock=True)
    if record is None:
        raise ApiError(404, "BENEFIT_RECORD_NOT_FOUND", "Benefit record was not found")
    if record.program_id is not None or record.participation_episode_id is not None:
        raise ApiError(
            409,
            "BENEFIT_RECORD_ALREADY_LINKED",
            "Only a benefit record without program lineage can be submitted",
        )
    episode = await session.scalar(
        select(ParticipationEpisode.id).where(
            ParticipationEpisode.id == body.participation_episode_id,
            ParticipationEpisode.participant_id == record.participant_id,
            ParticipationEpisode.program_id == body.program_id,
        )
    )
    if episode is None:
        raise ApiError(
            422,
            "PARTICIPATION_EPISODE_SCOPE_MISMATCH",
            "The selected episode must belong to the record's participant and program",
        )
    pending = await session.scalar(
        select(LegacyBenefitLineageReview.id).where(
            LegacyBenefitLineageReview.benefit_type == body.benefit_type,
            LegacyBenefitLineageReview.benefit_record_id == body.benefit_record_id,
            LegacyBenefitLineageReview.status == "REQUESTED",
        )
    )
    if pending is not None:
        raise ApiError(
            409,
            "BENEFIT_LINEAGE_REVIEW_PENDING",
            "A lineage review is already pending for this benefit record",
        )
    review = LegacyBenefitLineageReview(
        benefit_type=body.benefit_type,
        benefit_record_id=body.benefit_record_id,
        participant_id=record.participant_id,
        program_id=body.program_id,
        participation_episode_id=body.participation_episode_id,
        evidence_reference=body.evidence_reference,
        reason_reference=body.reason_reference,
        status="REQUESTED",
        requested_by=principal.identity_id,
    )
    session.add(review)
    await session.flush()
    append_audit(
        session,
        aggregate_type="LegacyBenefitLineageReview",
        aggregate_id=str(review.id),
        aggregate_version=None,
        action="LEGACY_BENEFIT_LINEAGE_REQUEST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=review.evidence_reference,
        scope={
            "benefit_type": review.benefit_type,
            "benefit_record_id": str(review.benefit_record_id),
            "participant_id": str(review.participant_id),
            "program_id": str(review.program_id),
            "participation_episode_id": str(review.participation_episode_id),
        },
    )
    await session.commit()
    return BenefitLineageReviewView.model_validate(review)


@router.post("/{review_id}/approve", response_model=BenefitLineageReviewView)
async def approve_benefit_lineage_review(
    review_id: UUID,
    body: BenefitLineageReviewDecision,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> BenefitLineageReviewView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "LEGACY_BENEFIT_LINEAGE_APPROVE",
        str(review_id),
    )
    review = await session.scalar(
        select(LegacyBenefitLineageReview)
        .where(LegacyBenefitLineageReview.id == review_id)
        .with_for_update()
    )
    if review is None:
        raise ApiError(404, "BENEFIT_LINEAGE_REVIEW_NOT_FOUND", "Lineage review was not found")
    if review.status != "REQUESTED":
        raise ApiError(
            409, "BENEFIT_LINEAGE_REVIEW_NOT_PENDING", "Only a pending review can be approved"
        )
    if review.requested_by == principal.identity_id:
        raise ApiError(
            403, "MAKER_CHECKER_REQUIRED", "The requester cannot approve the benefit lineage review"
        )
    record = await _load_benefit(session, review.benefit_type, review.benefit_record_id, lock=True)
    if (
        record is None
        or record.participant_id != review.participant_id
        or record.program_id is not None
        or record.participation_episode_id is not None
    ):
        raise ApiError(
            409,
            "BENEFIT_RECORD_LINEAGE_CHANGED",
            "The benefit record is no longer eligible for this lineage review",
        )
    episode = await session.scalar(
        select(ParticipationEpisode.id).where(
            ParticipationEpisode.id == review.participation_episode_id,
            ParticipationEpisode.participant_id == review.participant_id,
            ParticipationEpisode.program_id == review.program_id,
        )
    )
    if episode is None:
        raise ApiError(
            409,
            "PARTICIPATION_EPISODE_SCOPE_CHANGED",
            "The proposed participant episode no longer matches the review",
        )
    record.program_id = review.program_id
    record.participation_episode_id = review.participation_episode_id
    record.version += 1
    review.status = "APPROVED"
    review.reviewed_by = principal.identity_id
    review.reviewed_at = datetime.now(UTC)
    review.review_reason_reference = body.reason_reference
    append_audit(
        session,
        aggregate_type="LegacyBenefitLineageReview",
        aggregate_id=str(review.id),
        aggregate_version=None,
        action="LEGACY_BENEFIT_LINEAGE_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=review.evidence_reference,
        scope={
            "benefit_type": review.benefit_type,
            "benefit_record_id": str(review.benefit_record_id),
            "participant_id": str(review.participant_id),
            "program_id": str(review.program_id),
            "participation_episode_id": str(review.participation_episode_id),
        },
    )
    await session.commit()
    return BenefitLineageReviewView.model_validate(review)


@router.post("/{review_id}/reject", response_model=BenefitLineageReviewView)
async def reject_benefit_lineage_review(
    review_id: UUID,
    body: BenefitLineageReviewDecision,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> BenefitLineageReviewView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "LEGACY_BENEFIT_LINEAGE_REJECT",
        str(review_id),
    )
    review = await session.scalar(
        select(LegacyBenefitLineageReview)
        .where(LegacyBenefitLineageReview.id == review_id)
        .with_for_update()
    )
    if review is None:
        raise ApiError(404, "BENEFIT_LINEAGE_REVIEW_NOT_FOUND", "Lineage review was not found")
    if review.status != "REQUESTED":
        raise ApiError(
            409, "BENEFIT_LINEAGE_REVIEW_NOT_PENDING", "Only a pending review can be rejected"
        )
    if review.requested_by == principal.identity_id:
        raise ApiError(
            403, "MAKER_CHECKER_REQUIRED", "The requester cannot reject the benefit lineage review"
        )
    review.status = "REJECTED"
    review.reviewed_by = principal.identity_id
    review.reviewed_at = datetime.now(UTC)
    review.review_reason_reference = body.reason_reference
    append_audit(
        session,
        aggregate_type="LegacyBenefitLineageReview",
        aggregate_id=str(review.id),
        aggregate_version=None,
        action="LEGACY_BENEFIT_LINEAGE_REJECT",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={
            "benefit_type": review.benefit_type,
            "benefit_record_id": str(review.benefit_record_id),
            "program_id": str(review.program_id),
        },
    )
    await session.commit()
    return BenefitLineageReviewView.model_validate(review)
