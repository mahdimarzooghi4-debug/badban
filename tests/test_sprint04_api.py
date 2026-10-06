from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from badban.api.app import create_app
from badban.application.decision_snapshot import create_decision_snapshot
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_lifecycle import policy_transition_approval_payload
from badban.application.policy_resolution import ResolvedPolicyPack
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    Identity,
    PolicyVersion,
    RoleGrant,
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


async def _seed_identity(
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
                    scope_type="GLOBAL",
                    scope_id=None,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint04-api-test",
                )
            )
    return identity


async def _approved_transition(
    database,
    *,
    policy_id: UUID,
    target_status: str,
    checker: Identity,
) -> UUID:
    maker = Identity(
        identity_type="STAFF",
        external_subject=f"maker-{uuid4()}",
        status="ACTIVE",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(maker)
            await session.flush()
            policy = await session.get(PolicyVersion, policy_id)
            assert policy is not None
            payload = policy_transition_approval_payload(policy, target_status)
            action_type = "POLICY_APPROVAL" if target_status == "APPROVED" else "POLICY_ACTIVATION"
            approval = ApprovalRequest(
                action_type=action_type,
                target_type="PolicyVersion",
                target_id=str(policy.id),
                target_aggregate_version=policy.version,
                maker_identity_id=maker.id,
                checker_identity_id=checker.id,
                required_checker_role="GOVERNANCE_APPROVER",
                scope_type="GLOBAL",
                scope_id=None,
                payload_hash=canonical_request_hash(payload),
                reason="sprint04 api test",
                evidence_refs=[],
                status="APPROVED",
                approved_at=datetime.now(UTC),
                version=2,
            )
            session.add(approval)
            await session.flush()
            return approval.id


@pytest.mark.integration
async def test_policy_pack_admin_api_lifecycle_and_read_access(
    settings: Settings,
    database,
    clean_sprint03_tables,
    clean_sprint04_policy_tables,
) -> None:
    governance = await _seed_identity(
        database,
        subject="policy-governance",
        identity_type="GOVERNANCE",
        role="GOVERNANCE_APPROVER",
    )
    await _seed_identity(
        database,
        subject="policy-auditor",
        identity_type="AUDITOR",
        role="AUDITOR",
    )

    async with await _client(settings) as client:
        created = await client.post(
            "/api/v1/admin/policy-packs",
            headers=_headers("policy-governance", "create-pack"),
            json={
                "policy_code": "BOUNDED_PILOT",
                "version_number": 1,
                "scope_definition": {"pilot_scope": "bounded-pilot"},
                "component_version_ids": [],
                "schema_version": "1",
            },
        )
        assert created.status_code == 201
        policy_id = UUID(created.json()["id"])
        assert created.json()["lifecycle_status"] == "DRAFT"

        replay = await client.post(
            "/api/v1/admin/policy-packs",
            headers=_headers("policy-governance", "create-pack"),
            json={
                "policy_code": "BOUNDED_PILOT",
                "version_number": 1,
                "scope_definition": {"pilot_scope": "bounded-pilot"},
                "component_version_ids": [],
                "schema_version": "1",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == str(policy_id)

        reviewed = await client.post(
            f"/api/v1/admin/policy-packs/{policy_id}/review",
            headers=_headers("policy-governance", "review-pack"),
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["lifecycle_status"] == "REVIEWED"

    approval_id = await _approved_transition(
        database,
        policy_id=policy_id,
        target_status="APPROVED",
        checker=governance,
    )

    async with await _client(settings) as client:
        approved = await client.post(
            f"/api/v1/admin/policy-packs/{policy_id}/approve",
            headers=_headers("policy-governance", "approve-pack"),
            json={"approval_id": str(approval_id)},
        )
        assert approved.status_code == 200
        assert approved.json()["lifecycle_status"] == "APPROVED"
        assert approved.json()["approved_by"] == str(governance.id)

    activation_id = await _approved_transition(
        database,
        policy_id=policy_id,
        target_status="ACTIVE",
        checker=governance,
    )

    async with await _client(settings) as client:
        activated = await client.post(
            f"/api/v1/admin/policy-packs/{policy_id}/activate",
            headers=_headers("policy-governance", "activate-pack"),
            json={"approval_id": str(activation_id)},
        )
        assert activated.status_code == 200
        assert activated.json()["lifecycle_status"] == "ACTIVE"

        auditor_read = await client.get(
            f"/api/v1/admin/policy-packs/{policy_id}",
            headers=_headers("policy-auditor"),
        )
        assert auditor_read.status_code == 200
        assert auditor_read.json()["id"] == str(policy_id)

        listing = await client.get(
            "/api/v1/admin/policy-packs?limit=10",
            headers=_headers("policy-auditor"),
        )
        assert listing.status_code == 200
        assert [item["id"] for item in listing.json()["items"]] == [str(policy_id)]

        retired = await client.post(
            f"/api/v1/admin/policy-packs/{policy_id}/retire",
            headers=_headers("policy-governance", "retire-pack"),
        )
        assert retired.status_code == 200
        assert retired.json()["lifecycle_status"] == "RETIRED"


@pytest.mark.integration
async def test_policy_pack_admin_writes_require_governance_role(
    settings: Settings,
    database,
    clean_sprint03_tables,
    clean_sprint04_policy_tables,
) -> None:
    await _seed_identity(
        database,
        subject="read-only-auditor",
        identity_type="AUDITOR",
        role="AUDITOR",
    )

    async with await _client(settings) as client:
        denied = await client.post(
            "/api/v1/admin/policy-packs",
            headers=_headers("read-only-auditor", "denied-create"),
            json={
                "policy_code": "DENIED",
                "version_number": 1,
                "scope_definition": {"pilot_scope": "bounded-pilot"},
                "component_version_ids": [],
                "schema_version": "1",
            },
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "AUTHORIZATION_DENIED"


@pytest.mark.integration
async def test_decision_snapshot_is_read_only_through_admin_api(
    settings: Settings,
    database,
    clean_sprint03_tables,
    clean_sprint04_policy_tables,
) -> None:
    governance = await _seed_identity(
        database,
        subject="snapshot-governance",
        identity_type="GOVERNANCE",
        role="GOVERNANCE_APPROVER",
    )
    auditor = await _seed_identity(
        database,
        subject="snapshot-auditor",
        identity_type="AUDITOR",
        role="AUDITOR",
    )
    pack = PolicyVersion(
        policy_type="PILOT_POLICY_PACK",
        policy_code="SNAPSHOT_API_PACK",
        version_number=1,
        lifecycle_status="ACTIVE",
        scope_definition={"pilot_scope": "bounded-pilot"},
        payload={"component_version_ids": []},
        payload_hash=canonical_request_hash({"component_version_ids": []}),
        schema_version="1",
        activated_at=datetime.now(UTC),
        created_by=governance.id,
        approved_by=governance.id,
        approved_at=datetime.now(UTC),
        version=4,
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(pack)
            await session.flush()
            resolved = ResolvedPolicyPack(
                policy_pack_id=pack.id,
                policy_code=pack.policy_code,
                version_number=pack.version_number,
                component_version_ids=(),
            )
            snapshot = await create_decision_snapshot(
                session,
                business_entity_type="SYNTHETIC_ENTITY",
                business_entity_id="entity-api-1",
                decision_type="SYNTHETIC_DECISION",
                resolved_policy_pack=resolved,
                algorithm_code="SYNTHETIC_ALGORITHM",
                algorithm_version="v1",
                material_input_payload={"input": "1"},
                material_output_payload={"output": "1"},
                effective_at=datetime.now(UTC),
                actor_type="SYSTEM",
                actor_id=governance.id,
            )
            snapshot_id = snapshot.id

    async with await _client(settings) as client:
        read = await client.get(
            f"/api/v1/admin/decision-snapshots/{snapshot_id}",
            headers=_headers("snapshot-auditor"),
        )
        assert read.status_code == 200
        assert read.json()["id"] == str(snapshot_id)
        assert read.json()["policy_pack_id"] == str(pack.id)

        no_generic_write = await client.post(
            "/api/v1/admin/decision-snapshots",
            headers=_headers("snapshot-governance", "forged-snapshot"),
            json={"forged": True},
        )
        assert no_generic_write.status_code == 404

    assert auditor.identity_type == "AUDITOR"
