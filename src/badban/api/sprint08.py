from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.application.journal import JournalError, reverse_journal
from badban.infrastructure.persistence.models import JournalEntry, JournalPosting
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    SCOPE_LEGAL_ENTITY,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/finance")


class JournalPostingView(BaseModel):
    id: UUID
    account_code: str
    economic_owner_type: str
    economic_owner_id: UUID | None
    participant_id: UUID | None
    program_id: UUID | None
    provider_id: UUID | None
    asset_position_id: UUID | None
    guarantee_case_id: UUID | None
    claim_id: UUID | None
    reserve_account_id: UUID | None
    debit_amount: str = Field(json_schema_extra={"format": "decimal"})
    credit_amount: str = Field(json_schema_extra={"format": "decimal"})
    currency: str


class JournalEntryView(BaseModel):
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
    reason: str | None
    policy_version_reference: str | None
    posting_template_code: str | None
    posting_template_version: str | None
    account_mapping_reference: str | None
    evidence_reference: str | None
    postings: list[JournalPostingView]


class JournalReverseRequest(BaseModel):
    approval_request_id: UUID
    reason: str = Field(min_length=1, max_length=500)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


async def _authorize_journal(
    session: AsyncSession,
    *,
    principal: Principal,
    entry: JournalEntry,
    roles: set[str],
    action: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=SCOPE_LEGAL_ENTITY,
            scope_id=entry.legal_entity_id,
            allow_global=True,
            action=action,
            target_type="JournalEntry",
            target_id=str(entry.id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for journal scope") from exc


async def _entry_view(session: AsyncSession, entry: JournalEntry) -> JournalEntryView:
    postings = (
        await session.scalars(
            select(JournalPosting)
            .where(JournalPosting.journal_entry_id == entry.id)
            .order_by(JournalPosting.created_at, JournalPosting.id)
        )
    ).all()
    return JournalEntryView(
        id=entry.id,
        business_event_type=entry.business_event_type,
        business_event_id=entry.business_event_id,
        legal_entity_id=entry.legal_entity_id,
        currency=entry.currency,
        state=entry.state,
        effective_at=entry.effective_at,
        posted_at=entry.posted_at,
        reversal_of_entry_id=entry.reversal_of_entry_id,
        actor_reference=entry.actor_reference,
        correlation_id=entry.correlation_id,
        causation_id=entry.causation_id,
        reason=entry.reason,
        policy_version_reference=entry.policy_version_reference,
        posting_template_code=entry.posting_template_code,
        posting_template_version=entry.posting_template_version,
        account_mapping_reference=entry.account_mapping_reference,
        evidence_reference=entry.evidence_reference,
        postings=[
            JournalPostingView(
                id=p.id,
                account_code=p.account_code,
                economic_owner_type=p.economic_owner_type,
                economic_owner_id=p.economic_owner_id,
                participant_id=p.participant_id,
                program_id=p.program_id,
                provider_id=p.provider_id,
                asset_position_id=p.asset_position_id,
                guarantee_case_id=p.guarantee_case_id,
                claim_id=p.claim_id,
                reserve_account_id=p.reserve_account_id,
                debit_amount=_decimal(p.debit_amount),
                credit_amount=_decimal(p.credit_amount),
                currency=p.currency,
            )
            for p in postings
        ],
    )


@router.get(
    "/journals",
    response_model=list[JournalEntryView],
    summary="List journals for one authorized legal entity",
    description="Requires FINANCE_RECONCILIATION or AUDITOR in the legal-entity scope.",
)
async def list_journals(
    legal_entity_id: UUID = Query(...),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[JournalEntryView]:
    probe = JournalEntry(id=UUID(int=0), legal_entity_id=legal_entity_id)
    await _authorize_journal(
        session,
        principal=principal,
        entry=probe,
        roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
        action="JOURNAL_LIST",
        correlation_id=correlation_id,
    )
    entries = (
        await session.scalars(
            select(JournalEntry)
            .where(JournalEntry.legal_entity_id == legal_entity_id)
            .order_by(JournalEntry.posted_at.desc(), JournalEntry.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [await _entry_view(session, entry) for entry in entries]


@router.get(
    "/journals/{entry_id}",
    response_model=JournalEntryView,
    summary="Read journal",
    description="Requires FINANCE_RECONCILIATION or AUDITOR in the journal legal-entity scope.",
)
async def get_journal(
    entry_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> JournalEntryView:
    entry = await session.get(JournalEntry, entry_id)
    if entry is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Journal entry was not found")
    await _authorize_journal(
        session,
        principal=principal,
        entry=entry,
        roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
        action="JOURNAL_READ",
        correlation_id=correlation_id,
    )
    return await _entry_view(session, entry)


@router.post(
    "/journals/{entry_id}/reverse",
    response_model=JournalEntryView,
    summary="Reverse journal",
    description=(
        "Requires FINANCE_RECONCILIATION in the journal legal-entity scope and an approved "
        "GOVERNANCE_APPROVER maker-checker request bound to the exact reversal payload."
    ),
    responses={
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "RESOURCE_NOT_FOUND"},
        409: {"description": "Maker-checker, idempotency, state or reversal conflict"},
        422: {"description": "Invalid reversal request"},
    },
)
async def reverse_journal_endpoint(
    entry_id: UUID,
    body: JournalReverseRequest,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> JournalEntryView:
    entry = await session.get(JournalEntry, entry_id)
    if entry is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Journal entry was not found")
    await _authorize_journal(
        session,
        principal=principal,
        entry=entry,
        roles={ROLE_FINANCE_RECONCILIATION},
        action="JOURNAL_REVERSE",
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"journal:reverse:{entry.id}:{principal.identity_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return JournalEntryView.model_validate(replay)

    try:
        reversal = await reverse_journal(
            session,
            original_entry_id=entry.id,
            idempotency_key=f"journal-reversal:{entry.id}:{idempotency_key}",
            actor_reference=principal.identity_id,
            actor_type=principal.identity_type,
            correlation_id=correlation_id,
            reason=body.reason,
            approval_id=body.approval_request_id,
            require_approval=True,
        )
    except JournalError as exc:
        status_code = 404 if exc.code == "JOURNAL_NOT_FOUND" else 409
        raise ApiError(status_code, exc.code, str(exc)) from exc

    view = await _entry_view(session, reversal)
    complete_idempotency(record, status_code=200, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view
