from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import ApprovalRequest


def approval_payload_hash(payload: Any) -> str:
    return canonical_request_hash(payload)


async def get_approval_for_update(
    session: AsyncSession,
    approval_id: UUID,
) -> ApprovalRequest:
    request = await session.scalar(
        select(ApprovalRequest)
        .where(ApprovalRequest.id == approval_id)
        .with_for_update()
    )
    if request is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Approval Request was not found")
    return request


def expire_if_needed(request: ApprovalRequest, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    if (
        request.status == "PENDING"
        and request.expires_at is not None
        and request.expires_at <= current
    ):
        request.status = "EXPIRED"
        request.version += 1
        return True
    return False


def assert_approval_execution_eligible(
    request: ApprovalRequest,
    *,
    payload: Any,
    current_target_version: int | None,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    if request.expires_at is not None and request.expires_at <= current:
        raise ApiError(409, "APPROVAL_EXPIRED", "Approval Request is expired")
    if request.status != "APPROVED":
        raise ApiError(
            409,
            "APPROVAL_NOT_APPROVED",
            "Approval Request is not approved for execution",
        )
    if approval_payload_hash(payload) != request.payload_hash:
        raise ApiError(
            409,
            "APPROVAL_PAYLOAD_CHANGED",
            "Approved payload does not match the execution payload",
        )
    if (
        request.target_aggregate_version is not None
        and current_target_version != request.target_aggregate_version
    ):
        raise ApiError(
            409,
            "APPROVAL_TARGET_VERSION_CONFLICT",
            "Target aggregate version changed after approval",
        )
