from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.internal_valuation_observation_source import (
    InternalValuationObservationSource,
    build_internal_valuation_snapshot,
)
from badban.application.reconciliation_sources import (
    InternalValuationObservationRecord,
    ReconciliationSourceAcquisitionError,
    ReconciliationSourceRegistry,
    SourceTarget,
    acquire_verified_snapshot,
)
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    Identity,
    Participant,
    ParticipationEpisode,
    Program,
    ValuationObservation,
)

NOW = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
PROGRAM_ID = UUID("00000000-0000-0000-0000-000000000039")


def _record(*, program_id=PROGRAM_ID, observed_at=NOW - timedelta(minutes=2)):
    return InternalValuationObservationRecord(
        observed_at=observed_at,
        observation_id=uuid4(),
        asset_position_id=uuid4(),
        program_id=program_id,
        valued_quantity="5.125",
        unit_price="11.00",
        valuation_currency="IRR",
        fx_rate=None,
        gross_market_value="56.375",
        source_name="stored-source-name",
        source_reference="stored-reference",
        source_version_reference="v1",
        received_at=NOW - timedelta(minutes=1),
        valid_until=NOW + timedelta(days=1),
        freshness_status="STALE",
        evidence_reference="stored-evidence-reference",
    )


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return SimpleNamespace(all=lambda: [(*row, NOW) for row in self.rows])


def _target(program_id=PROGRAM_ID):
    return SourceTarget(reconciliation_type="INTERNAL_VALUATION_OBSERVATION", program_id=program_id)


def test_internal_valuation_snapshot_preserves_recorded_status_and_evidence():
    record = _record()
    snapshot = build_internal_valuation_snapshot(
        [record],
        program_id=PROGRAM_ID,
        snapshot_at=NOW,
        received_at=NOW + timedelta(seconds=1),
    )

    assert snapshot.reconciliation_type == "INTERNAL_VALUATION_OBSERVATION"
    assert snapshot.records[0].freshness_status == "STALE"
    assert Decimal(snapshot.records[0].gross_market_value) == Decimal("56.375")
    assert snapshot.evidence_references == (f"valuation-observation:{record.observation_id}",)


async def test_internal_valuation_source_uses_registered_verified_port():
    record = _record()
    observation = SimpleNamespace(
        id=record.observation_id,
        asset_position_id=record.asset_position_id,
        valued_quantity=Decimal("5.125"),
        unit_price=Decimal("11.00"),
        valuation_currency="IRR",
        fx_rate=None,
        gross_market_value=Decimal("56.375"),
        source_name=record.source_name,
        source_reference=record.source_reference,
        source_version_reference=record.source_version_reference,
        observed_at=record.observed_at,
        received_at=record.received_at,
        valid_until=record.valid_until,
        freshness_status=record.freshness_status,
        evidence_reference=record.evidence_reference,
    )
    position = SimpleNamespace(id=record.asset_position_id, program_id=PROGRAM_ID)
    registry = ReconciliationSourceRegistry()
    registry.register(
        InternalValuationObservationSource(
            cast(AsyncSession, _Session([(observation, position)])),
            program_id=PROGRAM_ID,
        )
    )

    snapshot = await acquire_verified_snapshot(
        registry,
        target=_target(),
        scope={"program_id": str(PROGRAM_ID)},
    )

    assert snapshot.reconciliation_type == "INTERNAL_VALUATION_OBSERVATION"
    assert snapshot.records[0].observation_id == record.observation_id


def test_valuation_snapshot_rejects_wrong_program_future_time_and_duplicates():
    for records in (
        [_record(program_id=uuid4())],
        [_record(observed_at=NOW + timedelta(seconds=1))],
    ):
        with pytest.raises(ReconciliationSourceAcquisitionError) as exc:
            build_internal_valuation_snapshot(
                records,
                program_id=PROGRAM_ID,
                snapshot_at=NOW,
                received_at=NOW + timedelta(seconds=1),
            )
        assert exc.value.code == "SOURCE_CONTRACT_INVALID"

    record = _record()
    with pytest.raises(ReconciliationSourceAcquisitionError) as duplicate:
        build_internal_valuation_snapshot(
            [record, record],
            program_id=PROGRAM_ID,
            snapshot_at=NOW,
            received_at=NOW,
        )
    assert duplicate.value.code == "SOURCE_CONTRACT_INVALID"


def test_valuation_snapshot_rejects_more_evidence_than_contract_allows():
    records = [_record() for _ in range(1001)]
    with pytest.raises(ReconciliationSourceAcquisitionError) as exc:
        build_internal_valuation_snapshot(
            records,
            program_id=PROGRAM_ID,
            snapshot_at=NOW,
            received_at=NOW,
        )
    assert exc.value.code == "SOURCE_CONTRACT_INVALID"


@pytest.mark.integration
async def test_internal_valuation_source_reads_program_scoped_observations(
    database,
    clean_sprint07_guarantee_tables,
):
    actor = Identity(
        identity_type="TEST",
        external_subject=f"sprint39-valuation-{uuid4()}",
        status="ACTIVE",
    )
    participant = Participant(external_reference=f"SPRINT39-{uuid4()}")
    program = Program(
        code=f"SPRINT39-{uuid4()}",
        name="Sprint 39 valuation observation test",
        status="ACTIVE",
        created_by=uuid4(),
    )
    asset_type = AssetType(
        asset_code=f"S39-{uuid4().hex[:12]}",
        name="Valuation test asset",
        status="ACTIVE",
        unit_code="GRAM",
        quantity_scale=8,
        created_by=uuid4(),
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([actor, participant, program, asset_type])
            await session.flush()
            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                consent_state="RECORDED",
                started_at=datetime.now(UTC) - timedelta(days=1),
                created_by=actor.id,
            )
            session.add(episode)
            await session.flush()
            position = AssetPosition(
                participation_episode_id=episode.id,
                program_id=program.id,
                asset_type_id=asset_type.id,
                ownership_funding_type="PARTICIPANT_OWNED",
                legal_owner_participant_id=participant.id,
                quantity=Decimal("5.125"),
                unit_code="GRAM",
                lifecycle_status="ACTIVE",
                created_by=actor.id,
            )
            session.add(position)
            await session.flush()
            observation = ValuationObservation(
                asset_position_id=position.id,
                valued_quantity=Decimal("5.125"),
                unit_price=Decimal("11.00"),
                valuation_currency="IRR",
                fx_rate=None,
                gross_market_value=Decimal("56.375"),
                source_name="integration-test-record",
                source_reference="recorded-source-reference",
                source_version_reference="recorded-v1",
                observed_at=datetime.now(UTC) - timedelta(minutes=2),
                received_at=datetime.now(UTC) - timedelta(minutes=1),
                valid_until=None,
                freshness_status="STALE",
                evidence_reference="recorded-evidence-ref",
                created_by=actor.id,
            )
            session.add(observation)
            await session.flush()
            observation_id = observation.id

    async with database.session_factory() as session:
        source = InternalValuationObservationSource(session, program_id=program.id)
        snapshot = await source.fetch_reconciliation_snapshot(
            _target(program.id), {"program_id": str(program.id)}
        )

    assert len(snapshot.records) == 1
    assert snapshot.records[0].observation_id == observation_id
    assert snapshot.records[0].freshness_status == "STALE"
    assert Decimal(snapshot.records[0].gross_market_value) == Decimal("56.375")
