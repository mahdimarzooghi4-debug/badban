from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.api.sprint13 import _authorize_read
from badban.infrastructure.persistence.models import ExternalLoanEvent, ExternalLoanMirror
from badban.security.authorization import Principal

router = APIRouter(prefix="/api/v1/external-loans", tags=["lender-event-evidence"])


class EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LenderEventEvidenceView(EventModel):
    id: UUID
    external_loan_mirror_id: UUID
    provider_event_id: str
    event_type: str
    processed_status: str
    principal_delta: str | None = Field(default=None, json_schema_extra={"format": "decimal"})
    outstanding_principal_reported: str | None = Field(
        default=None, json_schema_extra={"format": "decimal"}
    )
    provider_event_at: datetime
    received_at: datetime
    evidence_references: list[str]
    payload_hash: str
    provider_contract_version: str
    adapter_mapping_version: str
    inbound_normalization_version: str
    provider_event_sequence: int | None
    created_at: datetime


class LenderEventEvidencePage(EventModel):
    loan_id: UUID
    provider_id: UUID
    items: list[LenderEventEvidenceView]
    next_cursor: UUID | None


def _event_view(event: ExternalLoanEvent) -> LenderEventEvidenceView:
    return LenderEventEvidenceView(
        id=event.id,
        external_loan_mirror_id=event.external_loan_mirror_id,
        provider_event_id=event.provider_event_id,
        event_type=event.event_type,
        processed_status=event.processed_status,
        principal_delta=(
            format(event.principal_delta, "f") if event.principal_delta is not None else None
        ),
        outstanding_principal_reported=(
            format(event.outstanding_principal_reported, "f")
            if event.outstanding_principal_reported is not None
            else None
        ),
        provider_event_at=event.provider_event_at,
        received_at=event.received_at,
        evidence_references=list(event.evidence_references),
        payload_hash=event.payload_hash,
        provider_contract_version=event.provider_contract_version,
        adapter_mapping_version=event.adapter_mapping_version,
        inbound_normalization_version=event.inbound_normalization_version,
        provider_event_sequence=event.provider_event_sequence,
        created_at=event.created_at,
    )


async def _authorized_mirror(
    session: AsyncSession,
    *,
    loan_id: UUID,
    principal: Principal,
    correlation_id: UUID,
) -> ExternalLoanMirror:
    mirror = await session.get(ExternalLoanMirror, loan_id)
    if mirror is None:
        raise ApiError(404, "EXTERNAL_LOAN_NOT_FOUND", "External Loan Mirror not found")
    await _authorize_read(
        session,
        principal=principal,
        provider_id=mirror.provider_id,
        loan_id=mirror.id,
        correlation_id=correlation_id,
    )
    return mirror


@router.get(
    "/{loan_id}/events",
    response_model=LenderEventEvidencePage,
    description=(
        "Authorized Provider-scoped, read-only normalized lender event history. "
        "APPPLIED/STALE/HISTORY_ONLY/CORRECTED events are observed facts only; "
        "an event does not authorize guarantee activation, repayment posting, "
        "risk approval or any financial action. Chronological keyset cursor "
        "is bound to this same loan; no cross-provider event enumeration."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "EXTERNAL_LOAN_NOT_FOUND"},
        422: {"description": "LENDER_EVENT_CURSOR_INVALID or invalid limit"},
    },
)
async def list_lender_event_evidence(
    loan_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    after: UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderEventEvidencePage:
    mirror = await _authorized_mirror(
        session, loan_id=loan_id, principal=principal, correlation_id=correlation_id
    )
    anchor = None
    if after is not None:
        anchor = await session.scalar(
            select(ExternalLoanEvent).where(
                ExternalLoanEvent.id == after,
                ExternalLoanEvent.external_loan_mirror_id == mirror.id,
            )
        )
        if anchor is None:
            raise ApiError(
                422, "LENDER_EVENT_CURSOR_INVALID", "Cursor is not from this External Loan"
            )
    query = (
        select(ExternalLoanEvent)
        .where(ExternalLoanEvent.external_loan_mirror_id == mirror.id)
        .order_by(ExternalLoanEvent.provider_event_at, ExternalLoanEvent.id)
        .limit(limit + 1)
    )
    if anchor is not None:
        query = query.where(
            tuple_(ExternalLoanEvent.provider_event_at, ExternalLoanEvent.id)
            > tuple_(anchor.provider_event_at, anchor.id)
        )
    results = (await session.scalars(query)).all()
    more = len(results) > limit
    page = results[:limit]
    return LenderEventEvidencePage(
        loan_id=mirror.id,
        provider_id=mirror.provider_id,
        items=[_event_view(event) for event in page],
        next_cursor=page[-1].id if more and page else None,
    )


@router.get(
    "/{loan_id}/events/{event_id}",
    response_model=LenderEventEvidenceView,
    description=(
        "Read one recorded normalized event from an authorized lender's "
        "External Loan; no raw provider payload or financial mutation."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "EXTERNAL_LOAN_NOT_FOUND or LENDER_EVENT_NOT_FOUND"},
    },
)
async def get_lender_event_evidence(
    loan_id: UUID,
    event_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderEventEvidenceView:
    mirror = await _authorized_mirror(
        session, loan_id=loan_id, principal=principal, correlation_id=correlation_id
    )
    event = await session.scalar(
        select(ExternalLoanEvent).where(
            ExternalLoanEvent.id == event_id,
            ExternalLoanEvent.external_loan_mirror_id == mirror.id,
        )
    )
    if event is None:
        raise ApiError(404, "LENDER_EVENT_NOT_FOUND", "Event not found for External Loan")
    return _event_view(event)
