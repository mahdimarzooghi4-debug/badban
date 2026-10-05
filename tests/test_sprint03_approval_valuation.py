from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    Identity,
    JournalEntry,
    Participant,
    ParticipationEpisode,
    Program,
    RoleGrant,
    ValuationObservation,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


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
    headers = {"Authorization": f"Bearer {subject}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


async def _seed_asset_position(database, creator_id: UUID) -> AssetPosition:
    program = Program(
        code=f"P-{uuid4().hex[:8]}",
        name="Valuation Program",
        status="ACTIVE",
        created_by=creator_id,
    )
    participant = Participant(
        external_reference=f"participant-{uuid4()}",
        lifecycle_status="ACTIVE",
    )
    asset_type = AssetType(
        asset_code=f"ASSET-{uuid4().hex[:8]}",
        name="Configurable Non Gold Asset",
        status="ACTIVE",
        unit_code="UNIT",
        quantity_scale=8,
        currency_or_valuation_currency="IRR",
        valuation_source_reference="source:configured",
        eligibility_metadata={"pilot": True},
        custody_restriction_metadata={},
        created_by=creator_id,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([program, participant, asset_type])
            await session.flush()
            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                eligibility_reference="eligible:test",
                consent_state="RECORDED",
                started_at=datetime.now(UTC),
                created_by=creator_id,
            )
            session.add(episode)
            await session.flush()
            position = AssetPosition(
                participation_episode_id=episode.id,
                program_id=program.id,
                asset_type_id=asset_type.id,
                ownership_funding_type="PARTICIPANT_OWNED",
                legal_owner_entity_id=None,
                legal_owner_participant_id=participant.id,
                custodian_legal_entity_id=None,
                quantity=Decimal("250.12345678"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                source_reference="asset-source:test",
                created_by=creator_id,
            )
            session.add(position)
            await session.flush()
        await session.refresh(position)
    return position


@pytest.mark.integration
async def test_maker_checker_binds_payload_version_and_separation(
    settings: Settings,
    database,
    clean_sprint03_tables,
) -> None:
    maker = await _seed_identity(
        database,
        subject="maker",
        identity_type="STAFF",
        role="OPERATIONS",
    )
    await _seed_identity(
        database,
        subject="wrong-checker",
        identity_type="STAFF",
        role="RISK",
    )
    checker = await _seed_identity(
        database,
        subject="checker",
        identity_type="GOVERNANCE",
        role="GOVERNANCE_APPROVER",
    )
    payload = {"action": "future-policy-activation", "version": 7}

    async with await _client(settings) as client:
        created = await client.post(
            "/api/v1/approval-requests",
            headers=_headers("maker", "approval-1"),
            json={
                "action_type": "POLICY_ACTIVATION",
                "target_type": "PolicyPack",
                "target_id": "future-target",
                "target_aggregate_version": 3,
                "required_checker_role": "GOVERNANCE_APPROVER",
                "scope_type": "GLOBAL",
                "payload": payload,
                "reason": "foundation test",
            },
        )
        assert created.status_code == 201
        approval_id = created.json()["id"]
        assert created.json()["maker_identity_id"] == str(maker.id)
        assert created.json()["status"] == "PENDING"

        self_approval = await client.post(
            f"/api/v1/approval-requests/{approval_id}/approve",
            headers=_headers("maker"),
            json={},
        )
        assert self_approval.status_code == 403
        assert self_approval.json()["error"]["code"] == "APPROVAL_SELF_APPROVAL_FORBIDDEN"

        wrong_role = await client.post(
            f"/api/v1/approval-requests/{approval_id}/approve",
            headers=_headers("wrong-checker"),
            json={},
        )
        assert wrong_role.status_code == 403
        assert wrong_role.json()["error"]["code"] == "AUTHORIZATION_DENIED"

        approved = await client.post(
            f"/api/v1/approval-requests/{approval_id}/approve",
            headers=_headers("checker"),
            json={"reason": "checked"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED"
        assert approved.json()["checker_identity_id"] == str(checker.id)

        payload_changed = await client.post(
            f"/api/v1/approval-requests/{approval_id}/validate",
            headers=_headers("checker"),
            json={
                "payload": {"action": "future-policy-activation", "version": 8},
                "current_target_version": 3,
            },
        )
        assert payload_changed.status_code == 409
        assert payload_changed.json()["error"]["code"] == "APPROVAL_PAYLOAD_CHANGED"

        version_changed = await client.post(
            f"/api/v1/approval-requests/{approval_id}/validate",
            headers=_headers("checker"),
            json={"payload": payload, "current_target_version": 4},
        )
        assert version_changed.status_code == 409
        assert version_changed.json()["error"]["code"] == "APPROVAL_TARGET_VERSION_CONFLICT"

        valid = await client.post(
            f"/api/v1/approval-requests/{approval_id}/validate",
            headers=_headers("checker"),
            json={"payload": payload, "current_target_version": 3},
        )
        assert valid.status_code == 200
        assert valid.json()["eligible"] is True

    async with database.session_factory() as session:
        journal_count = await session.scalar(select(func.count()).select_from(JournalEntry))
    assert journal_count == 0


@pytest.mark.integration
async def test_expired_and_rejected_approvals_are_not_executable(
    settings: Settings,
    database,
    clean_sprint03_tables,
) -> None:
    await _seed_identity(
        database,
        subject="maker-expiry",
        identity_type="STAFF",
        role="OPERATIONS",
    )
    await _seed_identity(
        database,
        subject="checker-expiry",
        identity_type="GOVERNANCE",
        role="GOVERNANCE_APPROVER",
    )

    async with await _client(settings) as client:
        expired = await client.post(
            "/api/v1/approval-requests",
            headers=_headers("maker-expiry", "approval-expired"),
            json={
                "action_type": "TEST",
                "target_type": "Test",
                "target_id": "expired",
                "required_checker_role": "GOVERNANCE_APPROVER",
                "scope_type": "GLOBAL",
                "payload": {"x": 1},
                "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            },
        )
        expired_id = expired.json()["id"]
        expired_approval = await client.post(
            f"/api/v1/approval-requests/{expired_id}/approve",
            headers=_headers("checker-expiry"),
            json={},
        )
        assert expired_approval.status_code == 409
        assert expired_approval.json()["error"]["code"] == "APPROVAL_EXPIRED"

        rejected = await client.post(
            "/api/v1/approval-requests",
            headers=_headers("maker-expiry", "approval-rejected"),
            json={
                "action_type": "TEST",
                "target_type": "Test",
                "target_id": "rejected",
                "required_checker_role": "GOVERNANCE_APPROVER",
                "scope_type": "GLOBAL",
                "payload": {"x": 2},
            },
        )
        rejected_id = rejected.json()["id"]
        decision = await client.post(
            f"/api/v1/approval-requests/{rejected_id}/reject",
            headers=_headers("checker-expiry"),
            json={"reason": "not approved"},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "REJECTED"

        validate = await client.post(
            f"/api/v1/approval-requests/{rejected_id}/validate",
            headers=_headers("checker-expiry"),
            json={"payload": {"x": 2}, "current_target_version": None},
        )
        assert validate.status_code == 409
        assert validate.json()["error"]["code"] == "APPROVAL_NOT_APPROVED"


@pytest.mark.integration
async def test_valuation_is_exact_immutable_and_creates_no_journal(
    settings: Settings,
    database,
    clean_sprint03_tables,
) -> None:
    risk = await _seed_identity(
        database,
        subject="risk",
        identity_type="STAFF",
        role="RISK",
    )
    await _seed_identity(
        database,
        subject="ops-only",
        identity_type="STAFF",
        role="OPERATIONS",
    )
    position = await _seed_asset_position(database, risk.id)
    valid_until = datetime.now(UTC) + timedelta(hours=1)

    async with await _client(settings) as client:
        denied = await client.post(
            f"/api/v1/asset-positions/{position.id}/valuation-observations",
            headers=_headers("ops-only", "valuation-denied"),
            json={
                "valued_quantity": "2.00000000",
                "unit_price": "10.25",
                "valuation_currency": "IRR",
                "fx_rate": "3",
                "source_name": "approved-test-source",
                "source_reference": "quote:denied",
                "observed_at": datetime.now(UTC).isoformat(),
                "valid_until": valid_until.isoformat(),
            },
        )
        assert denied.status_code == 403

        created = await client.post(
            f"/api/v1/asset-positions/{position.id}/valuation-observations",
            headers=_headers("risk", "valuation-1"),
            json={
                "valued_quantity": "2.00000000",
                "unit_price": "10.25",
                "valuation_currency": "IRR",
                "fx_rate": "3",
                "source_name": "approved-test-source",
                "source_reference": "quote:1",
                "source_version_reference": "source-version:1",
                "observed_at": datetime.now(UTC).isoformat(),
                "valid_until": valid_until.isoformat(),
                "evidence_reference": "evidence://opaque/valuation-1",
            },
        )
        assert created.status_code == 201
        observation_id = UUID(created.json()["id"])
        assert Decimal(created.json()["gross_market_value"]) == Decimal("61.500000000000000000")
        assert created.json()["current_freshness_status"] == "FRESH"

        correction = await client.post(
            f"/api/v1/asset-positions/{position.id}/valuation-observations",
            headers=_headers("risk", "valuation-2"),
            json={
                "valued_quantity": "2.00000000",
                "unit_price": "11.00",
                "valuation_currency": "IRR",
                "fx_rate": "3",
                "source_name": "approved-test-source",
                "source_reference": "quote:2-correction",
                "source_version_reference": "source-version:1",
                "observed_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
                "valid_until": valid_until.isoformat(),
            },
        )
        assert correction.status_code == 201
        assert correction.json()["id"] != str(observation_id)

        listed = await client.get(
            f"/api/v1/asset-positions/{position.id}/valuation-observations",
            headers=_headers("risk"),
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 2

    async with database.session_factory() as session:
        journal_count = await session.scalar(select(func.count()).select_from(JournalEntry))
        stored_position = await session.get(AssetPosition, position.id)
        assert journal_count == 0
        assert stored_position is not None
        assert not hasattr(stored_position, "market_value")

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(ValuationObservation)
                    .where(ValuationObservation.id == observation_id)
                    .values(unit_price=Decimal("99"))
                )


@pytest.mark.integration
async def test_valuation_freshness_can_be_explicitly_stale(
    settings: Settings,
    database,
    clean_sprint03_tables,
) -> None:
    risk = await _seed_identity(
        database,
        subject="risk-stale",
        identity_type="STAFF",
        role="RISK",
    )
    position = await _seed_asset_position(database, risk.id)
    observed = datetime.now(UTC) - timedelta(hours=2)

    async with await _client(settings) as client:
        stale = await client.post(
            f"/api/v1/asset-positions/{position.id}/valuation-observations",
            headers=_headers("risk-stale", "valuation-stale"),
            json={
                "valued_quantity": "1",
                "unit_price": "5",
                "valuation_currency": "IRR",
                "source_name": "explicit-window-source",
                "source_reference": "quote:stale",
                "observed_at": observed.isoformat(),
                "valid_until": (observed + timedelta(minutes=30)).isoformat(),
            },
        )
        assert stale.status_code == 201
        assert stale.json()["freshness_status"] == "STALE"
        assert stale.json()["current_freshness_status"] == "STALE"
