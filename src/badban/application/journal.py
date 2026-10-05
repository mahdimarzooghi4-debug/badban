from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import JournalEntry, JournalPosting


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
        "lines": [asdict(line) for line in lines],
    }


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
) -> JournalEntry:
    _validate_lines(lines)
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
        lines=lines,
    )
    request_hash = canonical_request_hash(payload)
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
            select(JournalEntry).where(JournalEntry.reversal_of_entry_id == reversal_of_entry_id)
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
        state="POSTED",
        effective_at=effective,
        posted_at=now,
        reversal_of_entry_id=reversal_of_entry_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        actor_reference=actor_reference,
        correlation_id=correlation_id,
        causation_id=causation_id,
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
    return entry


async def reverse_journal(
    session: AsyncSession,
    *,
    original_entry_id: UUID,
    idempotency_key: str,
    actor_reference: UUID,
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
        correlation_id=correlation_id,
        lines=lines,
        effective_at=None,
        causation_id=original.correlation_id,
        reversal_of_entry_id=original.id,
        reason=reason,
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
