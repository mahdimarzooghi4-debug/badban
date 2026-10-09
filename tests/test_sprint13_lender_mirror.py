from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.external_loan import (
    ExternalLoanError,
    _lender_mirror_lock_key,
    process_lender_inbox_message,
    process_pending_lender_inbox_batch,
)
from badban.application.integration_events import process_inbox_message_once
from badban.application.lender_adapter import (
    LenderAdapterError,
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
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    CreditProductVersion,
    CreditProvider,
    ExternalLoanEvent,
    ExternalLoanMirror,
    GuaranteeCase,
    Identity,
    InboxMessage,
    JournalEntry,
    LegalEntity,
    Participant,
    ParticipationEpisode,
    Program,
    RoleGrant,
)
from badban.security.authorization import ROLE_AUDITOR, SCOPE_PROVIDER


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


class TestLenderAdapter:
    _STATUS_MAP: dict[
        str,
        Literal[
            "LOAN_APPROVED",
            "LOAN_DISBURSED",
            "REPAYMENT_RECEIVED",
            "LOAN_DELINQUENT",
            "LOAN_SETTLED",
            "LOAN_CORRECTED",
        ],
    ] = {
        "approved": "LOAN_APPROVED",
        "funded": "LOAN_DISBURSED",
        "paid": "REPAYMENT_RECEIVED",
        "late": "LOAN_DELINQUENT",
        "closed": "LOAN_SETTLED",
        "corrected": "LOAN_CORRECTED",
    }

    def __init__(self, provider_id: UUID, *, supports_sequence: bool = True) -> None:
        self.provider_id = provider_id
        self.supports_sequence = supports_sequence

    def capability_manifest(self) -> LenderCapabilityManifest:
        return LenderCapabilityManifest(
            integration_modes=frozenset({"WEBHOOK_CALLBACK"}),
            supported_commands=frozenset({"QUERY_LOAN_STATE"}),
            supported_inbound_events=frozenset(self._STATUS_MAP.values()),
            authentication_method="TEST_SIGNATURE",
            supports_polling=True,
            supports_webhook=True,
            supports_reconciliation_snapshot=True,
            supports_idempotency_key=True,
            supports_event_sequence=self.supports_sequence,
            rate_limit_policy_reference="test-only",
            provider_contract_version="provider-test-v1",
            adapter_mapping_version="mapping-test-v1",
            inbound_normalization_version="normalize-test-v1",
            outbound_mapping_version="outbound-test-v1",
        )

    async def verify_and_normalize(
        self,
        request: LenderInboundRequest,
    ) -> NormalizedLenderEvent:
        if request.headers.get("x-test-signature") != "valid":
            raise LenderAdapterError(
                "PROVIDER_AUTHENTICATION_FAILED",
                "test signature rejected",
            )
        raw = json.loads(request.body)
        try:
            event_type = self._STATUS_MAP[raw["provider_status"]]
        except (KeyError, TypeError) as exc:
            raise LenderAdapterError(
                "PROVIDER_CONTRACT_MISMATCH",
                "unknown test provider status",
            ) from exc

        digest = hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return NormalizedLenderEvent(
            provider_id=UUID(raw.get("provider_id", str(self.provider_id))),
            external_event_id=raw["external_event_id"],
            event_type=event_type,
            schema_version=1,
            external_loan_id=raw["external_loan_id"],
            event_time=datetime.fromisoformat(raw["event_time"]),
            received_at=request.received_at,
            original_principal=raw["original_principal"],
            disbursed_principal=raw.get("disbursed_principal"),
            outstanding_principal=raw["outstanding_principal"],
            currency=raw.get("currency", "IRR"),
            repayment_reference=raw.get("repayment_reference"),
            delinquency_state=raw.get("delinquency_state"),
            evidence_references=raw.get("evidence_references", []),
            payload_hash=digest,
            provider_contract_version="provider-test-v1",
            adapter_mapping_version=raw.get("adapter_mapping_version", "mapping-test-v1"),
            inbound_normalization_version="normalize-test-v1",
            provider_event_sequence=raw.get("sequence"),
            guarantee_case_id=(
                UUID(raw["guarantee_case_id"]) if raw.get("guarantee_case_id") is not None else None
            ),
        )

    async def submit_command(self, command: LenderOutboundCommand) -> LenderOperationResult:
        return LenderOperationResult(state="CONFIRMED")

    async def fetch_state(self, query: LenderStateQuery) -> LenderProviderState:
        return LenderProviderState(
            provider_id=query.provider_id,
            external_loan_id=query.external_loan_id,
            provider_state="ACTIVE",
            observed_at=datetime.now(UTC),
        )

    async def fetch_reconciliation_snapshot(
        self,
        scope: LenderReconciliationScope,
    ) -> LenderReconciliationSnapshot:
        return LenderReconciliationSnapshot(
            provider_id=scope.provider_id,
            snapshot_at=datetime.now(UTC),
            source_reference="test-statement-1",
            evidence_references=["evidence:test:statement-1"],
            loans=[
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

    def translate_error(self, error: Exception) -> TranslatedProviderError:
        return TranslatedProviderError(
            code="PROVIDER_CONTRACT_MISMATCH",
            classification="NON_RETRYABLE",
        )

    async def health_check(self) -> str:
        return "AVAILABLE"


@pytest.fixture
async def clean_sprint13_lender_tables(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "external_loan_events, external_loan_mirrors, "
                "guarantee_cases, credit_product_versions, credit_providers, "
                "legal_authorizations, legal_entities, journal_postings, journal_entries, "
                "participation_episodes, role_grants, audit_events, evidence_references, "
                "programs, participants, identities, idempotency_records, "
                "outbox_messages, inbox_messages, lender_inbox_scan_checkpoints "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


async def _seed_context(database):
    auditor = Identity(
        identity_type="AUDITOR",
        external_subject=f"sprint13-auditor-{uuid4()}",
        status="ACTIVE",
    )
    participant = Participant(
        external_reference=f"sprint13-participant-{uuid4()}",
        lifecycle_status="ACTIVE",
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([auditor, participant])
            await session.flush()

            program = Program(
                code=f"SPRINT13-{uuid4()}",
                name="Sprint 13 Program",
                status="ACTIVE",
                legal_entity_id=None,
                created_by=auditor.id,
                version=1,
            )
            entity = LegalEntity(
                legal_name="Sprint 13 Lender",
                registration_identifier=f"LENDER-{uuid4()}",
                entity_type="EXTERNAL_LENDER",
                status="ACTIVE",
                created_by=auditor.id,
                version=1,
            )
            session.add_all([program, entity])
            await session.flush()

            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                eligibility_reference="sprint13-test",
                consent_state="ACCEPTED",
                started_at=datetime.now(UTC) - timedelta(days=1),
                ended_at=None,
                created_by=auditor.id,
                version=1,
            )
            provider = CreditProvider(
                legal_entity_id=entity.id,
                provider_code=f"LENDER-{uuid4()}",
                display_name="Sprint 13 Test Lender",
                provider_type="EXTERNAL_LENDER",
                integration_mode="WEBHOOK_CALLBACK",
                authorization_review_state="TEST",
                lifecycle_status="ACTIVE",
                created_by=auditor.id,
                activated_at=datetime.now(UTC) - timedelta(minutes=1),
                version=1,
            )
            session.add_all([episode, provider])
            await session.flush()

            product = CreditProductVersion(
                provider_id=provider.id,
                lender_of_record_legal_entity_id=entity.id,
                product_code=f"PRODUCT-{uuid4()}",
                version_number=1,
                product_name="Sprint 13 Product",
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
                effective_from=datetime.now(UTC) - timedelta(minutes=1),
                activated_at=datetime.now(UTC) - timedelta(minutes=1),
                created_by=auditor.id,
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
                reservation_expires_at=datetime.now(UTC) + timedelta(days=1),
                legal_guarantee_external_id=f"GUARANTEE-{uuid4()}",
                legal_guarantee_issuer_id=None,
                external_loan_mirror_id=None,
                risk_snapshot_id=None,
                version=1,
            )
            session.add(guarantee)
            session.add(
                RoleGrant(
                    identity_id=auditor.id,
                    role_code=ROLE_AUDITOR,
                    scope_type=SCOPE_PROVIDER,
                    scope_id=provider.id,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint13-read",
                    version=1,
                )
            )
            await session.flush()

    return auditor, provider, guarantee


def _raw_event(
    provider: CreditProvider,
    *,
    status: str,
    event_id: str,
    sequence: int | None,
    guarantee_id: UUID | None = None,
    event_time: datetime | None = None,
    original: str = "100",
    outstanding: str = "100",
    disbursed: str | None = None,
    repayment_reference: str | None = None,
    delinquency_state: str | None = None,
    adapter_mapping_version: str = "mapping-test-v1",
) -> dict[str, object]:
    return {
        "provider_id": str(provider.id),
        "provider_status": status,
        "external_event_id": event_id,
        "external_loan_id": "loan-1",
        "event_time": (event_time or datetime.now(UTC)).isoformat(),
        "original_principal": original,
        "outstanding_principal": outstanding,
        "disbursed_principal": disbursed,
        "currency": "IRR",
        "repayment_reference": repayment_reference,
        "delinquency_state": delinquency_state,
        "evidence_references": [f"evidence:test:{event_id}"],
        "sequence": sequence,
        "guarantee_case_id": str(guarantee_id) if guarantee_id else None,
        "adapter_mapping_version": adapter_mapping_version,
    }


async def _app_client(settings: Settings):
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return app, AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.integration
async def test_lender_endpoint_fails_closed_without_configured_adapter(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)
    app, client = await _app_client(settings)
    async with client:
        response = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="approved",
                event_id="evt-1",
                sequence=1,
            ),
        )

    assert app.state.lender_adapter_registry is not None
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LENDER_ADAPTER_NOT_CONFIGURED"
    async with database.session_factory() as session:
        assert int(await session.scalar(select(func.count()).select_from(InboxMessage)) or 0) == 0


@pytest.mark.integration
async def test_authentication_failure_creates_no_inbox_event(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))

    async with client:
        response = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "invalid"},
            json=_raw_event(
                provider,
                status="approved",
                event_id="evt-auth-fail",
                sequence=1,
            ),
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PROVIDER_AUTHENTICATION_FAILED"
    async with database.session_factory() as session:
        assert int(await session.scalar(select(func.count()).select_from(InboxMessage)) or 0) == 0


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("approved", "LOAN_APPROVED"),
        ("funded", "LOAN_DISBURSED"),
        ("paid", "REPAYMENT_RECEIVED"),
        ("late", "LOAN_DELINQUENT"),
        ("closed", "LOAN_SETTLED"),
        ("corrected", "LOAN_CORRECTED"),
    ],
)
async def test_test_adapter_maps_provider_status_to_canonical_event(
    status: str,
    expected: str,
) -> None:
    provider_id = uuid4()
    adapter = TestLenderAdapter(provider_id)
    raw = {
        "provider_status": status,
        "external_event_id": "evt",
        "external_loan_id": "loan-1",
        "event_time": datetime.now(UTC).isoformat(),
        "original_principal": "100",
        "outstanding_principal": "100",
        "disbursed_principal": "100" if status == "funded" else None,
        "repayment_reference": "rep-1" if status == "paid" else None,
        "delinquency_state": "PAST_DUE" if status == "late" else None,
        "sequence": 1,
    }
    event = await adapter.verify_and_normalize(
        LenderInboundRequest(
            provider_id=provider_id,
            body=json.dumps(raw).encode(),
            headers={"x-test-signature": "valid"},
            received_at=datetime.now(UTC),
            correlation_id=uuid4(),
        )
    )
    assert event.event_type == expected


def test_normalized_lender_event_rejects_missing_event_specific_fields_and_naive_time() -> None:
    common = {
        "provider_id": uuid4(),
        "external_event_id": "event-1",
        "schema_version": 1,
        "external_loan_id": "loan-1",
        "event_time": datetime.now(UTC),
        "received_at": datetime.now(UTC),
        "original_principal": "100",
        "outstanding_principal": "100",
        "currency": "IRR",
        "evidence_references": [],
        "payload_hash": "a" * 64,
        "provider_contract_version": "v1",
        "adapter_mapping_version": "v1",
        "inbound_normalization_version": "v1",
    }

    with pytest.raises(ValidationError):
        NormalizedLenderEvent(**common, event_type="LOAN_DISBURSED")
    with pytest.raises(ValidationError):
        NormalizedLenderEvent(**common, event_type="REPAYMENT_RECEIVED")
    with pytest.raises(ValidationError):
        NormalizedLenderEvent(**common, event_type="LOAN_DELINQUENT")
    with pytest.raises(ValidationError):
        NormalizedLenderEvent(
            **{
                **common,
                "event_type": "LOAN_APPROVED",
                "event_time": datetime(2026, 10, 7, 12, 0, 0),
            }
        )
    with pytest.raises(ValidationError):
        NormalizedLenderEvent(
            **{
                **common,
                "event_type": "LOAN_APPROVED",
                "original_principal": "100000000000000000000",
                "outstanding_principal": "1",
            }
        )
    with pytest.raises(ValidationError):
        NormalizedLenderEvent(
            **{
                **common,
                "event_type": "LOAN_APPROVED",
                "original_principal": "1.0000000000000000001",
                "outstanding_principal": "1",
            }
        )


@pytest.mark.integration
async def test_ingestion_is_idempotent_and_changed_payload_fails_closed(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))
    payload = _raw_event(provider, status="approved", event_id="evt-idem", sequence=1)

    async with client:
        first = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=payload,
        )
        duplicate = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=payload,
        )
        changed = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json={**payload, "outstanding_principal": "99"},
        )

    assert first.status_code == 202
    assert first.json()["status"] == "ACCEPTED"
    assert duplicate.status_code == 202
    assert duplicate.json()["status"] == "DUPLICATE"
    assert duplicate.json()["inbox_message_id"] == first.json()["inbox_message_id"]
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "EVENT_DUPLICATE_PAYLOAD_MISMATCH"


@pytest.mark.integration
async def test_manifest_or_provider_scope_mismatch_fails_closed(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))

    async with client:
        scope_mismatch = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json={
                **_raw_event(provider, status="approved", event_id="evt-scope", sequence=1),
                "provider_id": str(uuid4()),
            },
        )
        version_mismatch = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="approved",
                event_id="evt-version",
                sequence=1,
                adapter_mapping_version="mapping-unknown",
            ),
        )

    assert scope_mismatch.status_code == 403
    assert scope_mismatch.json()["error"]["code"] == "EVENT_SCOPE_INVALID"
    assert version_mismatch.status_code == 422
    assert version_mismatch.json()["error"]["code"] == "PROVIDER_CONTRACT_MISMATCH"


@pytest.mark.integration
async def test_disbursement_updates_only_lender_mirror_not_guarantee_or_journal(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    auditor, provider, guarantee = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))

    async with client:
        approved = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="approved",
                event_id="evt-approved",
                sequence=1,
                guarantee_id=guarantee.id,
            ),
        )
        assert approved.status_code == 202
        assert (await process_pending_lender_inbox_batch(database)).processed == 1

        disbursed = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="funded",
                event_id="evt-funded",
                sequence=2,
                guarantee_id=guarantee.id,
                disbursed="100",
            ),
        )
        assert disbursed.status_code == 202
        assert (await process_pending_lender_inbox_batch(database)).processed == 1

        async with database.session_factory() as session:
            stored_guarantee = await session.get(GuaranteeCase, guarantee.id)
            mirror = await session.scalar(
                select(ExternalLoanMirror).where(
                    ExternalLoanMirror.provider_id == provider.id,
                    ExternalLoanMirror.external_loan_id == "loan-1",
                )
            )
            journal_count = int(
                await session.scalar(select(func.count()).select_from(JournalEntry)) or 0
            )

        assert stored_guarantee is not None
        assert stored_guarantee.state == "ISSUED"
        assert stored_guarantee.external_loan_mirror_id is None
        assert mirror is not None
        assert mirror.state == "ACTIVE"
        assert mirror.guarantee_case_id == guarantee.id
        assert mirror.disbursed_at is not None
        assert journal_count == 0

        read = await client.get(
            f"/api/v1/external-loans/{mirror.id}",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
        )
    assert read.status_code == 200
    assert read.json()["provider_id"] == str(provider.id)
    assert read.json()["lender_legal_entity_id"] == str(provider.legal_entity_id)
    assert read.json()["external_loan_id"] == "loan-1"


@pytest.mark.integration
async def test_repayment_and_delinquency_are_mirror_only_and_stale_event_does_not_regress(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, guarantee = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))
    base_time = datetime.now(UTC)

    events = [
        _raw_event(
            provider,
            status="approved",
            event_id="evt-1",
            sequence=1,
            guarantee_id=guarantee.id,
            event_time=base_time,
        ),
        _raw_event(
            provider,
            status="funded",
            event_id="evt-2",
            sequence=2,
            guarantee_id=guarantee.id,
            event_time=base_time + timedelta(seconds=1),
            disbursed="100",
        ),
        _raw_event(
            provider,
            status="paid",
            event_id="evt-3",
            sequence=3,
            guarantee_id=guarantee.id,
            event_time=base_time + timedelta(seconds=2),
            outstanding="80",
            repayment_reference="rep-1",
        ),
        _raw_event(
            provider,
            status="late",
            event_id="evt-4",
            sequence=4,
            guarantee_id=guarantee.id,
            event_time=base_time + timedelta(seconds=3),
            outstanding="80",
            delinquency_state="PAST_DUE",
        ),
    ]

    async with client:
        for payload in events:
            response = await client.post(
                f"/api/v1/integrations/lenders/{provider.id}/events",
                headers={"x-test-signature": "valid"},
                json=payload,
            )
            assert response.status_code == 202
            assert (await process_pending_lender_inbox_batch(database)).processed == 1

        stale = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="approved",
                event_id="evt-stale",
                sequence=2,
                guarantee_id=guarantee.id,
                event_time=base_time + timedelta(seconds=1),
                outstanding="100",
            ),
        )
        assert stale.status_code == 202
        assert (await process_pending_lender_inbox_batch(database)).processed == 1

    async with database.session_factory() as session:
        mirror = await session.scalar(
            select(ExternalLoanMirror).where(ExternalLoanMirror.provider_id == provider.id)
        )
        stored_guarantee = await session.get(GuaranteeCase, guarantee.id)
        statuses = (
            await session.scalars(
                select(ExternalLoanEvent.processed_status)
                .where(ExternalLoanEvent.external_loan_mirror_id == mirror.id)
                .order_by(ExternalLoanEvent.created_at, ExternalLoanEvent.id)
            )
        ).all()
        journal_count = int(
            await session.scalar(select(func.count()).select_from(JournalEntry)) or 0
        )

    assert mirror is not None
    assert mirror.state == "DELINQUENT"
    assert mirror.outstanding_principal == Decimal("80")
    assert mirror.delinquency_state == "PAST_DUE"
    assert stored_guarantee is not None
    assert stored_guarantee.state == "ISSUED"
    assert journal_count == 0
    assert statuses[-1] == "STALE"


@pytest.mark.integration
async def test_sequence_gap_leaves_event_unprocessed_until_missing_predecessor_arrives(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))
    base_time = datetime.now(UTC)

    async with client:
        first = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="approved",
                event_id="evt-seq-1",
                sequence=1,
                event_time=base_time,
            ),
        )
        assert first.status_code == 202
        assert (await process_pending_lender_inbox_batch(database)).processed == 1

        gap = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="paid",
                event_id="evt-seq-3",
                sequence=3,
                event_time=base_time + timedelta(seconds=2),
                outstanding="80",
                repayment_reference="rep-gap",
            ),
        )
        assert gap.status_code == 202
        gap_result = await process_pending_lender_inbox_batch(database)
        assert gap_result.failed == 1

        missing = await client.post(
            f"/api/v1/integrations/lenders/{provider.id}/events",
            headers={"x-test-signature": "valid"},
            json=_raw_event(
                provider,
                status="funded",
                event_id="evt-seq-2",
                sequence=2,
                event_time=base_time + timedelta(seconds=1),
                disbursed="100",
            ),
        )
        assert missing.status_code == 202

    first_retry = await process_pending_lender_inbox_batch(database)
    assert first_retry.processed >= 1
    second_retry = await process_pending_lender_inbox_batch(database)
    # Durable fair scanning may retry the gap message in the same batch as
    # its missing predecessor, instead of requiring a second worker poll.
    assert first_retry.processed + second_retry.processed == 2

    async with database.session_factory() as session:
        mirror = await session.scalar(
            select(ExternalLoanMirror).where(ExternalLoanMirror.provider_id == provider.id)
        )
        unprocessed = int(
            await session.scalar(
                select(func.count())
                .select_from(InboxMessage)
                .where(InboxMessage.processed_at.is_(None))
            )
            or 0
        )
    assert mirror is not None
    assert mirror.last_provider_event_sequence == 3
    assert mirror.outstanding_principal == Decimal("80")
    assert unprocessed == 0


@pytest.mark.integration
async def test_correction_is_append_only_and_event_history_is_database_protected(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))
    base_time = datetime.now(UTC)

    async with client:
        for payload in [
            _raw_event(
                provider,
                status="approved",
                event_id="evt-c-1",
                sequence=1,
                event_time=base_time,
            ),
            _raw_event(
                provider,
                status="corrected",
                event_id="evt-c-2",
                sequence=2,
                event_time=base_time + timedelta(seconds=1),
                original="120",
                outstanding="110",
            ),
        ]:
            response = await client.post(
                f"/api/v1/integrations/lenders/{provider.id}/events",
                headers={"x-test-signature": "valid"},
                json=payload,
            )
            assert response.status_code == 202
            assert (await process_pending_lender_inbox_batch(database)).processed == 1

    async with database.session_factory() as session:
        mirror = await session.scalar(
            select(ExternalLoanMirror).where(ExternalLoanMirror.provider_id == provider.id)
        )
        events = (
            await session.scalars(
                select(ExternalLoanEvent)
                .where(ExternalLoanEvent.external_loan_mirror_id == mirror.id)
                .order_by(ExternalLoanEvent.created_at, ExternalLoanEvent.id)
            )
        ).all()

    assert mirror is not None
    assert mirror.original_principal == Decimal("120")
    assert mirror.outstanding_principal == Decimal("110")
    assert [event.processed_status for event in events] == ["APPLIED", "CORRECTED"]

    event_id = events[-1].id
    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(ExternalLoanEvent)
                    .where(ExternalLoanEvent.id == event_id)
                    .values(processed_status="APPLIED")
                )
    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    delete(ExternalLoanEvent).where(ExternalLoanEvent.id == event_id)
                )


@pytest.mark.integration
async def test_external_loan_db_rejects_outstanding_above_original_principal(
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                session.add(
                    ExternalLoanMirror(
                        guarantee_case_id=None,
                        provider_id=provider.id,
                        external_loan_id="loan-invalid-principal-bound",
                        state="PENDING",
                        original_principal=Decimal("100"),
                        outstanding_principal=Decimal("101"),
                        currency="IRR",
                        version=1,
                    )
                )
                await session.flush()


@pytest.mark.integration
async def test_external_loan_query_is_provider_scoped_and_no_generic_mutation_api_exists(
    settings: Settings,
    database,
    clean_sprint13_lender_tables,
) -> None:
    auditor, provider, _ = await _seed_context(database)
    other_identity = Identity(
        identity_type="AUDITOR",
        external_subject=f"sprint13-other-{uuid4()}",
        status="ACTIVE",
    )
    mirror = ExternalLoanMirror(
        guarantee_case_id=None,
        provider_id=provider.id,
        external_loan_id="loan-read",
        state="PENDING",
        original_principal=Decimal("100"),
        outstanding_principal=Decimal("100"),
        currency="IRR",
        version=1,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([other_identity, mirror])
            await session.flush()
            mirror_id = mirror.id

    app, client = await _app_client(settings)
    async with client:
        allowed = await client.get(
            f"/api/v1/external-loans/{mirror_id}",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
        )
        denied = await client.get(
            f"/api/v1/external-loans/{mirror_id}",
            headers={"Authorization": f"Bearer {other_identity.external_subject}"},
        )

    assert allowed.status_code == 200
    assert denied.status_code == 403

    schema = app.openapi()
    assert set(schema["paths"]["/api/v1/external-loans/{loan_id}"]) == {"get"}


def test_reconciliation_snapshot_contract_rejects_naive_time_and_precision_drift() -> None:
    provider_id = uuid4()
    with pytest.raises(ValidationError):
        LenderReconciliationLoan(
            external_loan_id="loan-1",
            original_principal="100000000000000000000",
            outstanding_principal="1",
            currency="IRR",
            provider_state="ACTIVE",
            observed_at=datetime.now(UTC),
        )
    with pytest.raises(ValidationError):
        LenderReconciliationLoan(
            external_loan_id="loan-1",
            original_principal="1.0000000000000000001",
            outstanding_principal="1",
            currency="IRR",
            provider_state="ACTIVE",
            observed_at=datetime.now(UTC),
        )
    with pytest.raises(ValidationError):
        LenderReconciliationSnapshot(
            provider_id=provider_id,
            snapshot_at=datetime(2026, 10, 7, 12, 0, 0),
            source_reference="statement-1",
            evidence_references=[],
            loans=[],
        )


@pytest.mark.integration
async def test_reconciliation_snapshot_contract_is_provider_scoped(
    database,
    clean_sprint13_lender_tables,
) -> None:
    _, provider, _ = await _seed_context(database)
    adapter = TestLenderAdapter(provider.id)
    snapshot = await adapter.fetch_reconciliation_snapshot(
        LenderReconciliationScope(provider_id=provider.id)
    )

    assert snapshot.provider_id == provider.id
    assert snapshot.source_reference == "test-statement-1"
    assert snapshot.loans[0].external_loan_id == "loan-1"
    assert snapshot.loans[0].outstanding_principal == "75"


def test_lender_event_evidence_openapi_is_read_only(settings: Settings) -> None:
    paths = create_app(settings).openapi()["paths"]
    listing = paths["/api/v1/external-loans/{loan_id}/events"]
    detail = paths["/api/v1/external-loans/{loan_id}/events/{event_id}"]
    assert set(listing) == {"get"}
    assert set(detail) == {"get"}
    assert {"401", "403", "404", "422"}.issubset(listing["get"]["responses"])
    assert {"401", "403", "404"}.issubset(detail["get"]["responses"])
    schemas = create_app(settings).openapi()["components"]["schemas"]
    props = schemas["LenderEventEvidenceView"]["properties"]
    assert props["principal_delta"]["format"] == "decimal"
    assert props["outstanding_principal_reported"]["format"] == "decimal"
    assert "payload" not in props


@pytest.mark.integration
async def test_lender_event_history_scopes_provider_and_paginates_by_event_time(
    settings: Settings, database, clean_sprint13_lender_tables
) -> None:
    auditor, provider, guarantee = await _seed_context(database)
    other_user = Identity(
        identity_type="AUDITOR", external_subject=f"other-provider-{uuid4()}", status="ACTIVE"
    )
    base_time = datetime.now(UTC) - timedelta(minutes=3)
    mirror = ExternalLoanMirror(
        guarantee_case_id=guarantee.id,
        provider_id=provider.id,
        external_loan_id=f"loan-events-{uuid4()}",
        state="ACTIVE",
        original_principal=Decimal("100"),
        outstanding_principal=Decimal("70"),
        currency="IRR",
    )
    other_mirror = ExternalLoanMirror(
        guarantee_case_id=None,
        provider_id=provider.id,
        external_loan_id=f"other-loan-{uuid4()}",
        state="PENDING",
        original_principal=Decimal("50"),
        outstanding_principal=Decimal("50"),
        currency="IRR",
    )
    async with database.session_factory() as session:
        async with session.begin():
            other_provider = CreditProvider(
                legal_entity_id=provider.legal_entity_id,
                provider_code=f"OTHER-PROVIDER-{uuid4()}",
                display_name="Other scoped lender",
                provider_type="EXTERNAL_LENDER",
                integration_mode="WEBHOOK_CALLBACK",
                authorization_review_state="TEST",
                lifecycle_status="ACTIVE",
                created_by=auditor.id,
            )
            session.add_all([mirror, other_mirror, other_user, other_provider])
            await session.flush()
            session.add(
                RoleGrant(
                    identity_id=other_user.id,
                    role_code=ROLE_AUDITOR,
                    scope_type=SCOPE_PROVIDER,
                    scope_id=other_provider.id,
                    valid_from=base_time,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="test-provider-isolation",
                )
            )
            scoped_other_mirror = ExternalLoanMirror(
                guarantee_case_id=None,
                provider_id=other_provider.id,
                external_loan_id=f"other-provider-loan-{uuid4()}",
                state="PENDING",
                original_principal=Decimal("50"),
                outstanding_principal=Decimal("50"),
                currency="IRR",
            )
            session.add(scoped_other_mirror)
            await session.flush()
            other_provider_loan_id = scoped_other_mirror.id
            event_rows = []
            for i, (kind, processed, principal) in enumerate(
                [
                    ("LOAN_APPROVED", "APPLIED", None),
                    ("LOAN_DISBURSED", "APPLIED", Decimal("0")),
                    ("REPAYMENT_RECEIVED", "APPLIED", Decimal("-30.000")),
                    ("LOAN_CORRECTED", "CORRECTED", Decimal("0")),
                    ("LOAN_APPROVED", "STALE", None),
                ]
            ):
                event_rows.append(
                    ExternalLoanEvent(
                        external_loan_mirror_id=mirror.id,
                        provider_event_id=f"trace-{i}-{uuid4()}",
                        event_type=kind,
                        principal_delta=principal,
                        outstanding_principal_reported=Decimal("70.000"),
                        provider_event_at=base_time + timedelta(seconds=i),
                        received_at=base_time + timedelta(minutes=1),
                        evidence_references=[f"evidence:trace-{i}"],
                        payload_hash=hashlib.sha256(f"trace-{i}".encode()).hexdigest(),
                        processed_status=processed,
                        provider_contract_version="provider:test-v1",
                        adapter_mapping_version="mapping:test-v1",
                        inbound_normalization_version="normalize:test-v1",
                        provider_event_sequence=i + 1,
                    )
                )
            other_event = ExternalLoanEvent(
                external_loan_mirror_id=other_mirror.id,
                provider_event_id=f"foreign-cursor-{uuid4()}",
                event_type="LOAN_APPROVED",
                principal_delta=None,
                outstanding_principal_reported=Decimal("50"),
                provider_event_at=base_time,
                received_at=base_time,
                evidence_references=[],
                payload_hash="c" * 64,
                processed_status="HISTORY_ONLY",
                provider_contract_version="provider:test-v1",
                adapter_mapping_version="mapping:test-v1",
                inbound_normalization_version="normalize:test-v1",
            )
            session.add_all([*event_rows, other_event])
            await session.flush()
            mirror_id, other_id, foreign_cursor = mirror.id, other_mirror.id, other_event.id
            ids_in_order = [event.id for event in event_rows]
    app, client = await _app_client(settings)
    path = f"/api/v1/external-loans/{mirror_id}/events"
    auth = {"Authorization": f"Bearer {auditor.external_subject}"}
    denied_auth = {"Authorization": f"Bearer {other_user.external_subject}"}
    async with client:
        collected: list[str] = []
        cursor = None
        while True:
            parameters: dict[str, str | int] = {"limit": 2}
            if cursor is not None:
                parameters["after"] = cursor
            response = await client.get(path, headers=auth, params=parameters)
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["provider_id"] == str(provider.id)
            assert len(body["items"]) <= 2
            collected.extend(item["id"] for item in body["items"])
            cursor = body["next_cursor"]
            if cursor is None:
                break
        assert collected == [str(identifier) for identifier in ids_in_order]
        detail = await client.get(path + f"/{ids_in_order[2]}", headers=auth)
        assert detail.status_code == 200, detail.text
        assert detail.json()["event_type"] == "REPAYMENT_RECEIVED"
        assert Decimal(detail.json()["principal_delta"]) == Decimal("-30.000")
        assert detail.json()["evidence_references"] == ["evidence:trace-2"]
        assert detail.json()["processed_status"] == "APPLIED"
        corrected = await client.get(path + f"/{ids_in_order[3]}", headers=auth)
        assert corrected.status_code == 200
        assert corrected.json()["processed_status"] == "CORRECTED"
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers=denied_auth)).status_code == 403
        own_scoped = await client.get(
            f"/api/v1/external-loans/{other_provider_loan_id}/events",
            headers=denied_auth,
        )
        assert own_scoped.status_code == 200
        assert own_scoped.json()["items"] == []
        assert (
            await client.get(
                f"/api/v1/external-loans/{other_provider_loan_id}/events", headers=auth
            )
        ).status_code == 403
        assert (
            await client.get(path + f"/{ids_in_order[0]}", headers=denied_auth)
        ).status_code == 403
        assert (await client.get(path, headers=auth, params={"limit": 0})).status_code == 422
        assert (await client.get(path, headers=auth, params={"limit": 101})).status_code == 422
        foreign = await client.get(path, headers=auth, params={"after": str(foreign_cursor)})
        assert foreign.status_code == 422
        assert foreign.json()["error"]["code"] == "LENDER_EVENT_CURSOR_INVALID"
        cross_loan = await client.get(
            f"/api/v1/external-loans/{other_id}/events/{ids_in_order[0]}", headers=auth
        )
        assert cross_loan.status_code == 404
        assert cross_loan.json()["error"]["code"] == "LENDER_EVENT_NOT_FOUND"
        assert (
            await client.get(f"/api/v1/external-loans/{uuid4()}/events", headers=auth)
        ).status_code == 404
    assert set(app.openapi()["paths"]["/api/v1/external-loans/{loan_id}/events"]) == {"get"}
    async with database.session_factory() as session:
        stored = await session.get(GuaranteeCase, guarantee.id)
        assert stored is not None and stored.state == "ISSUED"
        assert int(await session.scalar(select(func.count()).select_from(JournalEntry)) or 0) == 0
        assert (
            int(await session.scalar(select(func.count()).select_from(ExternalLoanEvent)) or 0) == 6
        )


@pytest.mark.integration
async def test_lender_event_page_empty_and_revoked_grant_denies(
    settings: Settings, database, clean_sprint13_lender_tables
) -> None:
    auditor, provider, guarantee = await _seed_context(database)
    mirror = ExternalLoanMirror(
        guarantee_case_id=guarantee.id,
        provider_id=provider.id,
        external_loan_id=f"empty-loan-{uuid4()}",
        state="PENDING",
        original_principal=Decimal("100"),
        outstanding_principal=Decimal("100"),
        currency="IRR",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(mirror)
            await session.flush()
            mirror_id = mirror.id
    _, client = await _app_client(settings)
    path = f"/api/v1/external-loans/{mirror_id}/events"
    auth = {"Authorization": f"Bearer {auditor.external_subject}"}
    async with client:
        empty = await client.get(path, headers=auth)
        assert empty.status_code == 200
        assert empty.json()["items"] == []
        assert empty.json()["next_cursor"] is None
        async with database.session_factory() as session:
            async with session.begin():
                grants = (
                    await session.scalars(
                        select(RoleGrant).where(RoleGrant.identity_id == auditor.id)
                    )
                ).all()
                assert len(grants) == 1
                grants[0].status = "REVOKED"
        denied = await client.get(path, headers=auth)
        assert denied.status_code == 403


def test_lender_mirror_advisory_key_is_deterministic_and_provider_scoped() -> None:
    provider_id = uuid4()
    other_provider_id = uuid4()
    assert _lender_mirror_lock_key(provider_id, "loan-α") == _lender_mirror_lock_key(
        provider_id, "loan-α"
    )
    assert _lender_mirror_lock_key(provider_id, "loan-α") != _lender_mirror_lock_key(
        provider_id, "loan-β"
    )
    assert _lender_mirror_lock_key(provider_id, "loan-α") != _lender_mirror_lock_key(
        other_provider_id, "loan-α"
    )


@pytest.mark.integration
async def test_concurrent_first_lender_events_produce_single_mirror_and_no_business_effect(
    settings: Settings, database, clean_sprint13_lender_tables
) -> None:
    _, provider, guarantee = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))
    base_time = datetime.now(UTC)
    loan_id = f"concurrent-first-loan-{uuid4()}"
    events = [
        {
            **_raw_event(
                provider,
                status="approved",
                event_id=f"first-approved-{uuid4()}",
                sequence=1,
                guarantee_id=guarantee.id,
                event_time=base_time,
            ),
            "external_loan_id": loan_id,
        },
        {
            **_raw_event(
                provider,
                status="funded",
                event_id=f"first-disbursed-{uuid4()}",
                sequence=2,
                guarantee_id=guarantee.id,
                event_time=base_time + timedelta(seconds=1),
                disbursed="100",
            ),
            "external_loan_id": loan_id,
        },
    ]
    async with client:
        inbox_ids = []
        for payload in events:
            response = await client.post(
                f"/api/v1/integrations/lenders/{provider.id}/events",
                headers={"x-test-signature": "valid"},
                json=payload,
            )
            assert response.status_code == 202, response.text
            inbox_ids.append(UUID(response.json()["inbox_message_id"]))

    results = await asyncio.wait_for(
        asyncio.gather(
            *(
                process_inbox_message_once(
                    database, message_id=message_id, handler=process_lender_inbox_message
                )
                for message_id in inbox_ids
            )
        ),
        timeout=15,
    )
    assert len(results) == 2 and all(item.processed for item in results)

    async with database.session_factory() as session:
        mirrors = (
            await session.scalars(
                select(ExternalLoanMirror).where(
                    ExternalLoanMirror.provider_id == provider.id,
                    ExternalLoanMirror.external_loan_id == loan_id,
                )
            )
        ).all()
        assert len(mirrors) == 1
        mirror = mirrors[0]
        histories = (
            await session.scalars(
                select(ExternalLoanEvent).where(
                    ExternalLoanEvent.external_loan_mirror_id == mirror.id
                )
            )
        ).all()
        assert len(histories) == 2
        assert {x.provider_event_id for x in histories} == {
            str(event["external_event_id"]) for event in events
        }
        assert {x.processed_status for x in histories}.issubset({"APPLIED", "STALE"})
        assert mirror.state == "ACTIVE"
        assert mirror.last_provider_event_sequence == 2
        assert mirror.guarantee_case_id == guarantee.id
        persisted_guarantee = await session.get(GuaranteeCase, guarantee.id)
        assert persisted_guarantee is not None
        assert persisted_guarantee.state == "ISSUED"
        assert int(await session.scalar(select(func.count()).select_from(JournalEntry)) or 0) == 0
        assert (
            int(
                await session.scalar(
                    select(func.count())
                    .select_from(InboxMessage)
                    .where(InboxMessage.id.in_(inbox_ids), InboxMessage.processed_at.is_not(None))
                )
                or 0
            )
            == 2
        )


@pytest.mark.integration
async def test_competing_lender_loan_ids_cannot_double_link_same_guarantee(
    settings: Settings, database, clean_sprint13_lender_tables
) -> None:
    _, provider, guarantee = await _seed_context(database)
    app, client = await _app_client(settings)
    app.state.lender_adapter_registry.register(provider.id, TestLenderAdapter(provider.id))
    messages = []
    async with client:
        for number in range(2):
            payload = {
                **_raw_event(
                    provider,
                    status="approved",
                    event_id=f"competing-{number}-{uuid4()}",
                    sequence=1,
                    guarantee_id=guarantee.id,
                ),
                "external_loan_id": f"competing-loan-{number}-{uuid4()}",
            }
            response = await client.post(
                f"/api/v1/integrations/lenders/{provider.id}/events",
                headers={"x-test-signature": "valid"},
                json=payload,
            )
            assert response.status_code == 202, response.text
            messages.append(UUID(response.json()["inbox_message_id"]))
    results = await asyncio.wait_for(
        asyncio.gather(
            *(
                process_inbox_message_once(
                    database, message_id=message_id, handler=process_lender_inbox_message
                )
                for message_id in messages
            ),
            return_exceptions=True,
        ),
        timeout=15,
    )
    assert sum(not isinstance(x, BaseException) and x.processed for x in results) == 1
    errors = [x for x in results if isinstance(x, BaseException)]
    assert len(errors) == 1
    assert isinstance(errors[0], ExternalLoanError)
    assert errors[0].code == "LENDER_GUARANTEE_LINK_CONFLICT"
    async with database.session_factory() as session:
        mirrors = (
            await session.scalars(
                select(ExternalLoanMirror).where(
                    ExternalLoanMirror.guarantee_case_id == guarantee.id
                )
            )
        ).all()
        assert len(mirrors) == 1
        assert (
            int(await session.scalar(select(func.count()).select_from(ExternalLoanEvent)) or 0) == 1
        )
        assert int(await session.scalar(select(func.count()).select_from(JournalEntry)) or 0) == 0
        assert (
            int(
                await session.scalar(
                    select(func.count())
                    .select_from(InboxMessage)
                    .where(InboxMessage.id.in_(messages), InboxMessage.processed_at.is_not(None))
                )
                or 0
            )
            == 1
        )
