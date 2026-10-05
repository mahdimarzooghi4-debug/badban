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

    async def publish(self, subject: str, payload: bytes) -> tuple[str, int]:
        await self.connect()
        assert self._client is not None
        ack = await self._client.jetstream().publish(subject, payload)
        return ack.stream, ack.seq

    async def delete_stream(self, name: str) -> None:
        await self.connect()
        assert self._client is not None
        await self._client.jetstream().delete_stream(name)
