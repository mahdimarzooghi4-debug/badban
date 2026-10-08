from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.business_readiness import activate_stop_control
from badban.application.idempotency import canonical_request_hash
from badban.application.journal import JournalLine, post_journal
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    Identity,
    JournalEntry,
    OperationalStopControl,
    PolicyVersion,
    ReconciliationBlock,
    ReconciliationCase,
    ReconciliationRun,
    RecoveryVerification,
    RoleGrant,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_OPERATIONS,
    SCOPE_GLOBAL,
)


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def clean_sprint18_tables(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "recovery_verification_checks, recovery_verifications, "
                "operational_stop_controls, reconciliation_blocks, "
                "reconciliation_resolution_proposals, reconciliation_observations, "
                "reconciliation_cases, reconciliation_runs, "
                "journal_postings, journal_entries, outbox_messages, inbox_messages, "
                "evidence_references, legal_authorizations, role_grants, policy_versions, "
                "audit_events, identities "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


async def _identity_with_global_role(
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
                    scope_type=SCOPE_GLOBAL,
                    scope_id=None,
                    valid_from=datetime.now(UTC) - timedelta(minutes=1),
                    valid_until=None,
                    status="ACTIVE",
                    granted_by=None,
                    reason_ref="sprint18-test",
                    version=1,
                )
            )
    return identity


async def _seed_balanced_journal(database, *, actor_id: UUID) -> UUID:
    legal_entity_id = uuid4()
    async with database.session_factory() as session:
        async with session.begin():
            entry = await post_journal(
                session,
                business_event_type="SPRINT18_RECOVERY_FIXTURE",
                business_event_id=f"fixture-{uuid4()}",
                legal_entity_id=legal_entity_id,
                currency="IRR",
                idempotency_key=f"sprint18-{uuid4()}",
                actor_reference=actor_id,
                correlation_id=uuid4(),
                lines=[
                    JournalLine(
                        account_code="RECOVERY_TEST_DEBIT",
                        economic_owner_type="PROGRAM",
                        debit_amount=Decimal("10"),
                        credit_amount=Decimal("0"),
                    ),
                    JournalLine(
                        account_code="RECOVERY_TEST_CREDIT",
                        economic_owner_type="PROGRAM",
                        debit_amount=Decimal("0"),
                        credit_amount=Decimal("10"),
                    ),
                ],
                actor_type="STAFF",
            )
            entry_id = entry.id
    return entry_id


def _external_integrity_payload(*, restore_reference: str) -> dict[str, object]:
    return {
        "restore_reference": restore_reference,
        "environment_reference": "stage-recovery-test",
        "source_backup_reference": "backup:test:sprint18",
        "source_integrity_reference": "integrity:test:sprint18",
    }


@pytest.mark.integration
async def test_recovery_verification_passes_balanced_authoritative_state(
    settings: Settings,
    database,
    clean_sprint18_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint18-operator-pass",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )
    journal_id = await _seed_balanced_journal(database, actor_id=operator.id)

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/recovery-verifications",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json=_external_integrity_payload(restore_reference="restore-pass-1"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["failed_check_count"] == 0
    assert body["not_verified_check_count"] == 1
    checks = {check["check_code"]: check for check in body["checks"]}
    assert checks["JOURNAL_INTEGRITY"]["status"] == "PASS"
    assert checks["OUTBOX_INBOX_INTEGRITY"]["status"] == "PASS"
    assert checks["SOURCE_INTEGRITY_EXTERNAL_VERIFICATION"]["status"] == "NOT_VERIFIED"
    assert journal_id not in {
        UUID(value) for value in checks["JOURNAL_INTEGRITY"]["details"]["invalid_posted_entry_ids"]
    }


@pytest.mark.integration
async def test_recovery_verification_fails_closed_without_external_source_integrity(
    settings: Settings,
    database,
    clean_sprint18_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint18-operator-unverified",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/recovery-verifications",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={
                "restore_reference": "restore-unverified-1",
                "environment_reference": "stage-recovery-test",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["failed_check_count"] == 0
    assert body["not_verified_check_count"] == 1
    source_check = next(
        check
        for check in body["checks"]
        if check["check_code"] == "SOURCE_INTEGRITY_EXTERNAL_VERIFICATION"
    )
    assert source_check["status"] == "NOT_VERIFIED"


@pytest.mark.integration
async def test_caller_cannot_assert_external_source_integrity(
    settings: Settings,
    database,
    clean_sprint18_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint18-operator-no-self-attest",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/recovery-verifications",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json={
                "restore_reference": "restore-self-attest-rejected",
                "environment_reference": "stage-recovery-test",
                "source_integrity_reference": "integrity:test:sprint18",
                "source_integrity_verified": True,
            },
        )

    assert response.status_code == 422


@pytest.mark.integration
async def test_incomplete_recovered_journal_fails_closed_without_repair(
    settings: Settings,
    database,
    clean_sprint18_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint18-operator-incomplete",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )
    incomplete = JournalEntry(
        business_event_type="RESTORED_INCOMPLETE",
        business_event_id="restored-incomplete-1",
        legal_entity_id=uuid4(),
        currency="IRR",
        state="PREPARED",
        effective_at=datetime.now(UTC),
        posted_at=None,
        reversal_of_entry_id=None,
        idempotency_key=f"incomplete-{uuid4()}",
        request_hash="0" * 64,
        actor_reference=operator.id,
        correlation_id=uuid4(),
        causation_id=None,
        policy_version_reference=None,
        posting_template_reference=None,
        account_mapping_reference=None,
        evidence_reference=None,
        settlement_reference=None,
        reason=None,
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add(incomplete)
            await session.flush()
            incomplete_id = incomplete.id

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/recovery-verifications",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json=_external_integrity_payload(restore_reference="restore-incomplete-1"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    journal_check = next(
        check for check in body["checks"] if check["check_code"] == "JOURNAL_INTEGRITY"
    )
    assert journal_check["status"] == "FAIL"
    assert str(incomplete_id) in journal_check["details"]["invalid_posted_entry_ids"] or str(
        incomplete_id
    ) in journal_check["details"].get("prepared_entry_ids", [])
    assert journal_check["details"]["prepared_count"] == 1

    async with database.session_factory() as session:
        stored = await session.get(JournalEntry, incomplete_id)
    assert stored is not None
    assert stored.state == "PREPARED"
    assert stored.posted_at is None


async def _seed_stale_reconciliation_and_stop(database, *, actor: Identity) -> tuple[UUID, UUID]:
    now = datetime.now(UTC)
    scope = {"pilot_scope": "sprint18-recovery"}
    rule_payload = {"reconciliation_rules": {}}
    pack_payload: dict[str, object] = {"component_version_ids": []}
    async with database.session_factory() as session:
        async with session.begin():
            rule = PolicyVersion(
                policy_type="RECONCILIATION_POLICY",
                policy_code=f"SPRINT18-RECON-{uuid4()}",
                version_number=1,
                lifecycle_status="APPROVED",
                scope_definition=scope,
                payload=rule_payload,
                payload_hash=canonical_request_hash(rule_payload),
                schema_version="1",
                approved_at=now,
                approved_by=actor.id,
                created_by=actor.id,
                version=3,
            )
            session.add(rule)
            await session.flush()
            pack_payload["component_version_ids"] = [str(rule.id)]
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code=f"SPRINT18-PACK-{uuid4()}",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition=scope,
                payload=pack_payload,
                payload_hash=canonical_request_hash(pack_payload),
                schema_version="1",
                effective_from=now - timedelta(minutes=1),
                effective_to=None,
                approved_at=now,
                activated_at=now,
                approved_by=actor.id,
                created_by=actor.id,
                version=4,
            )
            session.add(pack)
            await session.flush()
            run = ReconciliationRun(
                reconciliation_type="LENDER_EXTERNAL_LOAN",
                provider_id=None,
                scope_definition=scope,
                scope_reference="scope:test:sprint18",
                policy_pack_id=pack.id,
                policy_pack_version=pack.version_number,
                rule_policy_version_id=rule.id,
                rule_policy_code=rule.policy_code,
                rule_policy_version_number=rule.version_number,
                rule_schema_version=rule.schema_version,
                internal_cutoff=now,
                external_cutoff=now,
                source_snapshot_ref="snapshot:test:sprint18",
                source_evidence_references=[],
                source_fingerprint=canonical_request_hash({"run": "sprint18-stale"}),
                status="COMPLETED",
                started_at=now,
                finished_at=now,
                matched_count=0,
                mismatch_count=0,
                stale_count=1,
                critical_count=0,
            )
            session.add(run)
            await session.flush()
            case = ReconciliationCase(
                run_id=run.id,
                reconciliation_type=run.reconciliation_type,
                internal_entity_type="RECOVERY_TEST",
                internal_entity_id="entity-1",
                external_provider_id=None,
                external_reference="external-1",
                status="STALE",
                materiality="WARNING",
                mismatch_reason_code="RECON_SOURCE_STALE",
                compared_at=now,
                resolved_at=None,
                resolution_reference=None,
                resolution_type=None,
                rule_policy_version_id=rule.id,
                rule_policy_version_number=rule.version_number,
                first_detected_at=now,
                last_observed_at=now,
                version=1,
            )
            session.add(case)
            await session.flush()
            block = ReconciliationBlock(
                reconciliation_case_id=case.id,
                blocked_command_type="RECOVERY_TEST_COMMAND",
                resource_type="RECOVERY_TEST",
                resource_id="entity-1",
                active=True,
                policy_version_id=rule.id,
                policy_version_number=rule.version_number,
                activated_at=now,
                cleared_at=None,
            )
            session.add(block)
            await session.flush()
            stop = await activate_stop_control(
                session,
                control_type="STOP_GUARANTEE_ACTIVATION",
                scope_type="GLOBAL",
                scope_id=None,
                reason="recovery safety stop",
                evidence_reference="evidence:test:sprint18-stop",
                actor_type=actor.identity_type,
                actor_id=actor.id,
                correlation_id=uuid4(),
            )
            return case.id, stop.id


@pytest.mark.integration
async def test_recovery_preserves_stale_reconciliation_and_active_stop(
    settings: Settings,
    database,
    clean_sprint18_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint18-operator-preserve",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )
    case_id, stop_id = await _seed_stale_reconciliation_and_stop(
        database,
        actor=operator,
    )

    async with await _client(settings) as client:
        response = await client.post(
            "/api/v1/recovery-verifications",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json=_external_integrity_payload(restore_reference="restore-preserve-1"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["not_verified_check_count"] == 1
    checks = {check["check_code"]: check for check in body["checks"]}
    assert checks["RECONCILIATION_STATE_READABILITY"]["status"] == "PASS"
    assert checks["RECONCILIATION_STATE_READABILITY"]["details"]["stale_case_count"] == 1
    assert checks["RECONCILIATION_STATE_READABILITY"]["details"]["active_block_count"] == 1
    assert (
        checks["RECONCILIATION_STATE_READABILITY"]["details"]["business_follow_up_required"] is True
    )
    assert checks["STOP_CONTROL_PRESERVATION"]["status"] == "PASS"
    assert checks["STOP_CONTROL_PRESERVATION"]["details"]["active_control_count"] == 1

    async with database.session_factory() as session:
        case = await session.get(ReconciliationCase, case_id)
        stop = await session.get(OperationalStopControl, stop_id)
    assert case is not None and case.status == "STALE"
    assert stop is not None and stop.active is True
    assert stop.cleared_at is None


@pytest.mark.integration
async def test_auditor_can_read_but_cannot_execute_and_evidence_is_append_only(
    settings: Settings,
    database,
    clean_sprint18_tables,
) -> None:
    operator = await _identity_with_global_role(
        database,
        subject="sprint18-operator-audit",
        identity_type="STAFF",
        role=ROLE_OPERATIONS,
    )
    auditor = await _identity_with_global_role(
        database,
        subject="sprint18-auditor",
        identity_type="AUDITOR",
        role=ROLE_AUDITOR,
    )

    async with await _client(settings) as client:
        created = await client.post(
            "/api/v1/recovery-verifications",
            headers={"Authorization": f"Bearer {operator.external_subject}"},
            json=_external_integrity_payload(restore_reference="restore-auditor-1"),
        )
        assert created.status_code == 201
        verification_id = UUID(created.json()["id"])

        denied = await client.post(
            "/api/v1/recovery-verifications",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
            json=_external_integrity_payload(restore_reference="restore-auditor-denied"),
        )
        assert denied.status_code == 403

        read = await client.get(
            f"/api/v1/recovery-verifications/{verification_id}",
            headers={"Authorization": f"Bearer {auditor.external_subject}"},
        )
        assert read.status_code == 200
        assert read.json()["id"] == str(verification_id)

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(RecoveryVerification)
                    .where(RecoveryVerification.id == verification_id)
                    .values(status="FAILED")
                )
