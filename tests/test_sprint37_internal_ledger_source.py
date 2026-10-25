from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.internal_ledger_source import (
    InternalPostedJournalSource,
    build_posted_journal_snapshot,
)
from badban.application.journal import JournalLine, post_journal
from badban.application.reconciliation_sources import (
    ReconciliationSourceAcquisitionError,
    ReconciliationSourceRegistry,
    ReconciliationSourceUnavailable,
    SourceTarget,
    acquire_verified_snapshot,
)
from badban.infrastructure.persistence.models import Identity, LegalEntity, Program

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
PROGRAM_ID = UUID("00000000-0000-0000-0000-000000000037")
LEGAL_ENTITY_ID = UUID("00000000-0000-0000-0000-000000000038")


def _row(
    *,
    account="1000.TEST",
    normal_balance="DEBIT",
    debit="0",
    credit="0",
    legal_entity_id=LEGAL_ENTITY_ID,
    posted_at=NOW - timedelta(days=1),
    program_id=PROGRAM_ID,
):
    entry = SimpleNamespace(
        id=uuid4(),
        state="POSTED",
        posted_at=posted_at,
        legal_entity_id=legal_entity_id,
        currency="IRR",
    )
    posting = SimpleNamespace(
        id=uuid4(),
        account_code=account,
        currency="IRR",
        legal_entity_id=legal_entity_id,
        economic_owner_type="PROGRAM",
        economic_owner_id=None,
        participant_id=None,
        program_id=program_id,
        provider_id=None,
        asset_position_id=None,
        guarantee_case_id=None,
        claim_id=None,
        reserve_account_id=None,
        debit_amount=Decimal(debit),
        credit_amount=Decimal(credit),
    )
    taxonomy = SimpleNamespace(
        account_code=account,
        normal_balance=normal_balance,
        ledger_layer="MONETARY",
    )
    return entry, posting, taxonomy


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        snapshot_at = datetime.now(UTC)
        return SimpleNamespace(all=lambda: [(*row, snapshot_at) for row in self.rows])


def _target() -> SourceTarget:
    return SourceTarget(reconciliation_type="LEDGER", program_id=PROGRAM_ID)


def test_posted_journal_snapshot_aggregates_exact_balances_and_keeps_legal_entity():
    other_entity = uuid4()
    rows = [
        _row(debit="100", credit="30"),
        _row(debit="10", credit="15"),
        _row(
            account="2000.TEST",
            normal_balance="CREDIT",
            debit="5",
            credit="80",
        ),
        _row(debit="7", legal_entity_id=other_entity),
    ]

    snapshot = build_posted_journal_snapshot(
        rows,
        program_id=PROGRAM_ID,
        snapshot_at=NOW,
        received_at=NOW + timedelta(seconds=1),
    )

    values = {
        (record.account_code, record.legal_entity_id): record.balance for record in snapshot.records
    }
    assert values[("1000.TEST", LEGAL_ENTITY_ID)] == "65"
    assert values[("2000.TEST", LEGAL_ENTITY_ID)] == "75"
    assert values[("1000.TEST", other_entity)] == "7"
    assert len(snapshot.evidence_references) == 4
    assert snapshot.schema_version == "reconciliation-source-v2"


async def test_internal_posted_journal_source_acquires_a_verified_snapshot():
    registry = ReconciliationSourceRegistry()
    port = InternalPostedJournalSource(
        cast(AsyncSession, _Session([_row(debit="125")])),
        program_id=PROGRAM_ID,
    )
    registry.register(port)

    snapshot = await acquire_verified_snapshot(
        registry,
        target=_target(),
        scope={"program_id": str(PROGRAM_ID)},
    )

    assert snapshot.reconciliation_type == "LEDGER"
    assert snapshot.scope_definition == {"program_id": str(PROGRAM_ID)}
    assert snapshot.records[0].balance == "125"
    assert snapshot.records[0].legal_entity_id == LEGAL_ENTITY_ID


async def test_empty_internal_journal_is_unavailable_not_a_zero_balance():
    registry = ReconciliationSourceRegistry()
    registry.register(
        InternalPostedJournalSource(cast(AsyncSession, _Session([])), program_id=PROGRAM_ID)
    )

    with pytest.raises(ReconciliationSourceAcquisitionError) as exc:
        await acquire_verified_snapshot(
            registry,
            target=_target(),
            scope={"program_id": str(PROGRAM_ID)},
        )

    assert exc.value.code == "SOURCE_UNAVAILABLE"


def test_inconsistent_legal_entity_lineage_is_rejected():
    entry, posting, taxonomy = _row(debit="10")
    posting.legal_entity_id = uuid4()

    with pytest.raises(ReconciliationSourceAcquisitionError) as exc:
        build_posted_journal_snapshot(
            [(entry, posting, taxonomy)],
            program_id=PROGRAM_ID,
            snapshot_at=NOW,
            received_at=NOW,
        )

    assert exc.value.code == "SOURCE_CONTRACT_INVALID"


def test_source_with_only_other_program_rows_is_unavailable():
    with pytest.raises(ReconciliationSourceUnavailable):
        build_posted_journal_snapshot(
            [],
            program_id=PROGRAM_ID,
            snapshot_at=NOW,
            received_at=NOW,
        )


@pytest.mark.integration
async def test_internal_ledger_source_reads_program_scoped_posted_journal(
    database,
    clean_sprint07_guarantee_tables,
):
    identity = Identity(
        identity_type="TEST",
        external_subject=f"sprint37-ledger-{uuid4()}",
        status="ACTIVE",
    )
    legal_entity = LegalEntity(
        legal_name="Sprint 37 Ledger Source",
        registration_identifier=f"SPRINT37-{uuid4()}",
        entity_type="TEST",
        status="ACTIVE",
        created_by=uuid4(),
    )
    program = Program(
        code=f"SPRINT37-{uuid4()}",
        name="Sprint 37 ledger source test",
        status="ACTIVE",
        legal_entity_id=legal_entity.id,
        created_by=uuid4(),
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([identity, legal_entity, program])

    async with database.session_factory() as session:
        async with session.begin():
            await post_journal(
                session,
                business_event_type="SPRINT37_LEDGER_SOURCE",
                business_event_id=f"cash-in-{uuid4()}",
                legal_entity_id=legal_entity.id,
                currency="IRR",
                idempotency_key=f"sprint37-cash-in-{uuid4()}",
                actor_reference=identity.id,
                correlation_id=uuid4(),
                lines=[
                    JournalLine(
                        account_code="1000.SETTLEMENT_CASH_CONTROL",
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        debit_amount=Decimal("100"),
                    ),
                    JournalLine(
                        account_code="2030.PROGRAM_CAPITAL_BALANCE",
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        credit_amount=Decimal("100"),
                    ),
                ],
            )
            await post_journal(
                session,
                business_event_type="SPRINT37_LEDGER_SOURCE",
                business_event_id=f"cash-out-{uuid4()}",
                legal_entity_id=legal_entity.id,
                currency="IRR",
                idempotency_key=f"sprint37-cash-out-{uuid4()}",
                actor_reference=identity.id,
                correlation_id=uuid4(),
                lines=[
                    JournalLine(
                        account_code="1000.SETTLEMENT_CASH_CONTROL",
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        credit_amount=Decimal("30"),
                    ),
                    JournalLine(
                        account_code="1010.PROGRAM_CASH_CONTROL",
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        debit_amount=Decimal("30"),
                    ),
                ],
            )

    async with database.session_factory() as session:
        source = InternalPostedJournalSource(session, program_id=program.id)
        snapshot = await source.fetch_reconciliation_snapshot(
            _target_for(program.id), {"program_id": str(program.id)}
        )

    balances = {record.account_code: record.balance for record in snapshot.records}
    assert balances["1000.SETTLEMENT_CASH_CONTROL"] == "70.000000000000000000"
    assert balances["1010.PROGRAM_CASH_CONTROL"] == "30.000000000000000000"
    assert balances["2030.PROGRAM_CAPITAL_BALANCE"] == "100.000000000000000000"
    assert all(record.legal_entity_id == legal_entity.id for record in snapshot.records)
    assert len(snapshot.evidence_references) == 2


def _target_for(program_id: UUID) -> SourceTarget:
    return SourceTarget(reconciliation_type="LEDGER", program_id=program_id)
