from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.approval import (
    assert_approval_execution_eligible,
    get_approval_for_update,
)
from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    JournalEntry,
    JournalPosting,
    OutboxMessage,
)
from badban.security.audit import append_audit
from badban.security.authorization import ROLE_GOVERNANCE_APPROVER, SCOPE_LEGAL_ENTITY

_MAX_DECIMAL_INTEGER_DIGITS = 20
_MAX_DECIMAL_SCALE = 18


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


def _validate_decimal(value: Decimal) -> None:
    if not value.is_finite():
        raise JournalError("JOURNAL_AMOUNT_INVALID", "Journal amount must be finite")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise JournalError("JOURNAL_AMOUNT_INVALID", "Journal amount must be finite")
    scale = max(-exponent, 0)
    integer_digits = max(value.adjusted() + 1, 0) if value != 0 else 0
    if scale > _MAX_DECIMAL_SCALE or integer_digits > _MAX_DECIMAL_INTEGER_DIGITS:
        raise JournalError(
            "JOURNAL_AMOUNT_PRECISION_INVALID",
            "Journal amount exceeds NUMERIC(38,18) precision",
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
        _validate_decimal(debit)
        _validate_decimal(credit)
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
    _validate_decimal(debit_total)
    _validate_decimal(credit_total)
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
    policy_version_reference: str | None,
    posting_template_code: str | None,
    posting_template_version: str | None,
    account_mapping_reference: str | None,
    evidence_reference: str | None,
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
        "policy_version_reference": policy_version_reference,
        "posting_template_code": posting_template_code,
        "posting_template_version": posting_template_version,
        "account_mapping_reference": account_mapping_reference,
        "evidence_reference": evidence_reference,
        "lines": [asdict(line) for line in lines],
    }


def _record_journal_event(
    session: AsyncSession,
    *,
    entry: JournalEntry,
    event_type: str,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    occurred_at: datetime,
) -> None:
    append_audit(
        session,
        aggregate_type="JournalEntry",
        aggregate_id=str(entry.id),
        aggregate_version=None,
        action=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=entry.evidence_reference,
        new_state={
            "state": entry.state,
            "business_event_type": entry.business_event_type,
            "business_event_id": entry.business_event_id,
            "legal_entity_id": str(entry.legal_entity_id),
            "currency": entry.currency,
            "reversal_of_entry_id": (
                str(entry.reversal_of_entry_id) if entry.reversal_of_entry_id else None
            ),
        },
        scope={"scope_type": SCOPE_LEGAL_ENTITY, "scope_id": str(entry.legal_entity_id)},
    )
    session.add(
        OutboxMessage(
            event_type=event_type,
            event_version=1,
            aggregate_type="JournalEntry",
            aggregate_id=str(entry.id),
            aggregate_version=1,
            payload={
                "journal_entry_id": str(entry.id),
                "business_event_type": entry.business_event_type,
                "business_event_id": entry.business_event_id,
                "legal_entity_id": str(entry.legal_entity_id),
                "currency": entry.currency,
                "effective_at": entry.effective_at.isoformat(),
                "posted_at": entry.posted_at.isoformat() if entry.posted_at else None,
                "reversal_of_entry_id": (
                    str(entry.reversal_of_entry_id) if entry.reversal_of_entry_id else None
                ),
                "policy_version_reference": entry.policy_version_reference,
                "posting_template_code": entry.posting_template_code,
                "posting_template_version": entry.posting_template_version,
                "account_mapping_reference": entry.account_mapping_reference,
                "evidence_reference": entry.evidence_reference,
                "actor": {"type": actor_type, "id": str(actor_id)},
            },
            correlation_id=correlation_id,
            causation_id=entry.causation_id,
            occurred_at=occurred_at,
        )
    )


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
    reversal_of_entry_id: UUID | None = None,
    reason: str | None = None,
    actor_type: str = "SYSTEM",
    policy_version_reference: str | None = None,
    posting_template_code: str | None = None,
    posting_template_version: str | None = None,
    account_mapping_reference: str | None = None,
    evidence_reference: str | None = None,
    event_type: str = "JournalPosted",
) -> JournalEntry:
    _validate_lines(lines)
    if not business_event_type.strip() or not business_event_id.strip():
        raise JournalError("JOURNAL_EVENT_INVALID", "Business event type and ID are required")
    if not currency.strip():
        raise JournalError("JOURNAL_CURRENCY_INVALID", "Journal currency is required")

    payload = _request_payload(
        business_event_type=business_event_type,
        business_event_id=business_event_id,
        legal_entity_id=legal_entity_id,
        currency=currency,
        effective_at=effective_at,
        reversal_of_entry_id=reversal_of_entry_id,
        reason=reason,
        policy_version_reference=policy_version_reference,
        posting_template_code=posting_template_code,
        posting_template_version=posting_template_version,
        account_mapping_reference=account_mapping_reference,
        evidence_reference=evidence_reference,
        lines=lines,
    )
    request_hash = canonical_request_hash(payload)

    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:idempotency_key, 0))"),
        {"idempotency_key": idempotency_key},
    )
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
        reason=reason,
        policy_version_reference=policy_version_reference,
        posting_template_code=posting_template_code,
        posting_template_version=posting_template_version,
        account_mapping_reference=account_mapping_reference,
        evidence_reference=evidence_reference,
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
    _record_journal_event(
        session,
        entry=entry,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_reference,
        correlation_id=correlation_id,
        occurred_at=now,
    )
    await session.flush()
    return entry


def journal_reversal_approval_payload(
    original: JournalEntry,
    *,
    reason: str,
) -> dict[str, object]:
    return {
        "action_type": "JOURNAL_REVERSAL",
        "journal_entry_id": str(original.id),
        "state": original.state,
        "request_hash": original.request_hash,
        "legal_entity_id": str(original.legal_entity_id),
        "currency": original.currency,
        "posted_at": original.posted_at.isoformat() if original.posted_at else None,
        "reason": reason,
    }


async def assert_journal_reversal_approval(
    session: AsyncSession,
    *,
    approval_id: UUID,
    original: JournalEntry,
    maker_identity_id: UUID,
    reason: str,
    now: datetime | None = None,
) -> ApprovalRequest:
    approval = await get_approval_for_update(session, approval_id)
    if (
        approval.action_type != "JOURNAL_REVERSAL"
        or approval.target_type != "JournalEntry"
        or approval.target_id != str(original.id)
    ):
        raise JournalError(
            "APPROVAL_PAYLOAD_CHANGED",
            "Approval Request is not bound to this journal reversal",
        )
    if approval.maker_identity_id != maker_identity_id:
        raise JournalError(
            "MAKER_CHECKER_REQUIRED",
            "Journal reversal must be executed by the approval maker",
        )
    if approval.required_checker_role != ROLE_GOVERNANCE_APPROVER:
        raise JournalError(
            "MAKER_CHECKER_REQUIRED",
            "Journal reversal requires a GOVERNANCE_APPROVER checker",
        )
    if approval.checker_identity_id is None:
        raise JournalError(
            "MAKER_CHECKER_REQUIRED",
            "Journal reversal requires an approved checker",
        )
    if approval.checker_identity_id == approval.maker_identity_id:
        raise JournalError(
            "SELF_APPROVAL_FORBIDDEN",
            "Maker and checker must be distinct identities",
        )
    try:
        assert_approval_execution_eligible(
            approval,
            payload=journal_reversal_approval_payload(original, reason=reason),
            current_target_version=None,
            now=now,
        )
    except Exception as exc:
        if hasattr(exc, "code"):
            raise JournalError(getattr(exc, "code"), str(exc)) from exc
        raise
    return approval


async def reverse_journal(
    session: AsyncSession,
    *,
    original_entry_id: UUID,
    idempotency_key: str,
    actor_reference: UUID,
    correlation_id: UUID,
    reason: str,
    actor_type: str = "SYSTEM",
    approval_id: UUID | None = None,
    require_approval: bool = False,
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
    if require_approval:
        if approval_id is None:
            raise JournalError(
                "MAKER_CHECKER_REQUIRED",
                "Journal reversal requires an approved maker-checker request",
            )
        await assert_journal_reversal_approval(
            session,
            approval_id=approval_id,
            original=original,
            maker_identity_id=actor_reference,
            reason=reason,
        )

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
    return await post_journal(
        session,
        business_event_type="REVERSAL",
        business_event_id=str(original.id),
        legal_entity_id=original.legal_entity_id,
        currency=original.currency,
        idempotency_key=idempotency_key,
        actor_reference=actor_reference,
        actor_type=actor_type,
        correlation_id=correlation_id,
        lines=lines,
        effective_at=None,
        causation_id=original.correlation_id,
        reversal_of_entry_id=original.id,
        reason=reason,
        policy_version_reference=original.policy_version_reference,
        posting_template_code=original.posting_template_code,
        posting_template_version=original.posting_template_version,
        account_mapping_reference=original.account_mapping_reference,
        evidence_reference=original.evidence_reference,
        event_type="JournalReversed",
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
