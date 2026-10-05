from __future__ import annotations

import os

import pytest
from sqlalchemy import text

os.environ.setdefault(
    "BADBAN_DATABASE_URL",
    "postgresql+asyncpg://badban@localhost:5432/badban",
)
os.environ.setdefault("BADBAN_NATS_URL", "nats://localhost:4222")
os.environ.setdefault("BADBAN_APP_ENV", "test")
os.environ.setdefault("BADBAN_LOG_LEVEL", "INFO")

from badban.config import Settings  # noqa: E402
from badban.infrastructure.persistence.database import Database  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@pytest.fixture
async def database(settings: Settings):
    db = Database(settings.database_url)
    try:
        yield db
    finally:
        await db.dispose()


@pytest.fixture
async def clean_foundation_tables(database: Database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE outbox_messages, inbox_messages, idempotency_records")
        )
    yield
