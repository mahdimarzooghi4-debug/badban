from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from badban.api.app import create_app
from badban.config import Settings
from badban.infrastructure.persistence.models import Identity, RoleGrant
from badban.security.audit import append_audit
from badban.security.authorization import ROLE_AUDITOR, SCOPE_GLOBAL, SCOPE_PROGRAM


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {subject}"}


async def _seed(database) -> dict:
    program_a, program_b = uuid4(), uuid4()
    correlation = uuid4()
    seeded: dict = {"a": program_a, "b": program_b, "correlation": correlation}
    async with database.session_factory() as session:
        async with session.begin():
            identities = [
                ("audit-scoped", "AUDITOR", ROLE_AUDITOR, SCOPE_PROGRAM, program_a),
                ("audit-global", "AUDITOR", ROLE_AUDITOR, SCOPE_GLOBAL, None),
                ("audit-ops", "STAFF", "OPERATIONS", SCOPE_PROGRAM, program_a),
                ("audit-service", "SERVICE", ROLE_AUDITOR, SCOPE_GLOBAL, None),
                ("audit-revoked", "AUDITOR", ROLE_AUDITOR, SCOPE_PROGRAM, program_a),
            ]
            for subject, identity_type, role, scope_type, scope_id in identities:
                identity = Identity(
                    identity_type=identity_type,
                    external_subject=subject,
                    status="ACTIVE",
                )
                session.add(identity)
                await session.flush()
                session.add(
                    RoleGrant(
                        identity_id=identity.id,
                        role_code=role,
                        scope_type=scope_type,
                        scope_id=scope_id,
                        valid_from=datetime.now(UTC) - timedelta(minutes=5),
                        status="REVOKED" if subject == "audit-revoked" else "ACTIVE",
                        granted_by=None,
                        reason_ref="audit-test",
                    )
                )
            for index in range(4):
                event = append_audit(
                    session,
                    aggregate_type="GuaranteeCase" if index < 3 else "JournalEntry",
                    aggregate_id="case-1" if index < 3 else "journal-1",
                    aggregate_version=index + 1,
                    action="CASE_OBSERVED" if index < 3 else "JOURNAL_OBSERVED",
                    actor_type="STAFF",
                    actor_id=uuid4(),
                    correlation_id=correlation if index < 3 else uuid4(),
                    outcome="SUCCESS",
                    previous_state={"internal_customer": "DO_NOT_EXPOSE"},
                    new_state={"private_value": "DO_NOT_EXPOSE"},
                    scope={"scope_type": SCOPE_PROGRAM, "scope_id": str(program_a)},
                )
                await session.flush()
                seeded[f"a{index}"] = event.id

            foreign = append_audit(
                session,
                aggregate_type="GuaranteeCase",
                aggregate_id="case-1",
                aggregate_version=9,
                action="CASE_OBSERVED",
                actor_type="STAFF",
                actor_id=uuid4(),
                correlation_id=correlation,
                outcome="SUCCESS",
                scope={"scope_type": SCOPE_PROGRAM, "scope_id": str(program_b)},
            )
            global_event = append_audit(
                session,
                aggregate_type="GuaranteeCase",
                aggregate_id="case-1",
                aggregate_version=10,
                action="CASE_OBSERVED",
                actor_type="STAFF",
                actor_id=uuid4(),
                correlation_id=correlation,
                outcome="SUCCESS",
                scope={"scope_type": SCOPE_GLOBAL},
            )
            unscoped = append_audit(
                session,
                aggregate_type="GuaranteeCase",
                aggregate_id="case-1",
                aggregate_version=11,
                action="CASE_OBSERVED",
                actor_type="STAFF",
                actor_id=uuid4(),
                correlation_id=correlation,
                outcome="SUCCESS",
            )
            await session.flush()
            seeded["foreign"] = foreign.id
            seeded["global_event"] = global_event.id
            seeded["unscoped"] = unscoped.id
    return seeded


def test_audit_api_openapi_is_read_only_and_metadata_only(settings: Settings) -> None:
    schema = create_app(settings).openapi()
    for path in (
        "/api/v1/audit/events",
        "/api/v1/audit/aggregates/{aggregate_type}/{aggregate_id}",
    ):
        assert set(schema["paths"][path]) == {"get"}
        assert {"401", "403", "422"}.issubset(schema["paths"][path]["get"]["responses"])
        assert "AUDITOR" in schema["paths"][path]["get"]["description"]
    fields = schema["components"]["schemas"]["AuditEventMetadata"]["properties"]
    assert "previous_state" not in fields
    assert "new_state" not in fields
    assert "scope" not in fields
    assert {"correlation_id", "actor_id", "outcome", "occurred_at"} <= fields.keys()


@pytest.mark.integration
async def test_program_scope_keyset_filters_and_payload_suppression(
    settings: Settings, database, clean_sprint02_tables
) -> None:
    ids = await _seed(database)
    url = f"/api/v1/audit/events?program_id={ids['a']}&limit=2"
    async with await _client(settings) as client:
        first = await client.get(url, headers=_headers("audit-scoped"))
        assert first.status_code == 200
        assert len(first.json()["items"]) == 2
        cursor = first.json()["next_cursor"]
        assert cursor is not None
        second = await client.get(url + f"&after={cursor}", headers=_headers("audit-scoped"))
        assert second.status_code == 200
        assert len(second.json()["items"]) == 2
        assert second.json()["next_cursor"] is None

        rows = first.json()["items"] + second.json()["items"]
        assert {row["id"] for row in rows} == {str(ids[f"a{i}"]) for i in range(4)}
        assert all("previous_state" not in row and "new_state" not in row for row in rows)
        assert "DO_NOT_EXPOSE" not in str(rows)
        assert all("scope" not in row for row in rows)

        wrong_cursor = await client.get(
            url + f"&after={ids['foreign']}", headers=_headers("audit-scoped")
        )
        assert wrong_cursor.status_code == 422
        assert wrong_cursor.json()["error"]["code"] == "AUDIT_CURSOR_INVALID"
        wrong_filter = await client.get(
            url + f"&action=JOURNAL_OBSERVED&after={ids['a0']}",
            headers=_headers("audit-scoped"),
        )
        assert wrong_filter.status_code == 422
        assert wrong_filter.json()["error"]["code"] == "AUDIT_CURSOR_INVALID"

        correlated = await client.get(
            f"/api/v1/audit/events?program_id={ids['a']}"
            f"&correlation={ids['correlation']}&aggregate_type=GuaranteeCase",
            headers=_headers("audit-scoped"),
        )
        assert correlated.status_code == 200
        assert len(correlated.json()["items"]) == 3

        aggregate = await client.get(
            f"/api/v1/audit/aggregates/GuaranteeCase/case-1?program_id={ids['a']}",
            headers=_headers("audit-scoped"),
        )
        assert aggregate.status_code == 200
        assert {item["id"] for item in aggregate.json()["items"]} == {
            str(ids[f"a{i}"]) for i in range(3)
        }

        aggregate_cursor = await client.get(
            f"/api/v1/audit/aggregates/GuaranteeCase/case-1?program_id={ids['a']}"
            f"&after={ids['a3']}",
            headers=_headers("audit-scoped"),
        )
        assert aggregate_cursor.status_code == 422


@pytest.mark.integration
async def test_global_auditor_needs_exact_role_and_explicit_program_filter(
    settings: Settings, database, clean_sprint02_tables
) -> None:
    ids = await _seed(database)
    async with await _client(settings) as client:
        scoped_global = await client.get("/api/v1/audit/events", headers=_headers("audit-scoped"))
        assert scoped_global.status_code == 403

        global_view = await client.get(
            "/api/v1/audit/events?limit=20", headers=_headers("audit-global")
        )
        assert global_view.status_code == 200
        seen = {row["id"] for row in global_view.json()["items"]}
        assert str(ids["foreign"]) in seen
        assert str(ids["global_event"]) in seen
        assert str(ids["unscoped"]) in seen

        scoped_other = await client.get(
            f"/api/v1/audit/events?program_id={ids['b']}",
            headers=_headers("audit-scoped"),
        )
        assert scoped_other.status_code == 403
        for subject in ("audit-ops", "audit-service", "audit-revoked"):
            rejected = await client.get(
                f"/api/v1/audit/events?program_id={ids['a']}",
                headers=_headers(subject),
            )
            assert rejected.status_code == 403
        no_token = await client.get(f"/api/v1/audit/events?program_id={ids['a']}")
        assert no_token.status_code == 401

    # Revocation takes effect on the next query; a previously issued token
    # must not be enough to preserve read permission.
    async with database.session_factory() as session:
        grant = await session.scalar(
            select(RoleGrant)
            .join(Identity, Identity.id == RoleGrant.identity_id)
            .where(Identity.external_subject == "audit-scoped")
        )
        assert grant is not None
        async with session.begin_nested():
            await session.execute(
                update(RoleGrant).where(RoleGrant.id == grant.id).values(status="REVOKED")
            )
        await session.commit()
    async with await _client(settings) as client:
        after_revocation = await client.get(
            f"/api/v1/audit/events?program_id={ids['a']}",
            headers=_headers("audit-scoped"),
        )
        assert after_revocation.status_code == 403
