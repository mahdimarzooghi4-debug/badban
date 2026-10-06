from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from badban.api.errors import ApiError
from badban.application.policy_resolution import resolve_active_policy_pack
from badban.infrastructure.persistence.models import PolicyVersion


def _active_pack(
    *,
    policy_code: str,
    scope_definition: dict[str, object],
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> PolicyVersion:
    return PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code=policy_code,
        version_number=1,
        lifecycle_status="ACTIVE",
        scope_definition=scope_definition,
        payload={"component_version_ids": []},
        schema_version="1",
        effective_from=effective_from,
        effective_to=effective_to,
        activated_at=datetime.now(UTC),
        created_by=uuid4(),
        version=4,
    )


@pytest.mark.integration
async def test_resolve_active_policy_pack_returns_exact_scope_and_effective_match(
    database,
    clean_sprint04_policy_tables,
) -> None:
    effective_at = datetime.now(UTC)
    expected = _active_pack(
        policy_code="BOUNDED_PILOT",
        scope_definition={"pilot_scope": "bounded-pilot"},
        effective_from=effective_at - timedelta(hours=1),
        effective_to=effective_at + timedelta(hours=1),
    )
    other_scope = _active_pack(
        policy_code="OTHER_SCOPE",
        scope_definition={"pilot_scope": "other-pilot"},
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([expected, other_scope])
            await session.flush()
            expected_id = expected.id

    async with database.session_factory() as session:
        resolved = await resolve_active_policy_pack(
            session,
            scope_definition={"pilot_scope": "bounded-pilot"},
            effective_at=effective_at,
        )

    assert resolved.policy_pack_id == expected_id
    assert resolved.policy_code == "BOUNDED_PILOT"
    assert resolved.version_number == 1


@pytest.mark.integration
async def test_resolve_active_policy_pack_fails_when_exact_scope_has_no_effective_match(
    database,
    clean_sprint04_policy_tables,
) -> None:
    effective_at = datetime.now(UTC)
    expired = _active_pack(
        policy_code="EXPIRED_PACK",
        scope_definition={"pilot_scope": "bounded-pilot"},
        effective_from=effective_at - timedelta(hours=2),
        effective_to=effective_at - timedelta(hours=1),
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(expired)

    async with database.session_factory() as session:
        with pytest.raises(ApiError) as exc:
            await resolve_active_policy_pack(
                session,
                scope_definition={"pilot_scope": "bounded-pilot"},
                effective_at=effective_at,
            )

    assert exc.value.code == "POLICY_SCOPE_NOT_FOUND"


@pytest.mark.integration
async def test_resolve_active_policy_pack_fails_closed_on_ambiguous_exact_scope(
    database,
    clean_sprint04_policy_tables,
) -> None:
    scope = {"pilot_scope": "bounded-pilot"}
    first = _active_pack(policy_code="PACK_A", scope_definition=scope)
    second = _active_pack(policy_code="PACK_B", scope_definition=scope)

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([first, second])
            await session.flush()
            expected_ids = sorted([str(first.id), str(second.id)])

    async with database.session_factory() as session:
        with pytest.raises(ApiError) as exc:
            await resolve_active_policy_pack(
                session,
                scope_definition=scope,
                effective_at=datetime.now(UTC),
            )

    assert exc.value.code == "POLICY_SCOPE_AMBIGUOUS"
    assert exc.value.details == {"policy_pack_ids": expected_ids}
