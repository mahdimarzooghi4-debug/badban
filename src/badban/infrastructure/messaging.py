from __future__ import annotations

from collections.abc import Sequence

import nats
from nats.aio.client import Client as NATS
from nats.js.api import StreamConfig


class NatsJetStreamTransport:
    def __init__(self, url: str) -> None:
        self._url = url
        self._client: NATS | None = None

    async def connect(self) -> None:
        if self._client is not None and self._client.is_connected:
            return
        self._client = await nats.connect(self._url, connect_timeout=2)

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.drain()

    async def ping(self) -> bool:
        try:
            await self.connect()
            assert self._client is not None
            await self._client.flush(timeout=2)
            return True
        except Exception:
            return False

    async def ensure_stream(self, name: str, subjects: Sequence[str]) -> None:
        await self.connect()
        assert self._client is not None
        jetstream = self._client.jetstream()
        try:
            await jetstream.stream_info(name)
        except Exception:
            await jetstream.add_stream(config=StreamConfig(name=name, subjects=list(subjects)))

    async def publish(
        self, subject: str, payload: bytes, *, message_id: str | None = None
    ) -> tuple[str, int]:
        """Include a stable event identity for JetStream's bounded deduplication.

        Nats-Msg-Id is advisory deduplication *within the stream's configured
        window*. After that window, delivery remains at-least-once and
        consumers still must deduplicate by immutable event_id.
        """
        if message_id is not None and not message_id.strip():
            raise ValueError("message_id must be nonblank when supplied")
        await self.connect()
        assert self._client is not None
        headers = {"Nats-Msg-Id": message_id} if message_id is not None else None
        ack = await self._client.jetstream().publish(subject, payload, headers=headers)
        return ack.stream, ack.seq

    async def consume_one(self, subject: str, timeout: float = 2.0) -> bytes:
        """Consume and acknowledge one persisted JetStream message."""
        await self.connect()
        assert self._client is not None
        subscription = await self._client.jetstream().subscribe(subject, manual_ack=True)
        try:
            message = await subscription.next_msg(timeout=timeout)
            await message.ack()
            return message.data
        finally:
            await subscription.unsubscribe()

    async def delete_stream(self, name: str) -> None:
        await self.connect()
        assert self._client is not None
        await self._client.jetstream().delete_stream(name)
