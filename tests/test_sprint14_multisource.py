from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_sprint13_lender_mirror import FakeVerifier
from test_sprint14_reconciliation import payload
from test_sprint14_reconciliation import recon_context as recon_context

from badban.api.app import create_app
from badban.api.errors import ApiError
from badban.api.sprint14 import RunBody
from badban.application.idempotency import canonical_request_hash
from badban.application.journal import JournalLine, post_journal
from badban.application.reconciliation import compare_fields
from badban.application.reconciliation_internal import build_internal_snapshot
from badban.application.reconciliation_multisource import run_source_reconciliation
from badban.application.reconciliation_policy import RECON_SCHEMA, ReconciliationRules
from badban.application.reconciliation_scope import SOURCE_ROLES
from badban.application.reconciliation_sources import (
    SNAPSHOT_ADAPTER,
    CustodyRecord,
    IssuerRecord,
    LedgerRecord,
    ReconciliationSourceRegistry,
    RegistryRecord,
    SettlementRecord,
    SourceCapability,
    SourceTarget,
    canonical_fields,
)
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    CreditProductVersion,
    CreditProvider,
    GuaranteeCase,
    JournalAccountTaxonomy,
    JournalEntry,
    JournalPosting,
    LegalAuthorization,
    LegalEntity,
    ParticipationEpisode,
    PolicyVersion,
    Program,
    ReconciliationBlock,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
    RoleGrant,
)

IMPLEMENTED = ["GUARANTEE_ISSUER", "CUSTODY", "LEDGER"]
EXTERNAL = ["GUARANTEE_ISSUER", "CUSTODY", "SETTLEMENT", "COLLATERAL_REGISTRY"]


class FixtureSourcePort:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def capability(self):
        return SourceCapability(
            self.snapshot.source_id,
            self.snapshot.reconciliation_type,
            "test-contract-v1",
            "test-mapping-v1",
        )

    async def fetch_reconciliation_snapshot(self, target, scope):
        self.calls += 1
        return self.snapshot


def make_snapshot(target, scope, now, records, **changes):
    data: dict[str, Any] = dict(
        source_id=str(target.identity),
        reconciliation_type=target.reconciliation_type,
        scope_definition=scope,
        snapshot_at=now.isoformat(),
        received_at=now.isoformat(),
        source_reference="test-only:independent-statement",
        schema_version="reconciliation-source-v1",
        contract_version="test-contract-v1",
        mapping_version="test-mapping-v1",
        evidence_references=["test-only:independent-evidence"],
        records=[r.model_dump(mode="json") for r in records],
    )
    data.update(changes)
    for key in ["snapshot_at", "received_at", "coverage_from", "coverage_to"]:
        value = data.get(key)
        if isinstance(value, str):
            data[key] = value.replace("+00:00", "Z")
    for key in ["coverage_from", "coverage_to", "watermark", "normalization_version"]:
        data.setdefault(key, None)
    data["content_hash"] = canonical_request_hash(
        {k: v for k, v in data.items() if k not in {"received_at", "content_hash"}}
    )
    return SNAPSHOT_ADAPTER.validate_python(data)


async def seed_source(
    database,
    base,
    kind,
    *,
    policy_changes=None,
    component_scope_changes=None,
    authorization_changes=None,
):
    actor, _, guarantee, _, _, _, _ = base
    legal_id = uuid4()
    async with database.session_factory() as session:
        async with session.begin():
            # No CreditProvider is created for this regulated source.
            session.add(
                LegalEntity(
                    id=legal_id,
                    legal_name="Test-only source",
                    registration_identifier=str(legal_id),
                    entity_type="TEST_ONLY",
                    status="ACTIVE",
                    created_by=actor.id,
                    version=1,
                )
            )
            await session.flush()
            episode = await session.get(ParticipationEpisode, guarantee.participation_episode_id)
            assert episode is not None
            program = await session.get(Program, episode.program_id)
            assert program is not None
            if kind == "LEDGER":
                program.legal_entity_id = legal_id
                target = SourceTarget(reconciliation_type="LEDGER", program_id=program.id)
                binding = {"program_id": str(program.id), "legal_entity_id": str(legal_id)}
                for code in ["1010.PROGRAM_CASH_CONTROL", "2030.PROGRAM_CAPITAL_BALANCE"]:
                    assert await session.get(JournalAccountTaxonomy, code) is not None
                await session.flush()
                await post_journal(
                    session,
                    business_event_type="TEST_ONLY",
                    business_event_id=str(uuid4()),
                    legal_entity_id=legal_id,
                    currency="IRR",
                    idempotency_key=str(uuid4()),
                    actor_reference=actor.id,
                    correlation_id=uuid4(),
                    lines=[
                        JournalLine(
                            account_code="1010.PROGRAM_CASH_CONTROL",
                            economic_owner_type="PROGRAM",
                            program_id=program.id,
                            debit_amount=Decimal("100"),
                        ),
                        JournalLine(
                            account_code="2030.PROGRAM_CAPITAL_BALANCE",
                            economic_owner_type="PROGRAM",
                            program_id=program.id,
                            credit_amount=Decimal("100"),
                        ),
                    ],
                )
                records = []
            else:
                target = SourceTarget.model_validate(
                    {"reconciliation_type": kind, "source_legal_entity_id": legal_id}
                )
                role = SOURCE_ROLES[kind]
                binding = {"legal_entity_id": str(legal_id), "role_code": role}
                at = datetime.now(UTC)
                authorization = LegalAuthorization(
                    legal_entity_id=legal_id,
                    role_code=role,
                    competent_authority="Test-only authority",
                    authorization_type="TEST_ONLY",
                    authorization_identifier=str(uuid4()),
                    scope_definition={},
                    permitted_product_scope={},
                    permitted_asset_type_ids=[],
                    evidence_reference="test-only:legal-evidence",
                    effective_from=at - timedelta(days=1),
                    expires_at=None,
                    last_compliance_review_at=at,
                    lifecycle_status="VALID",
                    verified_by=actor.id,
                    verified_at=at,
                    created_by=actor.id,
                    version=1,
                )
                for key, value in (authorization_changes or {}).items():
                    setattr(authorization, key, value)
                session.add(authorization)
                if kind == "GUARANTEE_ISSUER":
                    await session.execute(
                        update(GuaranteeCase)
                        .where(GuaranteeCase.id == guarantee.id)
                        .values(
                            legal_guarantee_issuer_id=legal_id,
                            legal_guarantee_external_id="guarantee-test",
                            updated_at=at - timedelta(seconds=1),
                        )
                    )
                    records = [
                        IssuerRecord(
                            external_guarantee_id="guarantee-test",
                            issued_amount="100",
                            issued_at=at,
                            beneficiary=(
                                await session.get(
                                    CreditProductVersion, guarantee.credit_product_version_id
                                )
                            ).lender_of_record_legal_entity_id,
                            currency="IRR",
                            state="ISSUED",
                            observed_at=at,
                        )
                    ]
                elif kind == "CUSTODY":
                    asset = AssetType(
                        asset_code=str(uuid4()),
                        name="Test asset (not Gold)",
                        status="ACTIVE",
                        unit_code="UNIT",
                        quantity_scale=18,
                        created_by=actor.id,
                        version=1,
                    )
                    session.add(asset)
                    await session.flush()
                    position = AssetPosition(
                        participation_episode_id=episode.id,
                        program_id=program.id,
                        asset_type_id=asset.id,
                        ownership_funding_type="PARTICIPANT_OWNED",
                        legal_owner_participant_id=episode.participant_id,
                        custodian_legal_entity_id=legal_id,
                        quantity=Decimal("100"),
                        unit_code="UNIT",
                        lifecycle_status="ACTIVE",
                        source_reference="custody-test",
                        created_by=actor.id,
                        version=1,
                        updated_at=at,
                    )
                    session.add(position)
                    await session.flush()
                    records = [
                        CustodyRecord(
                            asset_position_id=position.id,
                            custody_reference="custody-test",
                            asset_type=asset.asset_code,
                            quantity="100",
                            unit_code="UNIT",
                            state="ACTIVE",
                            observed_at=at,
                        )
                    ]
                elif kind == "SETTLEMENT":
                    records = [
                        SettlementRecord(
                            settlement_reference="settlement-test",
                            amount="100",
                            currency="IRR",
                            payer_role="TEST_PAYER",
                            payee_role="TEST_PAYEE",
                            value_date=at,
                            state="SETTLED",
                            observed_at=at,
                        )
                    ]
                else:
                    records = [
                        RegistryRecord(
                            registration_id="registry-test",
                            state="REGISTERED",
                            collateral_reference="test-only:collateral",
                            secured_amount="100",
                            observed_at=at,
                        )
                    ]
    now = datetime.now(UTC)
    if kind == "LEDGER":
        async with database.session_factory() as session:
            internal = await build_internal_snapshot(session, target, legal_entity_id=legal_id)
            records = [
                LedgerRecord.model_validate(
                    {
                        **{k: (None if v == "null" else v) for k, v in r.fields.items()},
                        "observed_at": now,
                    }
                )
                for r in internal.records
            ]
    scope = {"pilot_scope": "test-only-pilot", **binding}
    policy_scope = {**scope, "reconciliation_type": kind}
    data = payload()
    data["reconciliation_type"] = kind
    represented = {
        "GUARANTEE_ISSUER": [
            "external_guarantee_id",
            "issued_amount",
            "currency",
            "state",
            "beneficiary",
        ],
        "CUSTODY": [
            "asset_position_id",
            "custody_reference",
            "asset_type",
            "quantity",
            "unit_code",
            "state",
        ],
        "LEDGER": ["balance", "account_code", "currency"],
        "SETTLEMENT": ["amount", "currency", "state"],
        "COLLATERAL_REGISTRY": ["registration_id", "secured_amount", "state"],
    }[kind]
    data["rules"] = [
        dict(
            rule_code=field.upper(),
            field_code=field,
            comparison_mode="DECIMAL_EXACT"
            if field in {"issued_amount", "quantity", "balance", "amount", "secured_amount"}
            else "EXACT",
            materiality="MATERIAL",
            reason_code="RECON_FIELD_MISMATCH",
            blocked_commands=["CloseGuaranteeCase"],
        )
        for field in represented
    ]
    data.update(policy_changes or {})
    policy_scope.update(component_scope_changes or {})
    async with database.session_factory() as session:
        async with session.begin():
            policy = PolicyVersion(
                policy_type="RECONCILIATION_POLICY",
                policy_code="TEST_" + kind,
                version_number=1,
                lifecycle_status="APPROVED",
                scope_definition=policy_scope,
                payload=data,
                payload_hash=canonical_request_hash(data),
                schema_version=RECON_SCHEMA,
                created_by=actor.id,
                approved_by=actor.id,
                approved_at=now,
                version=1,
            )
            session.add(policy)
            await session.flush()
            pack_data = {"component_version_ids": [str(policy.id)]}
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="TEST_PACK_" + kind,
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition=scope,
                payload=pack_data,
                payload_hash=canonical_request_hash(pack_data),
                schema_version="1",
                created_by=actor.id,
                approved_by=actor.id,
                approved_at=now,
                activated_at=now,
                version=1,
            )
            session.add(pack)
    return actor, target, legal_id, policy_scope, now, records


@pytest.fixture(params=IMPLEMENTED)
async def source_context(database, recon_context, request):
    return await seed_source(database, recon_context, request.param)


async def execute(database, context, snapshot=None, *, at=None, registry=None):
    actor, target, _, scope, now, records = context
    if registry is None:
        registry = ReconciliationSourceRegistry()
        registry.register(FixtureSourcePort(snapshot or make_snapshot(target, scope, now, records)))
    async with database.session_factory() as session:
        async with session.begin():
            return await run_source_reconciliation(
                session,
                target=target,
                registry=registry,
                actor_id=actor.id,
                actor_type=actor.identity_type,
                correlation_id=uuid4(),
                now=at or now,
            )


@pytest.mark.integration
async def test_represented_internal_sources_match_without_domain_mutation(database, source_context):
    async with database.session_factory() as session:
        before = {
            model.__tablename__: (await session.execute(select(model))).scalars().all()
            for model in [
                GuaranteeCase,
                AssetPosition,
                JournalEntry,
                JournalPosting,
                CreditProvider,
            ]
        }
        before_values = {
            name: [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in rows]
            for name, rows in before.items()
        }
    run = await execute(database, source_context)
    assert run.counts["MATCHED"] == len(source_context[-1])
    assert run.provider_id is None
    async with database.session_factory() as session:
        after = {
            model.__tablename__: [
                {c.name: getattr(row, c.name) for c in model.__table__.columns}
                for row in (await session.scalars(select(model))).all()
            ]
            for model in [
                GuaranteeCase,
                AssetPosition,
                JournalEntry,
                JournalPosting,
                CreditProvider,
            ]
        }
        assert before_values == after
        assert await session.scalar(
            select(func.count()).select_from(ReconciliationObservation)
        ) == len(source_context[-1])


@pytest.mark.integration
async def test_decimal_discrepancy_is_detected(database, source_context):
    _, target, _, scope, now, records = source_context
    field = {"GUARANTEE_ISSUER": "issued_amount", "CUSTODY": "quantity", "LEDGER": "balance"}[
        target.reconciliation_type
    ]
    altered = [records[0].model_copy(update={field: "100.000000000000000001"}), *records[1:]]
    run = await execute(database, source_context, make_snapshot(target, scope, now, altered))
    assert run.counts["MISMATCH"] == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    "mode", ["missing_external", "external_only", "duplicate", "stale", "future", "unavailable"]
)
async def test_negative_source_paths_never_match(database, source_context, mode):
    _, target, _, scope, now, records = source_context
    if mode == "unavailable":
        run = await execute(database, source_context, registry=ReconciliationSourceRegistry())
        assert run.status == "SOURCE_UNAVAILABLE" and run.counts["MATCHED"] == 0
        return
    changed = list(records)
    options = {}
    at = now
    if mode == "missing_external":
        changed = []
    elif mode == "duplicate":
        changed += [records[0]]
    elif mode == "external_only":
        field = {
            "GUARANTEE_ISSUER": "external_guarantee_id",
            "CUSTODY": "custody_reference",
            "LEDGER": "account_code",
        }[target.reconciliation_type]
        changed = [r.model_copy(update={field: "test-only:unknown"}) for r in records]
    elif mode == "stale":
        at += timedelta(seconds=601)
    else:
        options.update(
            snapshot_at=(now + timedelta(seconds=1)).isoformat(),
            received_at=(now + timedelta(seconds=1)).isoformat(),
        )
        changed = [
            r.model_copy(update={"observed_at": now + timedelta(seconds=1)}) for r in records
        ]
    run = await execute(
        database, source_context, make_snapshot(target, scope, now, changed, **options), at=at
    )
    assert run.counts["MISMATCH"] + run.counts["STALE"] >= 1
    if mode != "duplicate":
        assert run.counts["MATCHED"] == 0


@pytest.mark.integration
async def test_concurrent_replay_content_conflict_and_freshness(database, source_context):
    _, target, _, scope, now, records = source_context
    snapshot = make_snapshot(target, scope, now, records)
    first, second = await asyncio.gather(
        execute(database, source_context, snapshot), execute(database, source_context, snapshot)
    )
    assert first.id == second.id
    stale = await execute(database, source_context, snapshot, at=now + timedelta(seconds=601))
    assert stale.id != first.id and stale.counts["MATCHED"] == 0
    field = {"GUARANTEE_ISSUER": "issued_amount", "CUSTODY": "quantity", "LEDGER": "balance"}[
        target.reconciliation_type
    ]
    changed = make_snapshot(
        target, scope, now, [records[0].model_copy(update={field: "90"}), *records[1:]]
    )
    with pytest.raises(ApiError) as exc:
        await execute(database, source_context, changed, at=now + timedelta(seconds=601))
    assert exc.value.code == "RECON_SNAPSHOT_CONFLICT"


@pytest.mark.integration
@pytest.mark.parametrize("bad", ["scope", "identity", "contract", "hash", "raw", "type"])
async def test_source_boundary_rejects_mismatched_evidence(database, source_context, bad):
    _, target, _, scope, now, records = source_context
    snapshot = make_snapshot(target, scope, now, records)
    port = FixtureSourcePort(snapshot)
    updates = {
        "scope": {"scope_definition": {**scope, "pilot_scope": "caller"}},
        "identity": {"source_id": uuid4()},
        "contract": {"contract_version": "other"},
        "hash": {"content_hash": "0" * 64},
        "type": {"reconciliation_type": "LENDER"},
        "raw": {"provider_raw_payload": {"untrusted": True}},
    }[bad]
    port.snapshot = snapshot.model_copy(update=updates)
    # Registration identity remains the actual target, not the corrupted response.
    registry = ReconciliationSourceRegistry()
    registry.register(FixtureSourcePort(snapshot))
    registry._ports[(target.reconciliation_type, target.identity)] = port
    with pytest.raises(ApiError) as exc:
        await execute(database, source_context, registry=registry)
    assert exc.value.code == "RECON_MAPPING_MISMATCH"
    async with database.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ReconciliationRun)) == 0


@pytest.mark.integration
@pytest.mark.parametrize("kind", EXTERNAL)
@pytest.mark.parametrize(
    "change", ["suspended", "expired", "wrong_role", "scoped", "entity_inactive"]
)
async def test_source_role_current_validity_is_mandatory(database, recon_context, kind, change):
    values = (
        {"lifecycle_status": "SUSPENDED"}
        if change == "suspended"
        else (
            {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
            if change == "expired"
            else (
                {"role_code": "LENDER"}
                if change == "wrong_role"
                else ({"scope_definition": {"unsupported": "scope"}} if change == "scoped" else {})
            )
        )
    )
    context = await seed_source(database, recon_context, kind, authorization_changes=values)
    _, _, legal_id, _, _, _ = context
    if change == "entity_inactive":
        async with database.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(LegalEntity).where(LegalEntity.id == legal_id).values(status="INACTIVE")
                )
    with pytest.raises(ApiError) as exc:
        await execute(database, context)
    assert exc.value.code == (
        "RECON_SOURCE_IDENTITY_INVALID"
        if change == "entity_inactive"
        else "RECON_SOURCE_AUTHORIZATION_INVALID"
    )


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["SETTLEMENT", "COLLATERAL_REGISTRY"])
async def test_unimplemented_internal_acquisition_preserves_external_only_evidence(
    database, recon_context, kind
):
    context = await seed_source(database, recon_context, kind)
    run = await execute(database, context)
    assert run.status == "SOURCE_UNAVAILABLE" and run.counts["MATCHED"] == 0
    assert run.internal_cutoff is None
    assert run.source_metadata["internal_contract_gap"] is not None
    async with database.session_factory() as session:
        observation = await session.scalar(select(ReconciliationObservation))
        assert observation.difference_payload["internal_fields"] is None
        assert observation.difference_payload["external_fields"]
        assert await session.scalar(select(func.count()).select_from(JournalEntry)) == 0
    # Comparison capability exists for actual future owning-domain snapshots;
    # this test does not claim an implemented internal acquisition or a runtime match.
    record = context[-1][0]
    data = payload()
    data["reconciliation_type"] = kind
    field = "amount" if kind == "SETTLEMENT" else "secured_amount"
    data["rules"] = [
        dict(
            rule_code="AMOUNT",
            field_code=field,
            comparison_mode="DECIMAL_EXACT",
            materiality="MATERIAL",
            reason_code="RECON_FIELD_MISMATCH",
            blocked_commands=[],
        )
    ]
    rules = ReconciliationRules.model_validate(data)
    assert (
        compare_fields(canonical_fields(record), canonical_fields(record), rules).status
        == "MATCHED"
    )
    changed = record.model_copy(update={field: "99"})
    assert (
        compare_fields(canonical_fields(record), canonical_fields(changed), rules).status
        == "MISMATCH"
    )


@pytest.mark.parametrize("type_", EXTERNAL + ["LEDGER"])
@pytest.mark.parametrize(
    "forbidden",
    [
        "pilot_scope",
        "policy_pack_id",
        "policy_version_id",
        "rules",
        "snapshot",
        "materiality",
        "tolerance",
        "freshness",
        "status",
    ],
)
def test_discriminated_requests_reject_caller_policy_and_snapshot(type_, forbidden):
    request = {
        "reconciliation_type": type_,
        "program_id" if type_ == "LEDGER" else "source_legal_entity_id": str(uuid4()),
        forbidden: "caller",
    }
    with pytest.raises(ValidationError):
        TypeAdapter(RunBody).validate_python(request)


def test_lender_legacy_and_strict_typed_identity():
    provider = str(uuid4())
    assert (
        TypeAdapter(RunBody).validate_python({"provider_id": provider}).reconciliation_type
        == "LENDER"
    )
    with pytest.raises(ValidationError):
        TypeAdapter(RunBody).validate_python(
            {"reconciliation_type": "CUSTODY", "provider_id": provider}
        )


@pytest.mark.integration
async def test_multi_source_api_scoped_grants_and_replay(database, source_context, settings):
    actor, target, _, scope, now, records = source_context
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    app.state.reconciliation_source_registry.register(
        FixtureSourcePort(make_snapshot(target, scope, now, records))
    )
    body = target.model_dump(mode="json", exclude_none=True)
    headers = {"Authorization": f"Bearer {actor.external_subject}", "Idempotency-Key": str(uuid4())}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post(
                "/api/v1/reconciliation/runs", json=body, headers={"Idempotency-Key": "test"}
            )
        ).status_code == 401
        assert (
            await client.post("/api/v1/reconciliation/runs", json=body, headers=headers)
        ).status_code == 403
        async with database.session_factory() as session:
            async with session.begin():
                session.add(
                    RoleGrant(
                        identity_id=actor.id,
                        role_code="FINANCE_RECONCILIATION",
                        scope_type="PROGRAM" if target.program_id else "LEGAL_ENTITY",
                        scope_id=target.identity,
                        status="ACTIVE",
                        valid_from=now - timedelta(seconds=1),
                        reason_ref="test-only",
                    )
                )
        first = await client.post("/api/v1/reconciliation/runs", json=body, headers=headers)
        assert first.status_code == 201, first.text
        second = await client.post("/api/v1/reconciliation/runs", json=body, headers=headers)
        assert second.json() == first.json()
        assert (
            await client.get("/api/v1/reconciliation/runs/" + first.json()["id"], headers=headers)
        ).status_code == 200
        cases = await client.get("/api/v1/reconciliation/cases", params=body, headers=headers)
        assert cases.status_code == 200 and len(cases.json()) == len(records)
        assert (
            await client.get(
                "/api/v1/reconciliation/cases/" + cases.json()[0]["id"], headers=headers
            )
        ).status_code == 200
    assert app.openapi()["paths"]["/api/v1/reconciliation/runs"]["post"]["requestBody"]
    await app.state.database.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("transient", [None, True, False])
async def test_custody_missing_external_hard_invariant_requires_explicit_lag_classification(
    database, recon_context, transient
):
    changes = {} if transient is None else {"custody_missing_external_transient_lag": transient}
    context = await seed_source(database, recon_context, "CUSTODY", policy_changes=changes)
    _, target, _, scope, now, _ = context
    run = await execute(database, context, make_snapshot(target, scope, now, []))
    assert run.counts["MATCHED"] == 0
    assert run.counts["CRITICAL"] == (0 if transient is True else 1)


@pytest.mark.integration
@pytest.mark.parametrize("kind", IMPLEMENTED)
async def test_policy_of_another_type_does_not_authorize_source(database, recon_context, kind):
    context = await seed_source(
        database, recon_context, kind, component_scope_changes={"reconciliation_type": "SETTLEMENT"}
    )
    with pytest.raises(ApiError) as exc:
        await execute(database, context)
    assert exc.value.code == "RECON_POLICY_NOT_FOUND"


@pytest.mark.integration
async def test_issuer_missing_internal_issue_timestamp_cannot_match(database, recon_context):
    rule = dict(
        rule_code="ISSUED_AT",
        field_code="issued_at",
        comparison_mode="EXACT",
        materiality="MATERIAL",
        reason_code="RECON_ISSUE_TIME_MISSING",
        blocked_commands=[],
    )
    context = await seed_source(
        database, recon_context, "GUARANTEE_ISSUER", policy_changes={"rules": [rule]}
    )
    run = await execute(database, context)
    assert run.counts["MATCHED"] == 0 and run.counts["MISMATCH"] == 1


@pytest.mark.integration
async def test_empty_journal_scope_does_not_create_zero_or_match(database, recon_context):
    source_context = await seed_source(database, recon_context, "LEDGER")
    _, target, legal_id, scope, now, _ = source_context
    async with database.engine.begin() as connection:
        await connection.execute(text("TRUNCATE journal_postings, journal_entries CASCADE"))
    async with database.session_factory() as session:
        internal = await build_internal_snapshot(session, target, legal_entity_id=legal_id)
        assert internal.available and not internal.records
    run = await execute(database, source_context, make_snapshot(target, scope, now, []))
    assert run.counts["MATCHED"] == 0 and run.internal_cutoff is None


@pytest.mark.integration
async def test_atomic_rollback_of_multisource_run(database, source_context):
    actor, target, _, scope, now, records = source_context
    registry = ReconciliationSourceRegistry()
    registry.register(FixtureSourcePort(make_snapshot(target, scope, now, records)))
    async with database.session_factory() as session:
        await run_source_reconciliation(
            session,
            target=target,
            registry=registry,
            actor_id=actor.id,
            actor_type=actor.identity_type,
            correlation_id=uuid4(),
            now=now,
        )
        await session.rollback()
    async with database.session_factory() as session:
        for model in [
            ReconciliationRun,
            ReconciliationCase,
            ReconciliationObservation,
            ReconciliationCase,
            ReconciliationBlock,
            ReconciliationBlock,
        ]:
            assert await session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.integration
async def test_multisource_history_is_immutable(database, source_context):
    run = await execute(database, source_context)
    for model in [ReconciliationRun, ReconciliationObservation]:
        with pytest.raises(DBAPIError):
            async with database.engine.begin() as connection:
                await connection.execute(update(model).values(id=uuid4()))
    async with database.session_factory() as session:
        assert await session.get(ReconciliationRun, run.id) is not None


@pytest.mark.integration
async def test_scope_ambiguity_has_no_first_match(database, source_context):
    _, target, _, scope, now, _ = source_context
    binding = {k: v for k, v in scope.items() if k != "reconciliation_type"}
    async with database.session_factory() as session:
        async with session.begin():
            existing = await session.scalar(
                select(PolicyVersion).where(
                    PolicyVersion.policy_type == "PILOT_POLICY_PACK",
                    PolicyVersion.scope_definition == binding,
                )
            )
            other = {**binding, "pilot_scope": "test-only:other-pilot"}
            session.add(
                PolicyVersion(
                    policy_type="PILOT_POLICY_PACK",
                    policy_code="OTHER_TEST",
                    version_number=1,
                    lifecycle_status="ACTIVE",
                    scope_definition=other,
                    payload=existing.payload,
                    payload_hash=existing.payload_hash,
                    schema_version="1",
                    created_by=uuid4(),
                    approved_by=uuid4(),
                    approved_at=now,
                    activated_at=now,
                    version=1,
                )
            )
    with pytest.raises(ApiError) as exc:
        await execute(database, source_context)
    assert exc.value.code == "RECON_SCOPE_AMBIGUOUS"


@pytest.mark.integration
async def test_additive_migration_refuses_to_erase_multisource_history(database, recon_context):
    import os
    import subprocess
    import sys
    from pathlib import Path

    context = await seed_source(database, recon_context, "CUSTODY")
    run = await execute(database, context)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "20261007_0015"],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Cannot downgrade multi-source reconciliation history" in result.stderr
    async with database.session_factory() as session:
        assert await session.get(ReconciliationRun, run.id) is not None
        assert (
            await session.scalar(text("SELECT version_num FROM alembic_version")) == "20261007_0016"
        )


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["SETTLEMENT", "COLLATERAL_REGISTRY"])
async def test_unregistered_blocked_domain_source_is_unavailable(database, recon_context, kind):
    context = await seed_source(database, recon_context, kind)
    run = await execute(database, context, registry=ReconciliationSourceRegistry())
    assert run.status == "SOURCE_UNAVAILABLE" and run.counts["MATCHED"] == 0
    assert run.source_metadata["outage_reason"] == "SOURCE_UNAVAILABLE"


@pytest.mark.integration
async def test_port_timeout_is_normalized_and_safe(database, source_context):
    _, target, _, scope, now, records = source_context

    class TimeoutSource(FixtureSourcePort):
        async def fetch_reconciliation_snapshot(self, target, scope):
            raise TimeoutError("untrusted transport details")

    registry = ReconciliationSourceRegistry()
    registry.register(TimeoutSource(make_snapshot(target, scope, now, records)))
    run = await execute(database, source_context, registry=registry)
    assert run.status == "SOURCE_UNAVAILABLE" and run.counts["MATCHED"] == 0
    assert run.source_metadata["outage_reason"] == "SOURCE_TIMEOUT"
    assert "untrusted transport details" not in str(run.source_metadata)


@pytest.mark.integration
async def test_missing_scope_pack_fails_closed(database, source_context):
    _, _, _, scope, _, _ = source_context
    binding = {k: v for k, v in scope.items() if k != "reconciliation_type"}
    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                update(PolicyVersion)
                .where(
                    PolicyVersion.policy_type == "PILOT_POLICY_PACK",
                    PolicyVersion.scope_definition == binding,
                )
                .values(lifecycle_status="SUPERSEDED")
            )
    with pytest.raises(ApiError) as exc:
        await execute(database, source_context)
    assert exc.value.code == "RECON_SCOPE_NOT_FOUND"


@pytest.mark.integration
@pytest.mark.parametrize(
    "kind,field",
    [
        ("SETTLEMENT", "amount"),
        ("SETTLEMENT", "currency"),
        ("SETTLEMENT", "state"),
        ("COLLATERAL_REGISTRY", "state"),
        ("COLLATERAL_REGISTRY", "secured_amount"),
    ],
)
async def test_unblocked_canonical_comparison_contracts(database, recon_context, kind, field):
    context = await seed_source(database, recon_context, kind)
    record = context[-1][0]
    data = payload()
    data["reconciliation_type"] = kind
    data["rules"] = [
        dict(
            rule_code="FIELD",
            field_code=field,
            comparison_mode="DECIMAL_EXACT" if field in {"amount", "secured_amount"} else "EXACT",
            materiality="MATERIAL",
            reason_code="RECON_FIELD_MISMATCH",
            blocked_commands=[],
        )
    ]
    rules = ReconciliationRules.model_validate(data)
    original = canonical_fields(record)
    changed = record.model_copy(
        update={field: "99" if field in {"amount", "secured_amount"} else "DIFFERENT"}
    )
    assert compare_fields(original, canonical_fields(changed), rules).status == "MISMATCH"
