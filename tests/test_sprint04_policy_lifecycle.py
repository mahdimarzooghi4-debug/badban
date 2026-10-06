from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_lifecycle import (
    approve_policy,
    assert_policy_payload_mutable,
    assert_policy_transition_allowed,
    review_policy,
)
from badban.infrastructure.persistence.models import PolicyVersion


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("DRAFT", "REVIEWED"),
        ("REVIEWED", "APPROVED"),
        ("APPROVED", "ACTIVE"),
        ("ACTIVE", "SUPERSEDED"),
        ("ACTIVE", "RETIRED"),
    ],
)
def test_policy_lifecycle_allows_only_declared_forward_transitions(
    current_status: str,
    target_status: str,
) -> None:
    assert_policy_transition_allowed(current_status, target_status)


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("DRAFT", "APPROVED"),
        ("DRAFT", "ACTIVE"),
        ("REVIEWED", "ACTIVE"),
        ("APPROVED", "REVIEWED"),
        ("ACTIVE", "APPROVED"),
        ("SUPERSEDED", "ACTIVE"),
        ("RETIRED", "ACTIVE"),
        ("UNKNOWN", "DRAFT"),
    ],
)
def test_policy_lifecycle_rejects_skips_reversals_and_terminal_reactivation(
    current_status: str,
    target_status: str,
) -> None:
    with pytest.raises(ApiError) as exc:
        assert_policy_transition_allowed(current_status, target_status)

    assert exc.value.code == "POLICY_VALIDATION_FAILED"
    assert exc.value.details == {
        "current_status": current_status,
        "target_status": target_status,
    }


@pytest.mark.parametrize("status", ["DRAFT", "REVIEWED", "APPROVED"])
def test_policy_payload_remains_mutable_before_activation(status: str) -> None:
    policy = _policy(status)

    assert_policy_payload_mutable(policy)


@pytest.mark.parametrize("status", ["ACTIVE", "SUPERSEDED", "RETIRED"])
def test_policy_payload_is_immutable_after_activation_history_begins(status: str) -> None:
    policy = _policy(status)

    with pytest.raises(ApiError) as exc:
        assert_policy_payload_mutable(policy)

    assert exc.value.code == "POLICY_VALIDATION_FAILED"
    assert exc.value.details == {"lifecycle_status": status}


def _policy(status: str) -> PolicyVersion:
    return PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code="BOUNDED_PILOT",
        version_number=1,
        lifecycle_status=status,
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload={"component_version_ids": []},
        schema_version="1",
        created_by=uuid4(),
        version=1,
    )



@pytest.mark.integration
async def test_review_and_approve_commands_persist_separate_lifecycle_steps(
    database,
    clean_sprint04_policy_tables,
) -> None:
    policy = _policy("DRAFT")
    async with database.session_factory() as session:
        async with session.begin():
            session.add(policy)
            await session.flush()
            policy_id = policy.id

    async with database.session_factory() as session:
        async with session.begin():
            reviewed = await review_policy(session, policy_id=policy_id)
            assert reviewed.lifecycle_status == "REVIEWED"
            assert reviewed.version == 2
            assert reviewed.payload_hash is None
            assert reviewed.approved_by is None
            assert reviewed.approved_at is None
            assert reviewed.activated_at is None

    approver_id = uuid4()
    approved_at = datetime.now(UTC)
    async with database.session_factory() as session:
        async with session.begin():
            approved = await approve_policy(
                session,
                policy_id=policy_id,
                approved_by=approver_id,
                now=approved_at,
            )
            assert approved.lifecycle_status == "APPROVED"
            assert approved.version == 3
            assert approved.payload_hash == canonical_request_hash(approved.payload)
            assert approved.approved_by == approver_id
            assert approved.approved_at == approved_at
            assert approved.activated_at is None


@pytest.mark.integration
async def test_approve_command_cannot_skip_review(
    database,
    clean_sprint04_policy_tables,
) -> None:
    policy = _policy("DRAFT")
    async with database.session_factory() as session:
        async with session.begin():
            session.add(policy)
            await session.flush()
            policy_id = policy.id

    async with database.session_factory() as session:
        with pytest.raises(ApiError) as exc:
            async with session.begin():
                await approve_policy(
                    session,
                    policy_id=policy_id,
                    approved_by=uuid4(),
                )

    assert exc.value.code == "POLICY_VALIDATION_FAILED"

    async with database.session_factory() as session:
        stored = await session.get(PolicyVersion, policy_id)

    assert stored is not None
    assert stored.lifecycle_status == "DRAFT"
    assert stored.payload_hash is None
    assert stored.approved_by is None
    assert stored.approved_at is None
    assert stored.activated_at is None
