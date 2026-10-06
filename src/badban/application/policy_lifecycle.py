from __future__ import annotations

from collections.abc import Mapping

from badban.api.errors import ApiError
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
