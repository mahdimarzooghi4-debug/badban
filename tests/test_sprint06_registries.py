from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.approval import approval_payload_hash
from badban.application.registry import (
    activate_credit_product_version,
    approve_provider_due_diligence,
    create_credit_product_version,
    legal_authorization_verification_payload,
    provider_activation_payload,
)
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    CreditProductVersion,
    CreditProvider,
    Identity,
    LegalAuthorization,
    LegalEntity,
    RoleGrant,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    SCOPE_GLOBAL,
    SCOPE_LEGAL_ENTITY,
    SCOPE_PROVIDER,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _headers(subject: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {subject}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


async def _identity(database, subject: str, identity_type: str = "STAFF") -> Identity:
    identity = Identity(
        identity_type=identity_type,
        external_subject=subject,
        status="ACTIVE",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(identity)
            await session.flush()
    return identity


async def _grant(
    database,
    *,
    identity_id: UUID,
    role_code: str,
    scope_type: str,
    scope_id: UUID | None,
) -> None:
    async with database.session_factory() as session:
        async with session.begin():
            session.add(
                RoleGrant(
                    identity_id=identity_id,
                    role_code=role_code,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint06-test",
                )
            )


async def _legal_entity(database, *, created_by: UUID) -> LegalEntity:
    entity = LegalEntity(
        legal_name="Synthetic External Lender Legal Entity",
        legal_identifier=f"LEGAL-{uuid4()}",
        created_by=created_by,
        version=1,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(entity)
            await session.flush()
    return entity


async def _approval(
    database,
    *,
    action_type: str,
    target_type: str,
    target_id: UUID,
    target_version: int,
    maker: Identity,
    checker: Identity,
    checker_role: str,
    scope_type: str,
    scope_id: UUID,
    payload: dict[str, object],
) -> ApprovalRequest:
    request = ApprovalRequest(
        action_type=action_type,
        target_type=target_type,
        target_id=str(target_id),
        target_aggregate_version=target_version,
        maker_identity_id=maker.id,
        checker_identity_id=checker.id,
        required_checker_role=checker_role,
        scope_type=scope_type,
        scope_id=scope_id,
        payload_hash=approval_payload_hash(payload),
        reason="sprint06 test approval",
        evidence_refs=[],
        status="APPROVED",
        approved_at=datetime.now(UTC),
        version=2,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(request)
            await session.flush()
    return request


@pytest.mark.integration
async def test_legal_authorization_and_provider_activation_flow(
    settings: Settings,
    database,
    clean_sprint03_tables,
    clean_sprint06_registry_tables,
) -> None:
    legal_maker = await _identity(database, "sprint06-legal-maker")
    legal_checker = await _identity(database, "sprint06-legal-checker")
    governance_maker = await _identity(database, "sprint06-gov-maker", "GOVERNANCE")
    governance_checker = await _identity(database, "sprint06-gov-checker", "GOVERNANCE")
    auditor = await _identity(database, "sprint06-auditor", "AUDITOR")

    await _grant(
        database,
        identity_id=legal_maker.id,
        role_code=ROLE_LEGAL_COMPLIANCE,
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
    )
    await _grant(
        database,
        identity_id=auditor.id,
        role_code=ROLE_AUDITOR,
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
    )
    entity = await _legal_entity(database, created_by=legal_maker.id)
    for identity in (legal_maker, legal_checker):
        await _grant(
            database,
            identity_id=identity.id,
            role_code=ROLE_LEGAL_COMPLIANCE,
            scope_type=SCOPE_LEGAL_ENTITY,
            scope_id=entity.id,
        )

    now = datetime.now(UTC)
    async with await _client(settings) as client:
        authorization_response = await client.post(
            f"/api/v1/admin/legal-entities/{entity.id}/authorizations",
            headers=_headers("sprint06-legal-maker", "auth-create"),
            json={
                "role_code": "EXTERNAL_LENDER",
                "competent_authority": "Synthetic Competent Authority",
                "authorization_type": "SYNTHETIC_LICENSE",
                "authorization_identifier": "SYNTHETIC-LICENSE-1",
                "permitted_product_scope": {"program_codes": ["SYNTHETIC"]},
                "permitted_asset_type_ids": [],
                "evidence_reference": "evidence://sprint06/legal/1",
                "effective_from": (now - timedelta(days=1)).isoformat(),
                "expires_at": (now + timedelta(days=30)).isoformat(),
                "last_compliance_review_at": now.isoformat(),
            },
        )
        assert authorization_response.status_code == 201
        authorization_id = UUID(authorization_response.json()["id"])

    async with database.session_factory() as session:
        authorization = await session.get(LegalAuthorization, authorization_id)
        assert authorization is not None
        verification_payload = legal_authorization_verification_payload(authorization)
        authorization_version = authorization.version

    verify_approval = await _approval(
        database,
        action_type="LEGAL_AUTHORIZATION_VERIFY",
        target_type="LegalAuthorization",
        target_id=authorization_id,
        target_version=authorization_version,
        maker=legal_maker,
        checker=legal_checker,
        checker_role=ROLE_LEGAL_COMPLIANCE,
        scope_type=SCOPE_LEGAL_ENTITY,
        scope_id=entity.id,
        payload=verification_payload,
    )

    async with await _client(settings) as client:
        verified = await client.post(
            f"/api/v1/admin/authorizations/{authorization_id}/verify",
            headers=_headers("sprint06-legal-checker", "auth-verify"),
            json={"approval_id": str(verify_approval.id)},
        )
        assert verified.status_code == 200
        assert verified.json()["lifecycle_status"] == "VALID"

        provider_response = await client.post(
            "/api/v1/admin/providers",
            headers=_headers("sprint06-legal-maker", "provider-create"),
            json={
                "legal_entity_id": str(entity.id),
                "provider_code": "SYNTHETIC_LENDER",
                "display_name": "Synthetic External Lender",
            },
        )
        assert provider_response.status_code == 201
        provider_id = UUID(provider_response.json()["id"])
        assert provider_response.json()["provider_type"] == "EXTERNAL_LENDER"
        assert provider_response.json()["lifecycle_status"] == "DRAFT"

        direct_lending_attempt = await client.post(
            "/api/v1/admin/providers",
            headers=_headers("sprint06-legal-maker", "direct-provider"),
            json={
                "legal_entity_id": str(entity.id),
                "provider_code": "DIRECT_BADBAN",
                "display_name": "Direct Badban",
                "provider_type": "DIRECT_LENDING",
            },
        )
        assert direct_lending_attempt.status_code == 422

    for identity in (governance_maker, governance_checker):
        await _grant(
            database,
            identity_id=identity.id,
            role_code=ROLE_GOVERNANCE_APPROVER,
            scope_type=SCOPE_PROVIDER,
            scope_id=provider_id,
        )

    async with database.session_factory() as session:
        async with session.begin():
            provider = await approve_provider_due_diligence(
                session,
                provider_id=provider_id,
                actor_type="STAFF",
                actor_id=legal_maker.id,
                correlation_id=uuid4(),
            )
            activation_payload = provider_activation_payload(provider)
            provider_version = provider.version

    activation_approval = await _approval(
        database,
        action_type="PROVIDER_ACTIVATION",
        target_type="CreditProvider",
        target_id=provider_id,
        target_version=provider_version,
        maker=governance_maker,
        checker=governance_checker,
        checker_role=ROLE_GOVERNANCE_APPROVER,
        scope_type=SCOPE_PROVIDER,
        scope_id=provider_id,
        payload=activation_payload,
    )

    async with await _client(settings) as client:
        activated = await client.post(
            f"/api/v1/admin/providers/{provider_id}/activate",
            headers=_headers("sprint06-gov-checker", "provider-activate"),
            json={"approval_id": str(activation_approval.id)},
        )
        assert activated.status_code == 200
        assert activated.json()["lifecycle_status"] == "ACTIVE"

        read = await client.get(
            f"/api/v1/admin/providers/{provider_id}",
            headers=_headers("sprint06-auditor"),
        )
        assert read.status_code == 200
        assert read.json()["id"] == str(provider_id)


@pytest.mark.integration
async def test_provider_activation_fails_closed_without_valid_legal_authorization(
    database,
    clean_sprint03_tables,
    clean_sprint06_registry_tables,
) -> None:
    legal = await _identity(database, "sprint06-noauth-legal")
    gov_maker = await _identity(database, "sprint06-noauth-maker", "GOVERNANCE")
    gov_checker = await _identity(database, "sprint06-noauth-checker", "GOVERNANCE")
    entity = await _legal_entity(database, created_by=legal.id)
    provider = CreditProvider(
        legal_entity_id=entity.id,
        provider_code="NO_AUTH_PROVIDER",
        display_name="No Auth Provider",
        provider_type="EXTERNAL_LENDER",
        lifecycle_status="APPROVED",
        approved_at=datetime.now(UTC),
        created_by=legal.id,
        version=2,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(provider)
            await session.flush()
            provider_id = provider.id
            payload = provider_activation_payload(provider)

    approval = await _approval(
        database,
        action_type="PROVIDER_ACTIVATION",
        target_type="CreditProvider",
        target_id=provider_id,
        target_version=2,
        maker=gov_maker,
        checker=gov_checker,
        checker_role=ROLE_GOVERNANCE_APPROVER,
        scope_type=SCOPE_PROVIDER,
        scope_id=provider_id,
        payload=payload,
    )

    from badban.application.registry import activate_provider

    async with database.session_factory() as session:
        with pytest.raises(Exception) as exc:
            async with session.begin():
                await activate_provider(
                    session,
                    provider_id=provider_id,
                    approval_id=approval.id,
                    actor_type="GOVERNANCE",
                    actor_id=gov_checker.id,
                    correlation_id=uuid4(),
                )

    assert getattr(exc.value, "code", None) == "AUTHORIZATION_INVALID"


@pytest.mark.integration
async def test_product_version_requires_active_provider_and_history_is_immutable(
    database,
    clean_sprint03_tables,
    clean_sprint06_registry_tables,
) -> None:
    actor = await _identity(database, "sprint06-product-actor")
    entity = await _legal_entity(database, created_by=actor.id)
    provider = CreditProvider(
        legal_entity_id=entity.id,
        provider_code="PRODUCT_PROVIDER",
        display_name="Product Provider",
        provider_type="EXTERNAL_LENDER",
        lifecycle_status="ACTIVE",
        approved_at=datetime.now(UTC),
        activated_at=datetime.now(UTC),
        created_by=actor.id,
        version=3,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(provider)
            await session.flush()
            product = await create_credit_product_version(
                session,
                provider_id=provider.id,
                product_code="SYNTHETIC_PRODUCT",
                version_number=1,
                product_name="Synthetic Product",
                terms={
                    "currency": "IRR",
                    "amount_rule_reference": "synthetic-only",
                    "tenor_model": {"type": "EXPLICIT_PROVIDER_CONFIGURATION"},
                },
                effective_from=datetime.now(UTC),
                effective_to=None,
                created_by=actor.id,
            )
            product_id = product.id
            await activate_credit_product_version(
                session,
                product_version_id=product.id,
            )

    async with database.session_factory() as session:
        product = await session.get(CreditProductVersion, product_id)
        assert product is not None
        assert product.lifecycle_status == "ACTIVE"
        assert product.lender_of_record_legal_entity_id == entity.id
        assert product.terms["currency"] == "IRR"

    with pytest.raises(DBAPIError):
        async with database.session_factory() as session:
            async with session.begin():
                product = await session.get(CreditProductVersion, product_id)
                assert product is not None
                product.terms = {"currency": "USD"}
                await session.flush()


@pytest.mark.integration
async def test_legal_authorization_scope_types_work_with_generic_approval_api(
    settings: Settings,
    database,
    clean_sprint03_tables,
    clean_sprint06_registry_tables,
) -> None:
    maker = await _identity(database, "sprint06-scope-maker")
    checker = await _identity(database, "sprint06-scope-checker")
    entity = await _legal_entity(database, created_by=maker.id)
    for identity in (maker, checker):
        await _grant(
            database,
            identity_id=identity.id,
            role_code=ROLE_LEGAL_COMPLIANCE,
            scope_type=SCOPE_LEGAL_ENTITY,
            scope_id=entity.id,
        )

    async with await _client(settings) as client:
        created = await client.post(
            "/api/v1/approval-requests",
            headers=_headers("sprint06-scope-maker", "approval-scope-create"),
            json={
                "action_type": "LEGAL_AUTHORIZATION_VERIFY",
                "target_type": "LegalAuthorization",
                "target_id": str(uuid4()),
                "target_aggregate_version": 1,
                "required_checker_role": "LEGAL_COMPLIANCE",
                "scope_type": "LEGAL_ENTITY",
                "scope_id": str(entity.id),
                "payload": {"synthetic": True},
                "evidence_refs": [],
            },
        )
        assert created.status_code == 201
        approval_id = created.json()["id"]

        approved = await client.post(
            f"/api/v1/approval-requests/{approval_id}/approve",
            headers=_headers("sprint06-scope-checker"),
            json={},
        )
        assert approved.status_code == 200
        assert approved.json()["scope_type"] == "LEGAL_ENTITY"
