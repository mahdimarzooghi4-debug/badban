from __future__ import annotations

from uuid import uuid4

import pytest

from badban.api.errors import ApiError
from badban.application.policy_lifecycle import (
    assert_policy_payload_mutable,
    assert_policy_transition_allowed,
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
