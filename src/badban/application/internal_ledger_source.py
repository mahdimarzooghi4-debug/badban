from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.idempotency import canonical_request_hash
from badban.application.reconciliation_sources import (
    LedgerRecord,
    LedgerSnapshot,
    ReconciliationSourceAcquisitionError,
    ReconciliationSourcePort,
    ReconciliationSourceUnavailable,
    SourceCapability,
    SourceTarget,
)
from badban.infrastructure.persistence.models import (
    JournalAccountTaxonomy,
    JournalEntry,
    JournalPosting,
)


class InternalPostedJournalSource(ReconciliationSourcePort):
    """Read-only, program-scoped source over immutable POSTED journal truth."""

    def __init__(self, session: AsyncSession, *, program_id: UUID) -> None:
        self._session = session
        self._program_id = program_id

    def capability(self) -> SourceCapability:
        return SourceCapability(
            source_id=self._program_id,
            reconciliation_type="LEDGER",
            contract_version="internal-posted-journal-v1",
            mapping_version="posted-account-normal-balance-v1",
            schema_version="reconciliation-source-v2",
        )

    async def fetch_reconciliation_snapshot(
        self, target: SourceTarget, scope: dict[str, str]
    ) -> LedgerSnapshot:
        if (
            target.reconciliation_type != "LEDGER"
            or target.program_id != self._program_id
            or target.provider_id is not None
            or target.source_legal_entity_id is not None
        ):
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

        expected_scope = {"program_id": str(self._program_id)}
        if scope != expected_scope:
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

        snapshot_cutoff = select(func.statement_timestamp()).scalar_subquery()
        rows = (
            await self._session.execute(
                select(
                    JournalEntry,
                    JournalPosting,
                    JournalAccountTaxonomy,
                    snapshot_cutoff.label("snapshot_at"),
                )
                .join(JournalPosting, JournalPosting.journal_entry_id == JournalEntry.id)
                .outerjoin(
                    JournalAccountTaxonomy,
                    JournalAccountTaxonomy.account_code == JournalPosting.account_code,
                )
                .where(
                    JournalEntry.state == "POSTED",
                    JournalEntry.posted_at.is_not(None),
                    JournalEntry.posted_at <= snapshot_cutoff,
                    JournalPosting.program_id == self._program_id,
                )
                .order_by(
                    JournalPosting.legal_entity_id,
                    JournalPosting.account_code,
                    JournalPosting.currency,
                    JournalEntry.posted_at,
                    JournalEntry.id,
                    JournalPosting.id,
                )
            )
        ).all()
        snapshot_at = rows[0][3] if rows else datetime.now(UTC)
        return build_posted_journal_snapshot(
            [row[:3] for row in rows],
            program_id=self._program_id,
            snapshot_at=snapshot_at,
            received_at=datetime.now(UTC),
        )


def build_posted_journal_snapshot(
    rows: Sequence[Any],
    *,
    program_id: UUID,
    snapshot_at: datetime,
    received_at: datetime,
) -> LedgerSnapshot:
    """Aggregate exact posted journal facts without treating absent rows as zero."""
    if not rows:
        raise ReconciliationSourceUnavailable()

    grouped: dict[tuple[Any, ...], tuple[Decimal, datetime]] = {}
    evidence_references: set[str] = set()
    for entry, posting, taxonomy in rows:
        if (
            entry.state != "POSTED"
            or entry.posted_at is None
            or entry.posted_at > snapshot_at
            or posting.program_id != program_id
        ):
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
        if taxonomy is None:
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
        if (
            entry.legal_entity_id != posting.legal_entity_id
            or entry.currency != posting.currency
            or posting.account_code != taxonomy.account_code
        ):
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
        if taxonomy.normal_balance not in {
            "DEBIT",
            "CREDIT",
            "MEMO",
        } or taxonomy.ledger_layer not in {
            "MONETARY",
            "MEMORANDUM_CONTROL",
            "EXTERNAL_MIRROR",
        }:
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

        debit = Decimal(posting.debit_amount)
        credit = Decimal(posting.credit_amount)
        if not debit.is_finite() or not credit.is_finite():
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
        signed_amount = credit - debit if taxonomy.normal_balance == "CREDIT" else debit - credit
        key = (
            posting.account_code,
            posting.currency,
            posting.legal_entity_id,
            posting.economic_owner_type,
            posting.economic_owner_id,
            posting.participant_id,
            posting.program_id,
            posting.provider_id,
            posting.asset_position_id,
            posting.guarantee_case_id,
            posting.claim_id,
            posting.reserve_account_id,
            taxonomy.ledger_layer,
            taxonomy.normal_balance,
        )
        prior_balance, prior_observed_at = grouped.get(key, (Decimal(0), entry.posted_at))
        grouped[key] = (
            prior_balance + signed_amount,
            max(prior_observed_at, entry.posted_at),
        )
        evidence_references.add(f"journal-entry:{entry.id}")

    if not grouped:
        raise ReconciliationSourceUnavailable()
    if len(evidence_references) > 1000:
        raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

    records = tuple(
        LedgerRecord(
            observed_at=observed_at,
            account_code=key[0],
            currency=key[1],
            legal_entity_id=key[2],
            economic_owner_type=key[3],
            economic_owner_id=key[4],
            participant_id=key[5],
            program_id=key[6],
            provider_id=key[7],
            asset_position_id=key[8],
            guarantee_case_id=key[9],
            claim_id=key[10],
            reserve_account_id=key[11],
            ledger_layer=key[12],
            normal_balance=key[13],
            balance=format(balance, "f"),
        )
        for key, (balance, observed_at) in sorted(grouped.items(), key=lambda item: repr(item[0]))
    )
    evidence = tuple(sorted(evidence_references))
    draft = LedgerSnapshot.model_construct(
        source_id=program_id,
        reconciliation_type="LEDGER",
        scope_definition={"program_id": str(program_id)},
        snapshot_at=snapshot_at,
        received_at=received_at,
        source_reference=f"badban:journal-postings:program:{program_id}:{snapshot_at.isoformat()}",
        schema_version="reconciliation-source-v2",
        contract_version="internal-posted-journal-v1",
        mapping_version="posted-account-normal-balance-v1",
        normalization_version=None,
        evidence_references=evidence,
        coverage_from=min(record.observed_at for record in records),
        coverage_to=snapshot_at,
        watermark=snapshot_at.isoformat(),
        content_hash="0" * 64,
        records=records,
    )
    payload = draft.model_dump(mode="json")
    payload["content_hash"] = canonical_request_hash(draft.semantic_payload())
    return LedgerSnapshot.model_validate(payload)
