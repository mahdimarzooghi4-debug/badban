from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import PolicyVersion

POLICY_LIFECYCLE_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "DRAFT": frozenset({"REVIEWED"}),
    "REVIEWED": frozenset({"APPROVED"}),
    "APPROVED": frozenset({"ACTIVE"}),
    "ACTIVE": frozenset({"SUPERSEDED", "RETIRED"}),
    "SUPERSEDED": frozenset(),
    "RETIRED": frozenset(),
}

IMMUTABLE_POLICY_STATES = frozenset({"ACTIVE", "SUPERSEDED", "RETIRED"})


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


async def review_policy(
    session: AsyncSession,
    *,
    policy_id: UUID,
) -> PolicyVersion:
    policy = await get_policy_for_update(session, policy_id)
    assert_policy_transition_allowed(policy.lifecycle_status, "REVIEWED")
    policy.lifecycle_status = "REVIEWED"
    policy.version += 1
    await session.flush()
    return policy


async def approve_policy(
    session: AsyncSession,
    *,
    policy_id: UUID,
    approved_by: UUID,
    now: datetime | None = None,
) -> PolicyVersion:
    policy = await get_policy_for_update(session, policy_id)
    assert_policy_transition_allowed(policy.lifecycle_status, "APPROVED")

    policy.lifecycle_status = "APPROVED"
    policy.payload_hash = canonical_request_hash(policy.payload)
    policy.approved_by = approved_by
    policy.approved_at = now or datetime.now(UTC)
    policy.version += 1
    await session.flush()
    return policy
