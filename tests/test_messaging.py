from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from badban.application.integration_events import publish_outbox_batch
from badban.infrastructure.messaging import NatsJetStreamTransport
from badban.infrastructure.persistence.models import OutboxMessage


@pytest.mark.integration
async def test_jetstream_publish_consume_smoke(settings) -> None:
    transport = NatsJetStreamTransport(settings.nats_url)
    stream_name = f"BADBAN_TEST_{uuid4().hex[:12].upper()}"
    subject = f"badban.test.{uuid4().hex}"
    payload = b'{"ok":true}'
    try:
        await transport.ensure_stream(stream_name, [subject])
        stream, sequence = await transport.publish(subject, payload)
        received = await transport.consume_one(subject)

        assert stream == stream_name
        assert sequence == 1
        assert received == payload
    finally:
        try:
            await transport.delete_stream(stream_name)
        finally:
            await transport.close()


@pytest.mark.integration
async def test_broker_failure_does_not_erase_pending_outbox(
    database, clean_foundation_tables
) -> None:
    event_id = uuid4()
    async with database.session_factory() as session:
        async with session.begin():
            session.add(
                OutboxMessage(
                    id=event_id,
                    event_type="FoundationProbeCreated",
                    event_version=1,
                    aggregate_type="FoundationProbe",
                    aggregate_id="probe-broker-down",
                    aggregate_version=1,
                    payload={"probe": True},
                    occurred_at=datetime.now(UTC),
                )
            )

    class UnavailableTransport(NatsJetStreamTransport):
        async def connect(self) -> None:
            raise RuntimeError("broker unavailable")

    unavailable = UnavailableTransport("nats://unavailable")
    with pytest.raises(RuntimeError, match="broker unavailable"):
        await unavailable.publish("badban.test.unavailable", b"payload")

    async with database.session_factory() as session:
        pending = await session.scalar(select(OutboxMessage).where(OutboxMessage.id == event_id))

    assert pending is not None
    assert pending.published_at is None


@pytest.mark.integration
async def test_jetstream_stable_event_identity_survives_ack_then_database_rollback(
    settings, database, clean_sprint11_event_tables
) -> None:
    """A broker ack followed by worker cancellation must not lose the Outbox.

    Retrying the same persisted event publishes with the same Nats-Msg-Id.
    JetStream can suppress the duplicate within its configured window, but
    consumer idempotency remains mandatory outside that bounded window.
    """
    event_id = uuid4()
    prefix = f"badban.s34.{uuid4().hex}"
    subject = f"{prefix}.AckRecoveryProbe"
    stream_name = f"BADBAN_S34_{uuid4().hex[:12].upper()}"
    payload = {"event": "original"}
    transport = NatsJetStreamTransport(settings.nats_url)

    class AckThenCancel:
        def __init__(self) -> None:
            self.receipt: tuple[str, int] | None = None

        async def publish(
            self, subject: str, payload: bytes, *, message_id: str | None = None
        ) -> tuple[str, int]:
            assert message_id == str(event_id)
            self.receipt = await transport.publish(subject, payload, message_id=message_id)
            raise asyncio.CancelledError("worker interrupted after broker acknowledgement")

    class ObservingRetry:
        def __init__(self) -> None:
            self.receipt: tuple[str, int] | None = None

        async def publish(
            self, subject: str, payload: bytes, *, message_id: str | None = None
        ) -> tuple[str, int]:
            assert message_id == str(event_id)
            self.receipt = await transport.publish(subject, payload, message_id=message_id)
            return self.receipt

    try:
        await transport.ensure_stream(stream_name, [subject])
        async with database.session_factory() as session:
            async with session.begin():
                session.add(
                    OutboxMessage(
                        id=event_id,
                        event_type="AckRecoveryProbe",
                        event_version=1,
                        aggregate_type="TestAggregate",
                        aggregate_id="stable-identity-1",
                        aggregate_version=1,
                        payload=payload,
                        occurred_at=datetime.now(UTC),
                    )
                )
        interrupted = AckThenCancel()
        with pytest.raises(asyncio.CancelledError):
            await publish_outbox_batch(database, interrupted, subject_prefix=prefix, batch_size=1)
        assert interrupted.receipt == (stream_name, 1)
        async with database.session_factory() as session:
            unacknowledged = await session.get(OutboxMessage, event_id)
            assert unacknowledged is not None
            assert unacknowledged.published_at is None
            assert unacknowledged.publish_attempts == 0

        retry = ObservingRetry()
        result = await publish_outbox_batch(database, retry, subject_prefix=prefix, batch_size=1)
        assert (result.claimed, result.published, result.failed) == (1, 1, 0)
        assert retry.receipt == (stream_name, 1)
        assert transport._client is not None
        info = await transport._client.jetstream().stream_info(stream_name)
        assert info.state.messages == 1

        received = json.loads(await transport.consume_one(subject))
        assert received["event_id"] == str(event_id)
        assert received["payload"] == payload
        async with database.session_factory() as session:
            stored = await session.get(OutboxMessage, event_id)
            assert stored is not None
            assert stored.published_at is not None
            assert stored.publish_attempts == 1
    finally:
        try:
            await transport.delete_stream(stream_name)
        finally:
            await transport.close()


@pytest.mark.integration
async def test_jetstream_same_identity_suppresses_duplicate_within_configured_window(
    settings,
) -> None:
    transport = NatsJetStreamTransport(settings.nats_url)
    stream_name = f"BADBAN_S34_{uuid4().hex[:12].upper()}"
    subject = f"badban.s34.{uuid4().hex}"
    event_id = str(uuid4())
    try:
        await transport.ensure_stream(stream_name, [subject])
        first = await transport.publish(subject, b"first", message_id=event_id)
        second = await transport.publish(subject, b"first", message_id=event_id)
        third = await transport.publish(subject, b"second", message_id=str(uuid4()))
        assert first == (stream_name, 1)
        assert second == first
        assert third == (stream_name, 2)
        assert transport._client is not None
        info = await transport._client.jetstream().stream_info(stream_name)
        assert info.state.messages == 2
        with pytest.raises(ValueError, match="message_id must be nonblank"):
            await transport.publish(subject, b"invalid", message_id=" ")
    finally:
        try:
            await transport.delete_stream(stream_name)
        finally:
            await transport.close()
