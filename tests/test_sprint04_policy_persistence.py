from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from badban.infrastructure.persistence.models import PolicyVersion


@pytest.mark.integration
async def test_policy_version_round_trip_persists_explicit_versioned_state(
    database,
    clean_sprint04_policy_tables,
) -> None:
    policy = PolicyVersion(
        policy_type="ASSET_TYPE_POLICY",
        policy_code="ASSET_ELIGIBILITY",
        version_number=1,
        lifecycle_status="DRAFT",
        scope_definition={"pilot_scope": "bounded-pilot", "asset_type": "GENERIC"},
        payload={"eligible": True},
        schema_version="1",
        effective_from=datetime.now(UTC),
        created_by=uuid4(),
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(policy)
            await session.flush()
            policy_id = policy.id

    async with database.session_factory() as session:
        stored = await session.get(PolicyVersion, policy_id)

    assert stored is not None
    assert stored.policy_type == "ASSET_TYPE_POLICY"
    assert stored.policy_code == "ASSET_ELIGIBILITY"
    assert stored.version_number == 1
    assert stored.lifecycle_status == "DRAFT"
    assert stored.scope_definition["pilot_scope"] == "bounded-pilot"
    assert stored.payload == {"eligible": True}
    assert stored.payload_hash is None


@pytest.mark.integration
async def test_policy_version_identity_is_unique(
    database,
    clean_sprint04_policy_tables,
) -> None:
    common = dict(
        policy_type="RISK_APPETITE_POLICY",
        policy_code="PILOT_RISK",
        version_number=1,
        lifecycle_status="DRAFT",
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload={},
        schema_version="1",
        created_by=uuid4(),
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(PolicyVersion(**common))

    async with database.session_factory() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(PolicyVersion(**common))
                await session.flush()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("overrides", "expected_constraint"),
    [
        ({"policy_type": "UNKNOWN_POLICY"}, "ck_policy_version_type"),
        ({"version_number": 0}, "ck_policy_version_number_positive"),
        ({"lifecycle_status": "UNKNOWN"}, "ck_policy_version_lifecycle_status"),
    ],
)
async def test_policy_version_rejects_invalid_schema_values(
    database,
    clean_sprint04_policy_tables,
    overrides,
    expected_constraint: str,
) -> None:
    values = {
        "policy_type": "LEGAL_AUTHORIZATION_POLICY",
        "policy_code": "LEGAL_BASELINE",
        "version_number": 1,
        "lifecycle_status": "DRAFT",
        "scope_definition": {"pilot_scope": "bounded-pilot"},
        "payload": {},
        "schema_version": "1",
        "created_by": uuid4(),
    }
    values.update(overrides)

    async with database.session_factory() as session:
        with pytest.raises(IntegrityError) as exc:
            async with session.begin():
                session.add(PolicyVersion(**values))
                await session.flush()

    assert expected_constraint in str(exc.value.orig)


@pytest.mark.integration
async def test_policy_version_rejects_invalid_effective_window(
    database,
    clean_sprint04_policy_tables,
) -> None:
    start = datetime.now(UTC)
    policy = PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code="BOUNDED_PILOT",
        version_number=1,
        lifecycle_status="DRAFT",
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload={"component_version_ids": []},
        schema_version="1",
        effective_from=start,
        effective_to=start - timedelta(seconds=1),
        created_by=uuid4(),
    )

    async with database.session_factory() as session:
        with pytest.raises(IntegrityError) as exc:
            async with session.begin():
                session.add(policy)
                await session.flush()

    assert "ck_policy_version_effective_window" in str(exc.value.orig)


@pytest.mark.integration
async def test_policy_version_rows_are_queryable_by_explicit_identity(
    database,
    clean_sprint04_policy_tables,
) -> None:
    rows = [
        PolicyVersion(
            policy_type="OWNERSHIP_FUNDING_POLICY",
            policy_code="OWNERSHIP",
            version_number=version,
            lifecycle_status="DRAFT",
            scope_definition={"pilot_scope": "bounded-pilot"},
            payload={"version_marker": version},
            schema_version="1",
            created_by=uuid4(),
        )
        for version in (1, 2)
    ]

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all(rows)

    async with database.session_factory() as session:
        found = await session.scalar(
            select(PolicyVersion).where(
                PolicyVersion.policy_type == "OWNERSHIP_FUNDING_POLICY",
                PolicyVersion.policy_code == "OWNERSHIP",
                PolicyVersion.version_number == 2,
            )
        )

    assert found is not None
    assert found.payload == {"version_marker": 2}
