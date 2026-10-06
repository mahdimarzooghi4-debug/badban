from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.approval import (
    assert_approval_execution_eligible,
    get_approval_for_update,
)
from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    OutboxMessage,
    PolicyVersion,
)
from badban.security.audit import append_audit

POLICY_LIFECYCLE_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "DRAFT": frozenset({"REVIEWED"}),
    "REVIEWED": frozenset({"APPROVED"}),
    "APPROVED": frozenset({"ACTIVE"}),
    "ACTIVE": frozenset({"SUPERSEDED", "RETIRED"}),
    "SUPERSEDED": frozenset(),
    "RETIRED": frozenset(),
}

IMMUTABLE_POLICY_STATES = frozenset({"ACTIVE", "SUPERSEDED", "RETIRED"})

_POLICY_TRANSITION_APPROVAL_ACTIONS: Mapping[str, str] = {
    "APPROVED": "POLICY_APPROVAL",
    "ACTIVE": "POLICY_ACTIVATION",
}

_POLICY_PACK_EVENT_TYPES: Mapping[tuple[str, str], str] = {
    ("DRAFT", "REVIEWED"): "PolicyPackReviewed",
    ("REVIEWED", "APPROVED"): "PolicyPackApproved",
    ("APPROVED", "ACTIVE"): "PolicyPackActivated",
    ("ACTIVE", "SUPERSEDED"): "PolicyPackSuperseded",
    ("ACTIVE", "RETIRED"): "PolicyPackRetired",
}


def assert_policy_transition_allowed(current_status: str, target_status: str) -> None:
    allowed_targets = POLICY_LIFECYCLE_TRANSITIONS.get(current_status)
    if allowed_targets is None or target_status not in allowed_targets:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Policy lifecycle transition is not allowed",
            {
                "current_status": current_status,
                "target_status": target_status,
            },
        )


def assert_policy_payload_mutable(policy: PolicyVersion) -> None:
    if policy.lifecycle_status in IMMUTABLE_POLICY_STATES:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Policy payload is immutable in its current lifecycle state",
            {"lifecycle_status": policy.lifecycle_status},
        )


async def get_policy_for_update(
    session: AsyncSession,
    policy_id: UUID,
) -> PolicyVersion:
    policy = await session.scalar(
        select(PolicyVersion).where(PolicyVersion.id == policy_id).with_for_update()
    )
    if policy is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Policy Version was not found")
    return policy



def policy_transition_approval_payload(
    policy: PolicyVersion,
    target_status: str,
) -> dict[str, object]:
    action_type = _POLICY_TRANSITION_APPROVAL_ACTIONS[target_status]
    return {
        "action_type": action_type,
        "target_status": target_status,
        "policy_id": str(policy.id),
        "policy_type": policy.policy_type,
        "policy_code": policy.policy_code,
        "version_number": policy.version_number,
        "scope_definition": policy.scope_definition,
        "payload_hash": canonical_request_hash(policy.payload),
        "schema_version": policy.schema_version,
        "effective_from": (
            policy.effective_from.isoformat() if policy.effective_from is not None else None
        ),
        "effective_to": (
            policy.effective_to.isoformat() if policy.effective_to is not None else None
        ),
    }


async def _get_policy_transition_approval(
    session: AsyncSession,
    *,
    approval_id: UUID,
    policy: PolicyVersion,
    target_status: str,
    now: datetime,
) -> ApprovalRequest:
    approval = await get_approval_for_update(session, approval_id)
    expected_action = _POLICY_TRANSITION_APPROVAL_ACTIONS[target_status]
    if (
        approval.action_type != expected_action
        or approval.target_type != "PolicyVersion"
        or approval.target_id != str(policy.id)
    ):
        raise ApiError(
            409,
            "APPROVAL_PAYLOAD_CHANGED",
            "Approval Request is not bound to this policy transition",
        )
    if approval.checker_identity_id is None:
        raise ApiError(
            409,
            "MAKER_CHECKER_REQUIRED",
            "Policy transition requires an approved maker-checker request",
        )
    if approval.checker_identity_id == approval.maker_identity_id:
        raise ApiError(
            409,
            "SELF_APPROVAL_FORBIDDEN",
            "Maker and checker must be distinct identities",
        )

    assert_approval_execution_eligible(
        approval,
        payload=policy_transition_approval_payload(policy, target_status),
        current_target_version=policy.version,
        now=now,
    )
    return approval


def _record_policy_transition(
    session: AsyncSession,
    *,
    policy: PolicyVersion,
    previous_status: str,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    occurred_at: datetime,
    causation_id: UUID | None = None,
    previous_active_policy_id: UUID | None = None,
    replacement_policy_id: UUID | None = None,
) -> None:
    append_audit(
        session,
        aggregate_type="PolicyVersion",
        aggregate_id=str(policy.id),
        aggregate_version=policy.version,
        action=f"POLICY_VERSION_{policy.lifecycle_status}",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        previous_state={"lifecycle_status": previous_status},
        new_state={"lifecycle_status": policy.lifecycle_status},
        scope=policy.scope_definition,
    )

    if policy.policy_type != "PILOT_POLICY_PACK":
        return

    event_type = _POLICY_PACK_EVENT_TYPES[(previous_status, policy.lifecycle_status)]
    payload = {
        "policy_id": str(policy.id),
        "policy_code": policy.policy_code,
        "version_number": policy.version_number,
        "scope": policy.scope_definition,
        "effective_from": (
            policy.effective_from.isoformat() if policy.effective_from is not None else None
        ),
        "effective_to": (
            policy.effective_to.isoformat() if policy.effective_to is not None else None
        ),
        "payload_hash": policy.payload_hash,
        "approved_by": str(policy.approved_by) if policy.approved_by is not None else None,
        "actor": {"type": actor_type, "id": str(actor_id)},
    }
    if previous_active_policy_id is not None:
        payload["previous_active_policy_id"] = str(previous_active_policy_id)
    if replacement_policy_id is not None:
        payload["replacement_policy_id"] = str(replacement_policy_id)

    session.add(
        OutboxMessage(
            event_type=event_type,
            event_version=1,
            aggregate_type="PolicyVersion",
            aggregate_id=str(policy.id),
            aggregate_version=policy.version,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
            occurred_at=occurred_at,
        )
    )


async def review_policy(
    session: AsyncSession,
    *,
    policy_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    now: datetime | None = None,
) -> PolicyVersion:
    policy = await get_policy_for_update(session, policy_id)
    previous_status = policy.lifecycle_status
    assert_policy_transition_allowed(previous_status, "REVIEWED")
    reviewed_at = now or datetime.now(UTC)
    policy.lifecycle_status = "REVIEWED"
    policy.version += 1
    _record_policy_transition(
        session,
        policy=policy,
        previous_status=previous_status,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=reviewed_at,
    )
    await session.flush()
    return policy


async def approve_policy(
    session: AsyncSession,
    *,
    policy_id: UUID,
    approval_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    now: datetime | None = None,
) -> PolicyVersion:
    policy = await get_policy_for_update(session, policy_id)
    previous_status = policy.lifecycle_status
    assert_policy_transition_allowed(previous_status, "APPROVED")

    approved_at = now or datetime.now(UTC)
    approval = await _get_policy_transition_approval(
        session,
        approval_id=approval_id,
        policy=policy,
        target_status="APPROVED",
        now=approved_at,
    )
    assert approval.checker_identity_id is not None

    policy.lifecycle_status = "APPROVED"
    policy.payload_hash = canonical_request_hash(policy.payload)
    policy.approved_by = approval.checker_identity_id
    policy.approved_at = approved_at
    policy.version += 1
    _record_policy_transition(
        session,
        policy=policy,
        previous_status=previous_status,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=approved_at,
    )
    await session.flush()
    return policy


async def activate_policy(
    session: AsyncSession,
    *,
    policy_id: UUID,
    approval_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    now: datetime | None = None,
) -> PolicyVersion:
    policy = await get_policy_for_update(session, policy_id)
    previous_status = policy.lifecycle_status
    assert_policy_transition_allowed(previous_status, "ACTIVE")

    activated_at = now or datetime.now(UTC)
    await _get_policy_transition_approval(
        session,
        approval_id=approval_id,
        policy=policy,
        target_status="ACTIVE",
        now=activated_at,
    )

    if policy.payload_hash is None or policy.payload_hash != canonical_request_hash(
        policy.payload
    ):
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Approved policy payload changed before activation",
        )

    scope_identity = canonical_request_hash(
        {
            "policy_type": policy.policy_type,
            "policy_code": policy.policy_code,
            "scope_definition": policy.scope_definition,
        }
    )
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope_identity, 0))"),
        {"scope_identity": scope_identity},
    )

    active_versions = (
        await session.scalars(
            select(PolicyVersion)
            .where(
                PolicyVersion.id != policy.id,
                PolicyVersion.policy_type == policy.policy_type,
                PolicyVersion.policy_code == policy.policy_code,
                PolicyVersion.scope_definition == policy.scope_definition,
                PolicyVersion.lifecycle_status == "ACTIVE",
            )
            .with_for_update()
        )
    ).all()

    if len(active_versions) > 1:
        raise ApiError(
            409,
            "POLICY_ACTIVATION_CONFLICT",
            "Exclusive policy scope has multiple ACTIVE versions",
        )

    previous_active_policy_id = None
    if active_versions:
        previous = active_versions[0]
        previous_active_policy_id = previous.id
        previous_status_for_active = previous.lifecycle_status
        previous.lifecycle_status = "SUPERSEDED"
        previous.superseded_at = activated_at
        previous.version += 1
        _record_policy_transition(
            session,
            policy=previous,
            previous_status=previous_status_for_active,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            occurred_at=activated_at,
            replacement_policy_id=policy.id,
        )

    policy.lifecycle_status = "ACTIVE"
    policy.activated_at = activated_at
    policy.version += 1
    _record_policy_transition(
        session,
        policy=policy,
        previous_status=previous_status,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=activated_at,
        previous_active_policy_id=previous_active_policy_id,
    )
    await session.flush()
    return policy
