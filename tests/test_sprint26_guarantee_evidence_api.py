from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from badban.api.app import create_app
from badban.config import Settings
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
    RoleGrant,
    ValuationObservation,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_OPERATIONS,
    ROLE_RISK,
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {subject}"}


async def _seed(database) -> dict[str, UUID | str]:
    async with database.session_factory() as session:
        async with session.begin():
            ops = Identity(
                identity_type="STAFF", external_subject=f"ev-ops-{uuid4()}", status="ACTIVE"
            )
            risk = Identity(
                identity_type="STAFF", external_subject=f"ev-risk-{uuid4()}", status="ACTIVE"
            )
            finance = Identity(
                identity_type="STAFF", external_subject=f"ev-finance-{uuid4()}", status="ACTIVE"
            )
            auditor = Identity(
                identity_type="AUDITOR", external_subject=f"ev-audit-{uuid4()}", status="ACTIVE"
            )
            outsider = Identity(
                identity_type="STAFF", external_subject=f"ev-other-{uuid4()}", status="ACTIVE"
            )
            participant = Participant(external_reference=f"ev-part-{uuid4()}")
            session.add_all([ops, risk, finance, auditor, outsider, participant])
            await session.flush()
            program = Program(
                code=f"EV-{uuid4().hex[:12]}", name="Evidence Program", created_by=ops.id
            )
            other_program = Program(
                code=f"OTHER-{uuid4().hex[:12]}", name="Other Program", created_by=ops.id
            )
            lender = LegalEntity(
                legal_name="Test Lender",
                registration_identifier=f"EV-ENTITY-{uuid4()}",
                entity_type="TEST",
                status="ACTIVE",
                created_by=ops.id,
            )
            asset_type = AssetType(
                asset_code=f"EV-TYPE-{uuid4().hex[:12]}",
                name="Flexible Asset",
                status="ACTIVE",
                unit_code="UNIT",
                quantity_scale=8,
                created_by=ops.id,
            )
            session.add_all([program, other_program, lender, asset_type])
            await session.flush()
            ep = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                consent_state="RECORDED",
                started_at=datetime.now(UTC),
                created_by=ops.id,
            )
            provider = CreditProvider(
                legal_entity_id=lender.id,
                provider_code=f"EV-PROV-{uuid4().hex[:12]}",
                display_name="Test Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="CONTROLLED_MANUAL",
                authorization_review_state="TEST_PENDING",
                lifecycle_status="DRAFT",
                created_by=ops.id,
            )
            session.add_all([ep, provider])
            await session.flush()
            product = CreditProductVersion(
                provider_id=provider.id,
                lender_of_record_legal_entity_id=lender.id,
                product_code=f"EV-PRODUCT-{uuid4().hex[:12]}",
                version_number=1,
                product_name="Test Product",
                product_type="EXTERNAL_CREDIT",
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
                policy_version_reference="test-ref:1",
                additional_terms={},
                effective_from=datetime.now(UTC) - timedelta(days=1),
                created_by=ops.id,
            )
            owned = AssetPosition(
                participation_episode_id=ep.id,
                program_id=program.id,
                asset_type_id=asset_type.id,
                ownership_funding_type="PARTICIPANT_OWNED",
                legal_owner_participant_id=participant.id,
                quantity=Decimal("5.250"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                created_by=ops.id,
            )
            unvalued = AssetPosition(
                participation_episode_id=ep.id,
                program_id=program.id,
                asset_type_id=asset_type.id,
                ownership_funding_type="PROGRAM_ATTRIBUTED",
                legal_owner_entity_id=lender.id,
                quantity=Decimal("3"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                created_by=ops.id,
            )
            session.add_all([product, owned, unvalued])
            await session.flush()
            guarantee = GuaranteeCase(
                participation_episode_id=ep.id,
                provider_id=provider.id,
                credit_product_version_id=product.id,
                state="REQUESTED",
                requested_principal=Decimal("25.125"),
                current_guarantee_exposure=Decimal("0"),
                guarantee_mode="FIXED",
            )
            value = ValuationObservation(
                asset_position_id=owned.id,
                valued_quantity=Decimal("5.250"),
                unit_price=Decimal("10"),
                valuation_currency="IRR",
                gross_market_value=Decimal("52.5"),
                source_name="Test Observation",
                source_reference="test:1",
                observed_at=datetime.now(UTC),
                received_at=datetime.now(UTC),
                freshness_status="FRESH",
                created_by=ops.id,
            )
            session.add_all([guarantee, value])
            now = datetime.now(UTC) - timedelta(minutes=1)
            session.add_all(
                [
                    RoleGrant(
                        identity_id=actor.id,
                        role_code=role,
                        scope_type=scope,
                        scope_id=scope_id,
                        valid_from=now,
                        status="ACTIVE",
                        granted_by=None,
                        reason_ref="test-evidence-read",
                    )
                    for actor, role, scope, scope_id in [
                        (ops, ROLE_OPERATIONS, SCOPE_PROGRAM, program.id),
                        (risk, ROLE_RISK, SCOPE_PROGRAM, program.id),
                        (finance, ROLE_FINANCE_RECONCILIATION, SCOPE_PROGRAM, program.id),
                        (auditor, ROLE_AUDITOR, SCOPE_GLOBAL, None),
                        (outsider, ROLE_OPERATIONS, SCOPE_PROGRAM, other_program.id),
                    ]
                ]
            )
            await session.flush()
            return {
                "guarantee": guarantee.id,
                "program": program.id,
                "owned": owned.id,
                "ops": ops.external_subject,
                "risk": risk.external_subject,
                "finance": finance.external_subject,
                "auditor": auditor.external_subject,
                "outsider": outsider.external_subject,
            }


def test_guarantee_read_schema_declares_scoped_auth_and_decimal_strings(
    settings: Settings,
) -> None:
    paths = create_app(settings).openapi()["paths"]
    detail = paths["/api/v1/guarantees/{guarantee_id}"]["get"]
    evidence = paths["/api/v1/guarantees/{guarantee_id}/request-evidence"]["get"]
    assert "OPERATIONS" in detail["description"]
    assert "AUDITOR" in detail["description"]
    assert "NOT" in evidence["description"]
    assert {"401", "403", "404"}.issubset(detail["responses"])
    assert {"401", "403", "404", "409"}.issubset(evidence["responses"])
    model = create_app(settings).openapi()["components"]["schemas"]["RequestBoundEvidenceView"]
    principal = model["properties"]["requested_principal"]
    assert principal["type"] == "string"
    assert principal["format"] == "decimal"


@pytest.mark.integration
async def test_scoped_guarantee_reads_are_exact_and_side_effect_free(
    settings: Settings, database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _seed(database)
    path = f"/api/v1/guarantees/{keys['guarantee']}"
    async with database.session_factory() as session:
        before = [
            int(await session.scalar(select(func.count()).select_from(model)) or 0)
            for model in (GuaranteeCase, JournalEntry, DecisionSnapshot, OutboxMessage)
        ]
    async with await _client(settings) as client:
        for subject in ("ops", "risk", "finance", "auditor"):
            detail = await client.get(path, headers=_headers(str(keys[subject])))
            assert detail.status_code == 200
            assert detail.json()["state"] == "REQUESTED"
            assert Decimal(detail.json()["requested_principal"]) == Decimal("25.125")
            evidence = await client.get(
                path + "/request-evidence", headers=_headers(str(keys[subject]))
            )
            assert evidence.status_code == 200
            body = evidence.json()
            assert body["guarantee_case_id"] == str(keys["guarantee"])
            assert body["provider_lifecycle_status"] == "DRAFT"
            assert body["product_lifecycle_status"] == "DRAFT"
            assert Decimal(body["requested_principal"]) == Decimal("25.125")
            assert len(body["backing"]["sources"]) == 2
            assert sorted(len(s["valuation_history"]) for s in body["backing"]["sources"]) == [0, 1]
            assert all(isinstance(s["quantity"], str) for s in body["backing"]["sources"])
            assert len(body["evidence_fingerprint"]) == 64
            assert len(body["backing"]["source_fingerprint"]) == 64
            assert "eligible" not in body
            assert "available_capacity" not in body
    async with database.session_factory() as session:
        after = [
            int(await session.scalar(select(func.count()).select_from(model)) or 0)
            for model in (GuaranteeCase, JournalEntry, DecisionSnapshot, OutboxMessage)
        ]
    assert before == after


@pytest.mark.integration
async def test_cross_program_and_missing_roles_cannot_read_guarantee_evidence(
    settings: Settings, database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _seed(database)
    path = f"/api/v1/guarantees/{keys['guarantee']}"
    async with await _client(settings) as client:
        for suffix in ("", "/request-evidence"):
            no_auth = await client.get(path + suffix)
            outsider = await client.get(path + suffix, headers=_headers(str(keys["outsider"])))
            missing = await client.get(
                f"/api/v1/guarantees/{uuid4()}" + suffix,
                headers=_headers(str(keys["ops"])),
            )
            assert no_auth.status_code == 401
            assert outsider.status_code == 403
            assert outsider.json()["error"]["code"] == "AUTHORIZATION_DENIED"
            assert missing.status_code == 404


@pytest.mark.integration
async def test_read_evidence_denies_transitioned_case_without_affecting_detail(
    settings: Settings, database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _seed(database)
    async with database.session_factory() as session:
        async with session.begin():
            case = await session.get(GuaranteeCase, keys["guarantee"])
            assert case is not None
            case.state = "RESERVED"
    path = f"/api/v1/guarantees/{keys['guarantee']}"
    async with await _client(settings) as client:
        detail = await client.get(path, headers=_headers(str(keys["ops"])))
        assert detail.status_code == 200
        assert detail.json()["state"] == "RESERVED"
        evidence = await client.get(path + "/request-evidence", headers=_headers(str(keys["ops"])))
        assert evidence.status_code == 409
        assert evidence.json()["error"]["code"] == "REQUEST_EVIDENCE_STATE_UNSUPPORTED"


@pytest.mark.integration
async def test_request_evidence_fingerprint_tracks_actual_asset_mutations(
    settings: Settings, database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _seed(database)
    path = f"/api/v1/guarantees/{keys['guarantee']}/request-evidence"
    async with await _client(settings) as client:
        before = await client.get(path, headers=_headers(str(keys["ops"])))
        assert before.status_code == 200
    async with database.session_factory() as session:
        async with session.begin():
            asset = await session.get(AssetPosition, keys["owned"])
            assert asset is not None
            asset.quantity = Decimal("6.25")
    async with await _client(settings) as client:
        after = await client.get(path, headers=_headers(str(keys["ops"])))
        assert after.status_code == 200
    assert before.json()["evidence_fingerprint"] != after.json()["evidence_fingerprint"]


def test_guarantee_ops_openapi_list_workspace_contract(settings: Settings) -> None:
    api = create_app(settings).openapi()
    listing = api["paths"]["/api/v1/guarantees"]["get"]
    workspace = api["paths"]["/api/v1/guarantees/{guarantee_id}/workspace"]["get"]
    assert {"401", "403", "422"}.issubset(listing["responses"])
    assert {"401", "403", "404", "409"}.issubset(workspace["responses"])
    components = api["components"]["schemas"]
    assert components["GuaranteeListView"]["properties"]["next_cursor"]
    assert components["GuaranteeWorkspaceFoundationView"]["properties"]["request_evidence"]
    assert (
        components["ExternalLoanObservedView"]["properties"]["outstanding_principal"]["format"]
        == "decimal"
    )


@pytest.mark.integration
async def test_program_scoped_guarantee_listing_pagination_and_authorization(
    settings: Settings, database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _seed(database)
    async with database.session_factory() as session:
        async with session.begin():
            original = await session.get(GuaranteeCase, keys["guarantee"])
            assert original is not None
            for _ in range(4):
                session.add(
                    GuaranteeCase(
                        participation_episode_id=original.participation_episode_id,
                        provider_id=original.provider_id,
                        credit_product_version_id=original.credit_product_version_id,
                        state="REQUESTED",
                        requested_principal=Decimal("11"),
                        current_guarantee_exposure=Decimal("0"),
                        guarantee_mode="FIXED",
                    )
                )
    base_url = "/api/v1/guarantees"
    params = {"program_id": str(keys["program"]), "limit": 2}
    async with await _client(settings) as client:
        all_ids: list[str] = []
        next_cursor = None
        while True:
            page_params = dict(params)
            if next_cursor is not None:
                page_params["after"] = next_cursor
            result = await client.get(
                base_url, headers=_headers(str(keys["ops"])), params=page_params
            )
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["program_id"] == str(keys["program"])
            assert len(body["items"]) <= 2
            all_ids += [entry["id"] for entry in body["items"]]
            next_cursor = body["next_cursor"]
            if next_cursor is None:
                break
        assert len(all_ids) == len(set(all_ids)) == 5
        assert all_ids == sorted(all_ids)
        assert str(keys["guarantee"]) in all_ids
        for role in ("risk", "finance", "auditor"):
            scoped = await client.get(base_url, headers=_headers(str(keys[role])), params=params)
            assert scoped.status_code == 200
        outsider = await client.get(
            base_url, headers=_headers(str(keys["outsider"])), params=params
        )
        assert outsider.status_code == 403
        assert (await client.get(base_url, params=params)).status_code == 401
        assert (
            await client.get(base_url, headers=_headers(str(keys["ops"])), params={"limit": 3})
        ).status_code == 422
        assert (
            await client.get(
                base_url,
                headers=_headers(str(keys["ops"])),
                params={"program_id": str(keys["program"]), "limit": 101},
            )
        ).status_code == 422
        empty = await client.get(
            base_url,
            headers=_headers(str(keys["ops"])),
            params={"program_id": str(keys["program"]), "state": "CLOSED"},
        )
        assert empty.status_code == 200
        assert empty.json()["items"] == []
        assert empty.json()["next_cursor"] is None


@pytest.mark.integration
async def test_workspace_uses_real_observed_sources_and_denies_cross_program(
    settings: Settings, database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _seed(database)
    url = f"/api/v1/guarantees/{keys['guarantee']}/workspace"
    async with await _client(settings) as client:
        for role in ("ops", "risk", "finance", "auditor"):
            result = await client.get(url, headers=_headers(str(keys[role])))
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["program_id"] == str(keys["program"])
            assert body["guarantee"]["state"] == "REQUESTED"
            assert body["provider"]["lifecycle_status"] == "DRAFT"
            assert body["captured_product"]["lifecycle_status"] == "DRAFT"
            assert body["request_evidence"]["guarantee_case_id"] == str(keys["guarantee"])
            assert len(body["request_evidence"]["backing"]["sources"]) == 2
            assert body["external_loan"] is None
            assert not body["backing_allocation_contract_available"]
            assert not body["claim_recovery_contract_available"]
            assert not body["action_eligibility_evaluated"]
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=_headers(str(keys["outsider"])))).status_code == 403
        missing = await client.get(
            f"/api/v1/guarantees/{uuid4()}/workspace",
            headers=_headers(str(keys["ops"])),
        )
        assert missing.status_code == 404


@pytest.mark.integration
async def test_workspace_refuses_mismatched_captured_product_and_keeps_state_observed(
    settings: Settings, database, clean_sprint07_guarantee_tables
) -> None:
    keys = await _seed(database)
    url = f"/api/v1/guarantees/{keys['guarantee']}/workspace"
    async with database.session_factory() as session:
        async with session.begin():
            guarantee = await session.get(GuaranteeCase, keys["guarantee"])
            assert guarantee is not None
            guarantee.state = "RESERVED"
    async with await _client(settings) as client:
        result = await client.get(url, headers=_headers(str(keys["ops"])))
        assert result.status_code == 200, result.text
        assert result.json()["guarantee"]["state"] == "RESERVED"
        assert result.json()["request_evidence"] is None
    async with database.session_factory() as session:
        async with session.begin():
            guarantee = await session.get(GuaranteeCase, keys["guarantee"])
            assert guarantee is not None
            original_provider = await session.get(CreditProvider, guarantee.provider_id)
            assert original_provider is not None
            other = CreditProvider(
                legal_entity_id=original_provider.legal_entity_id,
                provider_code=f"WS-OTHER-{uuid4().hex[:12]}",
                display_name="Different Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="CONTROLLED_MANUAL",
                authorization_review_state="PENDING",
                lifecycle_status="DRAFT",
                created_by=uuid4(),
            )
            session.add(other)
            await session.flush()
            guarantee.provider_id = other.id
    async with await _client(settings) as client:
        mismatch = await client.get(url, headers=_headers(str(keys["ops"])))
        assert mismatch.status_code == 409
        assert mismatch.json()["error"]["code"] == "GUARANTEE_WORKSPACE_LINEAGE_CONFLICT"
