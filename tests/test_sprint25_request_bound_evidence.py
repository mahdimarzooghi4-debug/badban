from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from badban.application.request_bound_backing_evidence import (
    RequestEvidenceError,
    read_request_bound_backing_evidence,
)
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    CreditProductVersion,
    CreditProvider,
    DecisionSnapshot,
    GuaranteeCase,
    Identity,
    JournalEntry,
    LegalEntity,
    OutboxMessage,
    Participant,
    ParticipationEpisode,
    Program,
    ValuationObservation,
)


async def _request_facts(database) -> dict[str, object]:
    actor = Identity(
        identity_type="STAFF", external_subject=f"request-evidence-{uuid4()}", status="ACTIVE"
    )
    participant = Participant(external_reference=f"request-evidence-participant-{uuid4()}")
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([actor, participant])
            await session.flush()
            program = Program(
                code=f"REQ-EV-{uuid4().hex[:12]}",
                name="Request Evidence Program",
                created_by=actor.id,
            )
            lender = LegalEntity(
                legal_name="Synthetic Lender",
                registration_identifier=f"TEST-EV-{uuid4()}",
                entity_type="SYNTHETIC_LENDER",
                status="ACTIVE",
                created_by=actor.id,
            )
            session.add_all([program, lender])
            await session.flush()
            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                consent_state="RECORDED",
                started_at=datetime.now(UTC),
                created_by=actor.id,
            )
            provider = CreditProvider(
                legal_entity_id=lender.id,
                provider_code=f"EV-PROV-{uuid4().hex[:12]}",
                display_name="Synthetic Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="CONTROLLED_MANUAL",
                authorization_review_state="SYNTHETIC_PENDING",
                lifecycle_status="DRAFT",
                created_by=actor.id,
            )
            asset_type = AssetType(
                asset_code=f"EV-ASSET-{uuid4().hex[:12]}",
                name="Configurable Source Asset",
                status="ACTIVE",
                unit_code="UNIT",
                quantity_scale=8,
                created_by=actor.id,
            )
            session.add_all([episode, provider, asset_type])
            await session.flush()
            product = CreditProductVersion(
                provider_id=provider.id,
                lender_of_record_legal_entity_id=lender.id,
                product_code=f"EV-PRODUCT-{uuid4().hex[:12]}",
                version_number=1,
                product_name="Synthetic Product",
                product_type="SYNTHETIC_EXTERNAL_CREDIT",
                lifecycle_status="DRAFT",
                currency="IRR",
                min_principal=Decimal("10"),
                max_principal=Decimal("100"),
                tenor_definition={"test": True},
                repayment_definition={"test": True},
                pricing_definition={"test": True},
                guarantee_mode="FIXED",
                delinquency_definition={"test": True},
                claim_definition={"test": True},
                policy_version_reference="synthetic-product-policy:1",
                additional_terms={},
                effective_from=datetime.now(UTC) - timedelta(days=1),
                created_by=actor.id,
            )
            owned = AssetPosition(
                participation_episode_id=episode.id,
                program_id=program.id,
                asset_type_id=asset_type.id,
                ownership_funding_type="PARTICIPANT_OWNED",
                legal_owner_participant_id=participant.id,
                quantity=Decimal("5"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                created_by=actor.id,
            )
            attributed = AssetPosition(
                participation_episode_id=episode.id,
                program_id=program.id,
                asset_type_id=asset_type.id,
                ownership_funding_type="PROGRAM_ATTRIBUTED",
                legal_owner_entity_id=lender.id,
                quantity=Decimal("3"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                created_by=actor.id,
            )
            session.add_all([product, owned, attributed])
            await session.flush()
            guarantee = GuaranteeCase(
                participation_episode_id=episode.id,
                provider_id=provider.id,
                credit_product_version_id=product.id,
                state="REQUESTED",
                requested_principal=Decimal("25"),
                current_guarantee_exposure=Decimal("0"),
                guarantee_mode="FIXED",
            )
            valuation = ValuationObservation(
                asset_position_id=owned.id,
                valued_quantity=Decimal("5"),
                unit_price=Decimal("12"),
                valuation_currency="IRR",
                gross_market_value=Decimal("60"),
                source_name="synthetic-valuation",
                source_reference="test:valuation:1",
                observed_at=datetime.now(UTC),
                received_at=datetime.now(UTC),
                freshness_status="FRESH",
                created_by=actor.id,
            )
            session.add_all([guarantee, valuation])
            await session.flush()
            return {
                "guarantee_id": guarantee.id,
                "program_id": program.id,
                "provider_id": provider.id,
                "product_id": product.id,
                "position_id": owned.id,
                "episode_id": episode.id,
            }


@pytest.mark.integration
async def test_request_evidence_links_real_guarantee_product_and_multiple_assets(
    database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _request_facts(database)
    async with database.session_factory() as session:
        first = await read_request_bound_backing_evidence(
            session, guarantee_case_id=keys["guarantee_id"], program_id=keys["program_id"]
        )
        replay = await read_request_bound_backing_evidence(
            session, guarantee_case_id=keys["guarantee_id"], program_id=keys["program_id"]
        )
        journal_count = await session.scalar(select(func.count()).select_from(JournalEntry))
        outbox_count = await session.scalar(select(func.count()).select_from(OutboxMessage))
        decisions = await session.scalar(select(func.count()).select_from(DecisionSnapshot))
    assert first == replay
    assert first.evidence_fingerprint == replay.evidence_fingerprint
    assert len(first.evidence_fingerprint) == 64
    assert first.guarantee_state == "REQUESTED"
    assert first.provider_id == keys["provider_id"]
    assert first.credit_product_version_id == keys["product_id"]
    assert first.product_lifecycle_status == "DRAFT"  # observed, not approved
    assert first.backing.episode_id == keys["episode_id"]
    assert len(first.backing.sources) == 2
    assert sum(len(a.valuation_history) for a in first.backing.sources) == 1
    assert not hasattr(first, "reservation_eligible")
    assert not hasattr(first, "available_capacity")
    assert journal_count == 0
    assert outbox_count == 0
    assert decisions == 0


@pytest.mark.integration
async def test_request_evidence_missing_and_wrong_program_fail_closed(
    database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _request_facts(database)
    async with database.session_factory() as session:
        with pytest.raises(RequestEvidenceError) as missing:
            await read_request_bound_backing_evidence(
                session, guarantee_case_id=uuid4(), program_id=keys["program_id"]
            )
        assert missing.value.code == "REQUEST_EVIDENCE_NOT_FOUND"
        with pytest.raises(RequestEvidenceError) as wrong_program:
            await read_request_bound_backing_evidence(
                session, guarantee_case_id=keys["guarantee_id"], program_id=uuid4()
            )
        assert wrong_program.value.code == "REQUEST_EVIDENCE_SCOPE_CONFLICT"


@pytest.mark.integration
async def test_request_evidence_rejects_transitioned_case(
    database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _request_facts(database)
    async with database.session_factory() as session:
        async with session.begin():
            guarantee = await session.get(GuaranteeCase, keys["guarantee_id"])
            assert guarantee is not None
            guarantee.state = "RESERVED"
    async with database.session_factory() as session:
        with pytest.raises(RequestEvidenceError) as unsupported:
            await read_request_bound_backing_evidence(
                session, guarantee_case_id=keys["guarantee_id"], program_id=keys["program_id"]
            )
    assert unsupported.value.code == "REQUEST_EVIDENCE_STATE_UNSUPPORTED"


@pytest.mark.integration
async def test_request_evidence_rejects_mismatched_captured_provider(
    database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _request_facts(database)
    async with database.session_factory() as session:
        async with session.begin():
            original = await session.get(CreditProvider, keys["provider_id"])
            assert original is not None
            other = CreditProvider(
                legal_entity_id=original.legal_entity_id,
                provider_code=f"EV-OTHER-{uuid4().hex[:12]}",
                display_name="Other Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="CONTROLLED_MANUAL",
                authorization_review_state="SYNTHETIC_PENDING",
                lifecycle_status="DRAFT",
                created_by=uuid4(),
            )
            session.add(other)
            await session.flush()
            guarantee = await session.get(GuaranteeCase, keys["guarantee_id"])
            assert guarantee is not None
            guarantee.provider_id = other.id
    async with database.session_factory() as session:
        with pytest.raises(RequestEvidenceError) as conflict:
            await read_request_bound_backing_evidence(
                session, guarantee_case_id=keys["guarantee_id"], program_id=keys["program_id"]
            )
    assert conflict.value.code == "REQUEST_EVIDENCE_LINEAGE_CONFLICT"


@pytest.mark.integration
async def test_request_evidence_fingerprint_changes_with_real_asset_version(
    database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _request_facts(database)
    async with database.session_factory() as session:
        before = await read_request_bound_backing_evidence(
            session, guarantee_case_id=keys["guarantee_id"], program_id=keys["program_id"]
        )
    async with database.session_factory() as session:
        async with session.begin():
            position = await session.get(AssetPosition, keys["position_id"])
            assert position is not None
            position.quantity = Decimal("6")
    async with database.session_factory() as session:
        after = await read_request_bound_backing_evidence(
            session, guarantee_case_id=keys["guarantee_id"], program_id=keys["program_id"]
        )
    assert before.evidence_fingerprint != after.evidence_fingerprint
