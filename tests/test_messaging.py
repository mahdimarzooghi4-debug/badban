from __future__ import annotations

from uuid import uuid4

import pytest

from badban.infrastructure.messaging import NatsJetStreamTransport


@pytest.mark.integration
async def test_jetstream_publish_smoke(settings) -> None:
    transport = NatsJetStreamTransport(settings.nats_url)
    stream_name = f"BADBAN_TEST_{uuid4().hex[:12].upper()}"
    subject = f"badban.test.{uuid4().hex}"
    try:
        await transport.ensure_stream(stream_name, [subject])
        stream, sequence = await transport.publish(subject, b'{"ok":true}')
        assert stream == stream_name
        assert sequence == 1
    finally:
        try:
            await transport.delete_stream(stream_name)
        finally:
            await transport.close()
