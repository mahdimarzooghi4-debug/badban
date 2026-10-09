from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import (
    GuaranteeReserveMetricsSnapshot,
    JournalEntry,
    JournalPosting,
    LegalEntity,
)
from badban.security.audit import append_audit
from badban.security.authorization import SCOPE_LEGAL_ENTITY

RESERVE_METRICS_ALGORITHM_CODE = "GUARANTEE_RESERVE_METRICS"
RESERVE_METRICS_ALGORITHM_VERSION = "GUARANTEE_RESERVE_METRICS_V1"
RESERVE_CASH_ACCOUNT = "1020.GUARANTEE_RESERVE_CASH_CONTROL"
RESERVE_DESIGNATED_ACCOUNT = "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE"


class ReserveMetricsError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def reserve_metrics_reference(snapshot: GuaranteeReserveMetricsSnapshot) -> str:
    return f"reserve-metrics:{snapshot.id}"


async def _lock_snapshot_scope(
    session: AsyncSession,
    *,
    legal_entity_id: UUID,
    currency: str,
    source_fingerprint: str,
) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": (f"reserve-metrics:{legal_entity_id}:{currency}:{source_fingerprint}")},
    )


async def create_reserve_metrics_snapshot(
    session: AsyncSession,
    *,
    legal_entity_id: UUID,
    currency: str,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> GuaranteeReserveMetricsSnapshot:
    normalized_currency = currency.strip()
    if not normalized_currency:
        raise ReserveMetricsError(
            "RESERVE_METRICS_CURRENCY_INVALID",
            "currency must not be blank",
        )

    legal_entity = await session.get(LegalEntity, legal_entity_id)
    if legal_entity is None:
        raise ReserveMetricsError(
            "RESERVE_METRICS_LEGAL_ENTITY_NOT_FOUND",
            "Legal entity was not found",
        )

    rows = (
        await session.execute(
            select(JournalPosting, JournalEntry.id)
            .join(JournalEntry, JournalEntry.id == JournalPosting.journal_entry_id)
            .where(
                JournalEntry.state == "POSTED",
                JournalPosting.legal_entity_id == legal_entity_id,
                JournalPosting.currency == normalized_currency,
                JournalPosting.account_code.in_([RESERVE_CASH_ACCOUNT, RESERVE_DESIGNATED_ACCOUNT]),
            )
            .order_by(JournalPosting.id)
        )
    ).all()

    cash_control_balance = Decimal("0")
    designated_balance = Decimal("0")
    source_journal_ids: set[str] = set()
    source_posting_ids: list[str] = []
    source_rows: list[dict[str, str]] = []

    for posting, journal_entry_id in rows:
        if (
            posting.participant_id is not None
            or posting.asset_position_id is not None
            or posting.economic_owner_type == "PARTICIPANT"
        ):
            raise ReserveMetricsError(
                "RESERVE_METRICS_SOURCE_OWNERSHIP_INVALID",
                "Participant-owned or AssetPosition-linked value cannot be counted as general reserve",
            )

        source_journal_ids.add(str(journal_entry_id))
        source_posting_ids.append(str(posting.id))
        if posting.account_code == RESERVE_CASH_ACCOUNT:
            cash_control_balance += posting.debit_amount - posting.credit_amount
        elif posting.account_code == RESERVE_DESIGNATED_ACCOUNT:
            designated_balance += posting.credit_amount - posting.debit_amount

        source_rows.append(
            {
                "posting_id": str(posting.id),
                "journal_entry_id": str(journal_entry_id),
                "account_code": posting.account_code,
                "debit_amount": format(posting.debit_amount, "f"),
                "credit_amount": format(posting.credit_amount, "f"),
                "currency": posting.currency,
                "economic_owner_type": posting.economic_owner_type,
                "economic_owner_id": (
                    str(posting.economic_owner_id)
                    if posting.economic_owner_id is not None
                    else ""
                ),
                "program_id": str(posting.program_id) if posting.program_id is not None else "",
                "reserve_account_id": (
                    str(posting.reserve_account_id)
                    if posting.reserve_account_id is not None
                    else ""
                ),
            }
        )

    journal_ids = sorted(source_journal_ids)
    source_fingerprint = canonical_request_hash(
        {
            "algorithm_code": RESERVE_METRICS_ALGORITHM_CODE,
            "algorithm_version": RESERVE_METRICS_ALGORITHM_VERSION,
            "legal_entity_id": str(legal_entity_id),
            "currency": normalized_currency,
            "source_rows": source_rows,
        }
    )

    await _lock_snapshot_scope(
        session,
        legal_entity_id=legal_entity_id,
        currency=normalized_currency,
        source_fingerprint=source_fingerprint,
    )

    existing = await session.scalar(
        select(GuaranteeReserveMetricsSnapshot).where(
            GuaranteeReserveMetricsSnapshot.legal_entity_id == legal_entity_id,
            GuaranteeReserveMetricsSnapshot.currency == normalized_currency,
            GuaranteeReserveMetricsSnapshot.source_fingerprint == source_fingerprint,
        )
    )
    if existing is not None:
        return existing

    now = datetime.now(UTC)
    snapshot = GuaranteeReserveMetricsSnapshot(
        legal_entity_id=legal_entity_id,
        currency=normalized_currency,
        cash_control_balance=cash_control_balance,
        designated_balance=designated_balance,
        source_journal_count=len(journal_ids),
        source_posting_count=len(source_posting_ids),
        source_journal_ids=journal_ids,
        source_posting_ids=source_posting_ids,
        source_fingerprint=source_fingerprint,
        algorithm_code=RESERVE_METRICS_ALGORITHM_CODE,
        algorithm_version=RESERVE_METRICS_ALGORITHM_VERSION,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        evaluated_at=now,
    )
    session.add(snapshot)
    await session.flush()

    append_audit(
        session,
        aggregate_type="GuaranteeReserveMetricsSnapshot",
        aggregate_id=str(snapshot.id),
        aggregate_version=None,
        action="RESERVE_METRICS_SNAPSHOT_CREATED",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        reason_code="POSTED_JOURNAL_RESERVE_METRICS",
        new_state={
            "legal_entity_id": str(legal_entity_id),
            "currency": normalized_currency,
            "cash_control_balance": format(cash_control_balance, "f"),
            "designated_balance": format(designated_balance, "f"),
            "source_fingerprint": source_fingerprint,
            "source_journal_count": len(journal_ids),
            "source_posting_count": len(source_posting_ids),
            "algorithm_version": RESERVE_METRICS_ALGORITHM_VERSION,
        },
        scope={
            "scope_type": SCOPE_LEGAL_ENTITY,
            "scope_id": str(legal_entity_id),
        },
    )
    await session.flush()
    return snapshot
