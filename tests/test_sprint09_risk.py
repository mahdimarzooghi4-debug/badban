from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.idempotency import canonical_request_hash
from badban.application.risk import (
    RiskEvaluationError,
    RiskEvaluationInputs,
    RiskPolicyRules,
    calculate_portfolio_risk,
    parse_risk_policy_rules,
)
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AuditEvent,
    Identity,
    OutboxMessage,
    PolicyVersion,
    PortfolioRiskSnapshot,
    RoleGrant,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _rules() -> RiskPolicyRules:
    return RiskPolicyRules(
        approved_portfolio_limit=Decimal("100"),
        committed_exposure_mode="ACTIVE_PLUS_RESERVED",
        utilization_warning_ratio=Decimal("0.75"),
        utilization_stop_ratio=Decimal("1.00"),
        reserve_coverage_target_ratio=Decimal("1.25"),
        reserve_coverage_warning_ratio=Decimal("1.00"),
        reserve_coverage_hard_minimum_ratio=Decimal("0.75"),
        require_stress_result=False,
    )


def _inputs(
    *,
    active: str = "50",
    reserved: str = "10",
    reserve_requirement: str = "20",
    reserve_available: str = "30",
    concentration_state: str = "GREEN",
    stress_state: str | None = None,
    stress_reference: str | None = None,
) -> RiskEvaluationInputs:
    return RiskEvaluationInputs(
        total_active_exposure=Decimal(active),
        total_reserved_exposure=Decimal(reserved),
        reserve_requirement=Decimal(reserve_requirement),
        reserve_available=Decimal(reserve_available),
        reserve_metrics_reference="reserve:authoritative:1",
        concentration_state=concentration_state,
        concentration_metrics_reference="concentration:authoritative:1",
        stress_state=stress_state,
        stress_result_reference=stress_reference,
        authoritative_input_references=("source:1",),
    )


def test_deterministic_risk_classification_uses_only_explicit_rules_and_inputs() -> None:
    green = calculate_portfolio_risk(rules=_rules(), inputs=_inputs())
    assert green.risk_state == "GREEN"
    assert green.committed_exposure == Decimal("60")

    amber = calculate_portfolio_risk(
        rules=_rules(),
        inputs=_inputs(active="70", reserved="10"),
    )
    assert amber.risk_state == "AMBER"
    assert amber.gate_states["exposure"] == "AMBER"

    red = calculate_portfolio_risk(
        rules=_rules(),
        inputs=_inputs(active="95", reserved="10"),
    )
    assert red.risk_state == "RED"
    assert red.gate_states["exposure"] == "RED"

    concentration_red = calculate_portfolio_risk(
        rules=_rules(),
        inputs=_inputs(concentration_state="RED"),
    )
    assert concentration_red.risk_state == "RED"


def test_reserve_and_stress_gates_fail_closed_without_defaults() -> None:
    reserve_red = calculate_portfolio_risk(
        rules=_rules(),
        inputs=_inputs(reserve_requirement="20", reserve_available="10"),
    )
    assert reserve_red.risk_state == "RED"
    assert reserve_red.gate_states["reserve"] == "RED"

    required_stress = replace(_rules(), require_stress_result=True)
    with pytest.raises(RiskEvaluationError) as exc:
        calculate_portfolio_risk(rules=required_stress, inputs=_inputs())
    assert exc.value.code == "RISK_INPUT_INVALID"


def test_risk_policy_schema_rejects_missing_or_inconsistent_thresholds() -> None:
    with pytest.raises(RiskEvaluationError) as missing:
        parse_risk_policy_rules({})
    assert missing.value.code == "RISK_POLICY_INVALID"

    payload = {
        "approved_portfolio_limit": "100",
        "committed_exposure_mode": "ACTIVE_PLUS_RESERVED",
        "utilization_warning_ratio": "1.00",
        "utilization_stop_ratio": "0.90",
        "reserve_coverage_target_ratio": "1.20",
        "reserve_coverage_warning_ratio": "1.00",
        "reserve_coverage_hard_minimum_ratio": "0.80",
        "require_stress_result": False,
    }
    with pytest.raises(RiskEvaluationError) as inconsistent:
        parse_risk_policy_rules(payload)
    assert inconsistent.value.code == "RISK_POLICY_INVALID"


async def _identity(database, *, subject: str, identity_type: str, role: str) -> Identity:
    identity = Identity(identity_type=identity_type, external_subject=subject, status="ACTIVE")
    async with database.session_factory() as session:
        async with session.begin():
            session.add(identity)
            await session.flush()
            session.add(
                RoleGrant(
                    identity_id=identity.id,
                    role_code=role,
                    scope_type="GLOBAL",
                    scope_id=None,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    reason_ref="sprint09-test",
                )
            )
    return identity


async def _policies(database) -> tuple[PolicyVersion, PolicyVersion]:
    scope = {"pilot_scope": "bounded-pilot"}
    risk_payload = {
        "approved_portfolio_limit": "1000",
        "committed_exposure_mode": "ACTIVE_PLUS_RESERVED",
        "utilization_warning_ratio": "0.80",
        "utilization_stop_ratio": "1.00",
        "reserve_coverage_target_ratio": "1.25",
        "reserve_coverage_warning_ratio": "1.00",
        "reserve_coverage_hard_minimum_ratio": "0.75",
        "require_stress_result": False,
    }
    risk = PolicyVersion(
        policy_type="RISK_APPETITE_POLICY",
        policy_code="PILOT_RISK",
        version_number=1,
        lifecycle_status="ACTIVE",
        scope_definition=scope,
        payload=risk_payload,
        payload_hash=canonical_request_hash(risk_payload),
        schema_version="1",
        activated_at=datetime.now(UTC),
        created_by=uuid4(),
        version=4,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(risk)
            await session.flush()
            pack_payload = {"component_version_ids": [str(risk.id)]}
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="BOUNDED_PILOT",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition=scope,
                payload=pack_payload,
                payload_hash=canonical_request_hash(pack_payload),
                schema_version="1",
                activated_at=datetime.now(UTC),
                created_by=uuid4(),
                version=4,
            )
            session.add(pack)
            await session.flush()
            await session.refresh(risk)
            await session.refresh(pack)
            return risk, pack


def _headers(subject: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {subject}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


@pytest.mark.integration
async def test_risk_api_creates_immutable_policy_bound_snapshot_and_state_change_event(
    settings,
    database,
    clean_sprint09_risk_tables,
) -> None:
    risk_identity = await _identity(
        database,
        subject="risk",
        identity_type="STAFF",
        role="RISK",
    )
    await _identity(
        database,
        subject="auditor",
        identity_type="AUDITOR",
        role="AUDITOR",
    )
    risk_policy, pack = await _policies(database)

    green_payload = {
        "scope_definition": {"pilot_scope": "bounded-pilot"},
        "reserve_requirement": "100",
        "reserve_available": "125",
        "reserve_metrics_reference": "reserve-ledger:snapshot:1",
        "concentration_state": "GREEN",
        "concentration_metrics_reference": "concentration:snapshot:1",
        "authoritative_input_references": ["portfolio-source:1"],
    }

    async with await _client(settings) as client:
        first = await client.post(
            "/api/v1/risk/portfolio/evaluate",
            headers=_headers("risk", "risk-eval-1"),
            json=green_payload,
        )
        assert first.status_code == 201, first.text
        body = first.json()
        snapshot_id = body["id"]
        assert body["risk_state"] == "GREEN"
        assert body["policy_pack_id"] == str(pack.id)
        assert body["risk_policy_version_id"] == str(risk_policy.id)
        assert body["total_active_exposure"] == "0.000000000000000000"
        assert body["total_reserved_exposure"] == "0.000000000000000000"
        assert body["approved_portfolio_limit"] == "1000.000000000000000000"

        replay = await client.post(
            "/api/v1/risk/portfolio/evaluate",
            headers=_headers("risk", "risk-eval-1"),
            json=green_payload,
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == snapshot_id

        changed_payload = dict(green_payload)
        changed_payload["concentration_state"] = "RED"
        changed_payload["concentration_metrics_reference"] = "concentration:snapshot:2"
        red = await client.post(
            "/api/v1/risk/portfolio/evaluate",
            headers=_headers("risk", "risk-eval-2"),
            json=changed_payload,
        )
        assert red.status_code == 201, red.text
        assert red.json()["risk_state"] == "RED"

        current = await client.get(
            "/api/v1/risk/portfolio",
            headers=_headers("auditor"),
        )
        assert current.status_code == 200
        assert current.json()["id"] == red.json()["id"]

        denied = await client.post(
            "/api/v1/risk/portfolio/evaluate",
            headers=_headers("auditor", "auditor-risk-eval"),
            json=green_payload,
        )
        assert denied.status_code == 403

        conflict_payload = dict(green_payload)
        conflict_payload["reserve_available"] = "124"
        conflict = await client.post(
            "/api/v1/risk/portfolio/evaluate",
            headers=_headers("risk", "risk-eval-1"),
            json=conflict_payload,
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    async with database.session_factory() as session:
        snapshots = await session.scalar(select(func.count()).select_from(PortfolioRiskSnapshot))
        evaluated_events = await session.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(OutboxMessage.event_type == "PortfolioRiskEvaluated")
        )
        changed_events = await session.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(OutboxMessage.event_type == "PortfolioRiskStateChanged")
        )
        audits = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "PORTFOLIO_RISK_EVALUATED")
        )
    assert snapshots == 2
    assert evaluated_events == 2
    assert changed_events == 1
    assert audits == 2

    with pytest.raises(DBAPIError):
        async with database.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(PortfolioRiskSnapshot)
                    .where(PortfolioRiskSnapshot.id == snapshot_id)
                    .values(risk_state="RED")
                )

    assert risk_identity.id is not None


@pytest.mark.integration
async def test_risk_evaluation_fails_closed_when_pack_has_no_risk_policy(
    settings,
    database,
    clean_sprint09_risk_tables,
) -> None:
    await _identity(database, subject="risk", identity_type="STAFF", role="RISK")
    scope = {"pilot_scope": "bounded-pilot"}
    pack_payload = {"component_version_ids": []}
    async with database.session_factory() as session:
        async with session.begin():
            session.add(
                PolicyVersion(
                    policy_type="PILOT_POLICY_PACK",
                    policy_code="NO_RISK",
                    version_number=1,
                    lifecycle_status="ACTIVE",
                    scope_definition=scope,
                    payload=pack_payload,
                    payload_hash=canonical_request_hash(pack_payload),
                    schema_version="1",
                    activated_at=datetime.now(UTC),
                    created_by=uuid4(),
                    version=4,
                )
            )

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/risk/portfolio/evaluate",
            headers=_headers("risk", "missing-risk-policy"),
            json={
                "scope_definition": scope,
                "reserve_requirement": "0",
                "reserve_available": "0",
                "reserve_metrics_reference": "reserve:none",
                "concentration_state": "GREEN",
                "concentration_metrics_reference": "concentration:reviewed:1",
            },
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "POLICY_COMPONENT_MISSING"

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(PortfolioRiskSnapshot))
    assert count == 0


def test_openapi_exposes_only_accepted_portfolio_risk_endpoints(settings) -> None:
    app = create_app(settings)
    schema = app.openapi()
    paths = schema["paths"]

    assert "/api/v1/risk/portfolio" in paths
    assert set(paths["/api/v1/risk/portfolio"]) == {"get"}
    assert "/api/v1/risk/portfolio/evaluate" in paths
    assert set(paths["/api/v1/risk/portfolio/evaluate"]) == {"post"}
    request_schema = schema["components"]["schemas"]["RiskEvaluateRequest"]["properties"]
    assert request_schema["reserve_requirement"]["format"] == "decimal"
    assert request_schema["reserve_available"]["format"] == "decimal"
