from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import AuditEvent


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
    evidence_reference: str | None = None,
    scope: dict[str, Any] | None = None,
) -> AuditEvent:
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
        evidence_reference=evidence_reference,
        correlation_id=correlation_id,
        outcome=outcome,
        scope=scope,
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    return event
