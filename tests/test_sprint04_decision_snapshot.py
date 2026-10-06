from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError

from badban.application.decision_snapshot import (
    create_decision_snapshot,
    get_decision_snapshot,
)
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_resolution import resolve_active_policy_pack
from badban.infrastructure.persistence.models import DecisionSnapshot, PolicyVersion


async def _persist_snapshot(database) -> tuple[UUID, UUID, dict[str, object], dict[str, object]]:
    scope: dict[str, object] = {"pilot_scope": "bounded-pilot"}
    material_input: dict[str, object] = {"eligible_quantity": "12.500"}
    material_output: dict[str, object] = {"observed_change": "synthetic"}
    component = PolicyVersion(
        policy_type="ASSET_TYPE_POLICY",
        policy_code="SNAPSHOT_TEST_COMPONENT",
        version_number=1,
        lifecycle_status="DRAFT",
        scope_definition=scope,
        payload={},
        schema_version="1",
        created_by=uuid4(),
        version=1,
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(component)
            await session.flush()
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="SNAPSHOT_TEST_PACK",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition=scope,
                payload={"component_version_ids": [str(component.id)]},
                schema_version="1",
                activated_at=datetime.now(UTC),
                created_by=uuid4(),
                version=4,
            )
            session.add(pack)
            await session.flush()
            pack_id = pack.id

    effective_at = datetime.now(UTC)
    async with database.session_factory() as session:
        async with session.begin():
            resolved = await resolve_active_policy_pack(
                session,
                scope_definition=scope,
                effective_at=effective_at,
            )
            snapshot = await create_decision_snapshot(
                session,
                business_entity_type="SYNTHETIC_ENTITY",
                business_entity_id="entity-1",
                decision_type="SYNTHETIC_DECISION",
                resolved_policy_pack=resolved,
                algorithm_code="SYNTHETIC_ALGORITHM",
                algorithm_version="v1",
                material_input_payload=material_input,
                material_output_payload=material_output,
                effective_at=effective_at,
                actor_type="SYSTEM",
                actor_id=uuid4(),
                valuation_observation_ids=(uuid4(),),
                authoritative_external_references=("synthetic:reference",),
            )
            snapshot_id = snapshot.id

    return snapshot_id, pack_id, material_input, material_output


@pytest.mark.integration
async def test_decision_snapshot_persists_exact_versions_hashes_and_read_model(
    database,
    clean_sprint04_policy_tables,
) -> None:
    snapshot_id, pack_id, material_input, material_output = await _persist_snapshot(database)

    async with database.session_factory() as session:
        snapshot = await get_decision_snapshot(session, snapshot_id)

    assert snapshot.policy_pack_id == pack_id
    assert snapshot.policy_pack_version == 1
    assert len(snapshot.component_version_ids) == 1
    assert snapshot.algorithm_code == "SYNTHETIC_ALGORITHM"
    assert snapshot.algorithm_version == "v1"
    assert snapshot.material_input_payload == material_input
    assert snapshot.material_output_payload == material_output
    assert snapshot.input_hash == canonical_request_hash(material_input)
    assert snapshot.output_hash == canonical_request_hash(material_output)
    assert len(snapshot.valuation_observation_ids) == 1
    assert snapshot.authoritative_external_references == ["synthetic:reference"]


@pytest.mark.integration
async def test_decision_snapshot_rejects_update_and_delete(
    database,
    clean_sprint04_policy_tables,
) -> None:
    snapshot_id, _, _, _ = await _persist_snapshot(database)

    with pytest.raises(DBAPIError):
        async with database.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(DecisionSnapshot)
                    .where(DecisionSnapshot.id == snapshot_id)
                    .values(decision_type="MUTATED")
                )

    with pytest.raises(DBAPIError):
        async with database.session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(DecisionSnapshot).where(DecisionSnapshot.id == snapshot_id)
                )

    async with database.session_factory() as session:
        snapshot = await get_decision_snapshot(session, snapshot_id)

    assert snapshot.decision_type == "SYNTHETIC_DECISION"
