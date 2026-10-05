from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import IdempotencyRecord


def canonical_request_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def acquire_idempotency(
    session: AsyncSession,
    *,
    scope: str,
    key: str,
    payload: Any,
) -> tuple[IdempotencyRecord, dict[str, Any] | None]:
    request_hash = canonical_request_hash(payload)
    existing = await session.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
        .with_for_update()
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ApiError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "Idempotency key was already used with a different request",
            )
        if existing.outcome_status == "COMPLETED" and existing.response_payload is not None:
            return existing, existing.response_payload
        raise ApiError(409, "IDEMPOTENCY_IN_PROGRESS", "Command is already in progress")

    record = IdempotencyRecord(
        scope=scope,
        idempotency_key=key,
        request_hash=request_hash,
        outcome_status="PENDING",
    )
    session.add(record)
    await session.flush()
    return record, None


def complete_idempotency(
    record: IdempotencyRecord,
    *,
    status_code: int,
    response_payload: dict[str, Any],
) -> None:
    record.outcome_status = "COMPLETED"
    record.response_code = status_code
    record.response_payload = response_payload
