from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.database import Database
from badban.infrastructure.persistence.models import InboxMessage, OutboxMessage
from badban.security.audit import append_audit

_EVENT_SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class IntegrationEventError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EventPublisher(Protocol):
    async def publish(self, subject: str, payload: bytes) -> tuple[str, int]: ...


InboxHandler = Callable[[AsyncSession, InboxMessage], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PublishBatchResult:
    claimed: int
    published: int
    failed: int


@dataclass(frozen=True, slots=True)
class InboxAcceptance:
    message_id: UUID
    created: bool


@dataclass(frozen=True, slots=True)
class InboxProcessResult:
    message_id: UUID
    processed: bool
    already_processed: bool


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def event_subject(event_type: str, *, prefix: str = "badban.events") -> str:
    if not event_type or _EVENT_SUBJECT_PATTERN.fullmatch(event_type) is None:
        raise IntegrationEventError(
            "EVENT_SUBJECT_INVALID",
            "Event type cannot be mapped to a broker subject safely",
        )
    return f"{prefix}.{event_type}"


def serialize_outbox_event(event: OutboxMessage) -> bytes:
    envelope = {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "event_version": event.event_version,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "aggregate_version": event.aggregate_version,
        "correlation_id": str(event.correlation_id) if event.correlation_id else None,
        "causation_id": str(event.causation_id) if event.causation_id else None,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }
    return _canonical_json_bytes(envelope)


async def publish_outbox_batch(
    database: Database,
    publisher: EventPublisher,
    *,
    batch_size: int = 50,
    subject_prefix: str = "badban.events",
    now: datetime | None = None,
) -> PublishBatchResult:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    effective_now = now or datetime.now(UTC)
    published = 0
    failed = 0

    async with database.session_factory() as session:
        async with session.begin():
            rows = (
                await session.scalars(
                    select(OutboxMessage)
                    .where(
                        OutboxMessage.published_at.is_(None),
                        OutboxMessage.dead_lettered_at.is_(None),
                        or_(
                            OutboxMessage.next_attempt_at.is_(None),
                            OutboxMessage.next_attempt_at <= effective_now,
                        ),
                    )
                    .order_by(OutboxMessage.created_at, OutboxMessage.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()

            for event in rows:
                event.publish_attempts += 1
                try:
                    await publisher.publish(
                        event_subject(event.event_type, prefix=subject_prefix),
                        serialize_outbox_event(event),
                    )
                except Exception as exc:
                    event.last_error = f"{type(exc).__name__}: {exc}"[:1000]
                    event.next_attempt_at = effective_now + timedelta(
                        seconds=max(1, event.publish_attempts)
                    )
                    failed += 1
                else:
                    event.published_at = datetime.now(UTC)
                    event.last_error = None
                    event.next_attempt_at = None
                    published += 1

    return PublishBatchResult(
        claimed=published + failed,
        published=published,
        failed=failed,
    )


async def accept_authenticated_inbox_event(
    database: Database,
    *,
    source_id: str,
    event_type: str,
    external_event_id: str,
    payload: dict[str, Any],
) -> InboxAcceptance:
    if not source_id.strip() or not event_type.strip() or not external_event_id.strip():
        raise IntegrationEventError(
            "EVENT_SCHEMA_INVALID",
            "Inbox identity fields must not be empty",
        )

    digest = payload_sha256(payload)
    message_id = uuid4()

    async with database.session_factory() as session:
        async with session.begin():
            inserted_id = await session.scalar(
                insert(InboxMessage)
                .values(
                    id=message_id,
                    source_id=source_id,
                    event_type=event_type,
                    external_event_id=external_event_id,
                    payload_hash=digest,
                    payload=payload,
                )
                .on_conflict_do_nothing(
                    index_elements=["source_id", "event_type", "external_event_id"]
                )
                .returning(InboxMessage.id)
            )

            if inserted_id is not None:
                return InboxAcceptance(message_id=inserted_id, created=True)

            existing = await session.scalar(
                select(InboxMessage)
                .where(
                    InboxMessage.source_id == source_id,
                    InboxMessage.event_type == event_type,
                    InboxMessage.external_event_id == external_event_id,
                )
                .with_for_update()
            )
            if existing is None:
                raise IntegrationEventError(
                    "EVENT_PROCESSING_RETRYABLE",
                    "Concurrent inbox event could not be resolved",
                )
            if existing.payload_hash != digest:
                raise IntegrationEventError(
                    "EVENT_DUPLICATE_PAYLOAD_MISMATCH",
                    "Duplicate external event identity has different payload",
                )
            return InboxAcceptance(message_id=existing.id, created=False)


async def process_inbox_message_once(
    database: Database,
    *,
    message_id: UUID,
    handler: InboxHandler,
    now: datetime | None = None,
) -> InboxProcessResult:
    effective_now = now or datetime.now(UTC)

    async with database.session_factory() as session:
        async with session.begin():
            message = await session.scalar(
                select(InboxMessage)
                .where(InboxMessage.id == message_id)
                .with_for_update()
            )
            if message is None:
                raise IntegrationEventError(
                    "INBOX_MESSAGE_NOT_FOUND",
                    "Inbox message does not exist",
                )
            if message.processed_at is not None:
                return InboxProcessResult(
                    message_id=message.id,
                    processed=False,
                    already_processed=True,
                )

            await handler(session, message)
            message.processed_at = effective_now

            return InboxProcessResult(
                message_id=message.id,
                processed=True,
                already_processed=False,
            )


async def dead_letter_outbox_message(
    database: Database,
    *,
    message_id: UUID,
    actor_id: UUID,
    actor_type: str,
    correlation_id: UUID,
    reason: str,
    now: datetime | None = None,
) -> OutboxMessage:
    clean_reason = reason.strip()
    if not clean_reason:
        raise IntegrationEventError(
            "OUTBOX_DEAD_LETTER_REASON_REQUIRED",
            "Dead-letter reason is required",
        )
    effective_now = now or datetime.now(UTC)

    async with database.session_factory() as session:
        async with session.begin():
            event = await session.scalar(
                select(OutboxMessage)
                .where(OutboxMessage.id == message_id)
                .with_for_update()
            )
            if event is None:
                raise IntegrationEventError(
                    "OUTBOX_MESSAGE_NOT_FOUND",
                    "Outbox message does not exist",
                )
            if event.published_at is not None:
                raise IntegrationEventError(
                    "OUTBOX_ALREADY_PUBLISHED",
                    "Published outbox message cannot be dead-lettered",
                )
            if event.dead_lettered_at is not None:
                if event.dead_letter_reason == clean_reason:
                    return event
                raise IntegrationEventError(
                    "OUTBOX_ALREADY_DEAD_LETTERED",
                    "Outbox message is already dead-lettered",
                )

            previous_state = {
                "dead_lettered": False,
                "publish_attempts": event.publish_attempts,
            }
            event.dead_lettered_at = effective_now
            event.dead_letter_reason = clean_reason
            event.next_attempt_at = None

            append_audit(
                session,
                aggregate_type="OutboxMessage",
                aggregate_id=str(event.id),
                aggregate_version=None,
                action="OUTBOX_DEAD_LETTERED",
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                outcome="SUCCESS",
                reason_code="EXPLICIT_DEAD_LETTER",
                previous_state=previous_state,
                new_state={
                    "dead_lettered": True,
                    "publish_attempts": event.publish_attempts,
                    "reason": clean_reason,
                },
            )

            await session.flush()
            return event


async def replay_dead_lettered_outbox_message(
    database: Database,
    *,
    message_id: UUID,
    actor_id: UUID,
    actor_type: str,
    correlation_id: UUID,
    reason: str,
    now: datetime | None = None,
) -> OutboxMessage:
    clean_reason = reason.strip()
    if not clean_reason:
        raise IntegrationEventError(
            "OUTBOX_REPLAY_REASON_REQUIRED",
            "Replay reason is required",
        )
    effective_now = now or datetime.now(UTC)

    async with database.session_factory() as session:
        async with session.begin():
            event = await session.scalar(
                select(OutboxMessage)
                .where(OutboxMessage.id == message_id)
                .with_for_update()
            )
            if event is None:
                raise IntegrationEventError(
                    "OUTBOX_MESSAGE_NOT_FOUND",
                    "Outbox message does not exist",
                )
            if event.published_at is not None:
                raise IntegrationEventError(
                    "OUTBOX_ALREADY_PUBLISHED",
                    "Published outbox message cannot be replayed",
                )
            if event.dead_lettered_at is None:
                raise IntegrationEventError(
                    "OUTBOX_NOT_DEAD_LETTERED",
                    "Only a dead-lettered outbox message may be replayed",
                )

            previous_state = {
                "dead_lettered": True,
                "dead_letter_reason": event.dead_letter_reason,
                "replay_count": event.replay_count,
            }
            event.dead_lettered_at = None
            event.dead_letter_reason = None
            event.last_error = None
            event.next_attempt_at = effective_now
            event.replay_count += 1

            append_audit(
                session,
                aggregate_type="OutboxMessage",
                aggregate_id=str(event.id),
                aggregate_version=None,
                action="OUTBOX_REPLAY_REQUESTED",
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                outcome="SUCCESS",
                reason_code="EXPLICIT_REPLAY",
                previous_state=previous_state,
                new_state={
                    "dead_lettered": False,
                    "replay_count": event.replay_count,
                    "reason": clean_reason,
                },
            )

            await session.flush()
            return event
