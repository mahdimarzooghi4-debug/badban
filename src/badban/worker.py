from __future__ import annotations

import argparse
import asyncio
import signal
from collections.abc import Sequence

import structlog

from badban.config import Settings, get_settings
from badban.infrastructure.messaging import NatsJetStreamTransport
from badban.infrastructure.persistence.database import Database
from badban.observability import configure_logging

logger = structlog.get_logger(__name__)


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
    transport = NatsJetStreamTransport(settings.nats_url)
    await transport.connect()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    logger.info("worker_started")
    try:
        await stop.wait()
    finally:
        await transport.close()
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
