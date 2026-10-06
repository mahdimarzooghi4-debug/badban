from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_lifecycle import (
    activate_policy,
    approve_policy,
    assert_policy_payload_mutable,
    assert_policy_transition_allowed,
    policy_transition_approval_payload,
    review_policy,
)
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    AuditEvent,
    Identity,
    OutboxMessage,
    PolicyVersion,
)


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



async def _approved_policy_request(
    session,
    *,
    policy: PolicyVersion,
    target_status: str,
) -> ApprovalRequest:
    maker = Identity(
        identity_type="STAFF",
        external_subject=f"maker-{uuid4()}",
        status="ACTIVE",
    )
    checker = Identity(
        identity_type="GOVERNANCE",
        external_subject=f"checker-{uuid4()}",
        status="ACTIVE",
    )
    session.add_all([maker, checker])
    await session.flush()

    payload = policy_transition_approval_payload(policy, target_status)
    action_type = (\n        "POLICY_APPROVAL" if target_status == "APPROVED" else "POLICY_ACTIVATION"\n    )
    approval = ApprovalRequest(
        action_type=action_type,
        target_type="PolicyVersion",
        target_id=str(policy.id),
        target_aggregate_version=policy.version,
        maker_identity_id=maker.id,
        checker_identity_id=checker.id,
        required_checker_role="GOVERNANCE_APPROVER",
        scope_type="GLOBAL",
        scope_id=None,
        payload_hash=canonical_request_hash(payload),
        reason="sprint04 maker-checker test",
        evidence_refs=[],
        status="APPROVED",
        approved_at=datetime.now(UTC),
        version=2,
    )
    session.add(approval)
    await session.flush()
    return approval


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
            reviewed = await review_policy(
                session,
                policy_id=policy_id,
                actor_type="GOVERNANCE",
                actor_id=uuid4(),
                correlation_id=uuid4(),
            )
            assert reviewed.lifecycle_status == "REVIEWED"
            assert reviewed.version == 2
            assert reviewed.payload_hash is None
            assert reviewed.approved_by is None
            assert reviewed.approved_at is None
            assert reviewed.activated_at is None

    approved_at = datetime.now(UTC)
    async with database.session_factory() as session:
        async with session.begin():
            policy = await session.get(PolicyVersion, policy_id)
            assert policy is not None
            approval = await _approved_policy_request(
                session,
                policy=policy,
                target_status="APPROVED",
            )
            approver_id = approval.checker_identity_id
            assert approver_id is not None
            approved = await approve_policy(
                session,
                policy_id=policy_id,
                approval_id=approval.id,
                actor_type="GOVERNANCE",
                actor_id=uuid4(),
                correlation_id=uuid4(),
                now=approved_at,
            )
            assert approved.lifecycle_status == "APPROVED"
            assert approved.version == 3
            assert approved.payload_hash == canonical_request_hash(approved.payload)
            assert approved.approved_by == approver_id
            assert approved.approved_at == approved_at
            assert approved.activated_at is None

    async with database.session_factory() as session:
        audit_actions = set(
            (
                await session.scalars(
                    select(AuditEvent.action).where(
                        AuditEvent.aggregate_type == "PolicyVersion",
                        AuditEvent.aggregate_id == str(policy_id),
                    )
                )
            ).all()
        )
        outbox_types = set(
            (
                await session.scalars(
                    select(OutboxMessage.event_type).where(
                        OutboxMessage.aggregate_type == "PolicyVersion",
                        OutboxMessage.aggregate_id == str(policy_id),
                    )
                )
            ).all()
        )

    assert {"POLICY_VERSION_REVIEWED", "POLICY_VERSION_APPROVED"} <= audit_actions
    assert {"PolicyPackReviewed", "PolicyPackApproved"} <= outbox_types


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
                policy = await session.get(PolicyVersion, policy_id)
                assert policy is not None
                approval = await _approved_policy_request(
                    session,
                    policy=policy,
                    target_status="APPROVED",
                )
                await approve_policy(
                    session,
                    policy_id=policy_id,
                    approval_id=approval.id,
                    actor_type="GOVERNANCE",
                    actor_id=uuid4(),
                    correlation_id=uuid4(),
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


@pytest.mark.integration
async def test_activate_policy_supersedes_prior_active_in_same_exact_scope(
    database,
    clean_sprint04_policy_tables,
) -> None:
    previous = PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code="BOUNDED_PILOT",
        version_number=1,
        lifecycle_status="ACTIVE",
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload={"component_version_ids": ["component-v1"]},
        payload_hash=canonical_request_hash({"component_version_ids": ["component-v1"]}),
        schema_version="1",
        activated_at=datetime.now(UTC),
        created_by=uuid4(),
        version=4,
    )
    candidate_payload = {"component_version_ids": ["component-v2"]}
    candidate = PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code="BOUNDED_PILOT",
        version_number=2,
        lifecycle_status="APPROVED",
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload=candidate_payload,
        payload_hash=canonical_request_hash(candidate_payload),
        schema_version="1",
        approved_at=datetime.now(UTC),
        approved_by=uuid4(),
        created_by=uuid4(),
        version=3,
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([previous, candidate])
            await session.flush()
            previous_id = previous.id
            candidate_id = candidate.id

    activated_at = datetime.now(UTC)
    async with database.session_factory() as session:
        async with session.begin():
            candidate = await session.get(PolicyVersion, candidate_id)
            assert candidate is not None
            approval = await _approved_policy_request(
                session,
                policy=candidate,
                target_status="ACTIVE",
            )
            activated = await activate_policy(
                session,
                policy_id=candidate_id,
                approval_id=approval.id,
                actor_type="GOVERNANCE",
                actor_id=uuid4(),
                correlation_id=uuid4(),
                now=activated_at,
            )

            assert activated.lifecycle_status == "ACTIVE"
            assert activated.activated_at == activated_at
            assert activated.version == 4

    async with database.session_factory() as session:
        old = await session.get(PolicyVersion, previous_id)
        new = await session.get(PolicyVersion, candidate_id)

    assert old is not None
    assert old.lifecycle_status == "SUPERSEDED"
    assert old.superseded_at == activated_at
    assert old.version == 5
    assert new is not None
    assert new.lifecycle_status == "ACTIVE"

    async with database.session_factory() as session:
        audit_actions = set(
            (
                await session.scalars(
                    select(AuditEvent.action).where(
                        AuditEvent.aggregate_type == "PolicyVersion",
                        AuditEvent.aggregate_id.in_([str(previous_id), str(candidate_id)]),
                    )
                )
            ).all()
        )
        outbox_types = set(
            (
                await session.scalars(
                    select(OutboxMessage.event_type).where(
                        OutboxMessage.aggregate_type == "PolicyVersion",
                        OutboxMessage.aggregate_id.in_([str(previous_id), str(candidate_id)]),
                    )
                )
            ).all()
        )

    assert {"POLICY_VERSION_SUPERSEDED", "POLICY_VERSION_ACTIVE"} <= audit_actions
    assert {"PolicyPackSuperseded", "PolicyPackActivated"} <= outbox_types


@pytest.mark.integration
async def test_activate_policy_rejects_payload_changed_after_approval(
    database,
    clean_sprint04_policy_tables,
) -> None:
    approved_payload = {"component_version_ids": ["approved-component"]}
    policy = PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code="BOUNDED_PILOT",
        version_number=1,
        lifecycle_status="APPROVED",
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload={"component_version_ids": ["changed-component"]},
        payload_hash=canonical_request_hash(approved_payload),
        schema_version="1",
        approved_at=datetime.now(UTC),
        approved_by=uuid4(),
        created_by=uuid4(),
        version=3,
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(policy)
            await session.flush()
            policy_id = policy.id

    async with database.session_factory() as session:
        with pytest.raises(ApiError) as exc:
            async with session.begin():
                policy = await session.get(PolicyVersion, policy_id)
                assert policy is not None
                approval = await _approved_policy_request(
                    session,
                    policy=policy,
                    target_status="ACTIVE",
                )
                await activate_policy(
                    session,
                    policy_id=policy_id,
                    approval_id=approval.id,
                    actor_type="GOVERNANCE",
                    actor_id=uuid4(),
                    correlation_id=uuid4(),
                )

    assert exc.value.code == "POLICY_VALIDATION_FAILED"

    async with database.session_factory() as session:
        stored = await session.get(PolicyVersion, policy_id)

    assert stored is not None
    assert stored.lifecycle_status == "APPROVED"
    assert stored.activated_at is None


@pytest.mark.integration
async def test_concurrent_activation_leaves_only_one_active_for_exact_scope(
    database,
    clean_sprint04_policy_tables,
) -> None:
    policies = []
    for version_number in (1, 2):
        payload = {"component_version_ids": [f"component-v{version_number}"]}
        policies.append(
            PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="BOUNDED_PILOT",
                version_number=version_number,
                lifecycle_status="APPROVED",
                scope_definition={"pilot_scope": "bounded-pilot"},
                payload=payload,
                payload_hash=canonical_request_hash(payload),
                schema_version="1",
                approved_at=datetime.now(UTC),
                approved_by=uuid4(),
                created_by=uuid4(),
                version=3,
            )
        )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all(policies)
            await session.flush()
            policy_ids = [policy.id for policy in policies]

    approvals = {}
    async with database.session_factory() as session:
        async with session.begin():
            for policy_id in policy_ids:
                policy = await session.get(PolicyVersion, policy_id)
                assert policy is not None
                approval = await _approved_policy_request(
                    session,
                    policy=policy,
                    target_status="ACTIVE",
                )
                approvals[policy_id] = approval.id

    async def activate(policy_id):
        async with database.session_factory() as session:
            async with session.begin():
                await activate_policy(
                    session,
                    policy_id=policy_id,
                    approval_id=approvals[policy_id],
                    actor_type="GOVERNANCE",
                    actor_id=uuid4(),
                    correlation_id=uuid4(),
                )

    await asyncio.gather(*(activate(policy_id) for policy_id in policy_ids))

    async with database.session_factory() as session:
        stored = (
            await session.scalars(
                select(PolicyVersion).where(
                    PolicyVersion.policy_type == "PILOT_POLICY_PACK",
                    PolicyVersion.policy_code == "BOUNDED_PILOT",
                )
            )
        ).all()

    assert sum(policy.lifecycle_status == "ACTIVE" for policy in stored) == 1
    assert sum(policy.lifecycle_status == "SUPERSEDED" for policy in stored) == 1



@pytest.mark.integration
async def test_policy_approval_rejects_stale_target_version(
    database,
    clean_sprint03_tables,
    clean_sprint04_policy_tables,
) -> None:
    policy = _policy("REVIEWED")
    policy.version = 2
    async with database.session_factory() as session:
        async with session.begin():
            session.add(policy)
            await session.flush()
            policy_id = policy.id
            approval = await _approved_policy_request(
                session,
                policy=policy,
                target_status="APPROVED",
            )
            approval_id = approval.id

    async with database.session_factory() as session:
        async with session.begin():
            stored = await session.get(PolicyVersion, policy_id)
            assert stored is not None
            stored.version += 1

    async with database.session_factory() as session:
        with pytest.raises(ApiError) as exc:
            async with session.begin():
                await approve_policy(
                    session,
                    policy_id=policy_id,
                    approval_id=approval_id,
                    actor_type="GOVERNANCE",
                    actor_id=uuid4(),
                    correlation_id=uuid4(),
                )

    assert exc.value.code == "APPROVAL_TARGET_VERSION_CONFLICT"

    async with database.session_factory() as session:
        stored = await session.get(PolicyVersion, policy_id)

    assert stored is not None
    assert stored.lifecycle_status == "REVIEWED"
    assert stored.payload_hash is None
    assert stored.approved_by is None


@pytest.mark.integration
async def test_policy_activation_rejects_changed_payload_bound_to_approval(
    database,
    clean_sprint03_tables,
    clean_sprint04_policy_tables,
) -> None:
    payload = {"component_version_ids": ["component-v1"]}
    policy = PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code="BOUNDED_PILOT",
        version_number=1,
        lifecycle_status="APPROVED",
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload=payload,
        payload_hash=canonical_request_hash(payload),
        schema_version="1",
        approved_at=datetime.now(UTC),
        approved_by=uuid4(),
        created_by=uuid4(),
        version=3,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(policy)
            await session.flush()
            policy_id = policy.id
            approval = await _approved_policy_request(
                session,
                policy=policy,
                target_status="ACTIVE",
            )
            approval_id = approval.id

    async with database.session_factory() as session:
        async with session.begin():
            stored = await session.get(PolicyVersion, policy_id)
            assert stored is not None
            stored.payload = {"component_version_ids": ["component-v2"]}

    async with database.session_factory() as session:
        with pytest.raises(ApiError) as exc:
            async with session.begin():
                await activate_policy(
                    session,
                    policy_id=policy_id,
                    approval_id=approval_id,
                    actor_type="GOVERNANCE",
                    actor_id=uuid4(),
                    correlation_id=uuid4(),
                )

    assert exc.value.code == "APPROVAL_PAYLOAD_CHANGED"

    async with database.session_factory() as session:
        stored = await session.get(PolicyVersion, policy_id)

    assert stored is not None
    assert stored.lifecycle_status == "APPROVED"
    assert stored.activated_at is None
