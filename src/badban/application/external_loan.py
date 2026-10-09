from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.integration_events import (
    InboxAcceptance,
    accept_authenticated_inbox_event,
    process_inbox_message_once,
)
from badban.application.lender_adapter import (
    LenderAdapterError,
    LenderAdapterRegistry,
    LenderInboundRequest,
    NormalizedLenderEvent,
)
from badban.infrastructure.persistence.database import Database
from badban.infrastructure.persistence.models import (
    CreditProvider,
    ExternalLoanEvent,
    ExternalLoanMirror,
    GuaranteeCase,
    InboxMessage,
    OutboxMessage,
)
from badban.security.audit import append_audit

_LENDER_SOURCE_PREFIX = "lender:"
_STATE_RANK = {
    "PENDING": 0,
    "ACTIVE": 1,
    "DELINQUENT": 2,
    "SETTLED": 3,
    "REPLACED": 4,
}


class ExternalLoanError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class LenderInboundAcceptance:
    inbox_message_id: UUID
    created: bool
    event_type: str
    external_loan_id: str


@dataclass(frozen=True, slots=True)
class LenderInboxBatchResult:
    claimed: int
    processed: int
    failed: int


def lender_source_id(provider_id: UUID) -> str:
    return f"{_LENDER_SOURCE_PREFIX}{provider_id}"


def _lender_mirror_lock_key(provider_id: UUID, external_loan_id: str) -> int:
    """Deterministic transaction lock scoped to one provider and external loan.

    A SELECT ... FOR UPDATE cannot serialize the creation of a row that does
    not exist. Use one PostgreSQL transaction advisory lock before the mirror
    lookup, independently of worker replica and Python process.
    """
    loan_identity = external_loan_id.encode("utf-8")
    digest = hashlib.sha256(
        b"badban:lender:mirror:v1:" + provider_id.bytes + loan_identity
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _safe_event_payload(event: NormalizedLenderEvent) -> dict[str, object]:
    return event.model_dump(mode="json")


def _dedupe_event_payload(event: NormalizedLenderEvent) -> dict[str, object]:
    payload = event.model_dump(mode="json")
    payload.pop("received_at", None)
    payload.pop("correlation_id", None)
    return payload


def _event_state(event_type: str) -> str | None:
    return {
        "LOAN_APPROVED": "PENDING",
        "LOAN_DISBURSED": "ACTIVE",
        "LOAN_DELINQUENT": "DELINQUENT",
        "LOAN_SETTLED": "SETTLED",
    }.get(event_type)


async def accept_lender_inbound_request(
    database: Database,
    registry: LenderAdapterRegistry,
    *,
    provider_id: UUID,
    body: bytes,
    headers: dict[str, str],
    correlation_id: UUID,
    received_at: datetime | None = None,
) -> LenderInboundAcceptance:
    received = received_at or datetime.now(UTC)

    async with database.session_factory() as session:
        provider = await session.get(CreditProvider, provider_id)
    if provider is None:
        raise LenderAdapterError("PROVIDER_NOT_FOUND", "Lender provider does not exist")
    if provider.provider_type != "EXTERNAL_LENDER":
        raise LenderAdapterError(
            "EVENT_SCOPE_INVALID",
            "Provider is not an External Lender",
        )

    adapter = registry.resolve(provider_id)
    manifest = adapter.capability_manifest()
    if provider.integration_mode not in manifest.integration_modes:
        raise LenderAdapterError(
            "PROVIDER_CONTRACT_MISMATCH",
            "Configured provider integration mode is not supported by its adapter",
        )

    request = LenderInboundRequest(
        provider_id=provider_id,
        body=body,
        headers=headers,
        received_at=received,
        correlation_id=correlation_id,
    )
    try:
        event = await adapter.verify_and_normalize(request)
    except LenderAdapterError:
        raise
    except Exception as exc:
        translated = adapter.translate_error(exc)
        raise LenderAdapterError(
            translated.code,
            "Lender adapter rejected the inbound request",
            classification=translated.classification,
        ) from exc

    event = event.model_copy(
        update={
            "received_at": received,
            "correlation_id": correlation_id,
        }
    )
    if event.provider_id != provider_id:
        raise LenderAdapterError(
            "EVENT_SCOPE_INVALID",
            "Normalized lender event provider does not match endpoint provider scope",
        )
    if event.event_type not in manifest.supported_inbound_events:
        raise LenderAdapterError(
            "PROVIDER_CONTRACT_MISMATCH",
            "Normalized lender event is not declared by the adapter manifest",
        )
    if (
        event.provider_contract_version != manifest.provider_contract_version
        or event.adapter_mapping_version != manifest.adapter_mapping_version
        or event.inbound_normalization_version != manifest.inbound_normalization_version
    ):
        raise LenderAdapterError(
            "PROVIDER_CONTRACT_MISMATCH",
            "Normalized lender event version lineage does not match adapter manifest",
        )
    if manifest.supports_event_sequence and event.provider_event_sequence is None:
        raise LenderAdapterError(
            "PROVIDER_CONTRACT_MISMATCH",
            "Adapter declares event sequencing but normalized event has no sequence",
        )

    acceptance: InboxAcceptance = await accept_authenticated_inbox_event(
        database,
        source_id=lender_source_id(provider_id),
        event_type=event.event_type,
        external_event_id=event.external_event_id,
        payload=_safe_event_payload(event),
        dedupe_payload=_dedupe_event_payload(event),
    )
    return LenderInboundAcceptance(
        inbox_message_id=acceptance.message_id,
        created=acceptance.created,
        event_type=event.event_type,
        external_loan_id=event.external_loan_id,
    )


async def _validate_guarantee_link(
    session: AsyncSession,
    *,
    provider_id: UUID,
    guarantee_case_id: UUID | None,
) -> None:
    if guarantee_case_id is None:
        return
    guarantee = await session.scalar(
        select(GuaranteeCase).where(GuaranteeCase.id == guarantee_case_id).with_for_update()
    )
    if guarantee is None:
        raise ExternalLoanError(
            "GUARANTEE_CASE_NOT_FOUND",
            "Normalized lender event references an unknown GuaranteeCase",
        )
    if guarantee.provider_id != provider_id:
        raise ExternalLoanError(
            "EVENT_SCOPE_INVALID",
            "GuaranteeCase belongs to a different lender provider",
        )
    existing_id = await session.scalar(
        select(ExternalLoanMirror.id).where(
            ExternalLoanMirror.guarantee_case_id == guarantee_case_id
        )
    )
    if existing_id is not None:
        raise ExternalLoanError(
            "LENDER_GUARANTEE_LINK_CONFLICT",
            "The GuaranteeCase is already linked to a different External Loan",
        )


def _assert_event_order(
    mirror: ExternalLoanMirror,
    event: NormalizedLenderEvent,
) -> bool:
    if mirror.last_provider_event_sequence is not None:
        if event.provider_event_sequence is None:
            raise ExternalLoanError(
                "EVENT_SEQUENCE_GAP",
                "Sequenced lender stream omitted provider event sequence",
                retryable=True,
            )
        if event.provider_event_sequence <= mirror.last_provider_event_sequence:
            return False
        if event.provider_event_sequence > mirror.last_provider_event_sequence + 1:
            raise ExternalLoanError(
                "EVENT_SEQUENCE_GAP",
                "Lender event sequence gap detected",
                retryable=True,
            )

    if (
        mirror.last_provider_event_at is not None
        and event.event_time < mirror.last_provider_event_at
    ):
        return False
    return True


def _assert_non_correction_consistency(
    mirror: ExternalLoanMirror,
    event: NormalizedLenderEvent,
) -> None:
    if event.event_type == "LOAN_CORRECTED":
        return
    if mirror.original_principal != event.original_principal_decimal():
        raise ExternalLoanError(
            "PROVIDER_CONTRACT_MISMATCH",
            "Original principal changed without LOAN_CORRECTED",
        )
    if mirror.currency != event.currency:
        raise ExternalLoanError(
            "PROVIDER_CONTRACT_MISMATCH",
            "Loan currency changed without an authorized correction contract",
        )


def _assert_state_progression(
    mirror: ExternalLoanMirror,
    desired_state: str | None,
) -> None:
    if desired_state is None or desired_state == mirror.state:
        return
    if _STATE_RANK[desired_state] < _STATE_RANK[mirror.state]:
        raise ExternalLoanError(
            "LENDER_EVENT_STATE_REGRESSION",
            "Lender event would regress ExternalLoanMirror state",
        )


def _event_history(
    *,
    mirror: ExternalLoanMirror,
    event: NormalizedLenderEvent,
    previous_outstanding: Decimal | None,
    processed_status: str,
) -> ExternalLoanEvent:
    principal_delta = (
        None
        if previous_outstanding is None
        else event.outstanding_principal_decimal() - previous_outstanding
    )
    return ExternalLoanEvent(
        external_loan_mirror_id=mirror.id,
        provider_event_id=event.external_event_id,
        event_type=event.event_type,
        principal_delta=principal_delta,
        outstanding_principal_reported=event.outstanding_principal_decimal(),
        provider_event_at=event.event_time,
        received_at=event.received_at,
        evidence_references=list(event.evidence_references),
        payload_hash=event.payload_hash.lower(),
        processed_status=processed_status,
        provider_contract_version=event.provider_contract_version,
        adapter_mapping_version=event.adapter_mapping_version,
        inbound_normalization_version=event.inbound_normalization_version,
        provider_event_sequence=event.provider_event_sequence,
    )


def _mirror_payload(mirror: ExternalLoanMirror) -> dict[str, object]:
    return {
        "external_loan_mirror_id": str(mirror.id),
        "guarantee_case_id": (
            str(mirror.guarantee_case_id) if mirror.guarantee_case_id is not None else None
        ),
        "provider_id": str(mirror.provider_id),
        "external_loan_id": mirror.external_loan_id,
        "state": mirror.state,
        "original_principal": format(mirror.original_principal, "f"),
        "outstanding_principal": format(mirror.outstanding_principal, "f"),
        "currency": mirror.currency,
        "disbursed_at": mirror.disbursed_at.isoformat() if mirror.disbursed_at else None,
        "settled_at": mirror.settled_at.isoformat() if mirror.settled_at else None,
        "delinquency_state": mirror.delinquency_state,
        "last_provider_event_at": (
            mirror.last_provider_event_at.isoformat()
            if mirror.last_provider_event_at is not None
            else None
        ),
        "last_provider_event_sequence": mirror.last_provider_event_sequence,
        "reconciliation_status": mirror.reconciliation_status,
        "version": mirror.version,
    }


async def apply_normalized_lender_event(
    session: AsyncSession,
    *,
    inbox_message: InboxMessage,
    event: NormalizedLenderEvent,
) -> ExternalLoanMirror:
    expected_source = lender_source_id(event.provider_id)
    if inbox_message.source_id != expected_source:
        raise ExternalLoanError(
            "EVENT_SCOPE_INVALID",
            "Inbox source does not match normalized lender provider",
        )

    provider = await session.get(CreditProvider, event.provider_id)
    if provider is None:
        raise ExternalLoanError("PROVIDER_NOT_FOUND", "Lender provider does not exist")

    # Serialize first insertion and subsequent updates across worker replicas.
    # The transaction that locks the Inbox row owns this advisory lock too;
    # the database releases it automatically on commit or rollback.
    await session.scalar(
        select(
            func.pg_advisory_xact_lock(
                _lender_mirror_lock_key(event.provider_id, event.external_loan_id)
            )
        )
    )

    mirror = await session.scalar(
        select(ExternalLoanMirror)
        .where(
            ExternalLoanMirror.provider_id == event.provider_id,
            ExternalLoanMirror.external_loan_id == event.external_loan_id,
        )
        .with_for_update()
    )

    if mirror is None:
        if event.event_type not in {"LOAN_APPROVED", "LOAN_DISBURSED"}:
            raise ExternalLoanError(
                "EXTERNAL_LOAN_MIRROR_MISSING_PREDECESSOR",
                "Cannot infer missing lender history for this event",
                retryable=True,
            )
        await _validate_guarantee_link(
            session,
            provider_id=event.provider_id,
            guarantee_case_id=event.guarantee_case_id,
        )
        mirror = ExternalLoanMirror(
            guarantee_case_id=event.guarantee_case_id,
            provider_id=event.provider_id,
            external_loan_id=event.external_loan_id,
            state="ACTIVE" if event.event_type == "LOAN_DISBURSED" else "PENDING",
            original_principal=event.original_principal_decimal(),
            outstanding_principal=event.outstanding_principal_decimal(),
            currency=event.currency,
            disbursed_at=event.event_time if event.event_type == "LOAN_DISBURSED" else None,
            settled_at=None,
            delinquency_state=event.delinquency_state,
            last_provider_event_at=event.event_time,
            last_provider_event_sequence=event.provider_event_sequence,
            last_synced_at=event.received_at,
            reconciliation_status=None,
            version=1,
        )
        session.add(mirror)
        await session.flush()
        previous_outstanding: Decimal | None = None
        processed_status = "APPLIED"
    else:
        if event.guarantee_case_id is not None:
            if mirror.guarantee_case_id is None:
                raise ExternalLoanError(
                    "LENDER_GUARANTEE_LINK_CHANGE_NOT_AUTHORIZED",
                    "Existing unlinked mirror cannot be linked by a provider event",
                )
            if mirror.guarantee_case_id != event.guarantee_case_id:
                raise ExternalLoanError(
                    "EVENT_SCOPE_INVALID",
                    "Provider event references a different GuaranteeCase",
                )

        in_order = _assert_event_order(mirror, event)
        previous_outstanding = mirror.outstanding_principal
        if not in_order:
            history = _event_history(
                mirror=mirror,
                event=event,
                previous_outstanding=previous_outstanding,
                processed_status="STALE",
            )
            session.add(history)
            append_audit(
                session,
                aggregate_type="ExternalLoanMirror",
                aggregate_id=str(mirror.id),
                aggregate_version=mirror.version,
                action="LENDER_EVENT_STALE",
                actor_type="PROVIDER_INTEGRATION",
                actor_id=event.provider_id,
                correlation_id=event.correlation_id or inbox_message.id,
                causation_id=inbox_message.id,
                outcome="SUCCESS",
                evidence_reference=(
                    event.evidence_references[0] if event.evidence_references else None
                ),
                new_state={
                    "provider_event_id": event.external_event_id,
                    "event_type": event.event_type,
                    "processed_status": "STALE",
                },
                scope={"scope_type": "PROVIDER", "scope_id": str(event.provider_id)},
            )
            await session.flush()
            return mirror

        _assert_non_correction_consistency(mirror, event)
        desired_state = _event_state(event.event_type)
        _assert_state_progression(mirror, desired_state)

        if event.event_type == "LOAN_CORRECTED":
            if mirror.currency != event.currency:
                raise ExternalLoanError(
                    "PROVIDER_CONTRACT_MISMATCH",
                    "LOAN_CORRECTED cannot rewrite loan currency",
                )
            mirror.original_principal = event.original_principal_decimal()
            processed_status = "CORRECTED"
        else:
            processed_status = "APPLIED"

        mirror.outstanding_principal = event.outstanding_principal_decimal()
        if desired_state is not None:
            mirror.state = desired_state
        if event.event_type == "LOAN_DISBURSED":
            mirror.disbursed_at = event.event_time
        if event.event_type == "LOAN_DELINQUENT":
            mirror.delinquency_state = event.delinquency_state
        if event.event_type == "LOAN_SETTLED":
            mirror.settled_at = event.event_time
        if event.event_type == "LOAN_CORRECTED" and event.delinquency_state is not None:
            mirror.delinquency_state = event.delinquency_state

        mirror.last_provider_event_at = event.event_time
        mirror.last_provider_event_sequence = event.provider_event_sequence
        mirror.last_synced_at = event.received_at
        mirror.version += 1

    history = _event_history(
        mirror=mirror,
        event=event,
        previous_outstanding=previous_outstanding,
        processed_status=processed_status,
    )
    session.add(history)

    payload = _mirror_payload(mirror)
    append_audit(
        session,
        aggregate_type="ExternalLoanMirror",
        aggregate_id=str(mirror.id),
        aggregate_version=mirror.version,
        action="LENDER_EVENT_APPLIED",
        actor_type="PROVIDER_INTEGRATION",
        actor_id=event.provider_id,
        correlation_id=event.correlation_id or inbox_message.id,
        causation_id=inbox_message.id,
        outcome="SUCCESS",
        evidence_reference=event.evidence_references[0] if event.evidence_references else None,
        new_state={
            **payload,
            "provider_event_id": event.external_event_id,
            "event_type": event.event_type,
            "processed_status": processed_status,
            "provider_contract_version": event.provider_contract_version,
            "adapter_mapping_version": event.adapter_mapping_version,
            "inbound_normalization_version": event.inbound_normalization_version,
        },
        scope={"scope_type": "PROVIDER", "scope_id": str(event.provider_id)},
    )
    session.add(
        OutboxMessage(
            event_type="ExternalLoanMirrorUpdated",
            event_version=1,
            aggregate_type="ExternalLoanMirror",
            aggregate_id=str(mirror.id),
            aggregate_version=mirror.version,
            payload={
                **payload,
                "provider_event_id": event.external_event_id,
                "source_event_type": event.event_type,
            },
            correlation_id=event.correlation_id,
            causation_id=inbox_message.id,
            occurred_at=event.received_at,
        )
    )
    await session.flush()
    return mirror


async def process_lender_inbox_message(
    session: AsyncSession,
    inbox_message: InboxMessage,
) -> None:
    try:
        event = NormalizedLenderEvent.model_validate(inbox_message.payload)
    except ValidationError as exc:
        raise ExternalLoanError(
            "EVENT_SCHEMA_INVALID",
            "Stored normalized lender event failed schema validation",
        ) from exc
    await apply_normalized_lender_event(
        session,
        inbox_message=inbox_message,
        event=event,
    )


async def process_pending_lender_inbox_batch(
    database: Database,
    *,
    batch_size: int = 50,
) -> LenderInboxBatchResult:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    async with database.session_factory() as session:
        message_ids = (
            await session.scalars(
                select(InboxMessage.id)
                .where(
                    InboxMessage.processed_at.is_(None),
                    InboxMessage.source_id.like(f"{_LENDER_SOURCE_PREFIX}%"),
                )
                .order_by(InboxMessage.received_at, InboxMessage.id)
                .limit(batch_size)
            )
        ).all()

    processed = 0
    failed = 0
    for message_id in message_ids:
        try:
            result = await process_inbox_message_once(
                database,
                message_id=message_id,
                handler=process_lender_inbox_message,
            )
        except ExternalLoanError:
            failed += 1
        else:
            if result.processed or result.already_processed:
                processed += 1

    return LenderInboxBatchResult(
        claimed=len(message_ids),
        processed=processed,
        failed=failed,
    )
