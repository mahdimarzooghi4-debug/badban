from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AuditEvent,
    Identity,
    Participant,
    Program,
    RoleGrant,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _seed_identity(
    database,
    *,
    subject: str,
    identity_type: str,
    role: str,
    scope_type: str = "GLOBAL",
    scope_id: UUID | None = None,
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
                    scope_type=scope_type,
                    scope_id=scope_id,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="test-fixture",
                )
            )
    return identity


def _headers(subject: str, key: str | None = None) -> dict[str, str]:
    result = {"Authorization": f"Bearer {subject}"}
    if key is not None:
        result["Idempotency-Key"] = key
    return result


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.integration
async def test_identity_scoped_program_asset_journey(
    settings: Settings,
    database,
    clean_sprint02_tables,
) -> None:
    governance = await _seed_identity(
        database,
        subject="governance-1",
        identity_type="GOVERNANCE",
        role="GOVERNANCE_APPROVER",
    )
    operator = await _seed_identity(
        database,
        subject="operator-1",
        identity_type="STAFF",
        role="OPERATIONS",
    )
    await _seed_identity(
        database,
        subject="auditor-1",
        identity_type="AUDITOR",
        role="AUDITOR",
    )

    async with await _client(settings) as client:
        me = await client.get("/api/v1/me", headers=_headers("operator-1"))
        assert me.status_code == 200
        assert me.json()["identity_id"] == str(operator.id)

        program_response = await client.post(
            "/api/v1/programs",
            headers=_headers("governance-1", "program-1"),
            json={"code": "PILOT-A", "name": "Pilot A", "status": "ACTIVE"},
        )
        assert program_response.status_code == 201
        program_id = UUID(program_response.json()["id"])

        participant_response = await client.post(
            "/api/v1/participants",
            headers=_headers("operator-1", "participant-1"),
            json={"external_reference": "participant-ext-1"},
        )
        assert participant_response.status_code == 201
        participant_id = UUID(participant_response.json()["id"])

        episode_response = await client.post(
            f"/api/v1/programs/{program_id}/participation-episodes",
            headers=_headers("operator-1", "episode-1"),
            json={
                "participant_id": str(participant_id),
                "eligibility_reference": "eligibility-ref-1",
                "consent_state": "RECORDED",
            },
        )
        assert episode_response.status_code == 201
        episode_id = UUID(episode_response.json()["id"])

        asset_type_response = await client.post(
            "/api/v1/asset-types",
            headers=_headers("governance-1", "asset-type-1"),
            json={
                "asset_code": "BOND_UNIT",
                "name": "Bond Unit",
                "status": "ACTIVE",
                "unit_code": "UNIT",
                "quantity_scale": 8,
                "currency_or_valuation_currency": "IRR",
                "valuation_source_reference": "approved-source-ref",
                "eligibility_metadata": {"pilot": True},
                "custody_restriction_metadata": {"requires_custody": True},
            },
        )
        assert asset_type_response.status_code == 201
        asset_type_id = UUID(asset_type_response.json()["id"])
        assert asset_type_response.json()["asset_code"] != "GOLD"

        position_response = await client.post(
            "/api/v1/asset-positions",
            headers=_headers("operator-1", "position-owned-1"),
            json={
                "participation_episode_id": str(episode_id),
                "asset_type_id": str(asset_type_id),
                "ownership_funding_type": "PARTICIPANT_OWNED",
                "legal_owner_participant_id": str(participant_id),
                "quantity": "123.12345678",
                "unit_code": "UNIT",
                "source_reference": "source-1",
                "evidence_reference": "evidence://opaque/1",
            },
        )
        assert position_response.status_code == 201
        assert position_response.json()["quantity"] == "123.123456780000000000"
        assert "market_value" not in position_response.json()
        assert "guarantee_capacity" not in position_response.json()

        replay = await client.post(
            "/api/v1/asset-positions",
            headers=_headers("operator-1", "position-owned-1"),
            json={
                "participation_episode_id": str(episode_id),
                "asset_type_id": str(asset_type_id),
                "ownership_funding_type": "PARTICIPANT_OWNED",
                "legal_owner_participant_id": str(participant_id),
                "quantity": "123.12345678",
                "unit_code": "UNIT",
                "source_reference": "source-1",
                "evidence_reference": "evidence://opaque/1",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == position_response.json()["id"]

        program_owner_id = uuid4()
        attributed = await client.post(
            "/api/v1/asset-positions",
            headers=_headers("operator-1", "position-program-1"),
            json={
                "participation_episode_id": str(episode_id),
                "asset_type_id": str(asset_type_id),
                "ownership_funding_type": "PROGRAM_ATTRIBUTED",
                "legal_owner_entity_id": str(program_owner_id),
                "quantity": "10.5",
                "unit_code": "UNIT",
                "source_reference": "program-source",
            },
        )
        assert attributed.status_code == 201
        assert attributed.json()["ownership_funding_type"] == "PROGRAM_ATTRIBUTED"

        auditor_write = await client.post(
            "/api/v1/asset-positions",
            headers=_headers("auditor-1", "auditor-write"),
            json={
                "participation_episode_id": str(episode_id),
                "asset_type_id": str(asset_type_id),
                "ownership_funding_type": "PARTICIPANT_OWNED",
                "legal_owner_participant_id": str(participant_id),
                "quantity": "1",
                "unit_code": "UNIT",
            },
        )
        assert auditor_write.status_code == 403

    async with database.session_factory() as session:
        positions = (await session.scalars(select(AssetPosition))).all()
        assert len(positions) == 2
        success_audits = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "ASSET_POSITION_CREATE",
                    AuditEvent.outcome == "SUCCESS",
                )
            )
        ).all()
        assert len(success_audits) == 2
        assert all(event.actor_id == operator.id for event in success_audits)
        assert any(event.evidence_reference == "evidence://opaque/1" for event in success_audits)
        assert all("Bearer" not in str(event.new_state) for event in success_audits)
        assert all("token" not in str(event.new_state).lower() for event in success_audits)

        program = await session.get(Program, program_id)
        assert program is not None
        assert program.created_by == governance.id


@pytest.mark.integration
async def test_cross_program_scope_is_denied_and_audited(
    settings: Settings,
    database,
    clean_sprint02_tables,
) -> None:
    program_a = Program(
        code="A",
        name="A",
        status="ACTIVE",
        created_by=uuid4(),
    )
    program_b = Program(
        code="B",
        name="B",
        status="ACTIVE",
        created_by=uuid4(),
    )
    participant = Participant(external_reference="p-cross", lifecycle_status="ACTIVE")
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([program_a, program_b, participant])
            await session.flush()

    identity = await _seed_identity(
        database,
        subject="operator-scoped",
        identity_type="STAFF",
        role="OPERATIONS",
        scope_type="PROGRAM",
        scope_id=program_a.id,
    )

    async with await _client(settings) as client:
        denied = await client.post(
            f"/api/v1/programs/{program_b.id}/participation-episodes",
            headers=_headers("operator-scoped", "wrong-program"),
            json={
                "participant_id": str(participant.id),
                "consent_state": "RECORDED",
            },
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "AUTHORIZATION_DENIED"

    async with database.session_factory() as session:
        denied_audit = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.actor_id == identity.id,
                AuditEvent.action == "PARTICIPATION_EPISODE_CREATE",
                AuditEvent.outcome == "DENIED",
            )
        )
        assert denied_audit is not None
        assert denied_audit.reason_code == "AUTHORIZATION_DENIED"


@pytest.mark.integration
async def test_service_identity_cannot_use_human_operations(
    settings: Settings,
    database,
    clean_sprint02_tables,
) -> None:
    await _seed_identity(
        database,
        subject="service-1",
        identity_type="SERVICE",
        role="OPERATIONS",
    )
    async with await _client(settings) as client:
        denied = await client.post(
            "/api/v1/participants",
            headers=_headers("service-1", "service-participant"),
            json={"external_reference": "should-not-create"},
        )
        assert denied.status_code == 403

    async with database.session_factory() as session:
        participant = await session.scalar(
            select(Participant).where(Participant.external_reference == "should-not-create")
        )
        assert participant is None


@pytest.mark.integration
async def test_inactive_asset_type_and_excess_scale_are_rejected(
    settings: Settings,
    database,
    clean_sprint02_tables,
) -> None:
    await _seed_identity(
        database,
        subject="governance-2",
        identity_type="GOVERNANCE",
        role="GOVERNANCE_APPROVER",
    )
    await _seed_identity(
        database,
        subject="operator-2",
        identity_type="STAFF",
        role="OPERATIONS",
    )
    async with await _client(settings) as client:
        program = await client.post(
            "/api/v1/programs",
            headers=_headers("governance-2", "p2"),
            json={"code": "P2", "name": "P2", "status": "ACTIVE"},
        )
        participant = await client.post(
            "/api/v1/participants",
            headers=_headers("operator-2", "person2"),
            json={"external_reference": "person-2"},
        )
        episode = await client.post(
            f"/api/v1/programs/{program.json()['id']}/participation-episodes",
            headers=_headers("operator-2", "ep2"),
            json={
                "participant_id": participant.json()["id"],
                "consent_state": "RECORDED",
            },
        )
        inactive_type = await client.post(
            "/api/v1/asset-types",
            headers=_headers("governance-2", "type-inactive"),
            json={
                "asset_code": "CASHLIKE",
                "name": "Cash Like",
                "status": "DRAFT",
                "unit_code": "UNIT",
                "quantity_scale": 2,
            },
        )
        rejected = await client.post(
            "/api/v1/asset-positions",
            headers=_headers("operator-2", "inactive-position"),
            json={
                "participation_episode_id": episode.json()["id"],
                "asset_type_id": inactive_type.json()["id"],
                "ownership_funding_type": "PARTICIPANT_OWNED",
                "legal_owner_participant_id": participant.json()["id"],
                "quantity": "1.00",
                "unit_code": "UNIT",
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "ASSET_TYPE_NOT_ACTIVE"

        active_type = await client.post(
            "/api/v1/asset-types",
            headers=_headers("governance-2", "type-active"),
            json={
                "asset_code": "FUND",
                "name": "Fund",
                "status": "ACTIVE",
                "unit_code": "UNIT",
                "quantity_scale": 2,
            },
        )
        precision_rejected = await client.post(
            "/api/v1/asset-positions",
            headers=_headers("operator-2", "precision-position"),
            json={
                "participation_episode_id": episode.json()["id"],
                "asset_type_id": active_type.json()["id"],
                "ownership_funding_type": "PARTICIPANT_OWNED",
                "legal_owner_participant_id": participant.json()["id"],
                "quantity": "1.001",
                "unit_code": "UNIT",
            },
        )
        assert precision_rejected.status_code == 422
        assert precision_rejected.json()["error"]["code"] == "ASSET_QUANTITY_SCALE_INVALID"


@pytest.mark.integration
async def test_audit_events_are_database_append_only(database, clean_sprint02_tables) -> None:
    actor_id = uuid4()
    event = AuditEvent(
        aggregate_type="Probe",
        aggregate_id="probe-1",
        aggregate_version=1,
        action="PROBE",
        actor_type="STAFF",
        actor_id=actor_id,
        correlation_id=uuid4(),
        outcome="SUCCESS",
        occurred_at=datetime.now(UTC),
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(event)
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(AuditEvent).where(AuditEvent.id == event.id).values(outcome="MUTATED")
                )
