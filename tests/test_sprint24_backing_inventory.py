from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from badban.application.backing_source_inventory import (
    BackingInventoryError,
    read_backing_source_inventory,
)
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    GuaranteeCase,
    Identity,
    JournalEntry,
    Participant,
    ParticipationEpisode,
    Program,
    ValuationObservation,
)


async def _source_facts(database):
    actor = Identity(
        identity_type="STAFF",
        external_subject=f"inventory-actor-{uuid4()}",
        status="ACTIVE",
    )
    participant = Participant(external_reference=f"inventory-{uuid4()}")
    program = Program(code=f"INV-{uuid4().hex[:12]}", name="Inventory Program", created_by=uuid4())
    asset_type_a = AssetType(
        asset_code=f"INV-A-{uuid4().hex[:12]}",
        name="Asset A",
        status="ACTIVE",
        unit_code="UNIT",
        quantity_scale=8,
        created_by=uuid4(),
    )
    asset_type_b = AssetType(
        asset_code=f"INV-B-{uuid4().hex[:12]}",
        name="Asset B",
        status="ACTIVE",
        unit_code="UNIT",
        quantity_scale=8,
        created_by=uuid4(),
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([actor, participant, program, asset_type_a, asset_type_b])
            await session.flush()
            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                consent_state="RECORDED",
                started_at=datetime.now(UTC),
                created_by=actor.id,
            )
            session.add(episode)
            await session.flush()
            owned = AssetPosition(
                participation_episode_id=episode.id,
                program_id=program.id,
                asset_type_id=asset_type_a.id,
                ownership_funding_type="PARTICIPANT_OWNED",
                legal_owner_participant_id=participant.id,
                quantity=Decimal("5.125"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                created_by=actor.id,
            )
            attributed = AssetPosition(
                participation_episode_id=episode.id,
                program_id=program.id,
                asset_type_id=asset_type_b.id,
                ownership_funding_type="PROGRAM_ATTRIBUTED",
                legal_owner_entity_id=uuid4(),
                quantity=Decimal("12"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                created_by=actor.id,
            )
            session.add_all([owned, attributed])
            await session.flush()
            first = ValuationObservation(
                asset_position_id=owned.id,
                valued_quantity=Decimal("5.125"),
                unit_price=Decimal("10.25"),
                valuation_currency="IRR",
                fx_rate=None,
                gross_market_value=Decimal("52.53125"),
                source_name="first-test-source",
                source_reference="valuation:old",
                observed_at=datetime.now(UTC) - timedelta(days=1),
                received_at=datetime.now(UTC) - timedelta(days=1),
                freshness_status="STALE",
                created_by=actor.id,
            )
            second = ValuationObservation(
                asset_position_id=owned.id,
                valued_quantity=Decimal("5.125"),
                unit_price=Decimal("11.00"),
                valuation_currency="IRR",
                fx_rate=None,
                gross_market_value=Decimal("56.375"),
                source_name="second-test-source",
                source_reference="valuation:new",
                observed_at=datetime.now(UTC),
                received_at=datetime.now(UTC),
                freshness_status="FRESH",
                created_by=actor.id,
            )
            session.add_all([first, second])
            await session.flush()
            return {
                "episode": episode.id,
                "program": program.id,
                "participant": participant.id,
                "owned": owned.id,
                "attributed": attributed.id,
                "type_a": asset_type_a.id,
                "actor": actor.id,
            }


@pytest.mark.integration
async def test_inventory_keeps_all_multi_asset_sources_and_raw_valuation_history(
    database, clean_sprint03_tables
) -> None:
    facts = await _source_facts(database)
    async with database.session_factory() as session:
        inventory = await read_backing_source_inventory(
            session, episode_id=facts["episode"], program_id=facts["program"]
        )
        replay = await read_backing_source_inventory(
            session, episode_id=facts["episode"], program_id=facts["program"]
        )
        journal_count = await session.scalar(select(func.count()).select_from(JournalEntry))
        guarantee_count = await session.scalar(select(func.count()).select_from(GuaranteeCase))

    assert len(inventory.sources) == 2
    assert inventory == replay
    assert inventory.source_fingerprint == replay.source_fingerprint
    assert len(inventory.source_fingerprint) == 64
    owned = next(source for source in inventory.sources if source.position_id == facts["owned"])
    attributed = next(
        source for source in inventory.sources if source.position_id == facts["attributed"]
    )
    assert owned.ownership_funding_type == "PARTICIPANT_OWNED"
    assert owned.legal_owner_participant_id == facts["participant"]
    assert owned.position_version >= 1
    assert owned.asset_type_version >= 1
    assert owned.quantity == Decimal("5.125")
    assert [obs.source_reference for obs in owned.valuation_history] == [
        "valuation:old",
        "valuation:new",
    ]
    assert [obs.recorded_freshness_status for obs in owned.valuation_history] == [
        "STALE",
        "FRESH",
    ]
    assert attributed.ownership_funding_type == "PROGRAM_ATTRIBUTED"
    assert attributed.valuation_history == ()
    assert not hasattr(inventory, "capacity")
    assert not hasattr(inventory, "eligible")
    assert journal_count == 0
    assert guarantee_count == 0


@pytest.mark.integration
async def test_inventory_missing_episode_and_cross_program_fail_closed(
    database, clean_sprint03_tables
) -> None:
    facts = await _source_facts(database)
    async with database.session_factory() as session:
        with pytest.raises(BackingInventoryError) as missing:
            await read_backing_source_inventory(
                session, episode_id=uuid4(), program_id=facts["program"]
            )
        assert missing.value.code == "BACKING_SOURCE_EPISODE_NOT_FOUND"
        with pytest.raises(BackingInventoryError) as cross_program:
            await read_backing_source_inventory(
                session, episode_id=facts["episode"], program_id=uuid4()
            )
        assert cross_program.value.code == "BACKING_SOURCE_SCOPE_CONFLICT"


@pytest.mark.integration
async def test_inventory_fingerprint_changes_on_real_source_change(
    database, clean_sprint03_tables
) -> None:
    facts = await _source_facts(database)
    async with database.session_factory() as session:
        before = await read_backing_source_inventory(
            session, episode_id=facts["episode"], program_id=facts["program"]
        )
    async with database.session_factory() as session:
        async with session.begin():
            source = await session.get(AssetPosition, facts["owned"])
            assert source is not None
            source.quantity = Decimal("6.125")
    async with database.session_factory() as session:
        after = await read_backing_source_inventory(
            session, episode_id=facts["episode"], program_id=facts["program"]
        )
    assert before.source_fingerprint != after.source_fingerprint
    assert before.sources != after.sources


@pytest.mark.integration
async def test_inventory_rejects_mismatched_asset_source_lineage(
    database, clean_sprint03_tables
) -> None:
    facts = await _source_facts(database)
    async with database.session_factory() as session:
        async with session.begin():
            second_program = Program(
                code=f"INV-OTHER-{uuid4().hex[:12]}",
                name="Other Program",
                created_by=uuid4(),
            )
            session.add(second_program)
            await session.flush()
            source = await session.get(AssetPosition, facts["owned"])
            assert source is not None
            source.program_id = second_program.id
    async with database.session_factory() as session:
        with pytest.raises(BackingInventoryError) as mismatch:
            await read_backing_source_inventory(
                session, episode_id=facts["episode"], program_id=facts["program"]
            )
    assert mismatch.value.code == "BACKING_SOURCE_SCOPE_CONFLICT"
