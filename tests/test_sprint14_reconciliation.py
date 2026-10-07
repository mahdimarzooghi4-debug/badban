from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_sprint13_lender_mirror import TestLenderAdapter as StubLenderAdapter
from test_sprint13_lender_mirror import _seed_context

from badban.api.app import create_app
from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.lender_adapter import (
    AdapterHealth,
    LenderAdapterRegistry,
    LenderReconciliationLoan,
    LenderReconciliationSnapshot,
)
from badban.application.policy_resolution import ResolvedPolicyPack
from badban.application.reconciliation import compare_fields, run_lender_reconciliation
from badban.application.reconciliation_policy import (
    RECON_SCHEMA,
    ReconciliationRules,
    resolve_reconciliation_policy,
    validate_pack_reconciliation_components,
    validate_reconciliation_component,
)
from badban.infrastructure.persistence.models import (
    AuditEvent,
    ExternalLoanMirror,
    GuaranteeCase,
    JournalEntry,
    OutboxMessage,
    PolicyVersion,
    ReconciliationBlock,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
    RoleGrant,
)


def payload():
    return {
        "schema_version": RECON_SCHEMA,
        "reconciliation_type": "LENDER",
        "rules": [
            {
                "rule_code": field.upper(),
                "field_code": field,
                "comparison_mode": "DECIMAL_EXACT"
                if field in {"original_principal", "outstanding_principal"}
                else "EXACT",
                "materiality": "WARNING",
                "reason_code": "RECON_AMOUNT_MISMATCH"
                if "principal" in field
                else "RECON_STATE_MISMATCH",
                "blocked_commands": [],
            }
            for field in [
                "external_loan_id",
                "original_principal",
                "outstanding_principal",
                "currency",
                "state",
            ]
        ],
        "freshness": {
            "internal_max_age_seconds": 600,
            "external_max_age_seconds": 600,
            "materiality": "MATERIAL",
            "blocked_commands": ["CloseGuaranteeCase"],
        },
        "missing_record_materiality": "MATERIAL",
        "missing_record_blocked_commands": ["CloseGuaranteeCase"],
        "cutoff_mismatch_materiality": "MATERIAL",
        "cutoff_mismatch_blocked_commands": ["CloseGuaranteeCase"],
        "principal_invariant_blocked_commands": ["ActivateGuaranteedLoan"],
    }


def fields(amount="100"):
    return {
        "external_loan_id": "loan-test",
        "original_principal": "100",
        "outstanding_principal": amount,
        "currency": "IRR",
        "state": "ACTIVE",
    }


@pytest.mark.parametrize(
    "change",
    [
        "missing_tolerance",
        "float_tolerance",
        "extra_expression",
        "missing_freshness",
        "bad_field",
        "bad_scope_type",
    ],
)
def test_strict_policy_fails_closed(change):
    data = payload()
    if change == "missing_tolerance":
        data["rules"][0]["comparison_mode"] = "TOLERANCE_BASED"
    elif change == "float_tolerance":
        data["rules"][1].update(comparison_mode="TOLERANCE_BASED", tolerance=0.1)
    elif change == "extra_expression":
        data["rules"][0]["expression"] = "anything"
    elif change == "missing_freshness":
        data.pop("freshness")
    elif change == "bad_field":
        data["rules"][0]["field_code"] = "raw_provider_payload"
    else:
        data["reconciliation_type"] = "UNKNOWN"
    with pytest.raises(ValidationError):
        ReconciliationRules.model_validate(data)


def test_exact_decimal_tolerance_and_informational():
    data = payload()
    rules = ReconciliationRules.model_validate(data)
    assert compare_fields(fields(), fields("100.000"), rules).status == "MATCHED"
    assert compare_fields(fields(), fields("100.01"), rules).status == "MISMATCH"
    data["rules"][2].update(comparison_mode="TOLERANCE_BASED", tolerance="0.01")
    rules = ReconciliationRules.model_validate(data)
    assert compare_fields(fields(), fields("100.01"), rules).status == "MATCHED"
    assert compare_fields(fields(), fields("100.010000000000000001"), rules).status == "MISMATCH"
    data["rules"][2].pop("tolerance")
    data["rules"][2]["comparison_mode"] = "INFORMATIONAL"
    result = compare_fields(fields(), fields("80"), ReconciliationRules.model_validate(data))
    assert result.status == "MATCHED" and result.differences


@pytest.fixture
async def recon_context(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE reconciliation_observations, reconciliation_blocks, "
                "reconciliation_cases, reconciliation_runs, external_loan_events, "
                "external_loan_mirrors, guarantee_cases, credit_product_versions, "
                "credit_providers, legal_entities, participation_episodes, programs, "
                "participants, identities, role_grants, audit_events, outbox_messages, "
                "inbox_messages, idempotency_records, policy_versions CASCADE"
            )
        )
    actor, provider, guarantee = await _seed_context(database)
    now = datetime.now(UTC)
    data = payload()
    scope = {"pilot_scope": "test-only-pilot", "provider_id": str(provider.id)}
    async with database.session_factory() as session:
        async with session.begin():
            policy = PolicyVersion(
                policy_type="RECONCILIATION_POLICY",
                policy_code="TEST_RECON",
                version_number=1,
                lifecycle_status="APPROVED",
                scope_definition={**scope, "reconciliation_type": "LENDER"},
                payload=data,
                payload_hash=canonical_request_hash(data),
                schema_version=RECON_SCHEMA,
                created_by=uuid4(),
                approved_by=uuid4(),
                approved_at=now,
                version=1,
            )
            session.add(policy)
            await session.flush()
            pack_data = {"component_version_ids": [str(policy.id)]}
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="TEST_PACK",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition=scope,
                payload=pack_data,
                payload_hash=canonical_request_hash(pack_data),
                schema_version="1",
                created_by=uuid4(),
                approved_at=now,
                approved_by=uuid4(),
                activated_at=now,
                version=1,
            )
            mirror = ExternalLoanMirror(
                provider_id=provider.id,
                external_loan_id="loan-test",
                guarantee_case_id=guarantee.id,
                state="ACTIVE",
                original_principal=Decimal("100"),
                outstanding_principal=Decimal("100"),
                currency="IRR",
                last_provider_event_at=now,
                last_synced_at=now,
                version=1,
            )
            session.add_all([pack, mirror])
            await session.flush()
    return actor, provider, guarantee, policy, pack, mirror, now


class SnapshotAdapter(StubLenderAdapter):
    def __init__(self, provider, now, *, amount="100", original="100", loans=True, cutoff=None):
        super().__init__(provider.id)
        self.snapshot = LenderReconciliationSnapshot(
            provider_id=provider.id,
            snapshot_at=cutoff or now,
            source_reference="test-only:independent-statement",
            evidence_references=["test-only:evidence"],
            loans=[
                LenderReconciliationLoan(
                    external_loan_id="loan-test",
                    original_principal=original,
                    outstanding_principal=amount,
                    currency="IRR",
                    provider_state="ACTIVE",
                    observed_at=cutoff or now,
                )
            ]
            if loans
            else [],
        )

    async def health_check(self) -> AdapterHealth:
        return "AVAILABLE"

    async def fetch_reconciliation_snapshot(self, scope):
        return self.snapshot


async def execute(database, context, adapter=None, *, at=None):
    actor, provider, _, _, _, _, now = context
    registry = LenderAdapterRegistry()
    if adapter is not None:
        registry.register(provider.id, adapter)
    async with database.session_factory() as session:
        async with session.begin():
            return await run_lender_reconciliation(
                session,
                provider_id=provider.id,
                registry=registry,
                actor_id=actor.id,
                actor_type=actor.identity_type,
                correlation_id=uuid4(),
                now=at or now,
            )


@pytest.mark.integration
async def test_run_is_atomic_immutable_and_does_not_mutate_financial_state(database, recon_context):
    actor, provider, guarantee, _, _, mirror, now = recon_context
    run = await execute(database, recon_context, SnapshotAdapter(provider, now))
    assert run.counts["MATCHED"] == 1
    async with database.session_factory() as session:
        assert (await session.get(GuaranteeCase, guarantee.id)).state == "ISSUED"
        assert (await session.get(ExternalLoanMirror, mirror.id)).version == 1
        assert await session.scalar(select(func.count()).select_from(JournalEntry)) == 0
        assert (
            await session.scalar(select(func.count()).select_from(ReconciliationObservation)) == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.aggregate_type == "ReconciliationRun")
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OutboxMessage)
                .where(OutboxMessage.aggregate_type == "ReconciliationRun")
            )
            == 2
        )
    for table in ["reconciliation_runs", "reconciliation_observations"]:
        with pytest.raises(DBAPIError):
            async with database.engine.begin() as connection:
                await connection.execute(text(f"DELETE FROM {table}"))


@pytest.mark.integration
@pytest.mark.parametrize(
    "mode",
    [
        "outage",
        "stale",
        "missing_external",
        "missing_internal",
        "duplicate_external",
        "cutoff",
        "critical",
    ],
)
async def test_negative_source_and_hard_invariant_paths(database, recon_context, mode):
    _, provider, _, _, _, mirror, now = recon_context
    adapter = SnapshotAdapter(provider, now)
    at = now
    if mode == "outage":
        adapter = None
    elif mode == "stale":
        at = now + timedelta(seconds=601)
    elif mode == "missing_external":
        adapter = SnapshotAdapter(provider, now, loans=False)
    elif mode == "missing_internal":
        async with database.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(ExternalLoanMirror)
                    .where(ExternalLoanMirror.id == mirror.id)
                    .values(external_loan_id="different")
                )
    elif mode == "duplicate_external":
        adapter.snapshot.loans.append(adapter.snapshot.loans[0])
    elif mode == "cutoff":
        adapter = SnapshotAdapter(provider, now, cutoff=now - timedelta(seconds=1))
    elif mode == "critical":
        adapter = SnapshotAdapter(provider, now, original="101")
    run = await execute(database, recon_context, adapter, at=at)
    assert run.counts["MATCHED"] == 0
    if mode in {"outage", "stale"}:
        assert run.counts["STALE"] == 1
    if mode == "critical":
        assert run.counts["CRITICAL"] == 1
        async with database.session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ReconciliationBlock)
                    .where(ReconciliationBlock.blocked_command_type == "ActivateGuaranteedLoan")
                )
                == 1
            )


@pytest.mark.integration
async def test_duplicate_and_concurrent_runs_and_snapshot_conflict(database, recon_context):
    _, provider, _, _, _, _, now = recon_context
    adapter = SnapshotAdapter(provider, now)
    first, second = await asyncio.gather(
        execute(database, recon_context, adapter), execute(database, recon_context, adapter)
    )
    assert first.id == second.id
    async with database.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ReconciliationRun)) == 1
    changed = SnapshotAdapter(provider, now, amount="90")
    with pytest.raises(ApiError) as error:
        await execute(database, recon_context, changed)
    assert error.value.code == "RECON_SNAPSHOT_CONFLICT"


@pytest.mark.integration
async def test_pinning_excludes_newer_unpinned_and_checks_scope(database, recon_context):
    _, _, _, policy, pack, _, _ = recon_context
    pinned = ResolvedPolicyPack(pack.id, pack.policy_code, pack.version_number, (policy.id,))
    async with database.session_factory() as session:
        async with session.begin():
            newer = PolicyVersion(
                policy_type="RECONCILIATION_POLICY",
                policy_code="TEST_RECON",
                version_number=2,
                lifecycle_status="ACTIVE",
                scope_definition=policy.scope_definition,
                payload=payload(),
                payload_hash=canonical_request_hash(payload()),
                schema_version=RECON_SCHEMA,
                approved_at=datetime.now(UTC),
                approved_by=uuid4(),
                created_by=uuid4(),
                version=1,
            )
            session.add(newer)
            await session.flush()
            selected, _ = await resolve_reconciliation_policy(
                session, pack=pinned, required_scope=policy.scope_definition
            )
            assert selected.id == policy.id
            for scope, ids, code in [
                (
                    dict(policy.scope_definition, pilot_scope="other"),
                    (policy.id,),
                    "RECON_POLICY_NOT_FOUND",
                ),
                (policy.scope_definition, (), "RECON_POLICY_NOT_FOUND"),
                (policy.scope_definition, (policy.id, newer.id), "RECON_POLICY_AMBIGUOUS"),
            ]:
                with pytest.raises(ApiError) as error:
                    await resolve_reconciliation_policy(
                        session,
                        pack=ResolvedPolicyPack(pack.id, pack.policy_code, 1, ids),
                        required_scope=scope,
                    )
                assert error.value.code == code


@pytest.mark.integration
@pytest.mark.parametrize("state", ["DRAFT", "REVIEWED"])
async def test_unapproved_policy_never_authorizes_runtime_or_pack(database, recon_context, state):
    _, _, _, policy, pack, _, _ = recon_context
    # New test-only component; approved rows are intentionally immutable.
    async with database.session_factory() as session:
        async with session.begin():
            draft = PolicyVersion(
                policy_type="RECONCILIATION_POLICY",
                policy_code="UNAPPROVED",
                version_number=1,
                lifecycle_status=state,
                scope_definition=policy.scope_definition,
                payload=payload(),
                payload_hash=canonical_request_hash(payload()),
                schema_version=RECON_SCHEMA,
                created_by=uuid4(),
                version=1,
            )
            session.add(draft)
            await session.flush()
            test_pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK", payload={"component_version_ids": [str(draft.id)]}
            )
            with pytest.raises(ApiError):
                await validate_pack_reconciliation_components(session, test_pack)
            with pytest.raises(ApiError):
                await resolve_reconciliation_policy(
                    session,
                    pack=ResolvedPolicyPack(pack.id, pack.policy_code, 1, (draft.id,)),
                    required_scope=policy.scope_definition,
                )


@pytest.mark.integration
async def test_approved_policy_content_is_immutable_and_hash_proof_rejected(
    database, recon_context
):
    _, _, _, policy, _, _, _ = recon_context
    with pytest.raises(DBAPIError):
        async with database.engine.begin() as connection:
            await connection.execute(
                update(PolicyVersion)
                .where(PolicyVersion.id == policy.id)
                .values(payload_hash="0" * 64)
            )
    clone = PolicyVersion(
        policy_type="RECONCILIATION_POLICY",
        lifecycle_status="APPROVED",
        approved_at=datetime.now(UTC),
        approved_by=uuid4(),
        payload=payload(),
        payload_hash="0" * 64,
        scope_definition=policy.scope_definition,
        schema_version=RECON_SCHEMA,
    )
    with pytest.raises(ApiError) as error:
        validate_reconciliation_component(clone, governed=True)
    assert error.value.code == "RECON_POLICY_INTEGRITY_INVALID"


@pytest.mark.integration
async def test_rollback_leaves_no_partial_run_audit_outbox(database, recon_context):
    actor, provider, _, _, _, _, now = recon_context
    registry = LenderAdapterRegistry()
    registry.register(provider.id, SnapshotAdapter(provider, now))
    async with database.session_factory() as session:
        await run_lender_reconciliation(
            session,
            provider_id=provider.id,
            registry=registry,
            actor_id=actor.id,
            actor_type=actor.identity_type,
            correlation_id=uuid4(),
            now=now,
        )
        await session.rollback()
    async with database.session_factory() as session:
        for cls in [
            ReconciliationRun,
            ReconciliationCase,
            ReconciliationObservation,
            ReconciliationBlock,
            OutboxMessage,
        ]:
            assert await session.scalar(select(func.count()).select_from(cls)) == 0


class IdentityVerifier:
    async def verify(self, token):
        return {"sub": token}


@pytest.mark.integration
async def test_run_read_api_authorization_idempotency_and_openapi(
    settings, database, recon_context
):
    actor, provider, _, _, _, _, now = recon_context
    app = create_app(settings)
    app.state.token_verifier = IdentityVerifier()
    app.state.lender_adapter_registry.register(provider.id, SnapshotAdapter(provider, now))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post(
                "/api/v1/reconciliation/runs",
                json={"provider_id": str(provider.id)},
                headers={"Idempotency-Key": "test-key"},
            )
        ).status_code == 401
        headers = {
            "Authorization": f"Bearer {actor.external_subject}",
            "Idempotency-Key": "test-key",
        }
        assert (
            await client.post(
                "/api/v1/reconciliation/runs",
                json={"provider_id": str(provider.id)},
                headers=headers,
            )
        ).status_code == 403
        async with database.session_factory() as session:
            async with session.begin():
                session.add(
                    RoleGrant(
                        identity_id=actor.id,
                        role_code="FINANCE_RECONCILIATION",
                        scope_type="PROVIDER",
                        scope_id=provider.id,
                        status="ACTIVE",
                        valid_from=now - timedelta(days=1),
                        granted_by=actor.id,
                    )
                )
        response = await client.post(
            "/api/v1/reconciliation/runs", json={"provider_id": str(provider.id)}, headers=headers
        )
        assert response.status_code == 201, response.text
        replay = await client.post(
            "/api/v1/reconciliation/runs", json={"provider_id": str(provider.id)}, headers=headers
        )
        assert replay.json() == response.json()
        assert (
            await client.get(
                "/api/v1/reconciliation/runs/" + response.json()["id"], headers=headers
            )
        ).status_code == 200
        cases = await client.get(
            "/api/v1/reconciliation/cases",
            params={"provider_id": str(provider.id)},
            headers=headers,
        )
        assert len(cases.json()) == 1
        assert (
            await client.get(
                "/api/v1/reconciliation/cases/" + cases.json()[0]["id"], headers=headers
            )
        ).status_code == 200
        assert (
            await client.post(
                "/api/v1/reconciliation/runs",
                json={"provider_id": str(provider.id), "pilot_scope": "caller-selected"},
                headers=headers,
            )
        ).status_code == 422
    paths = app.openapi()["paths"]
    assert "/api/v1/reconciliation/runs" in paths
    assert not any(
        "mark-matched" in path or "resolve" in path for path in paths if "reconciliation" in path
    )
    await app.state.database.dispose()


@pytest.mark.integration
async def test_changed_guarantee_fact_creates_new_immutable_comparison(database, recon_context):
    _, provider, guarantee, _, _, _, now = recon_context
    adapter = SnapshotAdapter(provider, now)
    first = await execute(database, recon_context, adapter)
    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                update(GuaranteeCase)
                .where(GuaranteeCase.id == guarantee.id)
                .values(issued_guarantee_amount=Decimal("90"), version=2)
            )
    second = await execute(database, recon_context, adapter)
    assert first.id != second.id
    assert second.counts["CRITICAL"] == 1


@pytest.mark.integration
async def test_missing_linked_guarantee_amount_cannot_match(database, recon_context):
    _, provider, guarantee, _, _, _, now = recon_context
    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                update(GuaranteeCase)
                .where(GuaranteeCase.id == guarantee.id)
                .values(issued_guarantee_amount=None)
            )
    run = await execute(database, recon_context, SnapshotAdapter(provider, now))
    assert run.counts["MATCHED"] == 0 and run.counts["MISMATCH"] == 1


@pytest.mark.integration
async def test_scope_has_no_default_or_caller_fallback_and_ambiguity_fails(database, recon_context):
    _, provider, _, _, pack, _, now = recon_context
    async with database.session_factory() as session:
        async with session.begin():
            other_payload = dict(pack.payload)
            other = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="OTHER_PILOT",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition={
                    "pilot_scope": "other-test-pilot",
                    "provider_id": str(provider.id),
                },
                payload=other_payload,
                payload_hash=canonical_request_hash(other_payload),
                schema_version="1",
                created_by=uuid4(),
                approved_at=now,
                approved_by=uuid4(),
                activated_at=now,
                version=1,
            )
            session.add(other)
    with pytest.raises(ApiError) as error:
        await execute(database, recon_context, SnapshotAdapter(provider, now))
    assert error.value.code == "RECON_SCOPE_AMBIGUOUS"


@pytest.mark.integration
async def test_unlinked_mirror_needs_explicit_provider_pack_binding(database, recon_context):
    _, provider, _, _, _, mirror, now = recon_context
    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                update(ExternalLoanMirror)
                .where(ExternalLoanMirror.id == mirror.id)
                .values(guarantee_case_id=None)
            )
    run = await execute(database, recon_context, SnapshotAdapter(provider, now))
    assert run.counts["MATCHED"] == 1


@pytest.mark.integration
async def test_timeout_empty_and_future_snapshots_never_match(database, recon_context):
    _, provider, _, _, _, _, now = recon_context

    class TimeoutSnapshotAdapter(SnapshotAdapter):
        async def fetch_reconciliation_snapshot(self, scope):
            raise TimeoutError("test-only timeout")

    timed = await execute(database, recon_context, TimeoutSnapshotAdapter(provider, now))
    assert timed.status == "SOURCE_UNAVAILABLE" and timed.counts["STALE"] == 1
    future = await execute(
        database, recon_context, SnapshotAdapter(provider, now, cutoff=now + timedelta(seconds=1))
    )
    assert future.counts["MATCHED"] == 0
    async with database.engine.begin() as connection:
        await connection.execute(text("TRUNCATE external_loan_mirrors CASCADE"))
    empty = await execute(database, recon_context, SnapshotAdapter(provider, now, loans=False))
    assert empty.counts["MATCHED"] == 0
