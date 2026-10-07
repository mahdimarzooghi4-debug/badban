from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from badban.api.app import create_app
from badban.application.approval import approval_payload_hash
from badban.application.journal import (
    JournalError,
    JournalLine,
    journal_reversal_approval_payload,
    post_journal,
)
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    AuditEvent,
    Identity,
    JournalEntry,
    JournalPosting,
    OutboxMessage,
    RoleGrant,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_GOVERNANCE_APPROVER,
    SCOPE_LEGAL_ENTITY,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _count(session, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _seed_roles(database, legal_entity_id):
    finance = Identity(
        identity_type="STAFF",
        external_subject="sprint08-finance",
        status="ACTIVE",
    )
    checker = Identity(
        identity_type="GOVERNANCE",
        external_subject="sprint08-checker",
        status="ACTIVE",
    )
    auditor = Identity(
        identity_type="AUDITOR",
        external_subject="sprint08-auditor",
        status="ACTIVE",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([finance, checker, auditor])
            await session.flush()
            now = datetime.now(UTC) - timedelta(minutes=1)
            session.add_all(
                [
                    RoleGrant(
                        identity_id=finance.id,
                        role_code=ROLE_FINANCE_RECONCILIATION,
                        scope_type=SCOPE_LEGAL_ENTITY,
                        scope_id=legal_entity_id,
                        valid_from=now,
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=None,
                        reason_ref="sprint08",
                        version=1,
                    ),
                    RoleGrant(
                        identity_id=checker.id,
                        role_code=ROLE_GOVERNANCE_APPROVER,
                        scope_type=SCOPE_LEGAL_ENTITY,
                        scope_id=legal_entity_id,
                        valid_from=now,
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=None,
                        reason_ref="sprint08",
                        version=1,
                    ),
                    RoleGrant(
                        identity_id=auditor.id,
                        role_code=ROLE_AUDITOR,
                        scope_type=SCOPE_LEGAL_ENTITY,
                        scope_id=legal_entity_id,
                        valid_from=now,
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=None,
                        reason_ref="sprint08",
                        version=1,
                    ),
                ]
            )
    return finance, checker, auditor


async def _post_foundation_journal(database, legal_entity_id, actor_id, key="sprint08-original"):
    async with database.session_factory() as session:
        async with session.begin():
            entry = await post_journal(
                session,
                business_event_type="SPRINT08_TEST",
                business_event_id=key,
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key=key,
                actor_reference=actor_id,
                actor_type="STAFF",
                correlation_id=uuid4(),
                lines=[
                    JournalLine(
                        account_code="1000.TEST",
                        economic_owner_type="PROGRAM",
                        debit_amount=Decimal("25.125"),
                    ),
                    JournalLine(
                        account_code="2000.TEST",
                        economic_owner_type="PROGRAM",
                        credit_amount=Decimal("25.125"),
                    ),
                ],
                policy_version_reference="policy-test:1",
                posting_template_code="TEST_TEMPLATE",
                posting_template_version="1",
                account_mapping_reference="mapping-test:1",
                evidence_reference="evidence-test",
            )
        entry_id = entry.id
    return entry_id


@pytest.mark.integration
async def test_post_journal_writes_audit_and_outbox_and_is_concurrency_safe(
    database,
    clean_sprint08_journal_tables,
) -> None:
    legal_entity_id = uuid4()
    actor_id = uuid4()
    correlation_id = uuid4()

    async def write_once():
        async with database.session_factory() as session:
            async with session.begin():
                entry = await post_journal(
                    session,
                    business_event_type="CONCURRENT_TEST",
                    business_event_id="event-1",
                    legal_entity_id=legal_entity_id,
                    currency="IRR",
                    idempotency_key="journal-concurrent-1",
                    actor_reference=actor_id,
                    correlation_id=correlation_id,
                    lines=[
                        JournalLine(
                            account_code="1000.TEST",
                            economic_owner_type="PROGRAM",
                            debit_amount=Decimal("10"),
                        ),
                        JournalLine(
                            account_code="2000.TEST",
                            economic_owner_type="PROGRAM",
                            credit_amount=Decimal("10"),
                        ),
                    ],
                )
            return entry.id

    first_id, second_id = await asyncio.gather(write_once(), write_once())
    assert first_id == second_id

    async with database.session_factory() as session:
        assert await _count(session, JournalEntry) == 1
        assert await _count(session, JournalPosting) == 2
        events = (
            await session.scalars(
                select(OutboxMessage).where(OutboxMessage.aggregate_id == str(first_id))
            )
        ).all()
        audits = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.aggregate_id == str(first_id))
            )
        ).all()
        assert [event.event_type for event in events] == ["JournalPosted"]
        assert [audit.action for audit in audits] == ["JournalPosted"]


@pytest.mark.integration
async def test_journal_rejects_precision_beyond_numeric_storage_boundary(
    database,
    clean_sprint08_journal_tables,
) -> None:
    async with database.session_factory() as session:
        with pytest.raises(JournalError) as exc:
            async with session.begin():
                await post_journal(
                    session,
                    business_event_type="PRECISION_TEST",
                    business_event_id="event-precision",
                    legal_entity_id=uuid4(),
                    currency="IRR",
                    idempotency_key="precision",
                    actor_reference=uuid4(),
                    correlation_id=uuid4(),
                    lines=[
                        JournalLine(
                            account_code="1000.TEST",
                            economic_owner_type="PROGRAM",
                            debit_amount=Decimal("1.0000000000000000001"),
                        ),
                        JournalLine(
                            account_code="2000.TEST",
                            economic_owner_type="PROGRAM",
                            credit_amount=Decimal("1.0000000000000000001"),
                        ),
                    ],
                )
        assert exc.value.code == "JOURNAL_AMOUNT_PRECISION_INVALID"
    async with database.session_factory() as session:
        assert await _count(session, JournalEntry) == 0
        assert await _count(session, OutboxMessage) == 0
        assert await _count(session, AuditEvent) == 0


@pytest.mark.integration
async def test_finance_read_and_maker_checker_reversal_are_scoped_and_idempotent(
    settings: Settings,
    database,
    clean_sprint08_journal_tables,
) -> None:
    legal_entity_id = uuid4()
    finance, checker, auditor = await _seed_roles(database, legal_entity_id)
    entry_id = await _post_foundation_journal(database, legal_entity_id, finance.id)
    async with database.session_factory() as session:
        original = await session.get(JournalEntry, entry_id)
        assert original is not None
        reason = "reverse sprint08 test"
        approval = ApprovalRequest(
            action_type="JOURNAL_REVERSAL",
            target_type="JournalEntry",
            target_id=str(original.id),
            target_aggregate_version=None,
            maker_identity_id=finance.id,
            checker_identity_id=checker.id,
            required_checker_role=ROLE_GOVERNANCE_APPROVER,
            scope_type=SCOPE_LEGAL_ENTITY,
            scope_id=legal_entity_id,
            payload_hash=approval_payload_hash(
                journal_reversal_approval_payload(original, reason=reason)
            ),
            reason=reason,
            evidence_refs=[],
            status="APPROVED",
            approved_at=datetime.now(UTC),
            version=2,
        )
        async with session.begin():
            session.add(approval)
        approval_id = approval.id

    async with await _client(settings) as client:
        read = await client.get(
            f"/api/v1/finance/journals/{entry_id}",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
        )
        assert read.status_code == 200
        assert isinstance(read.json()["postings"][0]["debit_amount"], str)

        reverse = await client.post(
            f"/api/v1/finance/journals/{entry_id}/reverse",
            headers={
                "Authorization": f"Bearer {finance.external_subject}",
                "Idempotency-Key": "reverse-1",
            },
            json={"approval_request_id": str(approval_id), "reason": reason},
        )
        assert reverse.status_code == 200
        replay = await client.post(
            f"/api/v1/finance/journals/{entry_id}/reverse",
            headers={
                "Authorization": f"Bearer {finance.external_subject}",
                "Idempotency-Key": "reverse-1",
            },
            json={"approval_request_id": str(approval_id), "reason": reason},
        )
        assert replay.status_code == 200
        assert replay.json() == reverse.json()

        auditor_reverse = await client.post(
            f"/api/v1/finance/journals/{entry_id}/reverse",
            headers={
                "Authorization": f"Bearer {auditor.external_subject}",
                "Idempotency-Key": "auditor-reverse",
            },
            json={"approval_request_id": str(approval_id), "reason": reason},
        )
        assert auditor_reverse.status_code == 403

    reversal_id = reverse.json()["id"]
    async with database.session_factory() as session:
        original = await session.get(JournalEntry, entry_id)
        reversal = await session.get(JournalEntry, reversal_id)
        assert original is not None
        assert reversal is not None
        assert reversal.reversal_of_entry_id == original.id
        assert await _count(session, JournalEntry) == 2
        reversed_events = (
            await session.scalars(
                select(OutboxMessage).where(OutboxMessage.aggregate_id == str(reversal.id))
            )
        ).all()
        assert [event.event_type for event in reversed_events] == ["JournalReversed"]


@pytest.mark.integration
async def test_reversal_rejects_changed_approval_payload_without_side_effect(
    settings: Settings,
    database,
    clean_sprint08_journal_tables,
) -> None:
    legal_entity_id = uuid4()
    finance, checker, _ = await _seed_roles(database, legal_entity_id)
    entry_id = await _post_foundation_journal(database, legal_entity_id, finance.id, "changed")
    async with database.session_factory() as session:
        original = await session.get(JournalEntry, entry_id)
        assert original is not None
        approval = ApprovalRequest(
            action_type="JOURNAL_REVERSAL",
            target_type="JournalEntry",
            target_id=str(original.id),
            target_aggregate_version=None,
            maker_identity_id=finance.id,
            checker_identity_id=checker.id,
            required_checker_role=ROLE_GOVERNANCE_APPROVER,
            scope_type=SCOPE_LEGAL_ENTITY,
            scope_id=legal_entity_id,
            payload_hash=approval_payload_hash(
                journal_reversal_approval_payload(original, reason="approved reason")
            ),
            reason="approved reason",
            evidence_refs=[],
            status="APPROVED",
            approved_at=datetime.now(UTC),
            version=2,
        )
        async with session.begin():
            session.add(approval)
        approval_id = approval.id

    async with await _client(settings) as client:
        response = await client.post(
            f"/api/v1/finance/journals/{entry_id}/reverse",
            headers={
                "Authorization": f"Bearer {finance.external_subject}",
                "Idempotency-Key": "changed-reason",
            },
            json={"approval_request_id": str(approval_id), "reason": "different reason"},
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "APPROVAL_PAYLOAD_CHANGED"
    async with database.session_factory() as session:
        assert await _count(session, JournalEntry) == 1
        events = (
            await session.scalars(
                select(OutboxMessage).where(OutboxMessage.event_type == "JournalReversed")
            )
        ).all()
        assert events == []


def test_sprint08_openapi_has_finance_read_reversal_and_no_generic_create(
    settings: Settings,
) -> None:
    schema = create_app(settings).openapi()
    assert "get" in schema["paths"]["/api/v1/finance/journals"]
    assert "post" not in schema["paths"]["/api/v1/finance/journals"]
    reversal = schema["paths"]["/api/v1/finance/journals/{entry_id}/reverse"]["post"]
    assert "FINANCE_RECONCILIATION" in reversal["description"]
    assert "GOVERNANCE_APPROVER" in reversal["description"]
    assert any(
        parameter["name"] == "Idempotency-Key" and parameter["in"] == "header"
        for parameter in reversal["parameters"]
    )
