from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.journal import JournalLine, post_journal
from badban.application.reserve_metrics import create_reserve_metrics_snapshot
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    GuaranteeReserveMetricsSnapshot,
    Identity,
    JournalEntry,
    JournalPosting,
    LegalEntity,
    RoleGrant,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


@pytest.fixture
async def clean_sprint21_tables(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "guarantee_reserve_metrics_snapshots, journal_postings, journal_entries, "
                "role_grants, audit_events, identities, legal_entities "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _legal_entity_and_identity(
    database,
    *,
    subject: str,
    role: str,
    identity_type: str = "STAFF",
    legal_entity_id: UUID | None = None,
) -> tuple[LegalEntity, Identity]:
    identity = Identity(
        identity_type=identity_type,
        external_subject=subject,
        status="ACTIVE",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(identity)
            await session.flush()
            if legal_entity_id is None:
                legal_entity = LegalEntity(
                    legal_name=f"Reserve Test {subject}",
                    registration_identifier=f"reserve-{uuid4()}",
                    entity_type="BADBAN",
                    status="ACTIVE",
                    created_by=identity.id,
                    version=1,
                )
                session.add(legal_entity)
                await session.flush()
            else:
                legal_entity = await session.get(LegalEntity, legal_entity_id)
                assert legal_entity is not None
            session.add(
                RoleGrant(
                    identity_id=identity.id,
                    role_code=role,
                    scope_type="LEGAL_ENTITY",
                    scope_id=legal_entity.id,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint21-test",
                    version=1,
                )
            )
    return legal_entity, identity


async def _post(
    database,
    *,
    legal_entity_id: UUID,
    actor_id: UUID,
    event_id: str,
    lines: list[JournalLine],
    currency: str = "IRR",
) -> UUID:
    async with database.session_factory() as session:
        async with session.begin():
            entry = await post_journal(
                session,
                business_event_type="SPRINT21_RESERVE_FIXTURE",
                business_event_id=event_id,
                legal_entity_id=legal_entity_id,
                currency=currency,
                idempotency_key=f"sprint21:{event_id}",
                actor_reference=actor_id,
                correlation_id=uuid4(),
                lines=lines,
                actor_type="STAFF",
            )
            return entry.id


@pytest.mark.integration
async def test_reserve_snapshot_keeps_cash_and_designated_balances_separate(
    settings: Settings,
    database,
    clean_sprint21_tables,
) -> None:
    legal_entity, finance = await _legal_entity_and_identity(
        database,
        subject="sprint21-finance",
        role=ROLE_FINANCE_RECONCILIATION,
    )
    await _post(
        database,
        legal_entity_id=legal_entity.id,
        actor_id=finance.id,
        event_id="reserve-cash-100",
        lines=[
            JournalLine(
                account_code="1020.GUARANTEE_RESERVE_CASH_CONTROL",
                economic_owner_type="RESERVE",
                debit_amount=Decimal("100"),
            ),
            JournalLine(
                account_code="2030.PROGRAM_CAPITAL_BALANCE",
                economic_owner_type="PROGRAM",
                credit_amount=Decimal("100"),
            ),
        ],
    )
    await _post(
        database,
        legal_entity_id=legal_entity.id,
        actor_id=finance.id,
        event_id="reserve-designated-80",
        lines=[
            JournalLine(
                account_code="3000.RECOGNIZED_RETURN_CLEARING",
                economic_owner_type="PROGRAM",
                debit_amount=Decimal("80"),
            ),
            JournalLine(
                account_code="2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
                economic_owner_type="RESERVE",
                credit_amount=Decimal("80"),
            ),
        ],
    )
    await _post(
        database,
        legal_entity_id=legal_entity.id,
        actor_id=finance.id,
        event_id="participant-nonreserve-50",
        lines=[
            JournalLine(
                account_code="1000.SETTLEMENT_CASH_CONTROL",
                economic_owner_type="PARTICIPANT",
                debit_amount=Decimal("50"),
            ),
            JournalLine(
                account_code="2000.PARTICIPANT_PAYABLE_BALANCE",
                economic_owner_type="PARTICIPANT",
                credit_amount=Decimal("50"),
            ),
        ],
    )

    async with await _client(settings) as client:
        first = await client.post(
            "/api/v1/finance/reserve-metrics/snapshots",
            headers={"Authorization": f"Bearer {finance.external_subject}"},
            json={"legal_entity_id": str(legal_entity.id), "currency": "IRR"},
        )
        second = await client.post(
            "/api/v1/finance/reserve-metrics/snapshots",
            headers={"Authorization": f"Bearer {finance.external_subject}"},
            json={"legal_entity_id": str(legal_entity.id), "currency": "IRR"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body["cash_control_balance"] == "100.000000000000000000"
    assert body["designated_balance"] == "80.000000000000000000"
    assert body["source_journal_count"] == 2
    assert body["source_posting_count"] == 2
    assert body["reserve_metrics_reference"].startswith("reserve-metrics:")
    assert "reserve_available" not in body
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.integration
async def test_reserve_snapshot_rejects_participant_owned_value_on_reserve_account(
    settings: Settings,
    database,
    clean_sprint21_tables,
) -> None:
    legal_entity, finance = await _legal_entity_and_identity(
        database,
        subject="sprint21-finance-participant-reserve",
        role=ROLE_FINANCE_RECONCILIATION,
    )
    await _post(
        database,
        legal_entity_id=legal_entity.id,
        actor_id=finance.id,
        event_id="participant-misposted-reserve",
        lines=[
            JournalLine(
                account_code="1020.GUARANTEE_RESERVE_CASH_CONTROL",
                economic_owner_type="PARTICIPANT",
                debit_amount=Decimal("25"),
            ),
            JournalLine(
                account_code="2000.PARTICIPANT_PAYABLE_BALANCE",
                economic_owner_type="PARTICIPANT",
                credit_amount=Decimal("25"),
            ),
        ],
    )

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/finance/reserve-metrics/snapshots",
            headers={"Authorization": f"Bearer {finance.external_subject}"},
            json={"legal_entity_id": str(legal_entity.id), "currency": "IRR"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RESERVE_METRICS_SOURCE_OWNERSHIP_INVALID"

    async with database.session_factory() as session:
        count = int(
            await session.scalar(select(func.count()).select_from(GuaranteeReserveMetricsSnapshot))
            or 0
        )
    assert count == 0


@pytest.mark.integration
async def test_reserve_snapshot_ignores_prepared_and_changes_on_new_posted_source(
    settings: Settings,
    database,
    clean_sprint21_tables,
) -> None:
    legal_entity, finance = await _legal_entity_and_identity(
        database,
        subject="sprint21-finance-change",
        role=ROLE_FINANCE_RECONCILIATION,
    )
    await _post(
        database,
        legal_entity_id=legal_entity.id,
        actor_id=finance.id,
        event_id="cash-in-100",
        lines=[
            JournalLine(
                account_code="1020.GUARANTEE_RESERVE_CASH_CONTROL",
                economic_owner_type="RESERVE",
                debit_amount=Decimal("100"),
            ),
            JournalLine(
                account_code="2030.PROGRAM_CAPITAL_BALANCE",
                economic_owner_type="PROGRAM",
                credit_amount=Decimal("100"),
            ),
        ],
    )

    async with database.session_factory() as session:
        async with session.begin():
            prepared = JournalEntry(
                business_event_type="SPRINT21_PREPARED",
                business_event_id="prepared-reserve",
                legal_entity_id=legal_entity.id,
                currency="IRR",
                state="PREPARED",
                effective_at=datetime.now(UTC),
                posted_at=None,
                reversal_of_entry_id=None,
                idempotency_key=f"prepared-{uuid4()}",
                request_hash="0" * 64,
                actor_reference=finance.id,
                correlation_id=uuid4(),
                causation_id=None,
                policy_version_reference=None,
                posting_template_reference=None,
                account_mapping_reference=None,
                evidence_reference=None,
                settlement_reference=None,
                reason=None,
            )
            session.add(prepared)
            await session.flush()
            session.add(
                JournalPosting(
                    journal_entry_id=prepared.id,
                    account_code="1020.GUARANTEE_RESERVE_CASH_CONTROL",
                    legal_entity_id=legal_entity.id,
                    economic_owner_type="RESERVE",
                    debit_amount=Decimal("999"),
                    credit_amount=Decimal("0"),
                    currency="IRR",
                )
            )

    async with await _client(settings) as client:
        before = await client.post(
            "/api/v1/finance/reserve-metrics/snapshots",
            headers={"Authorization": f"Bearer {finance.external_subject}"},
            json={"legal_entity_id": str(legal_entity.id), "currency": "IRR"},
        )
    assert before.status_code == 200
    assert before.json()["cash_control_balance"] == "100.000000000000000000"

    await _post(
        database,
        legal_entity_id=legal_entity.id,
        actor_id=finance.id,
        event_id="cash-out-20",
        lines=[
            JournalLine(
                account_code="1030.RECOVERY_CASH_CONTROL",
                economic_owner_type="RESERVE",
                debit_amount=Decimal("20"),
            ),
            JournalLine(
                account_code="1020.GUARANTEE_RESERVE_CASH_CONTROL",
                economic_owner_type="RESERVE",
                credit_amount=Decimal("20"),
            ),
        ],
    )

    async with await _client(settings) as client:
        after = await client.post(
            "/api/v1/finance/reserve-metrics/snapshots",
            headers={"Authorization": f"Bearer {finance.external_subject}"},
            json={"legal_entity_id": str(legal_entity.id), "currency": "IRR"},
        )
    assert after.status_code == 200
    assert after.json()["cash_control_balance"] == "80.000000000000000000"
    assert after.json()["id"] != before.json()["id"]
    assert after.json()["source_fingerprint"] != before.json()["source_fingerprint"]


@pytest.mark.integration
async def test_reserve_snapshot_auditor_is_read_only_and_snapshot_is_append_only(
    settings: Settings,
    database,
    clean_sprint21_tables,
) -> None:
    legal_entity, finance = await _legal_entity_and_identity(
        database,
        subject="sprint21-finance-audit",
        role=ROLE_FINANCE_RECONCILIATION,
    )
    _, auditor = await _legal_entity_and_identity(
        database,
        subject="sprint21-auditor",
        role=ROLE_AUDITOR,
        identity_type="AUDITOR",
        legal_entity_id=legal_entity.id,
    )

    async with await _client(settings) as client:
        created = await client.post(
            "/api/v1/finance/reserve-metrics/snapshots",
            headers={"Authorization": f"Bearer {finance.external_subject}"},
            json={"legal_entity_id": str(legal_entity.id), "currency": "IRR"},
        )
        assert created.status_code == 200
        snapshot_id = UUID(created.json()["id"])

        denied = await client.post(
            "/api/v1/finance/reserve-metrics/snapshots",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
            json={"legal_entity_id": str(legal_entity.id), "currency": "IRR"},
        )
        assert denied.status_code == 403

        read = await client.get(
            f"/api/v1/finance/reserve-metrics/snapshots/{snapshot_id}",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
        )
        assert read.status_code == 200

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(GuaranteeReserveMetricsSnapshot)
                    .where(GuaranteeReserveMetricsSnapshot.id == snapshot_id)
                    .values(currency="USD")
                )


@pytest.mark.integration
async def test_reserve_snapshot_concurrent_identical_source_is_single_record(
    database,
    clean_sprint21_tables,
) -> None:
    legal_entity, finance = await _legal_entity_and_identity(
        database,
        subject="sprint21-finance-concurrent",
        role=ROLE_FINANCE_RECONCILIATION,
    )
    await _post(
        database,
        legal_entity_id=legal_entity.id,
        actor_id=finance.id,
        event_id="concurrent-cash-10",
        lines=[
            JournalLine(
                account_code="1020.GUARANTEE_RESERVE_CASH_CONTROL",
                economic_owner_type="RESERVE",
                debit_amount=Decimal("10"),
            ),
            JournalLine(
                account_code="2030.PROGRAM_CAPITAL_BALANCE",
                economic_owner_type="PROGRAM",
                credit_amount=Decimal("10"),
            ),
        ],
    )

    async def create_one() -> UUID:
        async with database.session_factory() as session:
            async with session.begin():
                snapshot = await create_reserve_metrics_snapshot(
                    session,
                    legal_entity_id=legal_entity.id,
                    currency="IRR",
                    actor_type=finance.identity_type,
                    actor_id=finance.id,
                    correlation_id=uuid4(),
                )
                return snapshot.id

    first, second = await asyncio.gather(create_one(), create_one())

    assert first == second
    async with database.session_factory() as session:
        count = int(
            await session.scalar(select(func.count()).select_from(GuaranteeReserveMetricsSnapshot))
            or 0
        )
    assert count == 1
