from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.internal_asset_inventory_source import (
    InternalAssetInventorySource,
    build_internal_asset_inventory_snapshot,
)
from badban.application.reconciliation_sources import (
    InternalAssetInventoryRecord,
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
)

NOW = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
PROGRAM_ID = UUID("00000000-0000-0000-0000-000000000038")


def _record(*, program_id=PROGRAM_ID, quantity="5.125"):
    return InternalAssetInventoryRecord(
        observed_at=NOW - timedelta(minutes=1),
        asset_position_id=uuid4(),
        position_version=1,
        participation_episode_id=uuid4(),
        asset_type_id=uuid4(),
        asset_type_code="GOLD_UNIT",
        asset_type_status="ACTIVE",
        program_id=program_id,
        ownership_funding_type="PARTICIPANT_OWNED",
        legal_owner_entity_id=None,
        legal_owner_participant_id=uuid4(),
        custodian_legal_entity_id=None,
        quantity=quantity,
        unit_code="GRAM",
        lifecycle_status="ACTIVE",
        source_reference="asset-position:source-1",
    )


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return SimpleNamespace(all=lambda: [(*row, NOW) for row in self.rows])


def _target(program_id=PROGRAM_ID):
    return SourceTarget(reconciliation_type="INTERNAL_ASSET_INVENTORY", program_id=program_id)


def test_internal_asset_inventory_snapshot_is_typed_and_evidence_bound():
    record = _record()
    snapshot = build_internal_asset_inventory_snapshot(
        [record],
        program_id=PROGRAM_ID,
        snapshot_at=NOW,
        received_at=NOW + timedelta(seconds=1),
    )

    assert snapshot.reconciliation_type == "INTERNAL_ASSET_INVENTORY"
    assert snapshot.records == (record,)
    assert snapshot.evidence_references == (f"asset-position:{record.asset_position_id}",)
    assert snapshot.content_hash


async def test_internal_asset_inventory_source_uses_verified_acquisition():
    record = _record()
    position = SimpleNamespace(
        id=record.asset_position_id,
        version=1,
        updated_at=record.observed_at,
        program_id=PROGRAM_ID,
        participation_episode_id=record.participation_episode_id,
        asset_type_id=record.asset_type_id,
        ownership_funding_type="PARTICIPANT_OWNED",
        legal_owner_entity_id=None,
        legal_owner_participant_id=record.legal_owner_participant_id,
        custodian_legal_entity_id=None,
        quantity=record.quantity,
        unit_code="GRAM",
        lifecycle_status="ACTIVE",
        source_reference=record.source_reference,
    )
    asset_type = SimpleNamespace(
        id=record.asset_type_id,
        version=1,
        asset_code="GOLD_UNIT",
        status="ACTIVE",
    )
    episode = SimpleNamespace(
        id=record.participation_episode_id,
        version=1,
        program_id=PROGRAM_ID,
    )
    registry = ReconciliationSourceRegistry()
    registry.register(
        InternalAssetInventorySource(
            cast(AsyncSession, _Session([(position, asset_type, episode)])),
            program_id=PROGRAM_ID,
        )
    )

    snapshot = await acquire_verified_snapshot(
        registry,
        target=_target(),
        scope={"program_id": str(PROGRAM_ID)},
    )

    assert snapshot.reconciliation_type == "INTERNAL_ASSET_INVENTORY"
    assert snapshot.records[0].quantity == "5.125"
    assert snapshot.records[0].asset_position_id == record.asset_position_id


def test_inventory_rejects_wrong_program_and_duplicate_position_ids():
    with pytest.raises(ReconciliationSourceAcquisitionError) as wrong_program:
        build_internal_asset_inventory_snapshot(
            [_record(program_id=uuid4())],
            program_id=PROGRAM_ID,
            snapshot_at=NOW,
            received_at=NOW,
        )
    assert wrong_program.value.code == "SOURCE_CONTRACT_INVALID"

    record = _record()
    with pytest.raises(ReconciliationSourceAcquisitionError) as duplicate:
        build_internal_asset_inventory_snapshot(
            [record, record],
            program_id=PROGRAM_ID,
            snapshot_at=NOW,
            received_at=NOW,
        )
    assert duplicate.value.code == "SOURCE_CONTRACT_INVALID"


def test_inventory_record_requires_consistent_owner_dimensions():
    with pytest.raises(ValueError):
        InternalAssetInventoryRecord.model_validate(
            _record().model_dump(mode="json") | {"legal_owner_participant_id": None}
        )


@pytest.mark.integration
async def test_internal_inventory_source_reads_program_scoped_positions(
    database,
    clean_sprint07_guarantee_tables,
):
    actor = Identity(
        identity_type="TEST",
        external_subject=f"sprint38-inventory-{uuid4()}",
        status="ACTIVE",
    )
    participant = Participant(external_reference=f"SPRINT38-{uuid4()}")
    program = Program(
        code=f"SPRINT38-{uuid4()}",
        name="Sprint 38 internal inventory test",
        status="ACTIVE",
        created_by=uuid4(),
    )
    asset_type = AssetType(
        asset_code=f"S38-{uuid4().hex[:12]}",
        name="Inventory test asset",
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
                quantity="5.125",
                unit_code="GRAM",
                lifecycle_status="ACTIVE",
                source_reference="test-internal-position",
                created_by=actor.id,
            )
            session.add(position)
            await session.flush()
            position_id = position.id

    async with database.session_factory() as session:
        source = InternalAssetInventorySource(session, program_id=program.id)
        snapshot = await source.fetch_reconciliation_snapshot(
            _target(program.id), {"program_id": str(program.id)}
        )

    assert len(snapshot.records) == 1
    assert snapshot.records[0].asset_position_id == position_id
    assert snapshot.records[0].quantity == "5.125000000000000000"
    assert snapshot.records[0].legal_owner_participant_id == participant.id
