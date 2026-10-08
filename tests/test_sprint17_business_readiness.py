from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from badban.api.app import create_app
from badban.application.business_readiness import (
    BusinessReadinessError,
    assert_stop_control_allows,
)
from badban.application.idempotency import canonical_request_hash
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AssetType,
    AuditEvent,
    CreditProvider,
    Identity,
    LegalEntity,
    OperationalStopControl,
    PolicyVersion,
    PortfolioRiskSnapshot,
    RoleGrant,
)
from badban.security.authorization import ROLE_AUDITOR, ROLE_OPERATIONS, SCOPE_GLOBAL


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def clean_sprint17_tables(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE operational_stop_controls, portfolio_risk_snapshots, "
                "reconciliation_blocks, reconciliation_resolution_proposals, "
                "reconciliation_observations, reconciliation_cases, reconciliation_runs, "
                "role_grants, policy_versions, credit_providers, legal_entities, "
                "asset_types, audit_events, identities RESTART IDENTITY CASCADE"
            )
        )
    yield


async def _identity_with_global_role(
    database,
    *,
    subject: str,
    identity_type: str,
    role: str,
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
                    scope_type=SCOPE_GLOBAL,
                    scope_id=None,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint17-test",
                    version=1,
                )
            )
    return identity


async def _seed_ready_policy_and_risk(
    database,
    *,
    actor_id: UUID,
    scope_definition: dict[str, object],
) -> tuple[PolicyVersion, PortfolioRiskSnapshot]:
    now = datetime.now(UTC)
    risk_payload = {"reference": "sprint17-authoritative-risk-policy"}
    risk_policy = PolicyVersion(
        policy_type="RISK_APPETITE_POLICY",
        policy_code=f"SPRINT17-RISK-{uuid4()}",
        version_number=1,
        lifecycle_status="APPROVED",
        scope_definition=scope_definition,
        payload=risk_payload,
        payload_hash=canonical_request_hash(risk_payload),
        schema_version="1",
        approved_at=now - timedelta(minutes=2),
        approved_by=actor_id,
        created_by=actor_id,
        version=3,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(risk_policy)
            await session.flush()
            pack_payload = {"component_version_ids": [str(risk_policy.id)]}
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code=f"SPRINT17-PACK-{uuid4()}",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition=scope_definition,
                payload=pack_payload,
                payload_hash=canonical_request_hash(pack_payload),
                schema_version="1",
                effective_from=now - timedelta(minutes=5),
                effective_to=None,
                approved_at=now - timedelta(minutes=3),
                activated_at=now - timedelta(minutes=1),
                approved_by=actor_id,
                created_by=actor_id,
                version=4,
            )
            session.add(pack)
            await session.flush()
            snapshot = PortfolioRiskSnapshot(
                policy_pack_id=pack.id,
                policy_pack_version=pack.version_number,
                risk_policy_version_id=risk_policy.id,
                risk_policy_code=risk_policy.policy_code,
                risk_policy_version_number=risk_policy.version_number,
                risk_state="GREEN",
                total_active_exposure=Decimal("0"),
                total_reserved_exposure=Decimal("0"),
                committed_exposure=Decimal("0"),
                approved_portfolio_limit=Decimal("100"),
                reserve_requirement=Decimal("0"),
                reserve_available=Decimal("0"),
                reserve_metrics_reference="reserve:test:sprint17",
                concentration_metrics_reference="concentration:test:sprint17",
                stress_result_reference=None,
                evaluated_inputs={
                    "scope_definition": scope_definition,
                    "authoritative_input_references": ["test:sprint17"],
                },
                input_hash=canonical_request_hash({"scope": scope_definition, "state": "GREEN"}),
                algorithm_code="PORTFOLIO_RISK",
                algorithm_version="PORTFOLIO_RISK_V1",
                actor_type="STAFF",
                actor_id=actor_id,
                correlation_id=uuid4(),
                evaluated_at=now,
            )
            session.add(snapshot)
            await session.flush()
        await session.refresh(pack)
        await session.refresh(snapshot)
    return pack, snapshot


@pytest.mark.integration
async def test_business_readiness_is_separate_and_missing_signals_fail_closed(
    settings: Settings,
    database,
    clean_sprint17_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint17-operator-missing",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )
    scope = {"pilot_scope": "sprint17-missing"}

    async with await _client(settings) as client:
        live = await client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "alive"

        readiness = await client.post(
            "/api/v1/business-readiness/evaluate",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={"policy_scope_definition": scope},
        )
        assert readiness.status_code == 200
        body = readiness.json()
        assert body["status"] == "NOT_READY"
        codes = {reason["code"] for reason in body["reasons"]}
        assert "POLICY_NOT_READY" in codes
        assert "PORTFOLIO_RISK_UNAVAILABLE" in codes


@pytest.mark.integration
async def test_global_stop_activation_is_idempotent_and_clear_restores_ready(
    settings: Settings,
    database,
    clean_sprint17_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint17-operator-global",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )
    scope: dict[str, object] = {"pilot_scope": "sprint17-ready"}
    pack, risk = await _seed_ready_policy_and_risk(
        database,
        actor_id=operator.id,
        scope_definition=scope,
    )

    async with await _client(settings) as client:
        ready = await client.post(
            "/api/v1/business-readiness/evaluate",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={"policy_scope_definition": scope},
        )
        assert ready.status_code == 200
        assert ready.json()["status"] == "READY"
        assert ready.json()["policy_pack_id"] == str(pack.id)
        assert ready.json()["risk_snapshot_id"] == str(risk.id)

        created = await client.post(
            "/api/v1/operational-stop-controls",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={
                "control_type": "STOP_NEW_GUARANTEE_RESERVATIONS",
                "scope_type": "GLOBAL",
                "scope_id": None,
                "reason": "controlled operations stop",
                "evidence_reference": "evidence:test:stop-global",
            },
        )
        assert created.status_code == 201
        control_id = UUID(created.json()["id"])
        assert created.json()["active"] is True

        replay = await client.post(
            "/api/v1/operational-stop-controls",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={
                "control_type": "STOP_NEW_GUARANTEE_RESERVATIONS",
                "scope_type": "GLOBAL",
                "scope_id": None,
                "reason": "controlled operations stop",
                "evidence_reference": "evidence:test:stop-global",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == str(control_id)

        blocked_readiness = await client.post(
            "/api/v1/business-readiness/evaluate",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={"policy_scope_definition": scope},
        )
        assert blocked_readiness.status_code == 200
        assert blocked_readiness.json()["status"] == "NOT_READY"
        assert "STOP_CONTROL_ACTIVE" in {
            item["code"] for item in blocked_readiness.json()["reasons"]
        }

        async with database.session_factory() as session:
            with pytest.raises(BusinessReadinessError) as blocked:
                await assert_stop_control_allows(
                    session,
                    control_type="STOP_NEW_GUARANTEE_RESERVATIONS",
                    scope_type="GLOBAL",
                    scope_id=None,
                )
            assert blocked.value.code == "STOP_CONTROL_ACTIVE"

        cleared = await client.post(
            f"/api/v1/operational-stop-controls/{control_id}/clear",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
        )
        assert cleared.status_code == 200
        assert cleared.json()["active"] is False

        clear_replay = await client.post(
            f"/api/v1/operational-stop-controls/{control_id}/clear",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
        )
        assert clear_replay.status_code == 200
        assert clear_replay.json()["active"] is False

        restored = await client.post(
            "/api/v1/business-readiness/evaluate",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={"policy_scope_definition": scope},
        )
        assert restored.status_code == 200
        assert restored.json()["status"] == "READY"

    async with database.session_factory() as session:
        audit_actions = set((await session.scalars(select(AuditEvent.action))).all())
        assert "STOP_CONTROL_ACTIVATE" in audit_actions
        assert "STOP_CONTROL_CLEAR" in audit_actions


@pytest.mark.integration
async def test_provider_and_asset_stop_overlays_do_not_mutate_lifecycle_and_auditor_is_read_only(
    settings: Settings,
    database,
    clean_sprint17_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint17-operator-scoped",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )
    auditor = await _identity_with_global_role(
        database,
        subject="sprint17-auditor",
        identity_type="AUDITOR",
        role=ROLE_AUDITOR,
    )
    legal_entity = LegalEntity(
        legal_name="Sprint 17 Lender Entity",
        registration_identifier=f"SPRINT17-LE-{uuid4()}",
        entity_type="EXTERNAL_LENDER",
        status="ACTIVE",
        created_by=operator.id,
        version=1,
    )
    asset_type = AssetType(
        asset_code=f"SPRINT17-ASSET-{uuid4()}",
        name="Sprint 17 Asset",
        status="ACTIVE",
        unit_code="UNIT",
        quantity_scale=8,
        currency_or_valuation_currency="IRR",
        valuation_source_reference="source:test:sprint17",
        eligibility_metadata={},
        custody_restriction_metadata={},
        created_by=operator.id,
        version=1,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([legal_entity, asset_type])
            await session.flush()
            provider = CreditProvider(
                legal_entity_id=legal_entity.id,
                provider_code=f"SPRINT17-PROVIDER-{uuid4()}",
                display_name="Sprint 17 Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="POLLING",
                authorization_review_state="TEST",
                lifecycle_status="ACTIVE",
                activated_at=datetime.now(UTC),
                created_by=operator.id,
                version=1,
            )
            session.add(provider)
            await session.flush()
        await session.refresh(provider)
        await session.refresh(asset_type)

    async with await _client(settings) as client:
        invalid_scope = await client.post(
            "/api/v1/operational-stop-controls",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={
                "control_type": "SUSPEND_PROVIDER_FOR_NEW_ACTIONS",
                "scope_type": "GLOBAL",
                "scope_id": None,
                "reason": "invalid scope test",
            },
        )
        assert invalid_scope.status_code == 422
        assert invalid_scope.json()["error"]["code"] == "STOP_CONTROL_SCOPE_INVALID"

        provider_stop = await client.post(
            "/api/v1/operational-stop-controls",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={
                "control_type": "SUSPEND_PROVIDER_FOR_NEW_ACTIONS",
                "scope_type": "PROVIDER",
                "scope_id": str(provider.id),
                "reason": "provider operations overlay",
            },
        )
        assert provider_stop.status_code == 201

        asset_stop = await client.post(
            "/api/v1/operational-stop-controls",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={
                "control_type": "SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS",
                "scope_type": "ASSET_TYPE",
                "scope_id": str(asset_type.id),
                "reason": "asset operations overlay",
            },
        )
        assert asset_stop.status_code == 201

        auditor_list = await client.get(
            "/api/v1/operational-stop-controls",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
            params={"scope_type": "PROVIDER", "scope_id": str(provider.id)},
        )
        assert auditor_list.status_code == 200
        assert len(auditor_list.json()) == 1

        auditor_mutation = await client.post(
            "/api/v1/operational-stop-controls",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
            json={
                "control_type": "STOP_GUARANTEE_ACTIVATION",
                "scope_type": "GLOBAL",
                "scope_id": None,
                "reason": "auditor must not mutate",
            },
        )
        assert auditor_mutation.status_code == 403

    async with database.session_factory() as session:
        stored_provider = await session.get(CreditProvider, provider.id)
        stored_asset = await session.get(AssetType, asset_type.id)
        active_count = int(
            await session.scalar(
                select(func.count())
                .select_from(OperationalStopControl)
                .where(OperationalStopControl.active.is_(True))
            )
            or 0
        )
    assert stored_provider is not None and stored_provider.lifecycle_status == "ACTIVE"
    assert stored_asset is not None and stored_asset.status == "ACTIVE"
    assert active_count == 2
