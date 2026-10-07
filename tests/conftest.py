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
os.environ.setdefault("BADBAN_OIDC_ISSUER", "https://issuer.test/realms/badban")
os.environ.setdefault("BADBAN_OIDC_AUDIENCE", "badban-api")

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


@pytest.fixture
async def clean_sprint02_tables(database: Database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "asset_positions, participation_episodes, role_grants, "
                "audit_events, evidence_references, asset_types, programs, "
                "participants, identities, idempotency_records "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def clean_sprint03_tables(database: Database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "journal_postings, journal_entries, valuation_observations, approval_requests, "
                "outbox_messages, "
                "asset_positions, participation_episodes, role_grants, audit_events, "
                "evidence_references, asset_types, programs, participants, identities, "
                "idempotency_records "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def clean_sprint04_policy_tables(database: Database):
    async with database.engine.begin() as connection:
        await connection.execute(text("TRUNCATE policy_versions RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def clean_sprint06_registry_tables(database: Database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "credit_product_versions, credit_providers, legal_authorizations, legal_entities "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def clean_sprint07_guarantee_tables(database: Database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "guarantee_cases, credit_product_versions, credit_providers, "
                "legal_authorizations, legal_entities, journal_postings, journal_entries, "
                "decision_snapshots, policy_versions, valuation_observations, asset_positions, "
                "participation_episodes, role_grants, audit_events, evidence_references, "
                "asset_types, programs, participants, identities, idempotency_records, "
                "outbox_messages, inbox_messages "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def clean_sprint09_risk_tables(database: Database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "portfolio_risk_snapshots, guarantee_cases, policy_versions, "
                "role_grants, audit_events, identities, idempotency_records, "
                "outbox_messages "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield
