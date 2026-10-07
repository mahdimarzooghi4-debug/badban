from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.journal import (
    JournalError,
    reverse_journal_with_approval,
)
from badban.infrastructure.persistence.models import JournalEntry, JournalPosting
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    SCOPE_LEGAL_ENTITY,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/finance", tags=["finance-journals"])

DecimalString = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JournalSummaryView(OrmModel):
    id: UUID
    business_event_type: str
    business_event_id: str
    legal_entity_id: UUID
    currency: str
    state: str
    effective_at: datetime
    posted_at: datetime | None
    reversal_of_entry_id: UUID | None
    actor_reference: UUID
    correlation_id: UUID
    causation_id: UUID | None
    policy_version_reference: str | None
    posting_template_reference: str | None
    account_mapping_reference: str | None
    evidence_reference: str | None
    settlement_reference: str | None
    reason: str | None


class JournalPostingView(OrmModel):
    id: UUID
    account_code: str
    legal_entity_id: UUID
    economic_owner_type: str
    economic_owner_id: UUID | None
    participant_id: UUID | None
    program_id: UUID | None
    provider_id: UUID | None
    asset_position_id: UUID | None
    guarantee_case_id: UUID | None
    claim_id: UUID | None
    reserve_account_id: UUID | None
    debit_amount: DecimalString
    credit_amount: DecimalString
    currency: str


class JournalDetailView(JournalSummaryView):
    postings: list[JournalPostingView]


class JournalReverseRequest(BaseModel):
    approval_request_id: UUID
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value


async def _authorize(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    legal_entity_id: UUID,
    action: str,
    target_id: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=SCOPE_LEGAL_ENTITY,
            scope_id=legal_entity_id,
            allow_global=True,
            action=action,
            target_type="JournalEntry",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for journal scope") from exc


def _raise_journal_error(exc: JournalError) -> None:
    if exc.code == "JOURNAL_NOT_FOUND":
        raise ApiError(404, exc.code, str(exc)) from exc
    if exc.code in {
        "JOURNAL_ALREADY_REVERSED",
        "JOURNAL_IDEMPOTENCY_CONFLICT",
        "JOURNAL_NOT_POSTED",
        "JOURNAL_REVERSAL_APPROVAL_NOT_FOUND",
        "JOURNAL_REVERSAL_APPROVAL_BINDING_INVALID",
        "JOURNAL_REVERSAL_CHECKER_NOT_AUTHORIZED",
    }:
        raise ApiError(409, exc.code, str(exc)) from exc
    raise ApiError(422, exc.code, str(exc)) from exc


async def _detail(session: AsyncSession, entry: JournalEntry) -> JournalDetailView:
    postings = (
        await session.scalars(
            select(JournalPosting)
            .where(JournalPosting.journal_entry_id == entry.id)
            .order_by(JournalPosting.created_at, JournalPosting.id)
        )
    ).all()
    summary = JournalSummaryView.model_validate(entry)
    return JournalDetailView(
        **summary.model_dump(),
        postings=[JournalPostingView.model_validate(row) for row in postings],
    )


@router.get("/journals", response_model=list[JournalSummaryView])
async def list_journals(
    legal_entity_id: UUID = Query(...),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[JournalSummaryView]:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
        legal_entity_id=legal_entity_id,
        action="JOURNAL_LIST",
        target_id=str(legal_entity_id),
        correlation_id=correlation_id,
    )
    rows = (
        await session.scalars(
            select(JournalEntry)
            .where(
                JournalEntry.legal_entity_id == legal_entity_id,
                JournalEntry.state == "POSTED",
            )
            .order_by(JournalEntry.posted_at.desc(), JournalEntry.id)
        )
    ).all()
    return [JournalSummaryView.model_validate(row) for row in rows]


@router.get("/journals/{journal_id}", response_model=JournalDetailView)
async def get_journal(
    journal_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> JournalDetailView:
    entry = await session.get(JournalEntry, journal_id)
    if entry is None:
        raise ApiError(404, "JOURNAL_NOT_FOUND", "Journal entry was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
        legal_entity_id=entry.legal_entity_id,
        action="JOURNAL_READ",
        target_id=str(entry.id),
        correlation_id=correlation_id,
    )
    return await _detail(session, entry)


@router.post(
    "/journals/{journal_id}/reverse",
    response_model=JournalDetailView,
    status_code=status.HTTP_201_CREATED,
)
async def reverse_journal(
    journal_id: UUID,
    body: JournalReverseRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> JournalDetailView:
    original = await session.get(JournalEntry, journal_id)
    if original is None:
        raise ApiError(404, "JOURNAL_NOT_FOUND", "Journal entry was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_FINANCE_RECONCILIATION},
        legal_entity_id=original.legal_entity_id,
        action="JOURNAL_REVERSE",
        target_id=str(original.id),
        correlation_id=correlation_id,
    )
    try:
        reversal = await reverse_journal_with_approval(
            session,
            original_entry_id=original.id,
            approval_request_id=body.approval_request_id,
            idempotency_key=idempotency_key,
            actor_reference=principal.identity_id,
            actor_type=principal.identity_type,
            correlation_id=correlation_id,
            reason=body.reason,
        )
    except JournalError as exc:
        _raise_journal_error(exc)
        raise AssertionError("unreachable") from exc
    await session.commit()
    return await _detail(session, reversal)
