from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.evidence import EvidenceReferenceError, register_evidence_reference
from badban.config import Settings
from badban.infrastructure.persistence.models import AuditEvent, EvidenceReference
from badban.security.audit import AuditPayloadRejected, append_audit


@pytest.fixture
async def clean_sprint12_audit_evidence_tables(database):
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE "
                "audit_events, evidence_references, legal_entities "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.mark.integration
async def test_audit_event_persists_safe_lineage_and_is_append_only(
    database,
    clean_sprint12_audit_evidence_tables,
) -> None:
    actor_id = uuid4()
    correlation_id = uuid4()
    causation_id = uuid4()
    policy_pack_id = uuid4()

    async with database.session_factory() as session:
        async with session.begin():
            audit = append_audit(
                session,
                aggregate_type="TestAggregate",
                aggregate_id="aggregate-1",
                aggregate_version=3,
                action="TEST_ACTION",
                actor_type="STAFF",
                actor_id=actor_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                policy_pack_id=policy_pack_id,
                evidence_reference="evidence:opaque:1",
                outcome="SUCCESS",
                previous_state={"state": "OLD"},
                new_state={"state": "NEW", "amount": "10.00"},
                scope={"scope_type": "PROGRAM", "scope_id": str(uuid4())},
            )
            await session.flush()
            audit_id = audit.id

    async with database.session_factory() as session:
        stored = await session.get(AuditEvent, audit_id)

    assert stored is not None
    assert stored.actor_id == actor_id
    assert stored.correlation_id == correlation_id
    assert stored.causation_id == causation_id
    assert stored.policy_pack_id == policy_pack_id
    assert stored.evidence_reference == "evidence:opaque:1"
    assert stored.new_state == {"state": "NEW", "amount": "10.00"}

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(AuditEvent)
                    .where(AuditEvent.id == audit_id)
                    .values(outcome="MUTATED")
                )

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(delete(AuditEvent).where(AuditEvent.id == audit_id))


@pytest.mark.integration
async def test_unsafe_nested_audit_payload_fails_before_persistence(
    database,
    clean_sprint12_audit_evidence_tables,
) -> None:
    sensitive_value = "must-not-be-persisted"

    async with database.session_factory() as session:
        with pytest.raises(AuditPayloadRejected) as exc:
            async with session.begin():
                append_audit(
                    session,
                    aggregate_type="TestAggregate",
                    aggregate_id="aggregate-unsafe",
                    aggregate_version=1,
                    action="TEST_UNSAFE",
                    actor_type="SYSTEM",
                    actor_id=uuid4(),
                    correlation_id=uuid4(),
                    outcome="DENIED",
                    new_state={
                        "provider": {
                            "credentials": {
                                "access_token": sensitive_value,
                            }
                        }
                    },
                )

    assert exc.value.code == "AUDIT_PAYLOAD_UNSAFE"
    assert sensitive_value not in str(exc.value)

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(AuditEvent))
    assert count == 0


@pytest.mark.integration
async def test_evidence_registration_stores_metadata_only_and_history_is_append_only(
    database,
    clean_sprint12_audit_evidence_tables,
) -> None:
    captured_at = datetime.now(UTC)

    async with database.session_factory() as session:
        async with session.begin():
            evidence = await register_evidence_reference(
                session,
                evidence_type="LEGAL_AUTHORIZATION",
                storage_provider="private-object-store",
                storage_reference="evidence/legal/opaque-object-1",
                captured_at=captured_at,
                external_reference="authority-record-1",
                content_hash="sha256:example",
                media_type="application/pdf",
                verified_status="review-recorded",
            )
            evidence_id = evidence.id

    async with database.session_factory() as session:
        stored = await session.get(EvidenceReference, evidence_id)

    assert stored is not None
    assert stored.storage_reference == "evidence/legal/opaque-object-1"
    assert stored.captured_at == captured_at
    assert stored.verified_status == "review-recorded"
    assert not hasattr(stored, "content")

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(EvidenceReference)
                    .where(EvidenceReference.id == evidence_id)
                    .values(storage_reference="evidence/legal/changed")
                )

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    delete(EvidenceReference).where(EvidenceReference.id == evidence_id)
                )


@pytest.mark.integration
async def test_evidence_registration_rejects_public_http_storage_reference(
    database,
    clean_sprint12_audit_evidence_tables,
) -> None:
    async with database.session_factory() as session:
        with pytest.raises(EvidenceReferenceError) as exc:
            async with session.begin():
                await register_evidence_reference(
                    session,
                    evidence_type="CLAIM_EVIDENCE",
                    storage_provider="external-url",
                    storage_reference="https://public.example/evidence.pdf",
                    captured_at=datetime.now(UTC),
                )

    assert exc.value.code == "EVIDENCE_PUBLIC_STORAGE_URL_FORBIDDEN"

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(EvidenceReference))
    assert count == 0


@pytest.mark.integration
async def test_evidence_registration_requires_timezone_aware_capture_time(
    database,
    clean_sprint12_audit_evidence_tables,
) -> None:
    async with database.session_factory() as session:
        with pytest.raises(EvidenceReferenceError) as exc:
            async with session.begin():
                await register_evidence_reference(
                    session,
                    evidence_type="VALUATION_EVIDENCE",
                    storage_provider="private-object-store",
                    storage_reference="evidence/valuation/1",
                    captured_at=datetime(2026, 10, 7, 12, 0, 0),
                )

    assert exc.value.code == "EVIDENCE_CAPTURED_AT_TIMEZONE_REQUIRED"


def test_no_generic_audit_or_evidence_mutation_api(settings: Settings) -> None:
    schema = create_app(settings).openapi()
    mutation_methods = {"post", "put", "patch", "delete"}
    for path, operations in schema["paths"].items():
        if path.startswith("/api/v1/audit") or path.startswith("/api/v1/evidence"):
            assert not mutation_methods.intersection(operations)
