from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from badban.api.app import create_app
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    AuditEvent,
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
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_OPERATIONS,
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


def _headers(subject: str, key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        "Idempotency-Key": key,
    }


async def _seed_request_context(database):
    operations = Identity(
        identity_type="STAFF",
        external_subject="sprint07-operations",
        status="ACTIVE",
    )
    auditor = Identity(
        identity_type="AUDITOR",
        external_subject="sprint07-auditor",
        status="ACTIVE",
    )
    participant = Participant(
        external_reference=f"participant-{uuid4()}",
        lifecycle_status="ACTIVE",
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([operations, auditor, participant])
            await session.flush()

            program = Program(
                code=f"PROGRAM-{uuid4()}",
                name="Synthetic Program",
                status="ACTIVE",
                legal_entity_id=None,
                created_by=operations.id,
                version=1,
            )
            session.add(program)
            await session.flush()

            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                eligibility_reference="synthetic-eligibility",
                consent_state="ACCEPTED",
                started_at=datetime.now(UTC) - timedelta(days=1),
                ended_at=None,
                created_by=operations.id,
                version=1,
            )
            entity = LegalEntity(
                legal_name="Synthetic Lender Entity",
                registration_identifier=f"REG-{uuid4()}",
                entity_type="SYNTHETIC_LENDER",
                status="ACTIVE",
                created_by=operations.id,
                version=1,
            )
            session.add_all([episode, entity])
            await session.flush()

            provider = CreditProvider(
                legal_entity_id=entity.id,
                provider_code=f"PROVIDER-{uuid4()}",
                display_name="Synthetic Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="CONTROLLED_MANUAL",
                authorization_review_state="SYNTHETIC_PENDING",
                lifecycle_status="DRAFT",
                created_by=operations.id,
                version=1,
            )
            session.add(provider)
            await session.flush()

            product = CreditProductVersion(
                provider_id=provider.id,
                lender_of_record_legal_entity_id=entity.id,
                product_code=f"PRODUCT-{uuid4()}",
                version_number=1,
                product_name="Synthetic Product",
                product_type="SYNTHETIC_EXTERNAL_CREDIT",
                lifecycle_status="DRAFT",
                currency="IRR",
                min_principal=Decimal("10"),
                max_principal=Decimal("100"),
                tenor_definition={"mode": "SYNTHETIC", "reference": "test"},
                repayment_definition={"mode": "SYNTHETIC", "reference": "test"},
                pricing_definition={"mode": "SYNTHETIC", "reference": "test"},
                guarantee_mode="FIXED",
                delinquency_definition={"mode": "SYNTHETIC", "reference": "test"},
                claim_definition={"mode": "SYNTHETIC", "reference": "test"},
                policy_version_reference="synthetic-policy:1",
                additional_terms={},
                effective_from=datetime.now(UTC) - timedelta(minutes=1),
                effective_to=None,
                created_by=operations.id,
                version=1,
            )
            session.add(product)
            await session.flush()

            session.add_all(
                [
                    RoleGrant(
                        identity_id=operations.id,
                        role_code=ROLE_OPERATIONS,
                        scope_type=SCOPE_PROGRAM,
                        scope_id=program.id,
                        valid_from=datetime.now(UTC) - timedelta(minutes=1),
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=None,
                        reason_ref="sprint07-test",
                        version=1,
                    ),
                    RoleGrant(
                        identity_id=auditor.id,
                        role_code=ROLE_AUDITOR,
                        scope_type=SCOPE_GLOBAL,
                        scope_id=None,
                        valid_from=datetime.now(UTC) - timedelta(minutes=1),
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=None,
                        reason_ref="sprint07-test",
                        version=1,
                    ),
                ]
            )
            await session.flush()

            return operations, auditor, episode, provider, product


async def _count(session, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.integration
async def test_create_guarantee_request_is_idempotent_requested_only_and_side_effect_free(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    operations, _, episode, provider, product = await _seed_request_context(database)

    async with database.session_factory() as session:
        baseline_snapshots = await _count(session, DecisionSnapshot)
        baseline_journals = await _count(session, JournalEntry)
        baseline_outbox = await _count(session, OutboxMessage)

    payload = {
        "participation_episode_id": str(episode.id),
        "provider_id": str(provider.id),
        "credit_product_version_id": str(product.id),
        "requested_principal": "25.125",
    }

    async with await _client(settings) as client:
        first = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, "guarantee-request-1"),
            json=payload,
        )
        assert first.status_code == 201
        replay = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, "guarantee-request-1"),
            json=payload,
        )
        assert replay.status_code == 201
        assert replay.json() == first.json()

    body = first.json()
    guarantee_id = UUID(body["id"])
    assert body["state"] == "REQUESTED"
    assert isinstance(body["requested_principal"], str)
    assert Decimal(body["requested_principal"]) == Decimal("25.125")
    assert body["provider_id"] == str(provider.id)
    assert body["credit_product_version_id"] == str(product.id)
    assert body["guarantee_mode"] == product.guarantee_mode
    assert body["policy_pack_id"] is None
    assert body["reserved_guarantee_amount"] is None
    assert body["issued_guarantee_amount"] is None
    assert isinstance(body["current_guarantee_exposure"], str)
    assert Decimal(body["current_guarantee_exposure"]) == Decimal("0")
    assert body["reservation_expires_at"] is None
    assert body["legal_guarantee_external_id"] is None
    assert body["legal_guarantee_issuer_id"] is None
    assert body["external_loan_mirror_id"] is None
    assert body["risk_snapshot_id"] is None
    assert body["version"] == 1

    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 1
        stored = await session.get(GuaranteeCase, guarantee_id)
        assert stored is not None
        assert stored.policy_pack_id is None
        assert stored.state == "REQUESTED"
        assert stored.requested_principal == Decimal("25.125")
        assert await _count(session, DecisionSnapshot) == baseline_snapshots
        assert await _count(session, JournalEntry) == baseline_journals
        assert await _count(session, OutboxMessage) == baseline_outbox
        audit_actions = (
            await session.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.aggregate_type == "GuaranteeCase",
                    AuditEvent.aggregate_id == str(guarantee_id),
                )
            )
        ).all()
        assert audit_actions == ["GUARANTEE_REQUEST_CREATE"]


@pytest.mark.integration
async def test_concurrent_same_key_same_payload_creates_one_case_and_replays(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    operations, _, episode, provider, product = await _seed_request_context(database)
    payload = {
        "participation_episode_id": str(episode.id),
        "provider_id": str(provider.id),
        "credit_product_version_id": str(product.id),
        "requested_principal": "25.125",
    }

    async with await _client(settings) as client:
        first, second = await asyncio.gather(
            client.post(
                "/api/v1/guarantees",
                headers=_headers(operations.external_subject, "guarantee-concurrent"),
                json=payload,
            ),
            client.post(
                "/api/v1/guarantees",
                headers=_headers(operations.external_subject, "guarantee-concurrent"),
                json=payload,
            ),
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 1


@pytest.mark.integration
async def test_requested_principal_requires_decimal_string_and_storage_safe_scale(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    operations, _, episode, provider, product = await _seed_request_context(database)
    common = {
        "participation_episode_id": str(episode.id),
        "provider_id": str(provider.id),
        "credit_product_version_id": str(product.id),
    }

    async with await _client(settings) as client:
        binary_number = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, "decimal-number"),
            json={**common, "requested_principal": 25.125},
        )
        excessive_scale = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, "decimal-scale"),
            json={**common, "requested_principal": "25.0000000000000000001"},
        )

    assert binary_number.status_code == 422
    assert excessive_scale.status_code == 422
    assert excessive_scale.json()["error"]["code"] == "GUARANTEE_REQUEST_INVALID"
    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 0


@pytest.mark.integration
async def test_operations_grant_for_different_program_cannot_create_request(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    operations, _, episode, provider, product = await _seed_request_context(database)
    wrong_scope_identity = Identity(
        identity_type="STAFF",
        external_subject="sprint07-wrong-program",
        status="ACTIVE",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(wrong_scope_identity)
            await session.flush()
            other_program = Program(
                code=f"PROGRAM-{uuid4()}",
                name="Other Synthetic Program",
                status="ACTIVE",
                legal_entity_id=None,
                created_by=operations.id,
                version=1,
            )
            session.add(other_program)
            await session.flush()
            session.add(
                RoleGrant(
                    identity_id=wrong_scope_identity.id,
                    role_code=ROLE_OPERATIONS,
                    scope_type=SCOPE_PROGRAM,
                    scope_id=other_program.id,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint07-wrong-scope",
                    version=1,
                )
            )

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/guarantees",
            headers=_headers("sprint07-wrong-program", "wrong-program"),
            json={
                "participation_episode_id": str(episode.id),
                "provider_id": str(provider.id),
                "credit_product_version_id": str(product.id),
                "requested_principal": "25",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 0


@pytest.mark.integration
async def test_changed_payload_reusing_idempotency_key_fails_without_duplicate_case(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    operations, _, episode, provider, product = await _seed_request_context(database)
    base_payload = {
        "participation_episode_id": str(episode.id),
        "provider_id": str(provider.id),
        "credit_product_version_id": str(product.id),
        "requested_principal": "25",
    }

    async with await _client(settings) as client:
        first = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, "guarantee-request-conflict"),
            json=base_payload,
        )
        assert first.status_code == 201
        conflict = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, "guarantee-request-conflict"),
            json={**base_payload, "requested_principal": "26"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 1


@pytest.mark.integration
@pytest.mark.parametrize("requested_principal", ["9.999", "100.001"])
async def test_request_rejects_principal_outside_exact_product_bounds(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
    requested_principal: str,
) -> None:
    operations, _, episode, provider, product = await _seed_request_context(database)

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, f"bound-{requested_principal}"),
            json={
                "participation_episode_id": str(episode.id),
                "provider_id": str(provider.id),
                "credit_product_version_id": str(product.id),
                "requested_principal": requested_principal,
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GUARANTEE_REQUEST_INVALID"
    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 0


@pytest.mark.integration
async def test_request_rejects_product_from_different_provider(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    operations, _, episode, provider, product = await _seed_request_context(database)

    async with database.session_factory() as session:
        async with session.begin():
            other_entity = LegalEntity(
                legal_name="Other Synthetic Lender",
                registration_identifier=f"REG-{uuid4()}",
                entity_type="SYNTHETIC_LENDER",
                status="ACTIVE",
                created_by=operations.id,
                version=1,
            )
            session.add(other_entity)
            await session.flush()
            other_provider = CreditProvider(
                legal_entity_id=other_entity.id,
                provider_code=f"PROVIDER-{uuid4()}",
                display_name="Other Synthetic Provider",
                provider_type="EXTERNAL_LENDER",
                integration_mode="CONTROLLED_MANUAL",
                authorization_review_state="SYNTHETIC_PENDING",
                lifecycle_status="DRAFT",
                created_by=operations.id,
                version=1,
            )
            session.add(other_provider)
            await session.flush()
            other_provider_id = other_provider.id

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/guarantees",
            headers=_headers(operations.external_subject, "provider-mismatch"),
            json={
                "participation_episode_id": str(episode.id),
                "provider_id": str(other_provider_id),
                "credit_product_version_id": str(product.id),
                "requested_principal": "25",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GUARANTEE_REQUEST_INVALID"
    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 0


@pytest.mark.integration
async def test_auditor_cannot_create_guarantee_request_and_no_case_is_created(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    _, auditor, episode, provider, product = await _seed_request_context(database)

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/guarantees",
            headers=_headers(auditor.external_subject, "auditor-guarantee"),
            json={
                "participation_episode_id": str(episode.id),
                "provider_id": str(provider.id),
                "credit_product_version_id": str(product.id),
                "requested_principal": "25",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    async with database.session_factory() as session:
        assert await _count(session, GuaranteeCase) == 0
