from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from badban.api.app import create_app
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AuditEvent,
    GuaranteeCase,
    Identity,
    InboxMessage,
    JournalEntry,
    OutboxMessage,
    RoleGrant,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_OPERATIONS,
    ROLE_SYSTEM_OPERATOR,
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


def _headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {subject}"}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(database) -> dict:
    result: dict = {}
    program_id = uuid4()
    correlation_id = uuid4()
    start = datetime.now(UTC) - timedelta(minutes=5)
    async with database.session_factory() as session:
        async with session.begin():
            for subject, identity_type, role, scope, scope_id, state in (
                ("delivery-auditor", "AUDITOR", ROLE_AUDITOR, SCOPE_GLOBAL, None, "ACTIVE"),
                ("delivery-operator", "STAFF", ROLE_SYSTEM_OPERATOR, SCOPE_GLOBAL, None, "ACTIVE"),
                ("delivery-scoped", "AUDITOR", ROLE_AUDITOR, SCOPE_PROGRAM, program_id, "ACTIVE"),
                ("delivery-ops", "STAFF", ROLE_OPERATIONS, SCOPE_GLOBAL, None, "ACTIVE"),
                ("delivery-revoked", "AUDITOR", ROLE_AUDITOR, SCOPE_GLOBAL, None, "REVOKED"),
                ("delivery-service", "SERVICE", ROLE_AUDITOR, SCOPE_GLOBAL, None, "ACTIVE"),
            ):
                identity = Identity(
                    external_subject=subject, identity_type=identity_type, status="ACTIVE"
                )
                session.add(identity)
                await session.flush()
                session.add(
                    RoleGrant(
                        identity_id=identity.id,
                        role_code=role,
                        scope_type=scope,
                        scope_id=scope_id,
                        valid_from=start,
                        status=state,
                        reason_ref="delivery-fixture",
                    )
                )
            states = ("QUEUED", "RETRY_SCHEDULED", "DEAD_LETTERED", "PUBLISHED")
            for index, state in enumerate(states):
                event = OutboxMessage(
                    id=uuid4(),
                    event_type="JournalPosted" if index < 3 else "OtherEvent",
                    event_version=1,
                    aggregate_type="JournalEntry",
                    aggregate_id=f"journal-{index}",
                    aggregate_version=index + 1,
                    payload={"restricted": "DO_NOT_EXPOSE"},
                    correlation_id=correlation_id,
                    occurred_at=start + timedelta(seconds=index),
                    created_at=start + timedelta(seconds=index),
                    published_at=start if state == "PUBLISHED" else None,
                    next_attempt_at=(
                        datetime.now(UTC) + timedelta(hours=1)
                        if state == "RETRY_SCHEDULED"
                        else None
                    ),
                    dead_lettered_at=start if state == "DEAD_LETTERED" else None,
                    dead_letter_reason="DO_NOT_EXPOSE" if state == "DEAD_LETTERED" else None,
                    last_error="DO_NOT_EXPOSE",
                    publish_attempts=index,
                )
                session.add(event)
                result[state] = event.id
            for index, state in enumerate(("PENDING", "PROCESSED", "PENDING")):
                msg = InboxMessage(
                    id=uuid4(),
                    source_id="lender:one" if index < 2 else "lender:other",
                    event_type="LOAN_DISBURSED" if index < 2 else "LOAN_CORRECTED",
                    external_event_id=f"provider-{index}",
                    payload_hash="f" * 64,
                    payload={"restricted": "DO_NOT_EXPOSE"},
                    received_at=start + timedelta(seconds=index),
                    processed_at=start if state == "PROCESSED" else None,
                )
                session.add(msg)
                result[f"inbox-{index}"] = msg.id
    result["correlation"] = correlation_id
    return result


def test_delivery_openapi_is_read_only_and_payload_free(settings: Settings) -> None:
    schema = create_app(settings).openapi()
    for path in (
        "/api/v1/integration-delivery/outbox",
        "/api/v1/integration-delivery/inbox",
        "/api/v1/integration-delivery/outbox/{message_id}",
        "/api/v1/integration-delivery/inbox/{message_id}",
        "/api/v1/integration-delivery/summary",
    ):
        assert set(schema["paths"][path]) == {"get"}
        assert "GLOBAL" in schema["paths"][path]["get"]["description"]
        assert {"401", "403"}.issubset(schema["paths"][path]["get"]["responses"])
    for name in ("OutboxDeliveryView", "InboxDeliveryView"):
        props = schema["components"]["schemas"][name]["properties"]
        assert "payload" not in props
        assert "payload_hash" not in props
        assert "last_error" not in props
        assert "dead_letter_reason" not in props


@pytest.mark.integration
async def test_delivery_observations_paging_filters_and_summary(
    settings: Settings, database, clean_sprint11_event_tables
) -> None:
    ids = await _seed(database)
    before = []
    async with database.session_factory() as session:
        for model in (OutboxMessage, InboxMessage, GuaranteeCase, JournalEntry):
            before.append(int(await session.scalar(select(func.count()).select_from(model)) or 0))
    async with await _client(settings) as client:
        summary = await client.get(
            "/api/v1/integration-delivery/summary", headers=_headers("delivery-auditor")
        )
        assert summary.status_code == 200
        assert summary.json()["outbox"] == {
            "QUEUED": 1,
            "RETRY_SCHEDULED": 1,
            "DEAD_LETTERED": 1,
            "PUBLISHED": 1,
        }
        assert summary.json()["inbox"] == {"PENDING": 2, "PROCESSED": 1}

        first = await client.get(
            "/api/v1/integration-delivery/outbox?limit=2",
            headers=_headers("delivery-operator"),
        )
        assert first.status_code == 200
        assert len(first.json()["items"]) == 2
        cursor = first.json()["next_cursor"]
        assert cursor is not None
        second = await client.get(
            f"/api/v1/integration-delivery/outbox?limit=2&after={cursor}",
            headers=_headers("delivery-operator"),
        )
        assert second.status_code == 200
        assert len(second.json()["items"]) == 2
        assert second.json()["next_cursor"] is None
        rows = first.json()["items"] + second.json()["items"]
        assert {entry["id"] for entry in rows} == {
            str(ids[state]) for state in ("QUEUED", "RETRY_SCHEDULED", "DEAD_LETTERED", "PUBLISHED")
        }
        assert "DO_NOT_EXPOSE" not in str(rows)

        filtered = await client.get(
            "/api/v1/integration-delivery/outbox?status=DEAD_LETTERED&event_type=JournalPosted",
            headers=_headers("delivery-auditor"),
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()["items"]] == [str(ids["DEAD_LETTERED"]) ]
        wrong_cursor = await client.get(
            f"/api/v1/integration-delivery/outbox?status=DEAD_LETTERED&after={ids['QUEUED']}",
            headers=_headers("delivery-auditor"),
        )
        assert wrong_cursor.status_code == 422
        assert wrong_cursor.json()["error"]["code"] == "DELIVERY_CURSOR_INVALID"

        correlation = await client.get(
            f"/api/v1/integration-delivery/outbox?correlation_id={ids['correlation']}",
            headers=_headers("delivery-auditor"),
        )
        assert correlation.status_code == 200
        assert len(correlation.json()["items"]) == 4

        inbox = await client.get(
            "/api/v1/integration-delivery/inbox?source_id=lender:one&limit=1",
            headers=_headers("delivery-auditor"),
        )
        assert inbox.status_code == 200
        assert len(inbox.json()["items"]) == 1
        cursor = inbox.json()["next_cursor"]
        assert cursor is not None
        next_inbox = await client.get(
            f"/api/v1/integration-delivery/inbox?source_id=lender:one&limit=1&after={cursor}",
            headers=_headers("delivery-auditor"),
        )
        assert next_inbox.status_code == 200
        assert len(next_inbox.json()["items"]) == 1
        wrong_inbox = await client.get(
            f"/api/v1/integration-delivery/inbox?source_id=lender:one&after={ids['inbox-2']}",
            headers=_headers("delivery-auditor"),
        )
        assert wrong_inbox.status_code == 422
        assert wrong_inbox.json()["error"]["code"] == "DELIVERY_CURSOR_INVALID"
        pending = await client.get(
            "/api/v1/integration-delivery/inbox?status=PROCESSED",
            headers=_headers("delivery-auditor"),
        )
        assert pending.status_code == 200
        assert [entry["id"] for entry in pending.json()["items"]] == [str(ids["inbox-1"])]

        outbox_detail = await client.get(
            f"/api/v1/integration-delivery/outbox/{ids['RETRY_SCHEDULED']}",
            headers=_headers("delivery-auditor"),
        )
        assert outbox_detail.status_code == 200
        assert outbox_detail.json()["status"] == "RETRY_SCHEDULED"
        assert outbox_detail.json()["next_attempt_at"] is not None
        assert "DO_NOT_EXPOSE" not in outbox_detail.text
        inbox_detail = await client.get(
            f"/api/v1/integration-delivery/inbox/{ids['inbox-1']}",
            headers=_headers("delivery-auditor"),
        )
        assert inbox_detail.status_code == 200
        assert inbox_detail.json()["status"] == "PROCESSED"
        assert "DO_NOT_EXPOSE" not in inbox_detail.text

    async with database.session_factory() as session:
        after = []
        for model in (OutboxMessage, InboxMessage, GuaranteeCase, JournalEntry):
            after.append(int(await session.scalar(select(func.count()).select_from(model)) or 0))
    assert after == before


@pytest.mark.integration
async def test_delivery_security_and_missing_records(
    settings: Settings, database, clean_sprint11_event_tables
) -> None:
    ids = await _seed(database)
    async with await _client(settings) as client:
        for path in (
            "/api/v1/integration-delivery/summary",
            "/api/v1/integration-delivery/outbox",
            "/api/v1/integration-delivery/inbox",
            f"/api/v1/integration-delivery/outbox/{ids['QUEUED']}",
            f"/api/v1/integration-delivery/inbox/{ids['inbox-0']}",
        ):
            no_token = await client.get(path)
            assert no_token.status_code == 401
            for subject in (
                "delivery-scoped",
                "delivery-ops",
                "delivery-revoked",
                "delivery-service",
            ):
                denied = await client.get(path, headers=_headers(subject))
                assert denied.status_code == 403
                assert denied.json()["error"]["code"] == "AUTHORIZATION_DENIED"
        for subpath in ("outbox", "inbox"):
            missing = await client.get(
                f"/api/v1/integration-delivery/{subpath}/{uuid4()}",
                headers=_headers("delivery-auditor"),
            )
            assert missing.status_code == 404
    async with database.session_factory() as session:
        denied = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "INTEGRATION_DELIVERY_READ",
                AuditEvent.outcome == "DENIED",
            )
        )
    assert denied is not None and denied >= 1
