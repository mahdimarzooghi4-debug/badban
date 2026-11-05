from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from badban.api.app import create_app
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AuditEvent,
    Identity,
    LegalEntity,
    Program,
    RoleGrant,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {subject}"}


async def _identity(
    database,
    *,
    subject: str,
    identity_type: str = "STAFF",
    status: str = "ACTIVE",
    grants: list[tuple[str, str, UUID | None, datetime | None]] | None = None,
) -> Identity:
    identity = Identity(
        identity_type=identity_type,
        external_subject=subject,
        status=status,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(identity)
            await session.flush()
            for role_code, scope_type, scope_id, valid_from in grants or []:
                session.add(
                    RoleGrant(
                        identity_id=identity.id,
                        role_code=role_code,
                        scope_type=scope_type,
                        scope_id=scope_id,
                        valid_from=valid_from or datetime.now(UTC) - timedelta(minutes=1),
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=None,
                        reason_ref="sprint64-test",
                    )
                )
    return identity


async def _entity(
    database,
    *,
    created_by: UUID,
    name: str = "Reference Legal Entity",
) -> LegalEntity:
    entity = LegalEntity(
        legal_name=name,
        registration_identifier=f"REG-{uuid4()}",
        entity_type="NONPROFIT",
        status="ACTIVE",
        created_by=created_by,
        version=1,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(entity)
            await session.flush()
    return entity


@pytest.mark.integration
async def test_human_identity_directory_is_minimal_paged_and_audited(
    settings: Settings,
    database,
    clean_sprint64_directory_tables,
) -> None:
    governance = await _identity(
        database,
        subject="sprint64-governance",
        identity_type="GOVERNANCE",
        grants=[("GOVERNANCE_APPROVER", "GLOBAL", None, None)],
    )
    staff = await _identity(database, subject="sprint64-staff", identity_type="STAFF")
    auditor = await _identity(
        database,
        subject="sprint64-auditor",
        identity_type="AUDITOR",
        status="INACTIVE",
    )
    await _identity(database, subject="sprint64-participant", identity_type="PARTICIPANT")
    await _identity(database, subject="sprint64-service", identity_type="SERVICE")

    async with await _client(settings) as client:
        first = await client.get(
            "/api/v1/admin/directory/identities?limit=2&offset=0",
            headers=_headers("sprint64-governance"),
        )
        second = await client.get(
            "/api/v1/admin/directory/identities?limit=2&offset=2",
            headers=_headers("sprint64-governance"),
        )
        filtered = await client.get(
            "/api/v1/admin/directory/identities?identity_type=STAFF&limit=25&offset=0",
            headers=_headers("sprint64-governance"),
        )

    assert first.status_code == second.status_code == filtered.status_code == 200
    all_items = first.json()["items"] + second.json()["items"]
    assert {item["identity_id"] for item in all_items} == {
        str(governance.id),
        str(staff.id),
        str(auditor.id),
    }
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) == 1
    assert all(
        set(item) == {"identity_id", "identity_type", "status", "created_at"}
        for item in all_items
    )
    assert all("external_subject" not in item for item in all_items)
    assert all("national_id" not in item for item in all_items)
    assert filtered.json()["items"][0]["identity_id"] == str(staff.id)

    async with database.session_factory() as session:
        audits = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "ADMIN_HUMAN_IDENTITY_DIRECTORY_READ",
                    AuditEvent.actor_id == governance.id,
                    AuditEvent.outcome == "SUCCESS",
                )
            )
        ).all()
    assert len(audits) == 3


@pytest.mark.integration
async def test_identity_directory_requires_global_governance_not_scoped_or_expired(
    settings: Settings,
    database,
    clean_sprint64_directory_tables,
) -> None:
    await _identity(
        database,
        subject="sprint64-scoped",
        identity_type="GOVERNANCE",
        grants=[("GOVERNANCE_APPROVER", "PROGRAM", uuid4(), None)],
    )
    await _identity(database, subject="sprint64-no-grant")
    async with database.session_factory() as session:
        expired = Identity(
            identity_type="GOVERNANCE",
            external_subject="sprint64-expired",
            status="ACTIVE",
        )
        session.add(expired)
        await session.flush()
        session.add(
            RoleGrant(
                identity_id=expired.id,
                role_code="GOVERNANCE_APPROVER",
                scope_type="GLOBAL",
                scope_id=None,
                valid_from=datetime.now(UTC) - timedelta(days=2),
                valid_until=datetime.now(UTC) - timedelta(days=1),
                status="ACTIVE",
                reason_ref="expired",
            )
        )
        await session.commit()

    async with await _client(settings) as client:
        scoped = await client.get(
            "/api/v1/admin/directory/identities",
            headers=_headers("sprint64-scoped"),
        )
        absent = await client.get(
            "/api/v1/admin/directory/identities",
            headers=_headers("sprint64-no-grant"),
        )
        expired_response = await client.get(
            "/api/v1/admin/directory/identities",
            headers=_headers("sprint64-expired"),
        )

    assert scoped.status_code == 403
    assert absent.status_code == 403
    assert expired_response.status_code == 403


@pytest.mark.integration
async def test_legal_entity_directory_omits_registration_identifier(
    settings: Settings,
    database,
    clean_sprint64_directory_tables,
) -> None:
    legal = await _identity(
        database,
        subject="sprint64-legal",
        grants=[("LEGAL_COMPLIANCE", "GLOBAL", None, None)],
    )
    entity = await _entity(database, created_by=legal.id)

    async with await _client(settings) as client:
        response = await client.get(
            "/api/v1/admin/directory/legal-entities?limit=25&offset=0",
            headers=_headers("sprint64-legal"),
        )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["legal_entity_id"] == str(entity.id)
    assert item["legal_name"] == entity.legal_name
    assert set(item) == {
        "legal_entity_id",
        "legal_name",
        "entity_type",
        "status",
        "version",
        "created_at",
    }
    assert "registration_identifier" not in item
    assert "created_by" not in item


@pytest.mark.integration
async def test_program_directory_is_global_role_scoped_filtered_and_audited(
    settings: Settings,
    database,
    clean_sprint64_directory_tables,
) -> None:
    governance = await _identity(
        database,
        subject="sprint64-program-list",
        identity_type="GOVERNANCE",
        grants=[("GOVERNANCE_APPROVER", "GLOBAL", None, None)],
    )
    entity = await _entity(database, created_by=governance.id)
    active = Program(
        code="A-1",
        name="Active Program",
        status="ACTIVE",
        legal_entity_id=entity.id,
        created_by=governance.id,
    )
    inactive = Program(
        code="B-1",
        name="Inactive Program",
        status="INACTIVE",
        legal_entity_id=None,
        created_by=governance.id,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([active, inactive])
            await session.flush()

    async with await _client(settings) as client:
        response = await client.get(
            "/api/v1/admin/directory/programs?status=ACTIVE&limit=1&offset=0",
            headers=_headers("sprint64-program-list"),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["program_id"] == str(active.id)
    assert item["legal_entity_id"] == str(entity.id)
    assert set(item) == {
        "program_id",
        "code",
        "name",
        "status",
        "legal_entity_id",
        "version",
        "created_at",
    }
    assert "created_by" not in item

    async with database.session_factory() as session:
        audit = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "ADMIN_PROGRAM_DIRECTORY_READ",
                AuditEvent.actor_id == governance.id,
                AuditEvent.outcome == "SUCCESS",
            )
        )
    assert audit is not None


@pytest.mark.integration
async def test_directory_workspace_entries_match_exact_active_global_roles(
    settings: Settings,
    database,
    clean_sprint64_directory_tables,
) -> None:
    await _identity(
        database,
        subject="sprint64-index-governance",
        identity_type="GOVERNANCE",
        grants=[("GOVERNANCE_APPROVER", "GLOBAL", None, None)],
    )
    await _identity(
        database,
        subject="sprint64-index-legal",
        grants=[("LEGAL_COMPLIANCE", "GLOBAL", None, None)],
    )
    await _identity(
        database,
        subject="sprint64-index-auditor",
        identity_type="AUDITOR",
        grants=[("AUDITOR", "GLOBAL", None, None)],
    )
    await _identity(
        database,
        subject="sprint64-index-scoped",
        grants=[("LEGAL_COMPLIANCE", "LEGAL_ENTITY", uuid4(), None)],
    )

    async with await _client(settings) as client:
        results = {}
        for subject in (
            "sprint64-index-governance",
            "sprint64-index-legal",
            "sprint64-index-auditor",
            "sprint64-index-scoped",
        ):
            response = await client.get(
                "/api/v1/admin/workspace",
                headers=_headers(subject),
            )
            assert response.status_code == 200
            results[subject] = response.json()

    def has_workspace(body: dict, code: str) -> bool:
        return any(item["workspace_code"] == code for item in body["items"])

    governance = results["sprint64-index-governance"]
    legal = results["sprint64-index-legal"]
    auditor = results["sprint64-index-auditor"]
    scoped = results["sprint64-index-scoped"]

    assert has_workspace(governance, "ADMIN_HUMAN_IDENTITY_DIRECTORY")
    assert has_workspace(governance, "ADMIN_LEGAL_ENTITY_DIRECTORY")
    assert has_workspace(governance, "ADMIN_PROGRAM_DIRECTORY")
    assert not has_workspace(legal, "ADMIN_HUMAN_IDENTITY_DIRECTORY")
    assert has_workspace(legal, "ADMIN_LEGAL_ENTITY_DIRECTORY")
    assert not has_workspace(legal, "ADMIN_PROGRAM_DIRECTORY")
    assert not has_workspace(auditor, "ADMIN_HUMAN_IDENTITY_DIRECTORY")
    assert has_workspace(auditor, "ADMIN_LEGAL_ENTITY_DIRECTORY")
    assert has_workspace(auditor, "ADMIN_PROGRAM_DIRECTORY")
    assert not has_workspace(scoped, "ADMIN_LEGAL_ENTITY_DIRECTORY")
    assert not has_workspace(scoped, "ADMIN_PROGRAM_DIRECTORY")
