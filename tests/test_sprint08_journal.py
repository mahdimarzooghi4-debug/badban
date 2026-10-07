from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.journal import (
    JournalError,
    JournalLine,
    post_journal,
    reversal_approval_payload,
)
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AuditEvent,
    Identity,
    JournalEntry,
    JournalPosting,
    OutboxMessage,
    RoleGrant,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _identity(
    database,
    *,
    subject: str,
    identity_type: str,
    role: str,
    legal_entity_id: UUID,
) -> Identity:
    identity = Identity(
        identity_type=identity_type,
        external_subject=subject,
        status="ACTIVE",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(identity)
            await session.flush()
            session.add(
                RoleGrant(
                    identity_id=identity.id,
                    role_code=role,
                    scope_type="LEGAL_ENTITY",
                    scope_id=legal_entity_id,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint08-test",
                )
            )
    return identity


def _headers(subject: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {subject}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _lines(amount: str = "10") -> list[JournalLine]:
    value = Decimal(amount)
    return [
        JournalLine(
            account_code="1000",
            economic_owner_type="PROGRAM",
            debit_amount=value,
        ),
        JournalLine(
            account_code="2000",
            economic_owner_type="PROGRAM",
            credit_amount=value,
        ),
    ]


@pytest.mark.integration
async def test_decimal_storage_boundary_and_atomic_rollback(
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    with pytest.raises(JournalError) as fractional:
        async with database.session_factory() as session:
            await post_journal(
                session,
                business_event_type="PRECISION",
                business_event_id="fractional",
                legal_entity_id=uuid4(),
                currency="IRR",
                idempotency_key="precision-fractional",
                actor_reference=uuid4(),
                correlation_id=uuid4(),
                lines=_lines("1.0000000000000000001"),
            )
    assert fractional.value.code == "JOURNAL_AMOUNT_PRECISION_INVALID"

    with pytest.raises(JournalError) as integer:
        async with database.session_factory() as session:
            await post_journal(
                session,
                business_event_type="PRECISION",
                business_event_id="integer",
                legal_entity_id=uuid4(),
                currency="IRR",
                idempotency_key="precision-integer",
                actor_reference=uuid4(),
                correlation_id=uuid4(),
                lines=_lines("100000000000000000000"),
            )
    assert integer.value.code == "JOURNAL_AMOUNT_PRECISION_INVALID"

    legal_entity_id = uuid4()
    try:
        async with database.session_factory() as session:
            async with session.begin():
                await post_journal(
                    session,
                    business_event_type="ROLLBACK",
                    business_event_id="rollback-1",
                    legal_entity_id=legal_entity_id,
                    currency="IRR",
                    idempotency_key="rollback-1",
                    actor_reference=uuid4(),
                    correlation_id=uuid4(),
                    lines=_lines("5"),
                )
                raise RuntimeError("force rollback")
    except RuntimeError:
        pass

    async with database.session_factory() as session:
        journals = await session.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.business_event_id == "rollback-1")
        )
        audits = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "JOURNAL_POSTED")
        )
        outbox = await session.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(OutboxMessage.event_type == "JournalPosted")
        )
    assert journals == 0
    assert audits == 0
    assert outbox == 0


@pytest.mark.integration
async def test_lineage_is_preserved_without_invented_aggregate_amount_limit(
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    legal_entity_id = uuid4()
    actor_id = uuid4()
    effective_at = datetime.now(UTC)
    amount = Decimal("90000000000000000000")
    lines = [
        JournalLine(
            account_code="1000-A",
            economic_owner_type="PROGRAM",
            debit_amount=amount,
        ),
        JournalLine(
            account_code="1000-B",
            economic_owner_type="PROGRAM",
            debit_amount=amount,
        ),
        JournalLine(
            account_code="2000-A",
            economic_owner_type="PROGRAM",
            credit_amount=amount,
        ),
        JournalLine(
            account_code="2000-B",
            economic_owner_type="PROGRAM",
            credit_amount=amount,
        ),
    ]

    async with database.session_factory() as session:
        async with session.begin():
            entry = await post_journal(
                session,
                business_event_type="LINEAGE_TEST",
                business_event_id="lineage-1",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key="lineage-1",
                actor_reference=actor_id,
                actor_type="SYSTEM",
                correlation_id=uuid4(),
                effective_at=effective_at,
                policy_version_reference="policy-v1",
                posting_template_reference="template:v1",
                account_mapping_reference="mapping:v1",
                evidence_reference="evidence:1",
                settlement_reference="settlement:1",
                lines=lines,
            )
            entry_id = entry.id

    async with database.session_factory() as session:
        stored = await session.get(JournalEntry, entry_id)
        event = await session.scalar(
            select(OutboxMessage).where(
                OutboxMessage.aggregate_id == str(entry_id),
                OutboxMessage.event_type == "JournalPosted",
            )
        )
        totals = (
            await session.execute(
                select(
                    func.sum(JournalPosting.debit_amount),
                    func.sum(JournalPosting.credit_amount),
                ).where(JournalPosting.journal_entry_id == entry_id)
            )
        ).one()

    assert stored is not None
    assert stored.policy_version_reference == "policy-v1"
    assert stored.posting_template_reference == "template:v1"
    assert stored.account_mapping_reference == "mapping:v1"
    assert stored.evidence_reference == "evidence:1"
    assert stored.settlement_reference == "settlement:1"
    assert totals[0] == Decimal("180000000000000000000")
    assert totals[1] == Decimal("180000000000000000000")
    assert event is not None
    assert event.payload["policy_version_reference"] == "policy-v1"
    assert event.payload["posting_template_reference"] == "template:v1"
    assert event.payload["account_mapping_reference"] == "mapping:v1"
    assert event.payload["evidence_reference"] == "evidence:1"
    assert event.payload["settlement_reference"] == "settlement:1"
    assert event.payload["actor_type"] == "SYSTEM"

    async with database.session_factory() as session:
        with pytest.raises(JournalError) as changed:
            async with session.begin():
                await post_journal(
                    session,
                    business_event_type="LINEAGE_TEST",
                    business_event_id="lineage-1",
                    legal_entity_id=legal_entity_id,
                    currency="IRR",
                    idempotency_key="lineage-1",
                    actor_reference=actor_id,
                    correlation_id=uuid4(),
                    effective_at=effective_at,
                    policy_version_reference="policy-v2",
                    posting_template_reference="template:v1",
                    account_mapping_reference="mapping:v1",
                    evidence_reference="evidence:1",
                    settlement_reference="settlement:1",
                    lines=lines,
                )
    assert changed.value.code == "JOURNAL_IDEMPOTENCY_CONFLICT"


@pytest.mark.integration
async def test_concurrent_same_key_is_single_effect(
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    legal_entity_id = uuid4()
    actor = uuid4()
    effective_at = datetime.now(UTC)

    async def create_once() -> UUID:
        async with database.session_factory() as session:
            async with session.begin():
                entry = await post_journal(
                    session,
                    business_event_type="CONCURRENCY",
                    business_event_id="same-event",
                    legal_entity_id=legal_entity_id,
                    currency="IRR",
                    idempotency_key="same-concurrent-key",
                    actor_reference=actor,
                    correlation_id=uuid4(),
                    effective_at=effective_at,
                    lines=_lines("11.25"),
                )
                return entry.id

    first, second = await asyncio.gather(create_once(), create_once())
    assert first == second

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(JournalEntry))
        postings = await session.scalar(select(func.count()).select_from(JournalPosting))
        events = await session.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(OutboxMessage.event_type == "JournalPosted")
        )
    assert count == 1
    assert postings == 2
    assert events == 1


@pytest.mark.integration
async def test_db_rejects_unbalanced_posted_transition(
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    legal_entity_id = uuid4()
    entry = JournalEntry(
        business_event_type="DIRECT_DB_TEST",
        business_event_id="direct-unbalanced",
        legal_entity_id=legal_entity_id,
        currency="IRR",
        state="PREPARED",
        effective_at=datetime.now(UTC),
        posted_at=None,
        reversal_of_entry_id=None,
        idempotency_key="direct-unbalanced",
        request_hash="x" * 64,
        actor_reference=uuid4(),
        correlation_id=uuid4(),
        causation_id=None,
        reason=None,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(entry)
            await session.flush()
            session.add(
                JournalPosting(
                    journal_entry_id=entry.id,
                    account_code="1000",
                    legal_entity_id=legal_entity_id,
                    economic_owner_type="PROGRAM",
                    debit_amount=Decimal("10"),
                    credit_amount=Decimal("0"),
                    currency="IRR",
                )
            )
    with pytest.raises(DBAPIError):
        async with database.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(JournalEntry)
                    .where(JournalEntry.id == entry.id)
                    .values(state="POSTED", posted_at=datetime.now(UTC))
                )


@pytest.mark.integration
async def test_finance_api_reversal_requires_exact_governance_approval(
    settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    legal_entity_id = uuid4()
    finance = await _identity(
        database,
        subject="finance",
        identity_type="STAFF",
        role="FINANCE_RECONCILIATION",
        legal_entity_id=legal_entity_id,
    )
    await _identity(
        database,
        subject="governance",
        identity_type="GOVERNANCE",
        role="GOVERNANCE_APPROVER",
        legal_entity_id=legal_entity_id,
    )
    await _identity(
        database,
        subject="auditor",
        identity_type="AUDITOR",
        role="AUDITOR",
        legal_entity_id=legal_entity_id,
    )
    other_legal_entity_id = uuid4()
    await _identity(
        database,
        subject="other-auditor",
        identity_type="AUDITOR",
        role="AUDITOR",
        legal_entity_id=other_legal_entity_id,
    )
    await _identity(
        database,
        subject="other-finance",
        identity_type="STAFF",
        role="FINANCE_RECONCILIATION",
        legal_entity_id=other_legal_entity_id,
    )

    async with database.session_factory() as session:
        async with session.begin():
            original = await post_journal(
                session,
                business_event_type="SPRINT08_TEST",
                business_event_id="original",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key="original",
                actor_reference=finance.id,
                actor_type="STAFF",
                correlation_id=uuid4(),
                lines=_lines("25.50"),
            )
            approval_payload = reversal_approval_payload(original, "correct posting")
            original_id = original.id

    async with await _client(settings) as client:
        listed = await client.get(
            "/api/v1/finance/journals",
            params={"legal_entity_id": str(legal_entity_id)},
            headers=_headers("auditor"),
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        cross_scope_list = await client.get(
            "/api/v1/finance/journals",
            params={"legal_entity_id": str(legal_entity_id)},
            headers=_headers("other-auditor"),
        )
        assert cross_scope_list.status_code == 403

        detail = await client.get(
            f"/api/v1/finance/journals/{original_id}",
            headers=_headers("auditor"),
        )
        assert detail.status_code == 200
        cross_scope_detail = await client.get(
            f"/api/v1/finance/journals/{original_id}",
            headers=_headers("other-auditor"),
        )
        assert cross_scope_detail.status_code == 403
        assert detail.json()["postings"][0]["debit_amount"] in {
            "25.500000000000000000",
            "0.000000000000000000",
        }

        approval = await client.post(
            "/api/v1/approval-requests",
            headers=_headers("finance", "journal-reversal-approval"),
            json={
                "action_type": "JOURNAL_REVERSAL",
                "target_type": "JournalEntry",
                "target_id": str(original_id),
                "target_aggregate_version": None,
                "required_checker_role": "GOVERNANCE_APPROVER",
                "scope_type": "LEGAL_ENTITY",
                "scope_id": str(legal_entity_id),
                "payload": approval_payload,
                "reason": "maker requests exact reversal",
            },
        )
        assert approval.status_code == 201
        approval_id = approval.json()["id"]

        approved = await client.post(
            f"/api/v1/approval-requests/{approval_id}/approve",
            headers=_headers("governance"),
            json={"reason": "checked"},
        )
        assert approved.status_code == 200

        cross_scope_finance_denied = await client.post(
            f"/api/v1/finance/journals/{original_id}/reverse",
            headers=_headers("other-finance", "cross-scope-reversal"),
            json={
                "approval_request_id": approval_id,
                "reason": "correct posting",
            },
        )
        assert cross_scope_finance_denied.status_code == 403

        auditor_denied = await client.post(
            f"/api/v1/finance/journals/{original_id}/reverse",
            headers=_headers("auditor", "auditor-cannot-reverse"),
            json={
                "approval_request_id": approval_id,
                "reason": "correct posting",
            },
        )
        assert auditor_denied.status_code == 403

        changed = await client.post(
            f"/api/v1/finance/journals/{original_id}/reverse",
            headers=_headers("finance", "reversal-changed"),
            json={
                "approval_request_id": approval_id,
                "reason": "different reason",
            },
        )
        assert changed.status_code == 409
        assert changed.json()["error"]["code"] == "APPROVAL_PAYLOAD_CHANGED"

        reversed_response = await client.post(
            f"/api/v1/finance/journals/{original_id}/reverse",
            headers=_headers("finance", "reversal-accepted"),
            json={
                "approval_request_id": approval_id,
                "reason": "correct posting",
            },
        )
        assert reversed_response.status_code == 201
        reversal_body = reversed_response.json()
        reversal_id = reversal_body["id"]
        assert reversal_body["reversal_of_entry_id"] == str(original_id)
        reversal_postings = {
            posting["account_code"]: posting for posting in reversal_body["postings"]
        }
        assert reversal_postings["1000"]["debit_amount"] == "0.000000000000000000"
        assert reversal_postings["1000"]["credit_amount"] == "25.500000000000000000"
        assert reversal_postings["2000"]["debit_amount"] == "25.500000000000000000"
        assert reversal_postings["2000"]["credit_amount"] == "0.000000000000000000"

        replay = await client.post(
            f"/api/v1/finance/journals/{original_id}/reverse",
            headers=_headers("finance", "reversal-accepted"),
            json={
                "approval_request_id": approval_id,
                "reason": "correct posting",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == reversal_id

        second_reversal = await client.post(
            f"/api/v1/finance/journals/{original_id}/reverse",
            headers=_headers("finance", "reversal-second-key"),
            json={
                "approval_request_id": approval_id,
                "reason": "correct posting",
            },
        )
        assert second_reversal.status_code == 409
        assert second_reversal.json()["error"]["code"] == "JOURNAL_ALREADY_REVERSED"

    async with database.session_factory() as session:
        posted_events = (
            await session.scalars(
                select(OutboxMessage.event_type).order_by(OutboxMessage.created_at)
            )
        ).all()
        reversal_event = await session.scalar(
            select(OutboxMessage).where(
                OutboxMessage.aggregate_id == str(reversal_id),
                OutboxMessage.event_type == "JournalReversed",
            )
        )
        reversal_audit_count = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.aggregate_id == str(reversal_id),
                AuditEvent.action == "JOURNAL_REVERSED",
                AuditEvent.outcome == "SUCCESS",
            )
        )
    assert posted_events.count("JournalPosted") == 1
    assert posted_events.count("JournalReversed") == 1
    assert reversal_event is not None
    assert reversal_event.payload["reason"] == "correct posting"
    assert reversal_event.payload["approval_request_id"] == approval_id
    assert reversal_audit_count == 1


def test_openapi_exposes_only_accepted_finance_journal_mutation(settings) -> None:
    app = create_app(settings)
    schema = app.openapi()
    paths = schema["paths"]

    assert "/api/v1/finance/journals" in paths
    assert set(paths["/api/v1/finance/journals"]) == {"get"}
    assert "/api/v1/finance/journals/{journal_id}" in paths
    assert set(paths["/api/v1/finance/journals/{journal_id}"]) == {"get"}
    assert "/api/v1/finance/journals/{journal_id}/reverse" in paths
    assert set(paths["/api/v1/finance/journals/{journal_id}/reverse"]) == {"post"}
    assert "/api/v1/finance/journals/create" not in paths

    detail_schema = schema["components"]["schemas"]["JournalDetailView"]["properties"]
    assert detail_schema["effective_at"]["format"] == "date-time"
    assert "policy_version_reference" in detail_schema
    assert "posting_template_reference" in detail_schema
    assert "account_mapping_reference" in detail_schema
    assert "evidence_reference" in detail_schema
    assert "settlement_reference" in detail_schema
