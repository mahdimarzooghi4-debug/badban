from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.idempotency import canonical_request_hash
from badban.application.lender_adapter import (
    AdapterHealth,
    LenderCapabilityManifest,
    LenderInboundRequest,
    LenderOperationResult,
    LenderOutboundCommand,
    LenderProviderState,
    LenderReconciliationLoan,
    LenderReconciliationScope,
    LenderReconciliationSnapshot,
    LenderStateQuery,
    NormalizedLenderEvent,
    TranslatedProviderError,
)
from badban.application.reconciliation import ReconciliationError, execute_lender_reconciliation
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AuditEvent,
    CreditProductVersion,
    CreditProvider,
    ExternalLoanMirror,
    GuaranteeCase,
    Identity,
    JournalEntry,
    LegalEntity,
    OutboxMessage,
    Participant,
    ParticipationEpisode,
    PolicyVersion,
    Program,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
    RoleGrant,
)
from badban.security.authorization import ROLE_FINANCE_RECONCILIATION, SCOPE_PROVIDER


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


class SnapshotAdapter:
    def __init__(
        self,
        provider_id: UUID,
        snapshot: LenderReconciliationSnapshot,
        *,
        error: Exception | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.snapshot = snapshot
        self.error = error

    def capability_manifest(self) -> LenderCapabilityManifest:
        return LenderCapabilityManifest(
            integration_modes=frozenset({"POLLING"}),
            supported_commands=frozenset(),
            supported_inbound_events=frozenset(),
            authentication_method="TEST_ONLY",
            supports_polling=True,
            supports_webhook=False,
            supports_reconciliation_snapshot=True,
            supports_idempotency_key=False,
            supports_event_sequence=False,
            provider_contract_version="test-provider-v1",
            adapter_mapping_version="test-mapping-v1",
            inbound_normalization_version="test-normalization-v1",
            outbound_mapping_version="test-outbound-v1",
        )

    async def submit_command(self, command: LenderOutboundCommand) -> LenderOperationResult:
        raise AssertionError("submit_command is not used by reconciliation tests")

    async def fetch_state(self, query: LenderStateQuery) -> LenderProviderState:
        raise AssertionError("fetch_state is not used by reconciliation tests")

    async def verify_and_normalize(
        self,
        request: LenderInboundRequest,
    ) -> NormalizedLenderEvent:
        raise AssertionError("verify_and_normalize is not used by reconciliation tests")

    async def fetch_reconciliation_snapshot(
        self,
        scope: LenderReconciliationScope,
    ) -> LenderReconciliationSnapshot:
        assert scope.provider_id == self.provider_id
        if self.error is not None:
            raise self.error
        return self.snapshot

    def translate_error(self, error: Exception) -> TranslatedProviderError:
        return TranslatedProviderError(
            code="PROVIDER_UNAVAILABLE",
            classification="RETRYABLE",
        )

    async def health_check(self) -> AdapterHealth:
        return "AVAILABLE"


@pytest.fixture
async def clean_sprint14_reconciliation_tables(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "reconciliation_observations, reconciliation_cases, reconciliation_runs, "
                "external_loan_events, external_loan_mirrors, guarantee_cases, "
                "credit_product_versions, credit_providers, legal_authorizations, legal_entities, "
                "portfolio_risk_snapshots, decision_snapshots, policy_versions, "
                "journal_postings, journal_entries, participation_episodes, "
                "role_grants, audit_events, evidence_references, programs, participants, "
                "asset_positions, asset_types, identities, idempotency_records, "
                "outbox_messages, inbox_messages "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


def _rules(*, max_age: int = 300, materiality: str = "WARNING") -> dict[str, object]:
    return {
        "reconciliation_rules": {
            "LENDER_EXTERNAL_LOAN": {
                "max_source_age_seconds": max_age,
                "materiality_by_reason": {
                    "RECON_EXTERNAL_RECORD_MISSING": materiality,
                    "RECON_INTERNAL_RECORD_MISSING": materiality,
                    "RECON_AMOUNT_MISMATCH": materiality,
                    "RECON_STATE_MISMATCH": materiality,
                    "RECON_IDENTIFIER_MISMATCH": materiality,
                    "RECON_DUPLICATE_EXTERNAL_RECORD": materiality,
                    "RECON_SOURCE_STALE": materiality,
                },
                "decimal_tolerance_by_field": {},
            }
        }
    }


async def _seed(
    database,
    *,
    include_reconciliation_policy: bool = True,
    materiality: str = "WARNING",
    max_age: int = 300,
):
    now = datetime.now(UTC)
    operator = Identity(
        identity_type="STAFF",
        external_subject=f"sprint14-operator-{uuid4()}",
        status="ACTIVE",
    )
    outsider = Identity(
        identity_type="AUDITOR",
        external_subject=f"sprint14-outsider-{uuid4()}",
        status="ACTIVE",
    )
    participant = Participant(
        external_reference=f"sprint14-participant-{uuid4()}",
        lifecycle_status="ACTIVE",
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([operator, outsider, participant])
            await session.flush()

            program = Program(
                code=f"SPRINT14-{uuid4()}",
                name="Sprint 14 Program",
                status="ACTIVE",
                legal_entity_id=None,
                created_by=operator.id,
                version=1,
            )
            lender_entity = LegalEntity(
                legal_name="Sprint 14 Lender",
                registration_identifier=f"SPRINT14-LENDER-{uuid4()}",
                entity_type="EXTERNAL_LENDER",
                status="ACTIVE",
                created_by=operator.id,
                version=1,
            )
            session.add_all([program, lender_entity])
            await session.flush()

            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                eligibility_reference="sprint14-test",
                consent_state="ACCEPTED",
                started_at=now - timedelta(days=1),
                ended_at=None,
                created_by=operator.id,
                version=1,
            )
            provider = CreditProvider(
                legal_entity_id=lender_entity.id,
                provider_code=f"SPRINT14-LENDER-{uuid4()}",
                display_name="Sprint 14 Test Lender",
                provider_type="EXTERNAL_LENDER",
                integration_mode="POLLING",
                authorization_review_state="TEST",
                lifecycle_status="ACTIVE",
                activated_at=now - timedelta(minutes=1),
                created_by=operator.id,
                version=1,
            )
            session.add_all([episode, provider])
            await session.flush()

            product = CreditProductVersion(
                provider_id=provider.id,
                lender_of_record_legal_entity_id=lender_entity.id,
                product_code=f"SPRINT14-PRODUCT-{uuid4()}",
                version_number=1,
                product_name="Sprint 14 Product",
                product_type="EXTERNAL_CREDIT",
                lifecycle_status="ACTIVE",
                currency="IRR",
                min_principal=Decimal("1"),
                max_principal=Decimal("1000"),
                tenor_definition={"reference": "test"},
                repayment_definition={"reference": "test"},
                pricing_definition={"reference": "test"},
                guarantee_mode="FIXED",
                delinquency_definition={"reference": "test"},
                claim_definition={"reference": "test"},
                policy_version_reference="test-policy:1",
                additional_terms={},
                effective_from=now - timedelta(minutes=1),
                activated_at=now - timedelta(minutes=1),
                created_by=operator.id,
                version=1,
            )
            session.add(product)
            await session.flush()

            guarantee = GuaranteeCase(
                participation_episode_id=episode.id,
                provider_id=provider.id,
                credit_product_version_id=product.id,
                policy_pack_id=None,
                state="ISSUED",
                requested_principal=Decimal("100"),
                reserved_guarantee_amount=Decimal("100"),
                issued_guarantee_amount=Decimal("100"),
                current_guarantee_exposure=Decimal("0"),
                guarantee_mode="FIXED",
                reservation_expires_at=now + timedelta(days=1),
                legal_guarantee_external_id=f"SPRINT14-GUARANTEE-{uuid4()}",
                legal_guarantee_issuer_id=None,
                external_loan_mirror_id=None,
                risk_snapshot_id=None,
                version=1,
            )
            session.add(guarantee)
            await session.flush()

            mirror = ExternalLoanMirror(
                guarantee_case_id=guarantee.id,
                provider_id=provider.id,
                external_loan_id="loan-1",
                state="ACTIVE",
                original_principal=Decimal("100"),
                outstanding_principal=Decimal("75"),
                currency="IRR",
                disbursed_at=now - timedelta(hours=1),
                settled_at=None,
                delinquency_state=None,
                last_provider_event_at=now - timedelta(minutes=1),
                last_provider_event_sequence=3,
                last_synced_at=now - timedelta(minutes=1),
                reconciliation_status=None,
                version=1,
            )
            session.add(mirror)
            await session.flush()
            guarantee.external_loan_mirror_id = mirror.id

            policy_ids: list[str] = []
            if include_reconciliation_policy:
                rules = _rules(max_age=max_age, materiality=materiality)
                recon_policy = PolicyVersion(
                    policy_type="RECONCILIATION_POLICY",
                    policy_code="SPRINT14_RECON",
                    version_number=1,
                    lifecycle_status="APPROVED",
                    scope_definition={"pilot_scope": "bounded-pilot"},
                    payload=rules,
                    payload_hash=canonical_request_hash(rules),
                    schema_version="1",
                    approved_at=now - timedelta(minutes=2),
                    approved_by=operator.id,
                    created_by=operator.id,
                    version=3,
                )
                session.add(recon_policy)
                await session.flush()
                policy_ids.append(str(recon_policy.id))

            pack_payload = {"component_version_ids": policy_ids}
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="SPRINT14_PACK",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition={"pilot_scope": "bounded-pilot"},
                payload=pack_payload,
                payload_hash=canonical_request_hash(pack_payload),
                schema_version="1",
                approved_at=now - timedelta(minutes=2),
                activated_at=now - timedelta(minutes=1),
                approved_by=operator.id,
                created_by=operator.id,
                version=4,
            )
            session.add(pack)
            session.add(
                RoleGrant(
                    identity_id=operator.id,
                    role_code=ROLE_FINANCE_RECONCILIATION,
                    scope_type=SCOPE_PROVIDER,
                    scope_id=provider.id,
                    valid_from=now - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint14-test",
                    version=1,
                )
            )
            await session.flush()

    return operator, outsider, provider, guarantee, mirror


def _snapshot(
    provider_id: UUID,
    *,
    snapshot_at: datetime | None = None,
    loans: list[LenderReconciliationLoan] | None = None,
) -> LenderReconciliationSnapshot:
    return LenderReconciliationSnapshot(
        provider_id=provider_id,
        snapshot_at=snapshot_at or datetime.now(UTC),
        source_reference="test-statement-sprint14",
        evidence_references=["evidence:test:sprint14-statement"],
        loans=loans
        if loans is not None
        else [
            LenderReconciliationLoan(
                external_loan_id="loan-1",
                original_principal="100",
                outstanding_principal="75",
                currency="IRR",
                provider_state="ACTIVE",
                observed_at=datetime.now(UTC),
            )
        ],
    )


async def _execute(
    database,
    provider: CreditProvider,
    operator: Identity,
    adapter: SnapshotAdapter,
):
    from badban.application.lender_adapter import LenderAdapterRegistry

    registry = LenderAdapterRegistry()
    registry.register(provider.id, adapter)
    return await execute_lender_reconciliation(
        database,
        registry,
        provider_id=provider.id,
        scope_definition={"pilot_scope": "bounded-pilot"},
        scope_reference=None,
        actor_type=operator.identity_type,
        actor_id=operator.id,
        correlation_id=uuid4(),
    )


@pytest.mark.integration
async def test_exact_match_is_idempotent_and_does_not_mutate_financial_state(
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    operator, _, provider, guarantee, mirror = await _seed(database)
    adapter = SnapshotAdapter(provider.id, _snapshot(provider.id))

    first_id = await _execute(database, provider, operator, adapter)
    second_id = await _execute(database, provider, operator, adapter)
    assert second_id == first_id

    async with database.session_factory() as session:
        run = await session.get(ReconciliationRun, first_id)
        cases = (
            await session.scalars(
                select(ReconciliationCase).where(ReconciliationCase.run_id == first_id)
            )
        ).all()
        stored_guarantee = await session.get(GuaranteeCase, guarantee.id)
        stored_mirror = await session.get(ExternalLoanMirror, mirror.id)
        run_count = int(
            await session.scalar(select(func.count()).select_from(ReconciliationRun)) or 0
        )
        journal_count = int(
            await session.scalar(select(func.count()).select_from(JournalEntry)) or 0
        )

    assert run is not None
    assert run.status == "COMPLETED"
    assert run.matched_count == 1
    assert run.mismatch_count == 0
    assert run.stale_count == 0
    assert run_count == 1
    assert len(cases) == 1
    assert cases[0].status == "MATCHED"
    assert stored_mirror is not None and stored_mirror.reconciliation_status == "MATCHED"
    assert stored_guarantee is not None
    assert stored_guarantee.state == "ISSUED"
    assert stored_guarantee.issued_guarantee_amount == Decimal("100")
    assert stored_guarantee.current_guarantee_exposure == Decimal("0")
    assert journal_count == 0


@pytest.mark.integration
async def test_hard_guarantee_loan_principal_mismatch_is_always_critical(
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    operator, _, provider, guarantee, _ = await _seed(database, materiality="INFO")
    adapter = SnapshotAdapter(
        provider.id,
        _snapshot(
            provider.id,
            loans=[
                LenderReconciliationLoan(
                    external_loan_id="loan-1",
                    original_principal="90",
                    outstanding_principal="75",
                    currency="IRR",
                    provider_state="ACTIVE",
                    observed_at=datetime.now(UTC),
                )
            ],
        ),
    )

    run_id = await _execute(database, provider, operator, adapter)

    async with database.session_factory() as session:
        run = await session.get(ReconciliationRun, run_id)
        hard_case = await session.scalar(
            select(ReconciliationCase).where(
                ReconciliationCase.run_id == run_id,
                ReconciliationCase.mismatch_reason_code
                == "RECON_GUARANTEE_LOAN_PRINCIPAL_MISMATCH",
            )
        )
        stored_guarantee = await session.get(GuaranteeCase, guarantee.id)

    assert run is not None and run.critical_count == 1
    assert hard_case is not None
    assert hard_case.materiality == "CRITICAL"
    assert stored_guarantee is not None
    assert stored_guarantee.state == "ISSUED"
    assert stored_guarantee.issued_guarantee_amount == Decimal("100")


@pytest.mark.integration
async def test_stale_source_never_becomes_matched(
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    operator, _, provider, _, mirror = await _seed(database, max_age=30)
    adapter = SnapshotAdapter(
        provider.id,
        _snapshot(provider.id, snapshot_at=datetime.now(UTC) - timedelta(minutes=2)),
    )

    run_id = await _execute(database, provider, operator, adapter)

    async with database.session_factory() as session:
        run = await session.get(ReconciliationRun, run_id)
        cases = (
            await session.scalars(
                select(ReconciliationCase).where(ReconciliationCase.run_id == run_id)
            )
        ).all()
        stored_mirror = await session.get(ExternalLoanMirror, mirror.id)

    assert run is not None
    assert run.matched_count == 0
    assert run.stale_count == 1
    assert len(cases) == 1
    assert cases[0].status == "STALE"
    assert cases[0].mismatch_reason_code == "RECON_SOURCE_STALE"
    assert stored_mirror is not None
    assert stored_mirror.reconciliation_status == "STALE"


@pytest.mark.integration
async def test_missing_duplicate_and_internal_only_records_are_explicit_cases(
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    operator, _, provider, _, _ = await _seed(database)
    loan2 = LenderReconciliationLoan(
        external_loan_id="loan-2",
        original_principal="50",
        outstanding_principal="50",
        currency="IRR",
        provider_state="PENDING",
        observed_at=datetime.now(UTC),
    )
    loan3 = LenderReconciliationLoan(
        external_loan_id="loan-3",
        original_principal="60",
        outstanding_principal="60",
        currency="IRR",
        provider_state="PENDING",
        observed_at=datetime.now(UTC),
    )
    adapter = SnapshotAdapter(
        provider.id,
        _snapshot(provider.id, loans=[loan2, loan2.model_copy(), loan3]),
    )

    run_id = await _execute(database, provider, operator, adapter)
    async with database.session_factory() as session:
        reasons = set(
            (
                await session.scalars(
                    select(ReconciliationCase.mismatch_reason_code).where(
                        ReconciliationCase.run_id == run_id
                    )
                )
            ).all()
        )

    assert "RECON_EXTERNAL_RECORD_MISSING" in reasons
    assert "RECON_DUPLICATE_EXTERNAL_RECORD" in reasons
    assert "RECON_INTERNAL_RECORD_MISSING" in reasons


@pytest.mark.integration
async def test_amount_currency_and_state_differences_are_separate_auditable_cases(
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    operator, _, provider, _, _ = await _seed(database)
    adapter = SnapshotAdapter(
        provider.id,
        _snapshot(
            provider.id,
            loans=[
                LenderReconciliationLoan(
                    external_loan_id="loan-1",
                    original_principal="100",
                    outstanding_principal="70",
                    currency="USD",
                    provider_state="DELINQUENT",
                    observed_at=datetime.now(UTC),
                )
            ],
        ),
    )

    run_id = await _execute(database, provider, operator, adapter)
    async with database.session_factory() as session:
        reasons = set(
            (
                await session.scalars(
                    select(ReconciliationCase.mismatch_reason_code).where(
                        ReconciliationCase.run_id == run_id
                    )
                )
            ).all()
        )

    assert {
        "RECON_AMOUNT_MISMATCH",
        "RECON_IDENTIFIER_MISMATCH",
        "RECON_STATE_MISMATCH",
    } <= reasons


@pytest.mark.integration
async def test_missing_policy_and_missing_adapter_fail_closed(
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    from badban.application.lender_adapter import LenderAdapterRegistry

    operator, _, provider, _, _ = await _seed(
        database,
        include_reconciliation_policy=False,
    )
    registry = LenderAdapterRegistry()
    registry.register(provider.id, SnapshotAdapter(provider.id, _snapshot(provider.id)))

    with pytest.raises(ReconciliationError) as policy_exc:
        await execute_lender_reconciliation(
            database,
            registry,
            provider_id=provider.id,
            scope_definition={"pilot_scope": "bounded-pilot"},
            scope_reference=None,
            actor_type=operator.identity_type,
            actor_id=operator.id,
            correlation_id=uuid4(),
        )
    assert policy_exc.value.code == "RECONCILIATION_POLICY_MISSING"

    async with database.session_factory() as session:
        assert (
            int(await session.scalar(select(func.count()).select_from(ReconciliationRun)) or 0) == 0
        )


@pytest.mark.integration
async def test_observations_are_append_only_and_api_has_no_resolution_mutation(
    settings: Settings,
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    operator, outsider, provider, _, _ = await _seed(database)
    run_id = await _execute(
        database,
        provider,
        operator,
        SnapshotAdapter(provider.id, _snapshot(provider.id)),
    )

    async with database.session_factory() as session:
        observation = await session.scalar(
            select(ReconciliationObservation)
            .join(
                ReconciliationCase,
                ReconciliationCase.id == ReconciliationObservation.reconciliation_case_id,
            )
            .where(ReconciliationCase.run_id == run_id)
        )
        assert observation is not None
        observation_id = observation.id

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(ReconciliationObservation)
                    .where(ReconciliationObservation.id == observation_id)
                    .values(difference_payload={"mutated": True})
                )
    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    delete(ReconciliationObservation).where(
                        ReconciliationObservation.id == observation_id
                    )
                )

    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    schema = app.openapi()
    assert "/api/v1/reconciliation/runs" in schema["paths"]
    assert "/api/v1/reconciliation/cases" in schema["paths"]
    assert "/api/v1/reconciliation/cases/{case_id}/resolve" not in schema["paths"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        allowed = await client.get(
            f"/api/v1/reconciliation/runs/{run_id}",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
        )
        denied = await client.get(
            f"/api/v1/reconciliation/runs/{run_id}",
            headers={"Authorization": f"Bearer {outsider.external_subject}"},
        )
    assert allowed.status_code == 200
    assert denied.status_code == 403


@pytest.mark.integration
async def test_unconfigured_adapter_records_outage_audit_without_creating_run(
    database,
    clean_sprint14_reconciliation_tables,
) -> None:
    from badban.application.lender_adapter import LenderAdapterRegistry

    operator, _, provider, _, _ = await _seed(database)
    with pytest.raises(ReconciliationError) as exc:
        await execute_lender_reconciliation(
            database,
            LenderAdapterRegistry(),
            provider_id=provider.id,
            scope_definition={"pilot_scope": "bounded-pilot"},
            scope_reference=None,
            actor_type=operator.identity_type,
            actor_id=operator.id,
            correlation_id=uuid4(),
        )

    assert exc.value.code == "LENDER_ADAPTER_NOT_CONFIGURED"
    async with database.session_factory() as session:
        run_count = int(
            await session.scalar(select(func.count()).select_from(ReconciliationRun)) or 0
        )
        audit = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.aggregate_type == "CreditProvider",
                AuditEvent.aggregate_id == str(provider.id),
                AuditEvent.action == "RECONCILIATION_SOURCE_UNAVAILABLE",
            )
        )
        event_types = set((await session.scalars(select(OutboxMessage.event_type))).all())

    assert run_count == 0
    assert audit is not None
    assert "ReconciliationRunCompleted" not in event_types
