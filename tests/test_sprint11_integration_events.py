from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.integration_events import (
    IntegrationEventError,
    accept_authenticated_inbox_event,
    dead_letter_outbox_message,
    process_inbox_message_once,
    publish_outbox_batch,
    replay_dead_lettered_outbox_message,
)
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AuditEvent,
    IdempotencyRecord,
    InboxMessage,
    OutboxMessage,
)


class RecordingPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def publish(self, subject: str, payload: bytes) -> tuple[str, int]:
        envelope = json.loads(payload)
        self.calls.append((subject, envelope))
        if self.fail:
            raise RuntimeError("broker unavailable")
        return ("BADBAN_EVENTS", len(self.calls))


class BlockingPublisher(RecordingPublisher):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def publish(self, subject: str, payload: bytes) -> tuple[str, int]:
        envelope = json.loads(payload)
        self.calls.append((subject, envelope))
        self.started.set()
        await self.release.wait()
        return ("BADBAN_EVENTS", len(self.calls))


async def _insert_outbox(
    database,
    *,
    event_type: str = "TestEvent",
    payload: dict[str, object] | None = None,
) -> UUID:
    event_id = uuid4()
    async with database.session_factory() as session:
        async with session.begin():
            session.add(
                OutboxMessage(
                    id=event_id,
                    event_type=event_type,
                    event_version=1,
                    aggregate_type="TestAggregate",
                    aggregate_id=str(uuid4()),
                    aggregate_version=1,
                    payload=payload or {"amount": "10.00"},
                    correlation_id=uuid4(),
                    causation_id=None,
                    occurred_at=datetime.now(UTC),
                )
            )
    return event_id


@pytest.mark.integration
async def test_outbox_state_and_event_rollback_are_atomic(
    database,
    clean_sprint11_event_tables,
) -> None:
    event_id = uuid4()
    try:
        async with database.session_factory() as session:
            async with session.begin():
                session.add(
                    IdempotencyRecord(
                        scope="sprint11-rollback",
                        idempotency_key="state-change",
                        request_hash="a" * 64,
                        outcome_status="COMPLETED",
                    )
                )
                session.add(
                    OutboxMessage(
                        id=event_id,
                        event_type="AtomicEvent",
                        event_version=1,
                        aggregate_type="AtomicAggregate",
                        aggregate_id="aggregate-1",
                        aggregate_version=1,
                        payload={"state": "changed"},
                        correlation_id=uuid4(),
                        causation_id=None,
                        occurred_at=datetime.now(UTC),
                    )
                )
                raise RuntimeError("force rollback")
    except RuntimeError:
        pass

    async with database.session_factory() as session:
        state_count = await session.scalar(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(IdempotencyRecord.scope == "sprint11-rollback")
        )
        event = await session.get(OutboxMessage, event_id)

    assert state_count == 0
    assert event is None


@pytest.mark.integration
async def test_outbox_publish_success_serializes_versioned_envelope(
    database,
    clean_sprint11_event_tables,
) -> None:
    event_id = await _insert_outbox(database, event_type="JournalPosted")
    publisher = RecordingPublisher()

    result = await publish_outbox_batch(database, publisher)

    assert result.claimed == 1
    assert result.published == 1
    assert result.failed == 0
    assert len(publisher.calls) == 1
    subject, envelope = publisher.calls[0]
    assert subject == "badban.events.JournalPosted"
    assert envelope["event_id"] == str(event_id)
    assert envelope["event_type"] == "JournalPosted"
    assert envelope["event_version"] == 1
    assert envelope["aggregate_type"] == "TestAggregate"
    assert envelope["aggregate_version"] == 1
    assert envelope["payload"] == {"amount": "10.00"}

    async with database.session_factory() as session:
        stored = await session.get(OutboxMessage, event_id)

    assert stored is not None
    assert stored.published_at is not None
    assert stored.publish_attempts == 1
    assert stored.last_error is None
    assert stored.next_attempt_at is None


@pytest.mark.integration
async def test_outbox_failure_is_retryable_without_losing_event(
    database,
    clean_sprint11_event_tables,
) -> None:
    event_id = await _insert_outbox(database)
    failed_publisher = RecordingPublisher(fail=True)
    attempt_time = datetime.now(UTC)

    failed = await publish_outbox_batch(
        database,
        failed_publisher,
        now=attempt_time,
    )
    assert failed.claimed == 1
    assert failed.published == 0
    assert failed.failed == 1

    async with database.session_factory() as session:
        stored = await session.get(OutboxMessage, event_id)
        assert stored is not None
        retry_at = stored.next_attempt_at
        assert stored.published_at is None
        assert stored.publish_attempts == 1
        assert stored.last_error is not None
        assert "broker unavailable" in stored.last_error
        assert retry_at is not None
        assert retry_at > attempt_time

    too_early = await publish_outbox_batch(
        database,
        RecordingPublisher(),
        now=attempt_time,
    )
    assert too_early.claimed == 0

    success_publisher = RecordingPublisher()
    retried = await publish_outbox_batch(
        database,
        success_publisher,
        now=retry_at,
    )
    assert retried.published == 1

    async with database.session_factory() as session:
        stored = await session.get(OutboxMessage, event_id)

    assert stored is not None
    assert stored.published_at is not None
    assert stored.publish_attempts == 2
    assert stored.last_error is None


@pytest.mark.integration
async def test_two_publishers_do_not_claim_same_outbox_row_concurrently(
    database,
    clean_sprint11_event_tables,
) -> None:
    await _insert_outbox(database)
    publisher = BlockingPublisher()

    first_task = asyncio.create_task(
        publish_outbox_batch(database, publisher, batch_size=1)
    )
    await publisher.started.wait()

    second = await publish_outbox_batch(
        database,
        publisher,
        batch_size=1,
    )
    assert second.claimed == 0

    publisher.release.set()
    first = await first_task
    assert first.claimed == 1
    assert first.published == 1
    assert len(publisher.calls) == 1


@pytest.mark.integration
async def test_outbox_and_inbox_event_facts_are_database_immutable(
    database,
    clean_sprint11_event_tables,
) -> None:
    event_id = await _insert_outbox(database)
    inbox = await accept_authenticated_inbox_event(
        database,
        source_id="provider-1",
        event_type="LOAN_DISBURSED",
        external_event_id="external-1",
        payload={"principal": "100.00"},
    )

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(OutboxMessage)
                    .where(OutboxMessage.id == event_id)
                    .values(payload={"mutated": True})
                )

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(InboxMessage)
                    .where(InboxMessage.id == inbox.message_id)
                    .values(payload_hash="0" * 64)
                )

    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                update(OutboxMessage)
                .where(OutboxMessage.id == event_id)
                .values(last_error="delivery metadata may change")
            )


@pytest.mark.integration
async def test_explicit_dead_letter_and_replay_preserve_business_event_identity_and_audit(
    database,
    clean_sprint11_event_tables,
) -> None:
    event_id = await _insert_outbox(database, event_type="GuaranteeReserved")
    actor_id = uuid4()
    correlation_id = uuid4()

    dead_lettered = await dead_letter_outbox_message(
        database,
        message_id=event_id,
        actor_id=actor_id,
        actor_type="STAFF",
        correlation_id=correlation_id,
        reason="operator classified delivery exception",
    )
    assert dead_lettered.id == event_id
    assert dead_lettered.dead_lettered_at is not None

    blocked = await publish_outbox_batch(database, RecordingPublisher())
    assert blocked.claimed == 0

    replayed = await replay_dead_lettered_outbox_message(
        database,
        message_id=event_id,
        actor_id=actor_id,
        actor_type="STAFF",
        correlation_id=correlation_id,
        reason="dependency restored",
    )
    assert replayed.id == event_id
    assert replayed.dead_lettered_at is None
    assert replayed.replay_count == 1

    publisher = RecordingPublisher()
    published = await publish_outbox_batch(
        database,
        publisher,
        now=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert published.published == 1
    assert publisher.calls[0][1]["event_id"] == str(event_id)

    async with database.session_factory() as session:
        audits = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.aggregate_id == str(event_id))
                .order_by(AuditEvent.occurred_at)
            )
        ).all()

    assert [audit.action for audit in audits] == [
        "OUTBOX_DEAD_LETTERED",
        "OUTBOX_REPLAY_REQUESTED",
    ]


@pytest.mark.integration
async def test_inbox_duplicate_same_payload_returns_existing_and_changed_payload_fails_closed(
    database,
    clean_sprint11_event_tables,
) -> None:
    first = await accept_authenticated_inbox_event(
        database,
        source_id="lender-1",
        event_type="REPAYMENT_RECEIVED",
        external_event_id="repayment-1",
        payload={"amount": "25.00"},
    )
    duplicate = await accept_authenticated_inbox_event(
        database,
        source_id="lender-1",
        event_type="REPAYMENT_RECEIVED",
        external_event_id="repayment-1",
        payload={"amount": "25.00"},
    )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.message_id == first.message_id

    with pytest.raises(IntegrationEventError) as conflict:
        await accept_authenticated_inbox_event(
            database,
            source_id="lender-1",
            event_type="REPAYMENT_RECEIVED",
            external_event_id="repayment-1",
            payload={"amount": "26.00"},
        )
    assert conflict.value.code == "EVENT_DUPLICATE_PAYLOAD_MISMATCH"


@pytest.mark.integration
async def test_inbox_concurrent_duplicate_is_race_safe(
    database,
    clean_sprint11_event_tables,
) -> None:
    results = await asyncio.gather(
        accept_authenticated_inbox_event(
            database,
            source_id="lender-2",
            event_type="LOAN_SETTLED",
            external_event_id="loan-9",
            payload={"outstanding": "0.00"},
        ),
        accept_authenticated_inbox_event(
            database,
            source_id="lender-2",
            event_type="LOAN_SETTLED",
            external_event_id="loan-9",
            payload={"outstanding": "0.00"},
        ),
    )

    assert results[0].message_id == results[1].message_id
    assert sorted(result.created for result in results) == [False, True]

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(InboxMessage))
    assert count == 1


@pytest.mark.integration
async def test_inbox_handler_executes_exactly_once_for_duplicate_processing(
    database,
    clean_sprint11_event_tables,
) -> None:
    accepted = await accept_authenticated_inbox_event(
        database,
        source_id="issuer-1",
        event_type="GUARANTEE_ISSUED",
        external_event_id="guarantee-1",
        payload={"guarantee_id": "G-1"},
    )
    calls = 0

    async def handler(session, message: InboxMessage) -> None:
        nonlocal calls
        calls += 1
        session.add(
            IdempotencyRecord(
                scope="sprint11-handler",
                idempotency_key=str(message.id),
                request_hash="b" * 64,
                outcome_status="COMPLETED",
            )
        )

    first = await process_inbox_message_once(
        database,
        message_id=accepted.message_id,
        handler=handler,
    )
    second = await process_inbox_message_once(
        database,
        message_id=accepted.message_id,
        handler=handler,
    )

    assert first.processed is True
    assert second.already_processed is True
    assert calls == 1

    async with database.session_factory() as session:
        effect_count = await session.scalar(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(IdempotencyRecord.scope == "sprint11-handler")
        )
    assert effect_count == 1


@pytest.mark.integration
async def test_inbox_handler_failure_rolls_back_effect_and_can_retry_safely(
    database,
    clean_sprint11_event_tables,
) -> None:
    accepted = await accept_authenticated_inbox_event(
        database,
        source_id="custodian-1",
        event_type="COLLATERAL_REGISTERED",
        external_event_id="collateral-1",
        payload={"asset": "asset-1"},
    )

    async def failing_handler(session, message: InboxMessage) -> None:
        session.add(
            IdempotencyRecord(
                scope="sprint11-crash",
                idempotency_key=str(message.id),
                request_hash="c" * 64,
                outcome_status="COMPLETED",
            )
        )
        await session.flush()
        raise RuntimeError("crash before transaction commit")

    with pytest.raises(RuntimeError):
        await process_inbox_message_once(
            database,
            message_id=accepted.message_id,
            handler=failing_handler,
        )

    async with database.session_factory() as session:
        message = await session.get(InboxMessage, accepted.message_id)
        effect_count = await session.scalar(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(IdempotencyRecord.scope == "sprint11-crash")
        )

    assert message is not None
    assert message.processed_at is None
    assert effect_count == 0

    async def success_handler(session, message: InboxMessage) -> None:
        session.add(
            IdempotencyRecord(
                scope="sprint11-crash",
                idempotency_key=str(message.id),
                request_hash="c" * 64,
                outcome_status="COMPLETED",
            )
        )

    retried = await process_inbox_message_once(
        database,
        message_id=accepted.message_id,
        handler=success_handler,
    )
    assert retried.processed is True

    async with database.session_factory() as session:
        message = await session.get(InboxMessage, accepted.message_id)
        effect_count = await session.scalar(
            select(func.count())
            .select_from(IdempotencyRecord)
            .where(IdempotencyRecord.scope == "sprint11-crash")
        )

    assert message is not None
    assert message.processed_at is not None
    assert effect_count == 1


def test_no_generic_public_event_injection_api(settings: Settings) -> None:
    schema = create_app(settings).openapi()
    for path, operations in schema["paths"].items():
        assert not (path.startswith("/api/v1/events") and "post" in operations)
