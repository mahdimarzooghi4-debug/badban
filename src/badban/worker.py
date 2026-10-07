from __future__ import annotations

import argparse
import asyncio
import signal
from collections.abc import Sequence

import structlog

from badban.application.integration_events import publish_outbox_batch
from badban.config import Settings, get_settings
from badban.infrastructure.messaging import NatsJetStreamTransport
from badban.infrastructure.persistence.database import Database
from badban.observability import configure_logging

logger = structlog.get_logger(__name__)

EVENT_STREAM_NAME = "BADBAN_EVENTS"
EVENT_SUBJECT_PREFIX = "badban.events"
OUTBOX_BATCH_SIZE = 50
OUTBOX_IDLE_POLL_SECONDS = 1.0


async def _wait_or_stop(stop: asyncio.Event, timeout: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=timeout)
    except TimeoutError:
        pass


async def check_dependencies(settings: Settings) -> bool:
    database = Database(settings.database_url)
    transport = NatsJetStreamTransport(settings.nats_url)
    try:
        database_ok, nats_ok = await asyncio.gather(database.ping(), transport.ping())
        return database_ok and nats_ok
    finally:
        await transport.close()
        await database.dispose()


async def run_worker(settings: Settings) -> None:
    database = Database(settings.database_url)
    transport = NatsJetStreamTransport(settings.nats_url)
    await transport.connect()
    await transport.ensure_stream(
        EVENT_STREAM_NAME,
        [f"{EVENT_SUBJECT_PREFIX}.>"],
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    logger.info("worker_started")
    try:
        while not stop.is_set():
            try:
                result = await publish_outbox_batch(
                    database,
                    transport,
                    batch_size=OUTBOX_BATCH_SIZE,
                    subject_prefix=EVENT_SUBJECT_PREFIX,
                )
            except Exception:
                logger.exception("outbox_batch_failed")
                await _wait_or_stop(stop, OUTBOX_IDLE_POLL_SECONDS)
                continue

            if result.failed:
                logger.warning(
                    "outbox_publish_failures",
                    claimed=result.claimed,
                    published=result.published,
                    failed=result.failed,
                )
            if result.claimed == 0:
                await _wait_or_stop(stop, OUTBOX_IDLE_POLL_SECONDS)
    finally:
        await transport.close()
        await database.dispose()
        logger.info("worker_stopped")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings)
    if args.check:
        return 0 if asyncio.run(check_dependencies(settings)) else 1
    asyncio.run(run_worker(settings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
