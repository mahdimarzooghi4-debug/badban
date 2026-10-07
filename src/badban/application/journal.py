from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.approval import assert_approval_execution_eligible
from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    JournalEntry,
    JournalPosting,
    OutboxMessage,
    RoleGrant,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_FINANCE_RECONCILIATION,
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_GLOBAL,
    SCOPE_LEGAL_ENTITY,
)


class JournalError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class JournalLine:
    account_code: str
    economic_owner_type: str
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    economic_owner_id: UUID | None = None
    participant_id: UUID | None = None
    program_id: UUID | None = None
    provider_id: UUID | None = None
    asset_position_id: UUID | None = None
    guarantee_case_id: UUID | None = None
    claim_id: UUID | None = None
    reserve_account_id: UUID | None = None


def _validate_decimal_storage(amount: Decimal) -> None:
    if not amount.is_finite():
        raise JournalError(
            "JOURNAL_AMOUNT_PRECISION_INVALID",
            "Journal amounts must be finite decimal values",
        )
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int):
        raise JournalError(
            "JOURNAL_AMOUNT_PRECISION_INVALID",
            "Journal amounts must use finite decimal exponents",
        )
    fractional_digits = max(-exponent, 0)
    integer_digits = max(len(amount.as_tuple().digits) + exponent, 0)
    if fractional_digits > 18 or integer_digits > 20:
        raise JournalError(
            "JOURNAL_AMOUNT_PRECISION_INVALID",
            "Journal amount exceeds NUMERIC(38,18) storage boundary",
        )


def _validate_lines(lines: list[JournalLine]) -> None:
    if len(lines) < 2:
        raise JournalError("JOURNAL_LINES_INVALID", "A journal requires at least two postings")
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for line in lines:
        if not line.account_code.strip() or not line.economic_owner_type.strip():
            raise JournalError(
                "JOURNAL_LINES_INVALID",
                "Account code and economic owner type are required",
            )
        debit = line.debit_amount
        credit = line.credit_amount
        _validate_decimal_storage(debit)
        _validate_decimal_storage(credit)
        if debit < 0 or credit < 0:
            raise JournalError(
                "JOURNAL_LINES_INVALID",
                "Debit and credit amounts cannot be negative",
            )
        if (debit > 0) == (credit > 0):
            raise JournalError(
                "JOURNAL_LINES_INVALID",
                "Each posting must have exactly one positive side",
            )
        debit_total += debit
        credit_total += credit
    if debit_total <= 0 or debit_total != credit_total:
        raise JournalError(
            "JOURNAL_UNBALANCED",
            "Posted journal debit and credit totals must balance exactly",
        )


def _request_payload(
    *,
    business_event_type: str,
    business_event_id: str,
    legal_entity_id: UUID,
    currency: str,
    effective_at: datetime | None,
    reversal_of_entry_id: UUID | None,
    reason: str | None,
    actor_reference: UUID,
    causation_id: UUID | None,
    policy_version_reference: str | None,
    posting_template_reference: str | None,
    account_mapping_reference: str | None,
    evidence_reference: str | None,
    settlement_reference: str | None,
    lines: list[JournalLine],
) -> dict[str, Any]:
    return {
        "business_event_type": business_event_type,
        "business_event_id": business_event_id,
        "legal_entity_id": str(legal_entity_id),
        "currency": currency,
        "effective_at": effective_at.isoformat() if effective_at is not None else None,
        "reversal_of_entry_id": str(reversal_of_entry_id) if reversal_of_entry_id else None,
        "reason": reason,
        "actor_reference": str(actor_reference),
        "causation_id": str(causation_id) if causation_id else None,
        "policy_version_reference": policy_version_reference,
        "posting_template_reference": posting_template_reference,
        "account_mapping_reference": account_mapping_reference,
        "evidence_reference": evidence_reference,
        "settlement_reference": settlement_reference,
        "lines": [asdict(line) for line in lines],
    }


async def _lock_idempotency_key(session: AsyncSession, idempotency_key: str) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"journal:{idempotency_key}"},
    )


def _material_payload(
    entry: JournalEntry,
    *,
    actor_type: str,
    approval_request_id: UUID | None,
) -> dict[str, Any]:
    return {
        "journal_entry_id": str(entry.id),
        "business_event_type": entry.business_event_type,
        "business_event_id": entry.business_event_id,
        "legal_entity_id": str(entry.legal_entity_id),
        "currency": entry.currency,
        "effective_at": entry.effective_at.isoformat(),
        "posted_at": entry.posted_at.isoformat() if entry.posted_at is not None else None,
        "reversal_of_entry_id": (
            str(entry.reversal_of_entry_id) if entry.reversal_of_entry_id is not None else None
        ),
        "actor_reference": str(entry.actor_reference),
        "actor_type": actor_type,
        "correlation_id": str(entry.correlation_id),
        "causation_id": str(entry.causation_id) if entry.causation_id is not None else None,
        "policy_version_reference": entry.policy_version_reference,
        "posting_template_reference": entry.posting_template_reference,
        "account_mapping_reference": entry.account_mapping_reference,
        "evidence_reference": entry.evidence_reference,
        "settlement_reference": entry.settlement_reference,
        "reason": entry.reason,
        "approval_request_id": (
            str(approval_request_id) if approval_request_id is not None else None
        ),
    }


def _append_material_trace(
    session: AsyncSession,
    *,
    entry: JournalEntry,
    actor_type: str,
    event_type: str,
    approval_request_id: UUID | None,
) -> None:
    payload = _material_payload(
        entry,
        actor_type=actor_type,
        approval_request_id=approval_request_id,
    )
    action = "JOURNAL_REVERSED" if event_type == "JournalReversed" else "JOURNAL_POSTED"
    append_audit(
        session,
        aggregate_type="JournalEntry",
        aggregate_id=str(entry.id),
        aggregate_version=None,
        action=action,
        actor_type=actor_type,
        actor_id=entry.actor_reference,
        correlation_id=entry.correlation_id,
        outcome="SUCCESS",
        new_state=payload,
        scope={"scope_type": SCOPE_LEGAL_ENTITY, "scope_id": str(entry.legal_entity_id)},
    )
    session.add(
        OutboxMessage(
            event_type=event_type,
            event_version=1,
            aggregate_type="JournalEntry",
            aggregate_id=str(entry.id),
            aggregate_version=1,
            payload=payload,
            correlation_id=entry.correlation_id,
            causation_id=entry.causation_id,
            occurred_at=entry.posted_at or datetime.now(UTC),
        )
    )


async def _post_journal(
    session: AsyncSession,
    *,
    business_event_type: str,
    business_event_id: str,
    legal_entity_id: UUID,
    currency: str,
    idempotency_key: str,
    actor_reference: UUID,
    correlation_id: UUID,
    lines: list[JournalLine],
    effective_at: datetime | None = None,
    causation_id: UUID | None = None,
    policy_version_reference: str | None = None,
    posting_template_reference: str | None = None,
    account_mapping_reference: str | None = None,
    evidence_reference: str | None = None,
    settlement_reference: str | None = None,
    reversal_of_entry_id: UUID | None = None,
    reason: str | None = None,
    actor_type: str = "SYSTEM",
    material_event_type: str = "JournalPosted",
    approval_request_id: UUID | None = None,
) -> JournalEntry:
    _validate_lines(lines)
    if not business_event_type.strip() or not business_event_id.strip():
        raise JournalError(
            "JOURNAL_EVENT_INVALID",
            "Business event type and id are required",
        )
    if not currency.strip():
        raise JournalError("JOURNAL_CURRENCY_INVALID", "Journal currency is required")
    if not idempotency_key.strip():
        raise JournalError("JOURNAL_IDEMPOTENCY_KEY_INVALID", "Journal idempotency key is required")
    if reversal_of_entry_id is not None and (reason is None or not reason.strip()):
        raise JournalError("JOURNAL_REVERSAL_REASON_REQUIRED", "Reversal reason is required")
    if material_event_type not in {"JournalPosted", "JournalReversed"}:
        raise JournalError("JOURNAL_EVENT_INVALID", "Unsupported journal material event")

    payload = _request_payload(
        business_event_type=business_event_type,
        business_event_id=business_event_id,
        legal_entity_id=legal_entity_id,
        currency=currency,
        effective_at=effective_at,
        reversal_of_entry_id=reversal_of_entry_id,
        reason=reason,
        actor_reference=actor_reference,
        causation_id=causation_id,
        policy_version_reference=policy_version_reference,
        posting_template_reference=posting_template_reference,
        account_mapping_reference=account_mapping_reference,
        evidence_reference=evidence_reference,
        settlement_reference=settlement_reference,
        lines=lines,
    )
    request_hash = canonical_request_hash(payload)
    await _lock_idempotency_key(session, idempotency_key)
    existing = await session.scalar(
        select(JournalEntry)
        .where(JournalEntry.idempotency_key == idempotency_key)
        .with_for_update()
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise JournalError(
                "JOURNAL_IDEMPOTENCY_CONFLICT",
                "Journal idempotency key was used with a different request",
            )
        return existing

    if reversal_of_entry_id is not None:
        prior_reversal = await session.scalar(
            select(JournalEntry)
            .where(JournalEntry.reversal_of_entry_id == reversal_of_entry_id)
            .with_for_update()
        )
        if prior_reversal is not None:
            raise JournalError(
                "JOURNAL_ALREADY_REVERSED",
                "Journal entry already has a reversal",
            )

    now = datetime.now(UTC)
    effective = effective_at or now
    entry = JournalEntry(
        business_event_type=business_event_type,
        business_event_id=business_event_id,
        legal_entity_id=legal_entity_id,
        currency=currency,
        state="PREPARED",
        effective_at=effective,
        posted_at=None,
        reversal_of_entry_id=reversal_of_entry_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        actor_reference=actor_reference,
        correlation_id=correlation_id,
        causation_id=causation_id,
        policy_version_reference=policy_version_reference,
        posting_template_reference=posting_template_reference,
        account_mapping_reference=account_mapping_reference,
        evidence_reference=evidence_reference,
        settlement_reference=settlement_reference,
        reason=reason,
    )
    session.add(entry)
    await session.flush()

    session.add_all(
        [
            JournalPosting(
                journal_entry_id=entry.id,
                account_code=line.account_code,
                legal_entity_id=legal_entity_id,
                economic_owner_type=line.economic_owner_type,
                economic_owner_id=line.economic_owner_id,
                participant_id=line.participant_id,
                program_id=line.program_id,
                provider_id=line.provider_id,
                asset_position_id=line.asset_position_id,
                guarantee_case_id=line.guarantee_case_id,
                claim_id=line.claim_id,
                reserve_account_id=line.reserve_account_id,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                currency=currency,
            )
            for line in lines
        ]
    )
    await session.flush()
    entry.state = "POSTED"
    entry.posted_at = now
    await session.flush()
    _append_material_trace(
        session,
        entry=entry,
        actor_type=actor_type,
        event_type=material_event_type,
        approval_request_id=approval_request_id,
    )
    await session.flush()
    return entry


async def post_journal(
    session: AsyncSession,
    *,
    business_event_type: str,
    business_event_id: str,
    legal_entity_id: UUID,
    currency: str,
    idempotency_key: str,
    actor_reference: UUID,
    correlation_id: UUID,
    lines: list[JournalLine],
    effective_at: datetime | None = None,
    causation_id: UUID | None = None,
    policy_version_reference: str | None = None,
    posting_template_reference: str | None = None,
    account_mapping_reference: str | None = None,
    evidence_reference: str | None = None,
    settlement_reference: str | None = None,
    reason: str | None = None,
    actor_type: str = "SYSTEM",
) -> JournalEntry:
    return await _post_journal(
        session,
        business_event_type=business_event_type,
        business_event_id=business_event_id,
        legal_entity_id=legal_entity_id,
        currency=currency,
        idempotency_key=idempotency_key,
        actor_reference=actor_reference,
        correlation_id=correlation_id,
        lines=lines,
        effective_at=effective_at,
        causation_id=causation_id,
        policy_version_reference=policy_version_reference,
        posting_template_reference=posting_template_reference,
        account_mapping_reference=account_mapping_reference,
        evidence_reference=evidence_reference,
        settlement_reference=settlement_reference,
        reversal_of_entry_id=None,
        reason=reason,
        actor_type=actor_type,
        material_event_type="JournalPosted",
        approval_request_id=None,
    )


def reversal_approval_payload(original: JournalEntry, reason: str) -> dict[str, Any]:
    return {
        "action": "JOURNAL_REVERSAL",
        "target": {
            "type": "JournalEntry",
            "id": str(original.id),
        },
        "reason": reason,
        "expected": {
            "state": original.state,
            "legal_entity_id": str(original.legal_entity_id),
            "currency": original.currency,
            "posted_at": (
                original.posted_at.isoformat() if original.posted_at is not None else None
            ),
            "reversal_of_entry_id": (
                str(original.reversal_of_entry_id)
                if original.reversal_of_entry_id is not None
                else None
            ),
        },
    }


async def _assert_finance_initiator_is_active(
    session: AsyncSession,
    *,
    identity_id: UUID,
    legal_entity_id: UUID,
) -> None:
    now = datetime.now(UTC)
    grant = await session.scalar(
        select(RoleGrant)
        .where(
            RoleGrant.identity_id == identity_id,
            RoleGrant.role_code == ROLE_FINANCE_RECONCILIATION,
            RoleGrant.status == "ACTIVE",
            RoleGrant.valid_from <= now,
            or_(RoleGrant.valid_until.is_(None), RoleGrant.valid_until > now),
            or_(
                (RoleGrant.scope_type == SCOPE_LEGAL_ENTITY)
                & (RoleGrant.scope_id == legal_entity_id),
                (RoleGrant.scope_type == SCOPE_GLOBAL) & (RoleGrant.scope_id.is_(None)),
            ),
        )
        .limit(1)
    )
    if grant is None:
        raise JournalError(
            "JOURNAL_REVERSAL_INITIATOR_NOT_AUTHORIZED",
            "Journal reversal initiator no longer has an active finance reconciliation grant",
        )


async def _assert_governance_checker_is_active(
    session: AsyncSession,
    *,
    request: ApprovalRequest,
    legal_entity_id: UUID,
) -> None:
    checker_id = request.checker_identity_id
    if checker_id is None or checker_id == request.maker_identity_id:
        raise JournalError(
            "JOURNAL_REVERSAL_APPROVAL_BINDING_INVALID",
            "Journal reversal approval requires a distinct checker",
        )
    now = datetime.now(UTC)
    grant = await session.scalar(
        select(RoleGrant)
        .where(
            RoleGrant.identity_id == checker_id,
            RoleGrant.role_code == ROLE_GOVERNANCE_APPROVER,
            RoleGrant.status == "ACTIVE",
            RoleGrant.valid_from <= now,
            or_(RoleGrant.valid_until.is_(None), RoleGrant.valid_until > now),
            or_(
                (RoleGrant.scope_type == SCOPE_LEGAL_ENTITY)
                & (RoleGrant.scope_id == legal_entity_id),
                (RoleGrant.scope_type == SCOPE_GLOBAL) & (RoleGrant.scope_id.is_(None)),
            ),
        )
        .limit(1)
    )
    if grant is None:
        raise JournalError(
            "JOURNAL_REVERSAL_CHECKER_NOT_AUTHORIZED",
            "Journal reversal checker no longer has an active governance approval grant",
        )


async def reverse_journal(
    session: AsyncSession,
    *,
    original_entry_id: UUID,
    idempotency_key: str,
    actor_reference: UUID,
    correlation_id: UUID,
    reason: str,
    actor_type: str = "SYSTEM",
    approval_request_id: UUID | None = None,
) -> JournalEntry:
    del session, original_entry_id, idempotency_key, actor_reference
    del correlation_id, reason, actor_type, approval_request_id
    raise JournalError(
        "JOURNAL_REVERSAL_APPROVAL_REQUIRED",
        "Journal reversal must execute through the approved maker-checker path",
    )


async def _reverse_journal_after_approval(
    session: AsyncSession,
    *,
    original_entry_id: UUID,
    idempotency_key: str,
    actor_reference: UUID,
    correlation_id: UUID,
    reason: str,
    actor_type: str = "SYSTEM",
    approval_request_id: UUID | None = None,
) -> JournalEntry:
    if not reason.strip():
        raise JournalError("JOURNAL_REVERSAL_REASON_REQUIRED", "Reversal reason is required")
    original = await session.scalar(
        select(JournalEntry).where(JournalEntry.id == original_entry_id).with_for_update()
    )
    if original is None:
        raise JournalError("JOURNAL_NOT_FOUND", "Original journal entry was not found")
    if original.state != "POSTED":
        raise JournalError("JOURNAL_NOT_POSTED", "Only POSTED journals can be reversed")

    postings = (
        await session.scalars(
            select(JournalPosting)
            .where(JournalPosting.journal_entry_id == original.id)
            .order_by(JournalPosting.created_at, JournalPosting.id)
        )
    ).all()
    lines = [
        JournalLine(
            account_code=p.account_code,
            economic_owner_type=p.economic_owner_type,
            debit_amount=p.credit_amount,
            credit_amount=p.debit_amount,
            economic_owner_id=p.economic_owner_id,
            participant_id=p.participant_id,
            program_id=p.program_id,
            provider_id=p.provider_id,
            asset_position_id=p.asset_position_id,
            guarantee_case_id=p.guarantee_case_id,
            claim_id=p.claim_id,
            reserve_account_id=p.reserve_account_id,
        )
        for p in postings
    ]
    return await _post_journal(
        session,
        business_event_type="REVERSAL",
        business_event_id=str(original.id),
        legal_entity_id=original.legal_entity_id,
        currency=original.currency,
        idempotency_key=idempotency_key,
        actor_reference=actor_reference,
        correlation_id=correlation_id,
        lines=lines,
        effective_at=None,
        causation_id=original.correlation_id,
        policy_version_reference=original.policy_version_reference,
        posting_template_reference=original.posting_template_reference,
        account_mapping_reference=original.account_mapping_reference,
        evidence_reference=original.evidence_reference,
        settlement_reference=original.settlement_reference,
        reversal_of_entry_id=original.id,
        reason=reason,
        actor_type=actor_type,
        material_event_type="JournalReversed",
        approval_request_id=approval_request_id,
    )


async def reverse_journal_with_approval(
    session: AsyncSession,
    *,
    original_entry_id: UUID,
    approval_request_id: UUID,
    idempotency_key: str,
    actor_reference: UUID,
    actor_type: str,
    correlation_id: UUID,
    reason: str,
) -> JournalEntry:
    original = await session.scalar(
        select(JournalEntry).where(JournalEntry.id == original_entry_id).with_for_update()
    )
    if original is None:
        raise JournalError("JOURNAL_NOT_FOUND", "Original journal entry was not found")
    if original.state != "POSTED":
        raise JournalError("JOURNAL_NOT_POSTED", "Only POSTED journals can be reversed")
    if not reason.strip():
        raise JournalError("JOURNAL_REVERSAL_REASON_REQUIRED", "Reversal reason is required")

    approval = await session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_request_id).with_for_update()
    )
    if approval is None:
        raise JournalError(
            "JOURNAL_REVERSAL_APPROVAL_NOT_FOUND",
            "Journal reversal approval request was not found",
        )
    if (
        approval.action_type != "JOURNAL_REVERSAL"
        or approval.target_type != "JournalEntry"
        or approval.target_id != str(original.id)
        or approval.maker_identity_id != actor_reference
        or approval.required_checker_role != ROLE_GOVERNANCE_APPROVER
        or approval.scope_type != SCOPE_LEGAL_ENTITY
        or approval.scope_id != original.legal_entity_id
    ):
        raise JournalError(
            "JOURNAL_REVERSAL_APPROVAL_BINDING_INVALID",
            "Approval is not bound to this exact journal reversal",
        )
    await _assert_finance_initiator_is_active(
        session,
        identity_id=actor_reference,
        legal_entity_id=original.legal_entity_id,
    )
    await _assert_governance_checker_is_active(
        session,
        request=approval,
        legal_entity_id=original.legal_entity_id,
    )
    assert_approval_execution_eligible(
        approval,
        payload=reversal_approval_payload(original, reason),
        current_target_version=None,
    )

    return await _reverse_journal_after_approval(
        session,
        original_entry_id=original.id,
        idempotency_key=idempotency_key,
        actor_reference=actor_reference,
        actor_type=actor_type,
        correlation_id=correlation_id,
        reason=reason,
        approval_request_id=approval.id,
    )


async def account_totals(
    session: AsyncSession,
    *,
    account_code: str,
    currency: str,
    legal_entity_id: UUID,
) -> tuple[Decimal, Decimal]:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(JournalPosting.debit_amount), 0),
                func.coalesce(func.sum(JournalPosting.credit_amount), 0),
            )
            .join(JournalEntry, JournalEntry.id == JournalPosting.journal_entry_id)
            .where(
                JournalEntry.state == "POSTED",
                JournalPosting.account_code == account_code,
                JournalPosting.currency == currency,
                JournalPosting.legal_entity_id == legal_entity_id,
            )
        )
    ).one()
    return Decimal(row[0]), Decimal(row[1])
