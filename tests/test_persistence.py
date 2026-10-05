from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import column, select, table, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import IntegrityError

from badban.infrastructure.persistence.models import (
    IdempotencyRecord,
    InboxMessage,
    OutboxMessage,
)
from badban.infrastructure.persistence.optimistic import (
    OptimisticConcurrencyError,
    update_with_expected_version,
)


@pytest.mark.integration
async def test_transaction_rollback_removes_outbox_and_idempotency(
    database, clean_foundation_tables
) -> None:
    with pytest.raises(RuntimeError):
        async with database.session_factory() as session:
            async with session.begin():
                session.add(
                    IdempotencyRecord(
                        scope="test",
                        idempotency_key="idem-1",
                        request_hash="abc",
                        outcome_status="PENDING",
                    )
                )
                session.add(
                    OutboxMessage(
                        event_type="FoundationProbeCreated",
                        event_version=1,
                        aggregate_type="FoundationProbe",
                        aggregate_id="probe-1",
                        aggregate_version=1,
                        payload={"probe": True},
                        occurred_at=datetime.now(UTC),
                    )
                )
                raise RuntimeError("force rollback")

    async with database.session_factory() as session:
        outbox_count = len((await session.scalars(select(OutboxMessage))).all())
        idem_count = len((await session.scalars(select(IdempotencyRecord))).all())

    assert outbox_count == 0
    assert idem_count == 0


@pytest.mark.integration
async def test_inbox_provider_event_is_deduplicated(database, clean_foundation_tables) -> None:
    first = InboxMessage(
        source_id="provider-a",
        event_type="LOAN_DISBURSED",
        external_event_id="evt-1",
        payload_hash="hash-1",
        payload={"amount": "100.00"},
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(first)

    duplicate = InboxMessage(
        source_id="provider-a",
        event_type="LOAN_DISBURSED",
        external_event_id="evt-1",
        payload_hash="hash-1",
        payload={"amount": "100.00"},
    )
    async with database.session_factory() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(duplicate)
                await session.flush()


@pytest.mark.integration
async def test_postgresql_exact_decimal_round_trip(database) -> None:
    expected = Decimal("1234567890.123456789012345678")
    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                text("CREATE TEMP TABLE decimal_probe(value NUMERIC(38,18) NOT NULL)")
            )
            await session.execute(
                text("INSERT INTO decimal_probe(value) VALUES (:value)"),
                {"value": expected},
            )
            actual = await session.scalar(text("SELECT value FROM decimal_probe"))

    assert actual == expected


@pytest.mark.integration
async def test_optimistic_version_update_rejects_stale_version(database) -> None:
    record_id = uuid4()
    probe = table(
        "version_probe",
        column("id", PGUUID(as_uuid=True)),
        column("version"),
        column("value"),
    )
    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                text(
                    "CREATE TEMP TABLE version_probe("
                    "id uuid PRIMARY KEY, version integer NOT NULL, value text NOT NULL)"
                )
            )
            await session.execute(
                text("INSERT INTO version_probe(id, version, value) VALUES (:id, 1, 'a')"),
                {"id": record_id},
            )
            await update_with_expected_version(
                session,
                probe,
                record_id,
                expected_version=1,
                values={"value": "b"},
            )
            with pytest.raises(OptimisticConcurrencyError):
                await update_with_expected_version(
                    session,
                    probe,
                    record_id,
                    expected_version=1,
                    values={"value": "c"},
                )
