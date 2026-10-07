from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from badban.application.journal import (
    JournalError,
    JournalLine,
    account_totals,
    post_journal,
    reverse_journal,
)
from badban.infrastructure.persistence.models import JournalEntry, JournalPosting


@pytest.mark.integration
async def test_balanced_journal_is_exact_idempotent_and_derived(
    database,
    clean_sprint03_tables,
) -> None:
    legal_entity_id = uuid4()
    actor_id = uuid4()
    correlation_id = uuid4()
    effective_at = datetime.now(UTC)
    lines = [
        JournalLine(
            account_code="1000",
            economic_owner_type="PROGRAM",
            debit_amount=Decimal("123.456789012345678"),
        ),
        JournalLine(
            account_code="2000",
            economic_owner_type="PROGRAM",
            credit_amount=Decimal("123.456789012345678"),
        ),
    ]

    async with database.session_factory() as session:
        async with session.begin():
            entry = await post_journal(
                session,
                business_event_type="FOUNDATION_TEST",
                business_event_id="event-1",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key="journal-1",
                actor_reference=actor_id,
                correlation_id=correlation_id,
                effective_at=effective_at,
                lines=lines,
            )
        first_id = entry.id

    async with database.session_factory() as session:
        async with session.begin():
            replay = await post_journal(
                session,
                business_event_type="FOUNDATION_TEST",
                business_event_id="event-1",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key="journal-1",
                actor_reference=actor_id,
                correlation_id=correlation_id,
                effective_at=effective_at,
                lines=lines,
            )
        assert replay.id == first_id

    async with database.session_factory() as session:
        entry_count = await session.scalar(select(func.count()).select_from(JournalEntry))
        posting_count = await session.scalar(select(func.count()).select_from(JournalPosting))
        debit, credit = await account_totals(
            session,
            account_code="1000",
            currency="IRR",
            legal_entity_id=legal_entity_id,
        )

    assert entry_count == 1
    assert posting_count == 2
    assert debit == Decimal("123.456789012345678")
    assert credit == Decimal("0")


@pytest.mark.integration
async def test_unbalanced_and_changed_idempotent_journal_are_rejected(
    database,
    clean_sprint03_tables,
) -> None:
    legal_entity_id = uuid4()
    actor_id = uuid4()
    correlation_id = uuid4()
    effective_at = datetime.now(UTC)

    async with database.session_factory() as session:
        with pytest.raises(JournalError, match="balance"):
            await post_journal(
                session,
                business_event_type="UNBALANCED",
                business_event_id="bad-1",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key="unbalanced",
                actor_reference=actor_id,
                correlation_id=correlation_id,
                effective_at=effective_at,
                lines=[
                    JournalLine(
                        account_code="1000",
                        economic_owner_type="PROGRAM",
                        debit_amount=Decimal("10"),
                    ),
                    JournalLine(
                        account_code="2000",
                        economic_owner_type="PROGRAM",
                        credit_amount=Decimal("9"),
                    ),
                ],
            )

    base_lines = [
        JournalLine(
            account_code="1000",
            economic_owner_type="PROGRAM",
            debit_amount=Decimal("10"),
        ),
        JournalLine(
            account_code="2000",
            economic_owner_type="PROGRAM",
            credit_amount=Decimal("10"),
        ),
    ]
    async with database.session_factory() as session:
        async with session.begin():
            await post_journal(
                session,
                business_event_type="TEST",
                business_event_id="same",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key="same-key",
                actor_reference=actor_id,
                correlation_id=correlation_id,
                effective_at=effective_at,
                lines=base_lines,
            )

    changed_lines = [
        JournalLine(
            account_code="1000",
            economic_owner_type="PROGRAM",
            debit_amount=Decimal("11"),
        ),
        JournalLine(
            account_code="2000",
            economic_owner_type="PROGRAM",
            credit_amount=Decimal("11"),
        ),
    ]
    async with database.session_factory() as session:
        with pytest.raises(JournalError) as exc:
            async with session.begin():
                await post_journal(
                    session,
                    business_event_type="TEST",
                    business_event_id="same",
                    legal_entity_id=legal_entity_id,
                    currency="IRR",
                    idempotency_key="same-key",
                    actor_reference=actor_id,
                    correlation_id=correlation_id,
                    effective_at=effective_at,
                    lines=changed_lines,
                )
        assert exc.value.code == "JOURNAL_IDEMPOTENCY_CONFLICT"


@pytest.mark.integration
async def test_posted_journal_is_immutable_and_reversal_is_linked(
    database,
    clean_sprint03_tables,
) -> None:
    legal_entity_id = uuid4()
    actor_id = uuid4()
    original_correlation = uuid4()
    lines = [
        JournalLine(
            account_code="3000",
            economic_owner_type="PROGRAM",
            debit_amount=Decimal("25.50"),
        ),
        JournalLine(
            account_code="4000",
            economic_owner_type="PROGRAM",
            credit_amount=Decimal("25.50"),
        ),
    ]

    async with database.session_factory() as session:
        async with session.begin():
            original = await post_journal(
                session,
                business_event_type="FOUNDATION_TEST",
                business_event_id="event-reversal",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key="original-entry",
                actor_reference=actor_id,
                correlation_id=original_correlation,
                lines=lines,
            )
        original_id = original.id

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(JournalEntry)
                    .where(JournalEntry.id == original_id)
                    .values(reason="mutated")
                )

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                session.add(
                    JournalPosting(
                        journal_entry_id=original_id,
                        account_code="late-posting",
                        legal_entity_id=legal_entity_id,
                        economic_owner_type="PROGRAM",
                        debit_amount=Decimal("1"),
                        credit_amount=Decimal("0"),
                        currency="IRR",
                    )
                )
                await session.flush()

    async with database.session_factory() as session:
        async with session.begin():
            reversal = await reverse_journal(
                session,
                original_entry_id=original_id,
                idempotency_key="reversal-entry",
                actor_reference=actor_id,
                correlation_id=uuid4(),
                reason="correct foundation test",
            )
        reversal_id = reversal.id

    async with database.session_factory() as session:
        original = await session.get(JournalEntry, original_id)
        reversal = await session.get(JournalEntry, reversal_id)
        reversal_lines = (
            await session.scalars(
                select(JournalPosting)
                .where(JournalPosting.journal_entry_id == reversal_id)
                .order_by(JournalPosting.account_code)
            )
        ).all()

    assert original is not None
    assert original.reason is None
    assert reversal is not None
    assert reversal.reversal_of_entry_id == original_id
    by_account = {line.account_code: line for line in reversal_lines}
    assert by_account["3000"].credit_amount == Decimal("25.50")
    assert by_account["4000"].debit_amount == Decimal("25.50")

    async with database.session_factory() as session:
        async with session.begin():
            replay = await reverse_journal(
                session,
                original_entry_id=original_id,
                idempotency_key="reversal-entry",
                actor_reference=actor_id,
                correlation_id=uuid4(),
                reason="correct foundation test",
            )
        assert replay.id == reversal_id

    async with database.session_factory() as session:
        with pytest.raises(JournalError) as exc:
            async with session.begin():
                await reverse_journal(
                    session,
                    original_entry_id=original_id,
                    idempotency_key="second-reversal",
                    actor_reference=actor_id,
                    correlation_id=uuid4(),
                    reason="must fail",
                )
        assert exc.value.code == "JOURNAL_ALREADY_REVERSED"


@pytest.mark.integration
async def test_zero_sided_posting_and_generic_post_api_are_absent(
    settings,
    database,
    clean_sprint03_tables,
) -> None:
    with pytest.raises(JournalError) as exc:
        async with database.session_factory() as session:
            await post_journal(
                session,
                business_event_type="ZERO",
                business_event_id="zero",
                legal_entity_id=uuid4(),
                currency="IRR",
                idempotency_key="zero",
                actor_reference=uuid4(),
                correlation_id=uuid4(),
                lines=[
                    JournalLine(
                        account_code="1000",
                        economic_owner_type="PROGRAM",
                    ),
                    JournalLine(
                        account_code="2000",
                        economic_owner_type="PROGRAM",
                        credit_amount=Decimal("1"),
                    ),
                ],
            )
    assert exc.value.code == "JOURNAL_LINES_INVALID"

    from httpx import ASGITransport, AsyncClient

    from badban.api.app import create_app

    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/journal/entries", json={})

    assert response.status_code in {404, 405}
