from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    AuditEvent,
    Identity,
    ParticipationEpisode,
    Program,
    RoleGrant,
)
from badban.security.auth import AuthenticationError, TokenPrincipal


class StubAuthenticator:
    async def authenticate(self, token: str) -> TokenPrincipal:
        if token not in {"ops", "governance", "auditor", "nogrant"}:
            raise AuthenticationError("invalid test token")
        return TokenPrincipal(subject=f"{token}-subject", claims={"sub": f"{token}-subject"})


async def seed_identity(database, subject: str, identity_type: str = "STAFF") -> Identity:
    identity = Identity(external_subject=subject, identity_type=identity_type, status="ACTIVE")
    async with database.session_factory() as session:
        session.add(identity)
        await session.commit()
        await session.refresh(identity)
    return identity


async def seed_grant(
    database,
    identity: Identity,
    role_code: str,
    scope_type: str,
    scope_id: str,
    *,
    status: str = "ACTIVE",
    valid_until: datetime | None = None,
) -> RoleGrant:
    grant = RoleGrant(
        identity_id=identity.id,
        role_code=role_code,
        scope_type=scope_type,
        scope_id=scope_id,
        status=status,
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
        valid_until=valid_until,
    )
    async with database.session_factory() as session:
        session.add(grant)
        await session.commit()
        await session.refresh(grant)
    return grant


def client_for(settings) -> AsyncClient:
    app = create_app(settings, authenticator=StubAuthenticator())
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.integration
async def test_program_creation_is_scoped_and_audited(
    settings, database, clean_sprint02_tables
) -> None:
    ops = await seed_identity(database, "ops-subject")
    await seed_grant(database, ops, "OPERATIONS", "SYSTEM", "badban")

    async with client_for(settings) as client:
        response = await client.post(
            "/api/v1/programs",
            headers={"Authorization": "Bearer ops", "Idempotency-Key": "program-1"},
            json={"code": "PILOT-A", "name": "Pilot A"},
        )

    assert response.status_code == 201
    assert response.json()["code"] == "PILOT-A"

    async with database.session_factory() as session:
        audit = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "program:create",
                AuditEvent.outcome == "SUCCEEDED",
            )
        )
    assert audit is not None
    assert audit.actor_identity_id == ops.id


@pytest.mark.integration
async def test_no_grant_denies_write_and_records_denial(
    settings, database, clean_sprint02_tables
) -> None:
    identity = await seed_identity(database, "nogrant-subject")

    async with client_for(settings) as client:
        response = await client.post(
            "/api/v1/programs",
            headers={"Authorization": "Bearer nogrant", "Idempotency-Key": "denied-1"},
            json={"code": "DENIED", "name": "Denied"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "AUTHORIZATION_DENIED"

    async with database.session_factory() as session:
        programs = await session.scalar(select(func.count()).select_from(Program))
        denied = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.actor_identity_id == identity.id,
                AuditEvent.outcome == "DENIED",
            )
        )
    assert programs == 0
    assert denied is not None


@pytest.mark.integration
async def test_expired_grant_is_denied(settings, database, clean_sprint02_tables) -> None:
    ops = await seed_identity(database, "ops-subject")
    await seed_grant(
        database,
        ops,
        "OPERATIONS",
        "SYSTEM",
        "badban",
        valid_until=datetime.now(UTC) - timedelta(seconds=1),
    )

    async with client_for(settings) as client:
        response = await client.post(
            "/api/v1/programs",
            headers={"Authorization": "Bearer ops", "Idempotency-Key": "expired-1"},
            json={"code": "EXPIRED", "name": "Expired"},
        )

    assert response.status_code == 403


@pytest.mark.integration
async def test_configurable_asset_type_is_not_gold_hardcoded(
    settings, database, clean_sprint02_tables
) -> None:
    governance = await seed_identity(database, "governance-subject")
    await seed_grant(database, governance, "GOVERNANCE_APPROVER", "SYSTEM", "badban")

    async with client_for(settings) as client:
        response = await client.post(
            "/api/v1/asset-types",
            headers={"Authorization": "Bearer governance", "Idempotency-Key": "asset-type-1"},
            json={
                "code": "FIXED_INCOME_UNIT",
                "name": "Fixed Income Unit",
                "unit": "unit",
                "precision_scale": 6,
                "valuation_source_ref": "valuation-source:fixed-income",
                "eligibility_metadata": {"pilot_eligible": True},
                "custody_metadata": {"mode": "external"},
                "status": "APPROVED",
            },
        )

    assert response.status_code == 201
    assert response.json()["code"] == "FIXED_INCOME_UNIT"
    assert response.json()["unit"] == "unit"


@pytest.mark.integration
async def test_auditor_read_does_not_imply_write(
    settings, database, clean_sprint02_tables
) -> None:
    auditor = await seed_identity(database, "auditor-subject", "AUDITOR")
    await seed_grant(database, auditor, "AUDITOR", "SYSTEM", "badban")

    async with client_for(settings) as client:
        response = await client.post(
            "/api/v1/asset-types",
            headers={"Authorization": "Bearer auditor", "Idempotency-Key": "audit-write"},
            json={
                "code": "SHOULD_FAIL",
                "name": "Should Fail",
                "unit": "unit",
                "precision_scale": 2,
            },
        )

    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.parametrize("ownership_class", ["PARTICIPANT_OWNED", "PROGRAM_ATTRIBUTED"])
async def test_asset_position_exact_quantity_ownership_and_idempotency(
    settings,
    database,
    clean_sprint02_tables,
    ownership_class: str,
) -> None:
    ops = await seed_identity(database, "ops-subject")
    program_id = uuid4()
    async with database.session_factory() as session:
        program = Program(
            id=program_id,
            code="PROGRAM-1",
            name="Program 1",
            created_by=ops.id,
        )
        asset_type = AssetType(
            code="GENERIC_ASSET",
            name="Generic Asset",
            unit="unit",
            precision_scale=18,
            status="APPROVED",
            eligibility_metadata={},
            custody_metadata={},
            created_by=ops.id,
        )
        session.add_all([program, asset_type])
        await session.flush()
        episode = ParticipationEpisode(
            program_id=program.id,
            participant_ref="participant-opaque-1",
            created_by=ops.id,
        )
        session.add(episode)
        await session.commit()
        await session.refresh(asset_type)
        await session.refresh(episode)

    await seed_grant(database, ops, "OPERATIONS", "PROGRAM", str(program_id))
    quantity = "123.456789012345678901"
    payload = {
        "program_id": str(program_id),
        "participation_episode_id": str(episode.id),
        "asset_type_id": str(asset_type.id),
        "quantity": quantity,
        "ownership_class": ownership_class,
        "owner_ref": "owner:opaque",
        "custody_ref": "custody:opaque",
    }
    key = f"position-{ownership_class}"

    async with client_for(settings) as client:
        first = await client.post(
            "/api/v1/asset-positions",
            headers={"Authorization": "Bearer ops", "Idempotency-Key": key},
            json=payload,
        )
        second = await client.post(
            "/api/v1/asset-positions",
            headers={"Authorization": "Bearer ops", "Idempotency-Key": key},
            json=payload,
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["ownership_class"] == ownership_class
    assert Decimal(first.json()["quantity"]) == Decimal(quantity)

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(AssetPosition))
        stored = await session.scalar(select(AssetPosition))
    assert count == 1
    assert stored is not None
    assert stored.quantity == Decimal(quantity)


@pytest.mark.integration
async def test_inactive_asset_type_cannot_create_position(
    settings, database, clean_sprint02_tables
) -> None:
    ops = await seed_identity(database, "ops-subject")
    program_id = uuid4()
    async with database.session_factory() as session:
        program = Program(id=program_id, code="P2", name="P2", created_by=ops.id)
        asset_type = AssetType(
            code="INACTIVE_ASSET",
            name="Inactive",
            unit="unit",
            precision_scale=2,
            status="INACTIVE",
            eligibility_metadata={},
            custody_metadata={},
            created_by=ops.id,
        )
        session.add_all([program, asset_type])
        await session.flush()
        episode = ParticipationEpisode(
            program_id=program.id,
            participant_ref="participant-2",
            created_by=ops.id,
        )
        session.add(episode)
        await session.commit()
        await session.refresh(asset_type)
        await session.refresh(episode)

    await seed_grant(database, ops, "OPERATIONS", "PROGRAM", str(program_id))

    async with client_for(settings) as client:
        response = await client.post(
            "/api/v1/asset-positions",
            headers={"Authorization": "Bearer ops", "Idempotency-Key": "inactive-position"},
            json={
                "program_id": str(program_id),
                "participation_episode_id": str(episode.id),
                "asset_type_id": str(asset_type.id),
                "quantity": "1.00",
                "ownership_class": "PARTICIPANT_OWNED",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSET_TYPE_NOT_ACTIVE"


@pytest.mark.integration
async def test_cross_program_scope_is_denied(
    settings, database, clean_sprint02_tables
) -> None:
    ops = await seed_identity(database, "ops-subject")
    allowed_program = uuid4()
    other_program = uuid4()
    async with database.session_factory() as session:
        session.add_all(
            [
                Program(id=allowed_program, code="ALLOWED", name="Allowed", created_by=ops.id),
                Program(id=other_program, code="OTHER", name="Other", created_by=ops.id),
            ]
        )
        await session.commit()
    await seed_grant(database, ops, "OPERATIONS", "PROGRAM", str(allowed_program))

    async with client_for(settings) as client:
        response = await client.get(
            f"/api/v1/programs/{other_program}",
            headers={"Authorization": "Bearer ops"},
        )

    assert response.status_code == 403


@pytest.mark.integration
async def test_audit_events_are_database_append_only(
    database, clean_sprint02_tables
) -> None:
    identity = await seed_identity(database, "ops-subject")
    audit_id = uuid4()
    async with database.session_factory() as session:
        session.add(
            AuditEvent(
                id=audit_id,
                actor_identity_id=identity.id,
                action="test",
                target_type="Test",
                target_id="1",
                outcome="SUCCEEDED",
                evidence_refs=["evidence:opaque:1"],
            )
        )
        await session.commit()

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE audit_events SET outcome='CHANGED' WHERE id=:id"),
                {"id": audit_id},
            )
            await session.commit()
        await session.rollback()

    async with database.session_factory() as session:
        row = await session.get(AuditEvent, audit_id)
    assert row is not None
    assert row.outcome == "SUCCEEDED"
    assert row.evidence_refs == ["evidence:opaque:1"]


@pytest.mark.integration
async def test_invalid_bearer_token_is_rejected(
    settings, database, clean_sprint02_tables
) -> None:
    await seed_identity(database, "ops-subject")

    async with client_for(settings) as client:
        response = await client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer invalid"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"
