from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import AuditEvent

_FORBIDDEN_AUDIT_KEYS = frozenset(
    {
        "credentials",
        "password",
        "passphrase",
        "access_token",
        "refresh_token",
        "id_token",
        "session_token",
        "client_secret",
        "provider_secret",
        "webhook_secret",
        "private_key",
        "signing_key",
        "secret",
        "authorization_header",
        "cookie",
        "set_cookie",
        "raw_payload",
        "raw_provider_payload",
        "document_content",
        "evidence_content",
        "file_content",
        "blob_content",
    }
)
_REASON_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{0,119}$")

_FORBIDDEN_AUDIT_KEY_SUFFIXES = (
    "_password",
    "_passphrase",
    "_secret",
    "_token",
    "_private_key",
    "_authorization_header",
    "_raw_payload",
    "_document_content",
    "_evidence_content",
    "_file_content",
    "_blob_content",
)


class AuditPayloadRejected(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(f"Unsafe generic audit field is not permitted: {key}")
        self.code = "AUDIT_PAYLOAD_UNSAFE"
        self.key = key


def _normalized_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_")


def assert_safe_audit_payload(value: object, *, path: str = "audit") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = _normalized_key(key)
            if normalized in _FORBIDDEN_AUDIT_KEYS or normalized.endswith(
                _FORBIDDEN_AUDIT_KEY_SUFFIXES
            ):
                raise AuditPayloadRejected(f"{path}.{key}")
            assert_safe_audit_payload(nested, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            assert_safe_audit_payload(nested, path=f"{path}[{index}]")


def append_audit(
    session: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int | None,
    action: str,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    outcome: str,
    reason_code: str | None = None,
    previous_state: dict[str, Any] | None = None,
    new_state: dict[str, Any] | None = None,
    policy_pack_id: UUID | None = None,
    evidence_reference: str | None = None,
    causation_id: UUID | None = None,
    scope: dict[str, Any] | None = None,
) -> AuditEvent:
    if reason_code is not None and _REASON_CODE_PATTERN.fullmatch(reason_code) is None:
        raise AuditPayloadRejected("reason_code")

    for label, payload in (
        ("previous_state", previous_state),
        ("new_state", new_state),
        ("scope", scope),
    ):
        if payload is not None:
            assert_safe_audit_payload(payload, path=label)

    event = AuditEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        action=action,
        previous_state=previous_state,
        new_state=new_state,
        actor_type=actor_type,
        actor_id=actor_id,
        reason_code=reason_code,
        policy_pack_id=policy_pack_id,
        evidence_reference=evidence_reference,
        correlation_id=correlation_id,
        causation_id=causation_id,
        outcome=outcome,
        scope=scope,
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    return event
