from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.idempotency import canonical_request_hash
from badban.application.lender_adapter import (
    LenderAdapterError,
    LenderAdapterRegistry,
    LenderReconciliationLoan,
    LenderReconciliationScope,
    LenderReconciliationSnapshot,
)
from badban.application.policy_resolution import ResolvedPolicyPack, resolve_active_policy_pack
from badban.infrastructure.persistence.database import Database
from badban.infrastructure.persistence.models import (
    CreditProvider,
    ExternalLoanMirror,
    GuaranteeCase,
    OutboxMessage,
    PolicyVersion,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
)
from badban.security.audit import append_audit

LENDER_RECONCILIATION_TYPE = "LENDER_EXTERNAL_LOAN"
MATERIALITIES = frozenset({"INFO", "WARNING", "MATERIAL", "CRITICAL"})
HARD_PRINCIPAL_REASON = "RECON_GUARANTEE_LOAN_PRINCIPAL_MISMATCH"

_LENDER_POLICY_REASONS = frozenset(
    {
        "RECON_EXTERNAL_RECORD_MISSING",
        "RECON_INTERNAL_RECORD_MISSING",
        "RECON_AMOUNT_MISMATCH",
        "RECON_STATE_MISMATCH",
        "RECON_IDENTIFIER_MISMATCH",
        "RECON_DUPLICATE_EXTERNAL_RECORD",
        "RECON_SOURCE_STALE",
    }
)
_ALLOWED_DECIMAL_TOLERANCE_FIELDS = frozenset({"outstanding_principal"})
_MATERIALITY_RANK = {"INFO": 0, "WARNING": 1, "MATERIAL": 2, "CRITICAL": 3}


class ReconciliationError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ReconciliationPolicyRules:
    max_source_age_seconds: int
    materiality_by_reason: dict[str, str]
    decimal_tolerance_by_field: dict[str, Decimal]


@dataclass(frozen=True, slots=True)
class ResolvedReconciliationPolicy:
    policy_pack_id: UUID
    policy_pack_version: int
    scope_definition: dict[str, Any]
    rule_policy_version_id: UUID
    rule_policy_code: str
    rule_policy_version_number: int
    rule_schema_version: str
    rules: ReconciliationPolicyRules


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _parse_tolerance(value: object, *, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            f"{field} tolerance must be a decimal string",
        )
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            f"{field} tolerance must be a decimal string",
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            f"{field} tolerance must be finite and non-negative",
        )
    exponent = parsed.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            f"{field} tolerance must use a finite exponent",
        )
    scale = max(-exponent, 0)
    integer_digits = max(parsed.adjusted() + 1, 0)
    if scale > 18 or integer_digits > 20:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            f"{field} tolerance exceeds NUMERIC(38,18) precision",
        )
    return parsed


def parse_reconciliation_policy_rules(
    payload: dict[str, Any],
    *,
    reconciliation_type: str,
) -> ReconciliationPolicyRules:
    root = payload.get("reconciliation_rules")
    if not isinstance(root, dict):
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation Policy must define reconciliation_rules",
        )
    raw = root.get(reconciliation_type)
    if not isinstance(raw, dict):
        raise ReconciliationError(
            "RECONCILIATION_POLICY_MISSING",
            f"Reconciliation Policy has no rules for {reconciliation_type}",
        )

    max_age = raw.get("max_source_age_seconds")
    if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age <= 0:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "max_source_age_seconds must be an explicit positive integer",
        )

    materialities = raw.get("materiality_by_reason")
    if not isinstance(materialities, dict):
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "materiality_by_reason must be explicitly configured",
        )
    missing_reasons = sorted(_LENDER_POLICY_REASONS - set(materialities))
    if missing_reasons:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation Policy is missing required materiality mappings: "
            + ",".join(missing_reasons),
        )
    normalized_materialities: dict[str, str] = {}
    for reason, value in materialities.items():
        if reason not in _LENDER_POLICY_REASONS:
            continue
        if not isinstance(value, str) or value not in MATERIALITIES:
            raise ReconciliationError(
                "RECONCILIATION_POLICY_INVALID",
                f"Invalid materiality for {reason}",
            )
        normalized_materialities[reason] = value

    tolerances = raw.get("decimal_tolerance_by_field", {})
    if not isinstance(tolerances, dict):
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "decimal_tolerance_by_field must be an object when supplied",
        )
    unknown_fields = sorted(set(tolerances) - _ALLOWED_DECIMAL_TOLERANCE_FIELDS)
    if unknown_fields:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "Tolerance is not authorized for fields: " + ",".join(unknown_fields),
        )
    parsed_tolerances = {
        field: _parse_tolerance(value, field=field) for field, value in tolerances.items()
    }
    return ReconciliationPolicyRules(
        max_source_age_seconds=max_age,
        materiality_by_reason=normalized_materialities,
        decimal_tolerance_by_field=parsed_tolerances,
    )


async def resolve_reconciliation_policy(
    session: AsyncSession,
    *,
    resolved_policy_pack: ResolvedPolicyPack,
    reconciliation_type: str,
) -> ResolvedReconciliationPolicy:
    pack = await session.get(PolicyVersion, resolved_policy_pack.policy_pack_id)
    if pack is None or pack.policy_type != "PILOT_POLICY_PACK" or pack.lifecycle_status != "ACTIVE":
        raise ReconciliationError(
            "POLICY_PACK_NOT_ACTIVE",
            "Resolved Pilot Policy Pack is no longer ACTIVE",
        )
    if not resolved_policy_pack.component_version_ids:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_MISSING",
            "Pilot Policy Pack does not reference a Reconciliation Policy",
        )

    policies = (
        await session.scalars(
            select(PolicyVersion).where(
                PolicyVersion.id.in_(resolved_policy_pack.component_version_ids),
                PolicyVersion.policy_type == "RECONCILIATION_POLICY",
            )
        )
    ).all()
    if not policies:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_MISSING",
            "Pilot Policy Pack does not reference a Reconciliation Policy",
        )
    if len(policies) != 1:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_AMBIGUOUS",
            "Pilot Policy Pack must reference exactly one Reconciliation Policy",
        )
    policy = policies[0]
    if policy.scope_definition != pack.scope_definition:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation Policy scope does not match the Pilot Policy Pack scope",
        )
    if policy.lifecycle_status not in {"APPROVED", "ACTIVE", "SUPERSEDED", "RETIRED"}:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation Policy has not reached an approved immutable lineage state",
        )
    if policy.payload_hash is None or policy.payload_hash != canonical_request_hash(policy.payload):
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation Policy failed payload integrity verification",
        )

    rules = parse_reconciliation_policy_rules(
        policy.payload,
        reconciliation_type=reconciliation_type,
    )
    return ResolvedReconciliationPolicy(
        policy_pack_id=pack.id,
        policy_pack_version=pack.version_number,
        scope_definition=pack.scope_definition,
        rule_policy_version_id=policy.id,
        rule_policy_code=policy.policy_code,
        rule_policy_version_number=policy.version_number,
        rule_schema_version=policy.schema_version,
        rules=rules,
    )


def _snapshot_fingerprint(
    snapshot: LenderReconciliationSnapshot,
    *,
    policy: ResolvedReconciliationPolicy,
) -> str:
    payload = {
        "reconciliation_type": LENDER_RECONCILIATION_TYPE,
        "policy_version_id": str(policy.rule_policy_version_id),
        "policy_version_number": policy.rule_policy_version_number,
        "snapshot": snapshot.model_dump(mode="json"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _materiality(rules: ReconciliationPolicyRules, reason: str) -> str:
    if reason == HARD_PRINCIPAL_REASON:
        return "CRITICAL"
    try:
        return rules.materiality_by_reason[reason]
    except KeyError as exc:
        raise ReconciliationError(
            "RECONCILIATION_POLICY_INVALID",
            f"No materiality configured for {reason}",
        ) from exc


def _decimal_matches(
    field: str,
    internal: Decimal,
    external: Decimal,
    *,
    rules: ReconciliationPolicyRules,
) -> bool:
    tolerance = rules.decimal_tolerance_by_field.get(field)
    if tolerance is None:
        return internal == external
    return abs(internal - external) <= tolerance


async def _add_case(
    session: AsyncSession,
    *,
    run: ReconciliationRun,
    policy: ResolvedReconciliationPolicy,
    provider_id: UUID,
    internal_entity_id: UUID | None,
    external_reference: str | None,
    status: str,
    materiality: str,
    reason: str | None,
    difference: dict[str, Any],
    evidence_reference: str | None,
    compared_at: datetime,
) -> ReconciliationCase:
    case = ReconciliationCase(
        run_id=run.id,
        reconciliation_type=LENDER_RECONCILIATION_TYPE,
        internal_entity_type="ExternalLoanMirror",
        internal_entity_id=str(internal_entity_id) if internal_entity_id is not None else None,
        external_provider_id=provider_id,
        external_reference=external_reference,
        status=status,
        materiality=materiality,
        mismatch_reason_code=reason,
        compared_at=compared_at,
        resolved_at=None,
        resolution_reference=None,
        rule_policy_version_id=policy.rule_policy_version_id,
        rule_policy_version_number=policy.rule_policy_version_number,
        first_detected_at=compared_at,
        last_observed_at=compared_at,
        version=1,
    )
    session.add(case)
    await session.flush()
    session.add(
        ReconciliationObservation(
            reconciliation_case_id=case.id,
            internal_value_reference=(
                f"ExternalLoanMirror:{internal_entity_id}"
                if internal_entity_id is not None
                else "ExternalLoanMirror:MISSING"
            ),
            external_value_reference=(
                f"LenderLoan:{provider_id}:{external_reference}"
                if external_reference is not None
                else f"LenderLoan:{provider_id}:MISSING"
            ),
            difference_payload=difference,
            evidence_reference=evidence_reference,
            observed_at=compared_at,
        )
    )
    if status == "MISMATCH":
        session.add(
            OutboxMessage(
                event_type="ReconciliationMismatchDetected",
                event_version=1,
                aggregate_type="ReconciliationCase",
                aggregate_id=str(case.id),
                aggregate_version=case.version,
                payload={
                    "case_id": str(case.id),
                    "run_id": str(run.id),
                    "reconciliation_type": case.reconciliation_type,
                    "materiality": materiality,
                    "reason_code": reason,
                    "provider_id": str(provider_id),
                    "external_reference": external_reference,
                },
                correlation_id=None,
                causation_id=None,
                occurred_at=compared_at,
            )
        )
    elif status == "STALE":
        session.add(
            OutboxMessage(
                event_type="ReconciliationBecameStale",
                event_version=1,
                aggregate_type="ReconciliationCase",
                aggregate_id=str(case.id),
                aggregate_version=case.version,
                payload={
                    "case_id": str(case.id),
                    "run_id": str(run.id),
                    "reconciliation_type": case.reconciliation_type,
                    "materiality": materiality,
                    "reason_code": reason,
                    "provider_id": str(provider_id),
                },
                correlation_id=None,
                causation_id=None,
                occurred_at=compared_at,
            )
        )
    return case


async def _record_provider_unavailable(
    database: Database,
    *,
    provider_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    reason_code: str,
) -> None:
    async with database.session_factory() as session:
        async with session.begin():
            append_audit(
                session,
                aggregate_type="CreditProvider",
                aggregate_id=str(provider_id),
                aggregate_version=None,
                action="RECONCILIATION_SOURCE_UNAVAILABLE",
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                outcome="DENIED",
                reason_code=reason_code,
                scope={"scope_type": "PROVIDER", "scope_id": str(provider_id)},
            )


async def execute_lender_reconciliation(
    database: Database,
    registry: LenderAdapterRegistry,
    *,
    provider_id: UUID,
    scope_definition: dict[str, Any],
    scope_reference: str | None,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> UUID:
    started_at = datetime.now(UTC)

    async with database.session_factory() as session:
        resolved_pack = await resolve_active_policy_pack(
            session,
            scope_definition=scope_definition,
            effective_at=started_at,
        )
        policy = await resolve_reconciliation_policy(
            session,
            resolved_policy_pack=resolved_pack,
            reconciliation_type=LENDER_RECONCILIATION_TYPE,
        )
        provider = await session.get(CreditProvider, provider_id)
        if provider is None:
            raise ReconciliationError(
                "PROVIDER_NOT_FOUND",
                "Lender provider was not found",
            )

    try:
        adapter = registry.resolve(provider_id)
        manifest = adapter.capability_manifest()
        if not manifest.supports_reconciliation_snapshot:
            raise ReconciliationError(
                "RECONCILIATION_SOURCE_NOT_CONFIGURED",
                "Configured lender adapter does not support reconciliation snapshots",
            )
        snapshot = await adapter.fetch_reconciliation_snapshot(
            LenderReconciliationScope(
                provider_id=provider_id,
                scope_reference=scope_reference,
            )
        )
    except ReconciliationError:
        raise
    except LenderAdapterError as exc:
        await _record_provider_unavailable(
            database,
            provider_id=provider_id,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            reason_code="RECON_SOURCE_UNAVAILABLE",
        )
        raise ReconciliationError(exc.code, str(exc), retryable=True) from exc
    except Exception as exc:
        translated = adapter.translate_error(exc)
        await _record_provider_unavailable(
            database,
            provider_id=provider_id,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            reason_code="RECON_SOURCE_UNAVAILABLE",
        )
        raise ReconciliationError(
            translated.code,
            "Lender reconciliation source is unavailable",
            retryable=translated.classification in {"RETRYABLE", "UNKNOWN_OUTCOME"},
        ) from exc

    if snapshot.provider_id != provider_id:
        raise ReconciliationError(
            "RECONCILIATION_SCOPE_INVALID",
            "Lender reconciliation snapshot provider does not match the requested provider",
        )
    if snapshot.source_reference is None and not snapshot.evidence_references:
        raise ReconciliationError(
            "RECONCILIATION_EVIDENCE_REQUIRED",
            "Lender reconciliation snapshot requires a source or evidence reference",
        )

    compared_at = datetime.now(UTC)
    if snapshot.snapshot_at > compared_at:
        raise ReconciliationError(
            "RECONCILIATION_SOURCE_CUTOFF_INVALID",
            "Lender reconciliation snapshot cutoff is in the future",
        )
    fingerprint = _snapshot_fingerprint(snapshot, policy=policy)
    evidence_reference = (
        snapshot.evidence_references[0]
        if snapshot.evidence_references
        else snapshot.source_reference
    )

    async with database.session_factory() as session:
        async with session.begin():
            await session.execute(
                text(
                    "SELECT pg_advisory_xact_lock(hashtextextended(:reconciliation_fingerprint, 0))"
                ),
                {"reconciliation_fingerprint": fingerprint},
            )
            existing = await session.scalar(
                select(ReconciliationRun).where(ReconciliationRun.source_fingerprint == fingerprint)
            )
            if existing is not None:
                return existing.id

            run = ReconciliationRun(
                reconciliation_type=LENDER_RECONCILIATION_TYPE,
                provider_id=provider_id,
                scope_definition=scope_definition,
                policy_pack_id=policy.policy_pack_id,
                policy_pack_version=policy.policy_pack_version,
                rule_policy_version_id=policy.rule_policy_version_id,
                rule_policy_code=policy.rule_policy_code,
                rule_policy_version_number=policy.rule_policy_version_number,
                rule_schema_version=policy.rule_schema_version,
                internal_cutoff=compared_at,
                external_cutoff=snapshot.snapshot_at,
                source_snapshot_ref=snapshot.source_reference,
                source_evidence_references=snapshot.evidence_references,
                source_fingerprint=fingerprint,
                status="RUNNING",
                started_at=started_at,
                finished_at=None,
                matched_count=0,
                mismatch_count=0,
                stale_count=0,
                critical_count=0,
            )
            session.add(run)
            await session.flush()
            session.add(
                OutboxMessage(
                    event_type="ReconciliationRunStarted",
                    event_version=1,
                    aggregate_type="ReconciliationRun",
                    aggregate_id=str(run.id),
                    aggregate_version=1,
                    payload={
                        "run_id": str(run.id),
                        "reconciliation_type": run.reconciliation_type,
                        "provider_id": str(provider_id),
                        "rule_policy_version_id": str(policy.rule_policy_version_id),
                    },
                    correlation_id=correlation_id,
                    causation_id=None,
                    occurred_at=started_at,
                )
            )

            mirrors = (
                await session.scalars(
                    select(ExternalLoanMirror)
                    .where(ExternalLoanMirror.provider_id == provider_id)
                    .order_by(ExternalLoanMirror.external_loan_id)
                    .with_for_update()
                )
            ).all()
            mirror_by_external_id = {mirror.external_loan_id: mirror for mirror in mirrors}

            source_age = compared_at - snapshot.snapshot_at
            if source_age > timedelta(seconds=policy.rules.max_source_age_seconds):
                materiality = _materiality(policy.rules, "RECON_SOURCE_STALE")
                await _add_case(
                    session,
                    run=run,
                    policy=policy,
                    provider_id=provider_id,
                    internal_entity_id=None,
                    external_reference=None,
                    status="STALE",
                    materiality=materiality,
                    reason="RECON_SOURCE_STALE",
                    difference={
                        "snapshot_at": snapshot.snapshot_at.isoformat(),
                        "compared_at": compared_at.isoformat(),
                        "source_age_seconds": _decimal_text(
                            Decimal(str(source_age.total_seconds()))
                        ),
                        "max_source_age_seconds": policy.rules.max_source_age_seconds,
                    },
                    evidence_reference=evidence_reference,
                    compared_at=compared_at,
                )
                for mirror in mirrors:
                    mirror.reconciliation_status = "STALE"
                    mirror.version += 1
                run.stale_count = 1
                run.critical_count = 1 if materiality == "CRITICAL" else 0
            else:
                external_groups: dict[str, list[LenderReconciliationLoan]] = {}
                for loan in snapshot.loans:
                    external_groups.setdefault(loan.external_loan_id, []).append(loan)

                duplicate_ids = {
                    external_id for external_id, rows in external_groups.items() if len(rows) > 1
                }
                mismatch_mirror_ids: set[UUID] = set()

                for external_id in sorted(duplicate_ids):
                    materiality = _materiality(
                        policy.rules,
                        "RECON_DUPLICATE_EXTERNAL_RECORD",
                    )
                    mirror = mirror_by_external_id.get(external_id)
                    await _add_case(
                        session,
                        run=run,
                        policy=policy,
                        provider_id=provider_id,
                        internal_entity_id=mirror.id if mirror is not None else None,
                        external_reference=external_id,
                        status="MISMATCH",
                        materiality=materiality,
                        reason="RECON_DUPLICATE_EXTERNAL_RECORD",
                        difference={"external_record_count": len(external_groups[external_id])},
                        evidence_reference=evidence_reference,
                        compared_at=compared_at,
                    )
                    run.mismatch_count += 1
                    if materiality == "CRITICAL":
                        run.critical_count += 1
                    if mirror is not None:
                        mismatch_mirror_ids.add(mirror.id)

                guarantee_ids = {
                    mirror.guarantee_case_id
                    for mirror in mirrors
                    if mirror.guarantee_case_id is not None
                }
                guarantees = (
                    (
                        await session.scalars(
                            select(GuaranteeCase).where(GuaranteeCase.id.in_(guarantee_ids))
                        )
                    ).all()
                    if guarantee_ids
                    else []
                )
                guarantees_by_id = {guarantee.id: guarantee for guarantee in guarantees}

                all_external_ids = set(external_groups)
                all_internal_ids = set(mirror_by_external_id)
                for external_id in sorted(all_external_ids | all_internal_ids):
                    if external_id in duplicate_ids:
                        continue
                    mirror = mirror_by_external_id.get(external_id)
                    external_rows = external_groups.get(external_id, [])
                    external = external_rows[0] if external_rows else None

                    if mirror is None and external is not None:
                        reason = "RECON_INTERNAL_RECORD_MISSING"
                        materiality = _materiality(policy.rules, reason)
                        await _add_case(
                            session,
                            run=run,
                            policy=policy,
                            provider_id=provider_id,
                            internal_entity_id=None,
                            external_reference=external_id,
                            status="MISMATCH",
                            materiality=materiality,
                            reason=reason,
                            difference={"internal": None, "external_record_present": True},
                            evidence_reference=evidence_reference,
                            compared_at=compared_at,
                        )
                        run.mismatch_count += 1
                        if materiality == "CRITICAL":
                            run.critical_count += 1
                        continue

                    if mirror is not None and external is None:
                        reason = "RECON_EXTERNAL_RECORD_MISSING"
                        materiality = _materiality(policy.rules, reason)
                        await _add_case(
                            session,
                            run=run,
                            policy=policy,
                            provider_id=provider_id,
                            internal_entity_id=mirror.id,
                            external_reference=external_id,
                            status="MISMATCH",
                            materiality=materiality,
                            reason=reason,
                            difference={"internal_record_present": True, "external": None},
                            evidence_reference=evidence_reference,
                            compared_at=compared_at,
                        )
                        run.mismatch_count += 1
                        if materiality == "CRITICAL":
                            run.critical_count += 1
                        mismatch_mirror_ids.add(mirror.id)
                        continue

                    assert mirror is not None and external is not None
                    differences: list[tuple[str, dict[str, Any]]] = []
                    external_original = Decimal(external.original_principal)
                    external_outstanding = Decimal(external.outstanding_principal)

                    if mirror.original_principal != external_original:
                        differences.append(
                            (
                                "RECON_AMOUNT_MISMATCH",
                                {
                                    "field": "original_principal",
                                    "internal": _decimal_text(mirror.original_principal),
                                    "external": external.original_principal,
                                    "comparison": "DECIMAL_EXACT",
                                },
                            )
                        )
                    if not _decimal_matches(
                        "outstanding_principal",
                        mirror.outstanding_principal,
                        external_outstanding,
                        rules=policy.rules,
                    ):
                        differences.append(
                            (
                                "RECON_AMOUNT_MISMATCH",
                                {
                                    "field": "outstanding_principal",
                                    "internal": _decimal_text(mirror.outstanding_principal),
                                    "external": external.outstanding_principal,
                                    "tolerance": (
                                        _decimal_text(
                                            policy.rules.decimal_tolerance_by_field[
                                                "outstanding_principal"
                                            ]
                                        )
                                        if "outstanding_principal"
                                        in policy.rules.decimal_tolerance_by_field
                                        else None
                                    ),
                                },
                            )
                        )
                    if mirror.currency != external.currency:
                        differences.append(
                            (
                                "RECON_IDENTIFIER_MISMATCH",
                                {
                                    "field": "currency",
                                    "internal": mirror.currency,
                                    "external": external.currency,
                                },
                            )
                        )
                    if mirror.state != external.provider_state:
                        differences.append(
                            (
                                "RECON_STATE_MISMATCH",
                                {
                                    "field": "state",
                                    "internal": mirror.state,
                                    "external": external.provider_state,
                                },
                            )
                        )

                    if mirror.guarantee_case_id is not None:
                        guarantee = guarantees_by_id.get(mirror.guarantee_case_id)
                        issued_amount = (
                            guarantee.issued_guarantee_amount if guarantee is not None else None
                        )
                        if issued_amount is None or issued_amount != external_original:
                            differences.append(
                                (
                                    HARD_PRINCIPAL_REASON,
                                    {
                                        "field": "issued_guarantee_amount_vs_external_principal",
                                        "guarantee_case_id": str(mirror.guarantee_case_id),
                                        "issued_guarantee_amount": (
                                            _decimal_text(issued_amount)
                                            if issued_amount is not None
                                            else None
                                        ),
                                        "external_original_principal": external.original_principal,
                                        "comparison": "DECIMAL_EXACT_HARD_INVARIANT",
                                    },
                                )
                            )

                    if not differences:
                        await _add_case(
                            session,
                            run=run,
                            policy=policy,
                            provider_id=provider_id,
                            internal_entity_id=mirror.id,
                            external_reference=external_id,
                            status="MATCHED",
                            materiality="INFO",
                            reason=None,
                            difference={"matched": True},
                            evidence_reference=evidence_reference,
                            compared_at=compared_at,
                        )
                        mirror.reconciliation_status = "MATCHED"
                        mirror.version += 1
                        run.matched_count += 1
                        continue

                    mismatch_mirror_ids.add(mirror.id)
                    seen: set[tuple[str, str]] = set()
                    for reason, difference in differences:
                        identity = (reason, str(difference.get("field")))
                        if identity in seen:
                            continue
                        seen.add(identity)
                        materiality = _materiality(policy.rules, reason)
                        await _add_case(
                            session,
                            run=run,
                            policy=policy,
                            provider_id=provider_id,
                            internal_entity_id=mirror.id,
                            external_reference=external_id,
                            status="MISMATCH",
                            materiality=materiality,
                            reason=reason,
                            difference=difference,
                            evidence_reference=evidence_reference,
                            compared_at=compared_at,
                        )
                        run.mismatch_count += 1
                        if materiality == "CRITICAL":
                            run.critical_count += 1

                for mirror in mirrors:
                    if mirror.id in mismatch_mirror_ids:
                        mirror.reconciliation_status = "MISMATCH"
                        mirror.version += 1

            run.status = "COMPLETED"
            run.finished_at = datetime.now(UTC)
            append_audit(
                session,
                aggregate_type="ReconciliationRun",
                aggregate_id=str(run.id),
                aggregate_version=1,
                action="RECONCILIATION_RUN_COMPLETED",
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                outcome="SUCCESS",
                policy_pack_id=policy.policy_pack_id,
                new_state={
                    "reconciliation_type": run.reconciliation_type,
                    "provider_id": str(provider_id),
                    "rule_policy_version_id": str(policy.rule_policy_version_id),
                    "source_fingerprint": fingerprint,
                    "matched_count": run.matched_count,
                    "mismatch_count": run.mismatch_count,
                    "stale_count": run.stale_count,
                    "critical_count": run.critical_count,
                    "status": run.status,
                },
                scope={"scope_type": "PROVIDER", "scope_id": str(provider_id)},
            )
            session.add(
                OutboxMessage(
                    event_type="ReconciliationRunCompleted",
                    event_version=1,
                    aggregate_type="ReconciliationRun",
                    aggregate_id=str(run.id),
                    aggregate_version=1,
                    payload={
                        "run_id": str(run.id),
                        "reconciliation_type": run.reconciliation_type,
                        "provider_id": str(provider_id),
                        "matched_count": run.matched_count,
                        "mismatch_count": run.mismatch_count,
                        "stale_count": run.stale_count,
                        "critical_count": run.critical_count,
                        "rule_policy_version_id": str(policy.rule_policy_version_id),
                    },
                    correlation_id=correlation_id,
                    causation_id=None,
                    occurred_at=run.finished_at,
                )
            )
            await session.flush()
            return run.id
