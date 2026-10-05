from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.approval import (
    approval_payload_hash,
    assert_approval_execution_eligible,
    expire_if_needed,
    get_approval_for_update,
)
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.application.journal import account_totals
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    AssetPosition,
    AuditEvent,
    JournalEntry,
    JournalPosting,
    ValuationObservation,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_OPERATIONS,
    ROLE_RISK,
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1")

_ALLOWED_MAKER_ROLES = {
    ROLE_OPERATIONS,
    ROLE_RISK,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_GOVERNANCE_APPROVER,
}
_ALLOWED_CHECKER_ROLES = {
    ROLE_RISK,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_GOVERNANCE_APPROVER,
}


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ApprovalCreate(BaseModel):
    action_type: str = Field(min_length=1, max_length=160)
    target_type: str = Field(min_length=1, max_length=120)
    target_id: str = Field(min_length=1, max_length=160)
    target_aggregate_version: int | None = Field(default=None, ge=0)
    required_checker_role: Literal[
        "RISK",
        "FINANCE_RECONCILIATION",
        "LEGAL_COMPLIANCE",
        "GOVERNANCE_APPROVER",
    ]
    scope_type: Literal["GLOBAL", "PROGRAM", "PARTICIPANT", "ASSET_TYPE", "ASSET_POSITION"]
    scope_id: UUID | None = None
    payload: dict[str, Any]
    reason: str | None = Field(default=None, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> ApprovalCreate:
        if self.scope_type == SCOPE_GLOBAL and self.scope_id is not None:
            raise ValueError("GLOBAL scope must not include scope_id")
        if self.scope_type != SCOPE_GLOBAL and self.scope_id is None:
            raise ValueError("Non-GLOBAL scope requires scope_id")
        return self


class ApprovalView(OrmModel):
    id: UUID
    action_type: str
    target_type: str
    target_id: str
    target_aggregate_version: int | None
    maker_identity_id: UUID
    checker_identity_id: UUID | None
    required_checker_role: str
    scope_type: str
    scope_id: UUID | None
    payload_hash: str
    reason: str | None
    evidence_refs: list[str]
    status: str
    expires_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    cancelled_at: datetime | None
    version: int


class ApprovalDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ApprovalValidation(BaseModel):
    payload: dict[str, Any]
    current_target_version: int | None = Field(default=None, ge=0)


class ApprovalEligibility(BaseModel):
    approval_request_id: UUID
    eligible: bool
    status: str


class ValuationCreate(BaseModel):
    valued_quantity: Decimal = Field(ge=0, max_digits=38, decimal_places=18)
    unit_price: Decimal = Field(ge=0, max_digits=38, decimal_places=18)
    valuation_currency: str = Field(min_length=1, max_length=16)
    fx_rate: Decimal | None = Field(default=None, gt=0, max_digits=38, decimal_places=18)
    source_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=255)
    source_version_reference: str | None = Field(default=None, max_length=255)
    observed_at: datetime
    valid_until: datetime | None = None
    evidence_reference: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_window(self) -> ValuationCreate:
        if self.valid_until is not None and self.valid_until < self.observed_at:
            raise ValueError("valid_until cannot precede observed_at")
        return self


class ValuationView(OrmModel):
    id: UUID
    asset_position_id: UUID
    valued_quantity: Decimal
    unit_price: Decimal
    valuation_currency: str
    fx_rate: Decimal | None
    gross_market_value: Decimal
    source_name: str
    source_reference: str
    source_version_reference: str | None
    observed_at: datetime
    received_at: datetime
    valid_until: datetime | None
    freshness_status: str
    evidence_reference: str | None
    created_by: UUID
    created_at: datetime
    current_freshness_status: str | None = None


class JournalPostingView(OrmModel):
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
    debit_amount: Decimal
    credit_amount: Decimal
    currency: str


class JournalEntryView(OrmModel):
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
    postings: list[JournalPostingView]


class JournalBalanceView(BaseModel):
    account_code: str
    legal_entity_id: UUID
    currency: str
    debit_total: Decimal
    credit_total: Decimal
    net_debit: Decimal


async def _authorize(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    scope_type: str,
    scope_id: UUID | None,
    allow_global: bool,
    action: str,
    target_type: str,
    target_id: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=scope_type,
            scope_id=scope_id,
            allow_global=allow_global,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for requested scope") from exc


async def _approval_read_access(
    session: AsyncSession,
    *,
    principal: Principal,
    approval: ApprovalRequest,
    correlation_id: UUID,
) -> None:
    if principal.identity_id == approval.maker_identity_id:
        return
    await _authorize(
        session,
        principal=principal,
        roles={approval.required_checker_role, ROLE_AUDITOR},
        scope_type=approval.scope_type,
        scope_id=approval.scope_id,
        allow_global=approval.scope_type != SCOPE_GLOBAL,
        action="APPROVAL_REQUEST_READ",
        target_type="ApprovalRequest",
        target_id=str(approval.id),
        correlation_id=correlation_id,
    )


def _current_freshness(observation: ValuationObservation) -> str:
    if observation.valid_until is None:
        return "UNKNOWN"
    return "FRESH" if datetime.now(UTC) <= observation.valid_until else "STALE"


def _valuation_view(observation: ValuationObservation) -> ValuationView:
    view = ValuationView.model_validate(observation)
    view.current_freshness_status = _current_freshness(observation)
    return view


@router.post(
    "/approval-requests",
    response_model=ApprovalView,
    status_code=status.HTTP_201_CREATED,
)
async def create_approval_request(
    body: ApprovalCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ApprovalView:
    if body.required_checker_role not in _ALLOWED_CHECKER_ROLES:
        raise ApiError(422, "APPROVAL_CHECKER_ROLE_INVALID", "Checker role is not allowed")
    await _authorize(
        session,
        principal=principal,
        roles=_ALLOWED_MAKER_ROLES,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        allow_global=body.scope_type != SCOPE_GLOBAL,
        action="APPROVAL_REQUEST_CREATE",
        target_type=body.target_type,
        target_id=body.target_id,
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"approval_request:create:{principal.identity_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return ApprovalView.model_validate(replay)

    request = ApprovalRequest(
        action_type=body.action_type,
        target_type=body.target_type,
        target_id=body.target_id,
        target_aggregate_version=body.target_aggregate_version,
        maker_identity_id=principal.identity_id,
        required_checker_role=body.required_checker_role,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        payload_hash=approval_payload_hash(body.payload),
        reason=body.reason,
        evidence_refs=body.evidence_refs,
        status="PENDING",
        expires_at=body.expires_at,
    )
    session.add(request)
    await session.flush()
    view = ApprovalView.model_validate(request)
    append_audit(
        session,
        aggregate_type="ApprovalRequest",
        aggregate_id=str(request.id),
        aggregate_version=request.version,
        action="APPROVAL_REQUEST_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=view.model_dump(mode="json"),
        scope={"scope_type": request.scope_type, "scope_id": str(request.scope_id) if request.scope_id else None},
    )
    complete_idempotency(record, status_code=201, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.get("/approval-requests/{approval_id}", response_model=ApprovalView)
async def get_approval_request(
    approval_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ApprovalView:
    request = await session.get(ApprovalRequest, approval_id)
    if request is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Approval Request was not found")
    await _approval_read_access(
        session,
        principal=principal,
        approval=request,
        correlation_id=correlation_id,
    )
    if expire_if_needed(request):
        await session.commit()
    return ApprovalView.model_validate(request)


@router.post("/approval-requests/{approval_id}/approve", response_model=ApprovalView)
async def approve_request(
    approval_id: UUID,
    body: ApprovalDecision,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ApprovalView:
    request = await get_approval_for_update(session, approval_id)
    if expire_if_needed(request):
        await session.commit()
        raise ApiError(409, "APPROVAL_EXPIRED", "Approval Request is expired")
    if request.status != "PENDING":
        raise ApiError(409, "APPROVAL_STATE_CONFLICT", "Approval Request is not PENDING")
    if principal.identity_id == request.maker_identity_id:
        append_audit(
            session,
            aggregate_type="ApprovalRequest",
            aggregate_id=str(request.id),
            aggregate_version=request.version,
            action="APPROVAL_REQUEST_APPROVE",
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
            outcome="DENIED",
            reason_code="APPROVAL_SELF_APPROVAL_FORBIDDEN",
            scope={"scope_type": request.scope_type, "scope_id": str(request.scope_id) if request.scope_id else None},
        )
        await session.commit()
        raise ApiError(403, "APPROVAL_SELF_APPROVAL_FORBIDDEN", "Maker cannot approve own request")
    await _authorize(
        session,
        principal=principal,
        roles={request.required_checker_role},
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        allow_global=request.scope_type != SCOPE_GLOBAL,
        action="APPROVAL_REQUEST_APPROVE",
        target_type="ApprovalRequest",
        target_id=str(request.id),
        correlation_id=correlation_id,
    )
    request.checker_identity_id = principal.identity_id
    request.status = "APPROVED"
    request.approved_at = datetime.now(UTC)
    request.version += 1
    if body.reason is not None:
        request.reason = body.reason
    append_audit(
        session,
        aggregate_type="ApprovalRequest",
        aggregate_id=str(request.id),
        aggregate_version=request.version,
        action="APPROVAL_REQUEST_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": request.scope_type, "scope_id": str(request.scope_id) if request.scope_id else None},
    )
    await session.commit()
    return ApprovalView.model_validate(request)


@router.post("/approval-requests/{approval_id}/reject", response_model=ApprovalView)
async def reject_request(
    approval_id: UUID,
    body: ApprovalDecision,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ApprovalView:
    request = await get_approval_for_update(session, approval_id)
    if expire_if_needed(request):
        await session.commit()
        raise ApiError(409, "APPROVAL_EXPIRED", "Approval Request is expired")
    if request.status != "PENDING":
        raise ApiError(409, "APPROVAL_STATE_CONFLICT", "Approval Request is not PENDING")
    if principal.identity_id == request.maker_identity_id:
        raise ApiError(403, "APPROVAL_SELF_APPROVAL_FORBIDDEN", "Maker cannot reject own request")
    await _authorize(
        session,
        principal=principal,
        roles={request.required_checker_role},
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        allow_global=request.scope_type != SCOPE_GLOBAL,
        action="APPROVAL_REQUEST_REJECT",
        target_type="ApprovalRequest",
        target_id=str(request.id),
        correlation_id=correlation_id,
    )
    request.checker_identity_id = principal.identity_id
    request.status = "REJECTED"
    request.rejected_at = datetime.now(UTC)
    request.version += 1
    if body.reason is not None:
        request.reason = body.reason
    append_audit(
        session,
        aggregate_type="ApprovalRequest",
        aggregate_id=str(request.id),
        aggregate_version=request.version,
        action="APPROVAL_REQUEST_REJECT",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": request.scope_type, "scope_id": str(request.scope_id) if request.scope_id else None},
    )
    await session.commit()
    return ApprovalView.model_validate(request)


@router.post("/approval-requests/{approval_id}/cancel", response_model=ApprovalView)
async def cancel_request(
    approval_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ApprovalView:
    request = await get_approval_for_update(session, approval_id)
    if request.status != "PENDING":
        raise ApiError(409, "APPROVAL_STATE_CONFLICT", "Approval Request is not PENDING")
    if principal.identity_id != request.maker_identity_id:
        raise ApiError(403, "AUTHORIZATION_DENIED", "Only the maker may cancel the request")
    request.status = "CANCELLED"
    request.cancelled_at = datetime.now(UTC)
    request.version += 1
    append_audit(
        session,
        aggregate_type="ApprovalRequest",
        aggregate_id=str(request.id),
        aggregate_version=request.version,
        action="APPROVAL_REQUEST_CANCEL",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": request.scope_type, "scope_id": str(request.scope_id) if request.scope_id else None},
    )
    await session.commit()
    return ApprovalView.model_validate(request)


@router.post(
    "/approval-requests/{approval_id}/validate",
    response_model=ApprovalEligibility,
)
async def validate_approval(
    approval_id: UUID,
    body: ApprovalValidation,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ApprovalEligibility:
    request = await session.get(ApprovalRequest, approval_id)
    if request is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Approval Request was not found")
    await _approval_read_access(
        session,
        principal=principal,
        approval=request,
        correlation_id=correlation_id,
    )
    assert_approval_execution_eligible(
        request,
        payload=body.payload,
        current_target_version=body.current_target_version,
    )
    return ApprovalEligibility(
        approval_request_id=request.id,
        eligible=True,
        status=request.status,
    )


@router.post(
    "/asset-positions/{position_id}/valuation-observations",
    response_model=ValuationView,
    status_code=status.HTTP_201_CREATED,
)
async def create_valuation_observation(
    position_id: UUID,
    body: ValuationCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ValuationView:
    position = await session.get(AssetPosition, position_id)
    if position is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset Position was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_RISK},
        scope_type=SCOPE_PROGRAM,
        scope_id=position.program_id,
        allow_global=True,
        action="VALUATION_OBSERVATION_CREATE",
        target_type="AssetPosition",
        target_id=str(position.id),
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"valuation:create:{position.id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return ValuationView.model_validate(replay)

    received_at = datetime.now(UTC)
    fx = body.fx_rate if body.fx_rate is not None else Decimal("1")
    gross = body.valued_quantity * body.unit_price * fx
    if body.valid_until is None:
        freshness = "UNKNOWN"
    else:
        freshness = "FRESH" if received_at <= body.valid_until else "STALE"
    observation = ValuationObservation(
        asset_position_id=position.id,
        valued_quantity=body.valued_quantity,
        unit_price=body.unit_price,
        valuation_currency=body.valuation_currency,
        fx_rate=body.fx_rate,
        gross_market_value=gross,
        source_name=body.source_name,
        source_reference=body.source_reference,
        source_version_reference=body.source_version_reference,
        observed_at=body.observed_at,
        received_at=received_at,
        valid_until=body.valid_until,
        freshness_status=freshness,
        evidence_reference=body.evidence_reference,
        created_by=principal.identity_id,
    )
    session.add(observation)
    await session.flush()
    view = _valuation_view(observation)
    append_audit(
        session,
        aggregate_type="ValuationObservation",
        aggregate_id=str(observation.id),
        aggregate_version=None,
        action="VALUATION_OBSERVATION_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=view.model_dump(mode="json"),
        evidence_reference=body.evidence_reference,
        scope={"scope_type": SCOPE_PROGRAM, "scope_id": str(position.program_id)},
    )
    complete_idempotency(record, status_code=201, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.get(
    "/asset-positions/{position_id}/valuation-observations",
    response_model=list[ValuationView],
)
async def list_valuation_observations(
    position_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[ValuationView]:
    position = await session.get(AssetPosition, position_id)
    if position is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset Position was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_RISK, ROLE_OPERATIONS, ROLE_AUDITOR},
        scope_type=SCOPE_PROGRAM,
        scope_id=position.program_id,
        allow_global=True,
        action="VALUATION_OBSERVATION_LIST",
        target_type="AssetPosition",
        target_id=str(position.id),
        correlation_id=correlation_id,
    )
    rows = (
        await session.scalars(
            select(ValuationObservation)
            .where(ValuationObservation.asset_position_id == position.id)
            .order_by(ValuationObservation.observed_at.desc(), ValuationObservation.created_at.desc())
        )
    ).all()
    return [_valuation_view(row) for row in rows]


@router.get(
    "/asset-positions/{position_id}/valuation-observations/latest",
    response_model=ValuationView,
)
async def latest_valuation_observation(
    position_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ValuationView:
    position = await session.get(AssetPosition, position_id)
    if position is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset Position was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_RISK, ROLE_OPERATIONS, ROLE_AUDITOR},
        scope_type=SCOPE_PROGRAM,
        scope_id=position.program_id,
        allow_global=True,
        action="VALUATION_OBSERVATION_READ_LATEST",
        target_type="AssetPosition",
        target_id=str(position.id),
        correlation_id=correlation_id,
    )
    observation = await session.scalar(
        select(ValuationObservation)
        .where(ValuationObservation.asset_position_id == position.id)
        .order_by(ValuationObservation.observed_at.desc(), ValuationObservation.created_at.desc())
        .limit(1)
    )
    if observation is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "No valuation observation exists")
    return _valuation_view(observation)


async def _authorize_journal_read(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
    target_id: str,
) -> None:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="JOURNAL_READ",
        target_type="Journal",
        target_id=target_id,
        correlation_id=correlation_id,
    )


@router.get("/journal/entries/{entry_id}", response_model=JournalEntryView)
async def get_journal_entry(
    entry_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> JournalEntryView:
    await _authorize_journal_read(
        session,
        principal=principal,
        correlation_id=correlation_id,
        target_id=str(entry_id),
    )
    entry = await session.get(JournalEntry, entry_id)
    if entry is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Journal entry was not found")
    postings = (
        await session.scalars(
            select(JournalPosting)
            .where(JournalPosting.journal_entry_id == entry.id)
            .order_by(JournalPosting.created_at, JournalPosting.id)
        )
    ).all()
    return JournalEntryView(
        **JournalEntryView.model_validate(
            {
                "id": entry.id,
                "business_event_type": entry.business_event_type,
                "business_event_id": entry.business_event_id,
                "legal_entity_id": entry.legal_entity_id,
                "currency": entry.currency,
                "state": entry.state,
                "effective_at": entry.effective_at,
                "posted_at": entry.posted_at,
                "reversal_of_entry_id": entry.reversal_of_entry_id,
                "actor_reference": entry.actor_reference,
                "correlation_id": entry.correlation_id,
                "causation_id": entry.causation_id,
                "reason": entry.reason,
                "postings": [JournalPostingView.model_validate(row) for row in postings],
            }
        ).model_dump()
    )


@router.get("/journal/accounts/{account_code}/balance", response_model=JournalBalanceView)
async def get_journal_balance(
    account_code: str,
    legal_entity_id: UUID = Query(...),
    currency: str = Query(..., min_length=1, max_length=16),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> JournalBalanceView:
    await _authorize_journal_read(
        session,
        principal=principal,
        correlation_id=correlation_id,
        target_id=account_code,
    )
    debit, credit = await account_totals(
        session,
        account_code=account_code,
        currency=currency,
        legal_entity_id=legal_entity_id,
    )
    return JournalBalanceView(
        account_code=account_code,
        legal_entity_id=legal_entity_id,
        currency=currency,
        debit_total=debit,
        credit_total=credit,
        net_debit=debit - credit,
    )
