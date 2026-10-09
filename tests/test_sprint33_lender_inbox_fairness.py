from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from badban.application.external_loan import (
    _select_pending_lender_inbox_ids,
    lender_source_id,
    process_pending_lender_inbox_batch,
)
from badban.application.lender_adapter import NormalizedLenderEvent
from badban.infrastructure.persistence.database import Database
from badban.infrastructure.persistence.models import (
    CreditProvider,
    ExternalLoanEvent,
    ExternalLoanMirror,
    GuaranteeCase,
    Identity,
    InboxMessage,
    JournalEntry,
    LenderInboxScanCheckpoint,
    LegalEntity,
    OutboxMessage,
)


@pytest.fixture
async def clean_sprint33_tables(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE lender_inbox_scan_checkpoints, external_loan_events, "
                "external_loan_mirrors, guarantee_cases, credit_product_versions, "
                "credit_providers, legal_entities, identities, audit_events, "
                "outbox_messages, inbox_messages, journal_postings, journal_entries "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


async def _seed_batch(database, *, poison_count: int, valid_count: int) -> dict:
    now = datetime.now(UTC) - timedelta(minutes=1)
    result: dict = {"poison": [], "valid": [], "provider_id": None}
    async with database.session_factory() as session:
        async with session.begin():
            actor = Identity(
                identity_type="STAFF",
                external_subject=f"sprint33-actor-{uuid4()}",
                status="ACTIVE",
            )
            session.add(actor)
            await session.flush()
            legal = LegalEntity(
                legal_name="Sprint 33 Test Lender",
                registration_identifier=f"sprint33-{uuid4()}",
                entity_type="EXTERNAL_LENDER",
                status="ACTIVE",
                created_by=actor.id,
            )
            session.add(legal)
            await session.flush()
            provider = CreditProvider(
                legal_entity_id=legal.id,
                provider_code=f"S33-{uuid4()}",
                display_name="Sprint 33 Test Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="CONTROLLED_MANUAL",
                authorization_review_state="TEST_PENDING",
                lifecycle_status="DRAFT",
                created_by=actor.id,
            )
            session.add(provider)
            await session.flush()
            result["provider_id"] = provider.id

            for idx in range(poison_count + valid_count):
                message_id = uuid4()
                received_at = now + timedelta(seconds=idx)
                if idx < poison_count:
                    # A syntactically valid Inbox row with an invalid normalized
                    # provider event remains unprocessed and must not starve peers.
                    event_payload: dict = {"not_a_normalized_event": True}
                    result["poison"].append(message_id)
                else:
                    evt = NormalizedLenderEvent(
                        provider_id=provider.id,
                        external_event_id=f"s33-{idx}-{uuid4()}",
                        event_type="LOAN_APPROVED",
                        schema_version=1,
                        external_loan_id=f"s33-loan-{idx}-{uuid4()}",
                        event_time=received_at,
                        received_at=received_at,
                        original_principal="100.00",
                        outstanding_principal="100.00",
                        currency="IRR",
                        payload_hash="a" * 64,
                        provider_contract_version="test-v1",
                        adapter_mapping_version="test-v1",
                        inbound_normalization_version="test-v1",
                    )
                    event_payload = evt.model_dump(mode="json")
                    result["valid"].append(message_id)
                session.add(
                    InboxMessage(
                        id=message_id,
                        source_id=lender_source_id(provider.id),
                        event_type="LOAN_APPROVED",
                        external_event_id=f"s33-evt-{idx}-{uuid4()}",
                        payload_hash="a" * 64,
                        payload=event_payload,
                        received_at=received_at,
                    )
                )
    return result


@pytest.mark.integration
async def test_poison_oldest_does_not_starve_later_real_lender_events(
    settings, database, clean_sprint33_tables
) -> None:
    keys = await _seed_batch(database, poison_count=2, valid_count=2)
    first = await process_pending_lender_inbox_batch(database, batch_size=2)
    assert (first.claimed, first.failed, first.processed) == (2, 2, 0)

    # Simulate a worker process restarting by using a completely new Database
    # object; selection must continue after persisted checkpoint, not from head.
    restarted = Database(settings.database_url)
    try:
        second = await process_pending_lender_inbox_batch(restarted, batch_size=2)
    finally:
        await restarted.dispose()
    assert (second.claimed, second.failed, second.processed) == (2, 0, 2)

    async with database.session_factory() as session:
        good = (
            await session.scalars(select(InboxMessage).where(InboxMessage.id.in_(keys["valid"])))
        ).all()
        bad = (
            await session.scalars(select(InboxMessage).where(InboxMessage.id.in_(keys["poison"])))
        ).all()
        assert len(good) == len(bad) == 2
        assert all(x.processed_at is not None for x in good)
        assert all(x.processed_at is None for x in bad)
        assert (
            int(await session.scalar(select(func.count()).select_from(ExternalLoanMirror)) or 0)
            == 2
        )
        assert (
            int(await session.scalar(select(func.count()).select_from(ExternalLoanEvent)) or 0) == 2
        )
        assert int(await session.scalar(select(func.count()).select_from(OutboxMessage)) or 0) == 2
        assert int(await session.scalar(select(func.count()).select_from(JournalEntry)) or 0) == 0
        assert int(await session.scalar(select(func.count()).select_from(GuaranteeCase)) or 0) == 0
        checkpoint = await session.get(LenderInboxScanCheckpoint, "lender-inbox:v1")
        assert checkpoint is not None
        assert checkpoint.last_message_id == keys["valid"][-1]

    # Wraparound still retries failed messages, without losing them.
    wrapped = await process_pending_lender_inbox_batch(database, batch_size=2)
    assert (wrapped.claimed, wrapped.failed, wrapped.processed) == (2, 2, 0)


@pytest.mark.integration
async def test_replica_scanners_rotate_distinct_pending_pages_without_skipping(
    database, clean_sprint33_tables
) -> None:
    keys = await _seed_batch(database, poison_count=6, valid_count=0)
    first, second, third = await asyncio.wait_for(
        asyncio.gather(
            _select_pending_lender_inbox_ids(database, batch_size=2),
            _select_pending_lender_inbox_ids(database, batch_size=2),
            _select_pending_lender_inbox_ids(database, batch_size=2),
        ),
        timeout=15,
    )
    assert len(first) == len(second) == len(third) == 2
    assert set(first).isdisjoint(second)
    assert set(first).isdisjoint(third)
    assert set(second).isdisjoint(third)
    assert set(first + second + third) == set(keys["poison"])

    # The next transaction wraps and retries the oldest pending cohort.
    fourth = await _select_pending_lender_inbox_ids(database, batch_size=2)
    assert fourth == keys["poison"][:2]


@pytest.mark.integration
async def test_processed_rows_excluded_and_cursor_pair_protected(
    database, clean_sprint33_tables
) -> None:
    keys = await _seed_batch(database, poison_count=3, valid_count=0)
    first = await _select_pending_lender_inbox_ids(database, batch_size=2)
    assert first == keys["poison"][:2]
    async with database.session_factory() as session:
        async with session.begin():
            row = await session.get(InboxMessage, first[0])
            assert row is not None
            row.processed_at = datetime.now(UTC)

    second = await _select_pending_lender_inbox_ids(database, batch_size=2)
    assert second == [keys["poison"][2], keys["poison"][1]]

    async with database.session_factory() as session:
        checkpoint = await session.get(LenderInboxScanCheckpoint, "lender-inbox:v1")
        assert checkpoint is not None
        assert isinstance(checkpoint.last_message_id, UUID)
    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                from sqlalchemy import update

                await session.execute(
                    update(LenderInboxScanCheckpoint)
                    .where(LenderInboxScanCheckpoint.stream_key == "lender-inbox:v1")
                    .values(last_message_id=None)
                )


@pytest.mark.integration
async def test_zero_pending_and_invalid_batch_are_safe(database, clean_sprint33_tables) -> None:
    assert await _select_pending_lender_inbox_ids(database, batch_size=1) == []
    assert (await process_pending_lender_inbox_batch(database, batch_size=1)).claimed == 0
    with pytest.raises(ValueError):
        await process_pending_lender_inbox_batch(database, batch_size=0)
    assert int(await _get_checkpoint_count(database)) == 1


async def _get_checkpoint_count(database) -> int:
    async with database.session_factory() as session:
        return int(
            await session.scalar(select(func.count()).select_from(LenderInboxScanCheckpoint)) or 0
        )
