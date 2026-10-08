from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import (
    CreditProvider,
    EvidenceReference,
    Identity,
    InboxMessage,
    JournalEntry,
    JournalPosting,
    LegalAuthorization,
    OperationalStopControl,
    OutboxMessage,
    PolicyVersion,
    ReconciliationBlock,
    ReconciliationCase,
    ReconciliationRun,
    RecoveryVerification,
    RecoveryVerificationCheck,
    RoleGrant,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    SCOPE_ASSET_POSITION,
    SCOPE_ASSET_TYPE,
    SCOPE_GLOBAL,
    SCOPE_LEGAL_ENTITY,
    SCOPE_PARTICIPANT,
    SCOPE_PROGRAM,
    SCOPE_PROVIDER,
)

RECOVERY_VERIFICATION_VERSION = "RECOVERY_VERIFICATION_V1"
_CHECK_STATUS = Literal["PASS", "FAIL", "NOT_VERIFIED"]
_VALID_SCOPE_TYPES = {
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
    SCOPE_PARTICIPANT,
    SCOPE_ASSET_TYPE,
    SCOPE_ASSET_POSITION,
    SCOPE_PROVIDER,
    SCOPE_LEGAL_ENTITY,
}


class RecoveryVerificationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RecoveryCheck:
    code: str
    status: _CHECK_STATUS
    details: dict[str, Any]
    evidence_reference: str | None = None


def _required_text(value: str, *, code: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise RecoveryVerificationError(code, f"{field} must not be blank")
    return cleaned


def _optional_text(value: str | None, *, code: str, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise RecoveryVerificationError(code, f"{field} must not be blank when supplied")
    return cleaned


async def _database_check(session: AsyncSession) -> RecoveryCheck:
    value = await session.scalar(text("SELECT 1"))
    return RecoveryCheck(
        code="DATABASE_REACHABILITY",
        status="PASS" if value == 1 else "FAIL",
        details={"select_one": value == 1},
    )


async def _journal_check(session: AsyncSession) -> RecoveryCheck:
    entries = (await session.scalars(select(JournalEntry))).all()
    posting_rows = (
        await session.execute(
            select(
                JournalPosting.journal_entry_id,
                func.count(JournalPosting.id),
                func.coalesce(func.sum(JournalPosting.debit_amount), 0),
                func.coalesce(func.sum(JournalPosting.credit_amount), 0),
            ).group_by(JournalPosting.journal_entry_id)
        )
    ).all()
    posting_totals = {
        entry_id: (int(count), Decimal(debit), Decimal(credit))
        for entry_id, count, debit, credit in posting_rows
    }
    by_id = {entry.id: entry for entry in entries}
    invalid_posted: list[str] = []
    invalid_reversals: list[str] = []
    prepared_ids: list[str] = []

    for entry in entries:
        if entry.state == "PREPARED":
            prepared_ids.append(str(entry.id))
            continue
        if entry.state != "POSTED":
            invalid_posted.append(str(entry.id))
            continue
        count, debit, credit = posting_totals.get(
            entry.id,
            (0, Decimal("0"), Decimal("0")),
        )
        if count < 2 or debit <= 0 or debit != credit:
            invalid_posted.append(str(entry.id))
        if entry.reversal_of_entry_id is not None:
            original = by_id.get(entry.reversal_of_entry_id)
            if original is None or original.id == entry.id or original.state != "POSTED":
                invalid_reversals.append(str(entry.id))

    status: _CHECK_STATUS = (
        "PASS" if not invalid_posted and not invalid_reversals and not prepared_ids else "FAIL"
    )
    return RecoveryCheck(
        code="JOURNAL_INTEGRITY",
        status=status,
        details={
            "journal_entry_count": len(entries),
            "posted_count": sum(1 for entry in entries if entry.state == "POSTED"),
            "prepared_count": len(prepared_ids),
            "prepared_entry_ids": prepared_ids,
            "invalid_posted_entry_ids": invalid_posted,
            "invalid_reversal_entry_ids": invalid_reversals,
        },
    )


async def _messaging_check(session: AsyncSession) -> RecoveryCheck:
    outbox = (await session.scalars(select(OutboxMessage))).all()
    inbox = (await session.scalars(select(InboxMessage))).all()
    posted = (
        await session.scalars(select(JournalEntry).where(JournalEntry.state == "POSTED"))
    ).all()

    journal_events = {
        (message.event_type, message.aggregate_type, message.aggregate_id) for message in outbox
    }
    missing_journal_event_ids: list[str] = []
    for entry in posted:
        expected = "JournalReversed" if entry.reversal_of_entry_id is not None else "JournalPosted"
        if (expected, "JournalEntry", str(entry.id)) not in journal_events:
            missing_journal_event_ids.append(str(entry.id))

    malformed_outbox = [
        str(message.id)
        for message in outbox
        if message.publish_attempts < 0
        or message.replay_count < 0
        or (message.published_at is not None and message.dead_lettered_at is not None)
    ]
    seen_inbox: set[tuple[str, str, str]] = set()
    duplicate_inbox_ids: list[str] = []
    malformed_inbox_ids: list[str] = []
    for message in inbox:
        key = (message.source_id, message.event_type, message.external_event_id)
        if key in seen_inbox:
            duplicate_inbox_ids.append(str(message.id))
        seen_inbox.add(key)
        if (
            not message.source_id.strip()
            or not message.event_type.strip()
            or not message.external_event_id.strip()
            or not message.payload_hash.strip()
        ):
            malformed_inbox_ids.append(str(message.id))

    status: _CHECK_STATUS = (
        "PASS"
        if not missing_journal_event_ids
        and not malformed_outbox
        and not duplicate_inbox_ids
        and not malformed_inbox_ids
        else "FAIL"
    )
    return RecoveryCheck(
        code="OUTBOX_INBOX_INTEGRITY",
        status=status,
        details={
            "outbox_count": len(outbox),
            "unpublished_outbox_count": sum(
                1
                for message in outbox
                if message.published_at is None and message.dead_lettered_at is None
            ),
            "dead_lettered_outbox_count": sum(
                1 for message in outbox if message.dead_lettered_at is not None
            ),
            "inbox_count": len(inbox),
            "unprocessed_inbox_count": sum(1 for message in inbox if message.processed_at is None),
            "missing_journal_event_ids": missing_journal_event_ids,
            "malformed_outbox_ids": malformed_outbox,
            "duplicate_inbox_ids": duplicate_inbox_ids,
            "malformed_inbox_ids": malformed_inbox_ids,
        },
    )


async def _evidence_check(session: AsyncSession) -> RecoveryCheck:
    rows = (await session.scalars(select(EvidenceReference))).all()
    invalid_ids: list[str] = []
    for evidence in rows:
        scheme = urlsplit(evidence.storage_reference).scheme.lower()
        if (
            not evidence.evidence_type.strip()
            or not evidence.storage_provider.strip()
            or not evidence.storage_reference.strip()
            or scheme in {"http", "https"}
            or (evidence.content_hash is not None and not evidence.content_hash.strip())
        ):
            invalid_ids.append(str(evidence.id))

    return RecoveryCheck(
        code="EVIDENCE_METADATA_INTEGRITY",
        status="PASS" if not invalid_ids else "FAIL",
        details={
            "evidence_reference_count": len(rows),
            "invalid_evidence_reference_ids": invalid_ids,
            "external_object_content_verified": False,
            "external_object_content_status": "NOT_VERIFIED",
        },
    )


async def _access_control_check(session: AsyncSession) -> RecoveryCheck:
    grants = (await session.scalars(select(RoleGrant))).all()
    identities = {
        identity.id: identity for identity in (await session.scalars(select(Identity))).all()
    }
    invalid_grants: list[str] = []
    for grant in grants:
        identity = identities.get(grant.identity_id)
        scope_valid = grant.scope_type in _VALID_SCOPE_TYPES and (
            (grant.scope_type == SCOPE_GLOBAL and grant.scope_id is None)
            or (grant.scope_type != SCOPE_GLOBAL and grant.scope_id is not None)
        )
        active_identity_valid = grant.status != "ACTIVE" or (
            identity is not None and identity.status == "ACTIVE"
        )
        if not scope_valid or not active_identity_valid:
            invalid_grants.append(str(grant.id))

    return RecoveryCheck(
        code="ACCESS_CONTROL_INTEGRITY",
        status="PASS" if not invalid_grants else "FAIL",
        details={
            "role_grant_count": len(grants),
            "invalid_role_grant_ids": invalid_grants,
        },
    )


async def _policy_legal_provider_check(
    session: AsyncSession,
    *,
    evaluated_at: datetime,
) -> RecoveryCheck:
    active_policies = (
        await session.scalars(
            select(PolicyVersion).where(PolicyVersion.lifecycle_status == "ACTIVE")
        )
    ).all()
    invalid_policy_ids = [
        str(policy.id)
        for policy in active_policies
        if policy.payload_hash is None
        or policy.payload_hash != canonical_request_hash(policy.payload)
    ]

    valid_authorizations = (
        await session.scalars(
            select(LegalAuthorization).where(LegalAuthorization.lifecycle_status == "VALID")
        )
    ).all()
    invalid_authorization_ids = [
        str(authorization.id)
        for authorization in valid_authorizations
        if authorization.effective_from > evaluated_at
        or (authorization.expires_at is not None and authorization.expires_at <= evaluated_at)
    ]
    providers = (await session.scalars(select(CreditProvider))).all()

    status: _CHECK_STATUS = (
        "PASS" if not invalid_policy_ids and not invalid_authorization_ids else "FAIL"
    )
    return RecoveryCheck(
        code="POLICY_PROVIDER_LEGAL_INTEGRITY",
        status=status,
        details={
            "active_policy_count": len(active_policies),
            "invalid_active_policy_ids": invalid_policy_ids,
            "provider_count": len(providers),
            "valid_legal_authorization_count": len(valid_authorizations),
            "invalid_valid_authorization_ids": invalid_authorization_ids,
        },
    )


async def _reconciliation_check(session: AsyncSession) -> RecoveryCheck:
    runs = (await session.scalars(select(ReconciliationRun))).all()
    cases = (await session.scalars(select(ReconciliationCase))).all()
    blocks = (await session.scalars(select(ReconciliationBlock))).all()
    return RecoveryCheck(
        code="RECONCILIATION_STATE_READABILITY",
        status="PASS",
        details={
            "run_count": len(runs),
            "failed_run_count": sum(1 for run in runs if run.status == "FAILED"),
            "case_count": len(cases),
            "unresolved_case_count": sum(
                1 for case in cases if case.status in {"PENDING", "MISMATCH", "STALE", "DISPUTED"}
            ),
            "stale_case_count": sum(1 for case in cases if case.status == "STALE"),
            "active_block_count": sum(1 for block in blocks if block.active),
            "business_follow_up_required": any(
                case.status in {"PENDING", "MISMATCH", "STALE", "DISPUTED"} for case in cases
            )
            or any(block.active for block in blocks),
        },
    )


async def _stop_control_check(session: AsyncSession) -> RecoveryCheck:
    controls = (await session.scalars(select(OperationalStopControl))).all()
    invalid_ids: list[str] = []
    for control in controls:
        if control.active:
            if control.cleared_at is not None or control.cleared_by is not None:
                invalid_ids.append(str(control.id))
        elif control.cleared_at is None or control.cleared_by is None:
            invalid_ids.append(str(control.id))
    return RecoveryCheck(
        code="STOP_CONTROL_PRESERVATION",
        status="PASS" if not invalid_ids else "FAIL",
        details={
            "control_count": len(controls),
            "active_control_count": sum(1 for control in controls if control.active),
            "invalid_control_ids": invalid_ids,
            "controls_auto_cleared": False,
        },
    )


def _source_integrity_check(
    *,
    source_integrity_reference: str | None,
) -> RecoveryCheck:
    return RecoveryCheck(
        code="SOURCE_INTEGRITY_EXTERNAL_VERIFICATION",
        status="NOT_VERIFIED",
        details={
            "externally_verified": False,
            "authoritative_external_verifier_connected": False,
            "verification_reference_supplied": source_integrity_reference is not None,
        },
        evidence_reference=source_integrity_reference,
    )


async def execute_recovery_verification(
    session: AsyncSession,
    *,
    restore_reference: str,
    environment_reference: str,
    source_backup_reference: str | None,
    source_integrity_reference: str | None,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> RecoveryVerification:
    restore_ref = _required_text(
        restore_reference,
        code="RECOVERY_RESTORE_REFERENCE_REQUIRED",
        field="restore_reference",
    )
    environment_ref = _required_text(
        environment_reference,
        code="RECOVERY_ENVIRONMENT_REFERENCE_REQUIRED",
        field="environment_reference",
    )
    backup_ref = _optional_text(
        source_backup_reference,
        code="RECOVERY_BACKUP_REFERENCE_INVALID",
        field="source_backup_reference",
    )
    integrity_ref = _optional_text(
        source_integrity_reference,
        code="RECOVERY_INTEGRITY_REFERENCE_INVALID",
        field="source_integrity_reference",
    )
    started_at = datetime.now(UTC)
    checks = [
        await _database_check(session),
        await _journal_check(session),
        await _messaging_check(session),
        await _evidence_check(session),
        await _access_control_check(session),
        await _policy_legal_provider_check(session, evaluated_at=started_at),
        await _reconciliation_check(session),
        await _stop_control_check(session),
        _source_integrity_check(source_integrity_reference=integrity_ref),
    ]
    failed_count = sum(1 for check in checks if check.status == "FAIL")
    not_verified_count = sum(1 for check in checks if check.status == "NOT_VERIFIED")
    status = "PASSED" if failed_count == 0 and not_verified_count == 0 else "FAILED"
    completed_at = datetime.now(UTC)
    verification = RecoveryVerification(
        restore_reference=restore_ref,
        source_backup_reference=backup_ref,
        source_integrity_reference=integrity_ref,
        environment_reference=environment_ref,
        verification_version=RECOVERY_VERIFICATION_VERSION,
        status=status,
        check_count=len(checks),
        failed_check_count=failed_count,
        not_verified_check_count=not_verified_count,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        started_at=started_at,
        completed_at=completed_at,
    )
    session.add(verification)
    await session.flush()

    session.add_all(
        [
            RecoveryVerificationCheck(
                recovery_verification_id=verification.id,
                check_code=check.code,
                status=check.status,
                details=check.details,
                evidence_reference=check.evidence_reference,
            )
            for check in checks
        ]
    )
    append_audit(
        session,
        aggregate_type="RecoveryVerification",
        aggregate_id=str(verification.id),
        aggregate_version=None,
        action="RECOVERY_VERIFICATION_EXECUTED",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS" if status == "PASSED" else "FAILED",
        reason_code=(
            "RECOVERY_VERIFICATION_PASSED" if status == "PASSED" else "RECOVERY_VERIFICATION_FAILED"
        ),
        new_state={
            "status": status,
            "verification_version": RECOVERY_VERIFICATION_VERSION,
            "check_count": len(checks),
            "failed_check_count": failed_count,
            "not_verified_check_count": not_verified_count,
        },
        scope={"scope_type": SCOPE_GLOBAL, "scope_id": None},
    )
    await session.flush()
    return verification
