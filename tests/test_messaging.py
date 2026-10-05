from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nats.errors import NoServersError
from sqlalchemy import select

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

    unavailable = NatsJetStreamTransport("nats://127.0.0.1:1")
    try:
        with pytest.raises(NoServersError):
            await unavailable.publish("badban.test.unavailable", b"payload")
    finally:
        await unavailable.close()

    async with database.session_factory() as session:
        pending = await session.scalar(select(OutboxMessage).where(OutboxMessage.id == event_id))

    assert pending is not None
    assert pending.published_at is None
