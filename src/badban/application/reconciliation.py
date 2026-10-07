from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.lender_adapter import (
    LenderAdapterError,
    LenderAdapterRegistry,
    LenderReconciliationScope,
    LenderReconciliationSnapshot,
)
from badban.application.reconciliation_policy import (
    ReconciliationRules,
    resolve_provider_pack,
    resolve_reconciliation_policy,
)
from badban.infrastructure.persistence.models import (
    ExternalLoanMirror,
    GuaranteeCase,
    OutboxMessage,
    ReconciliationBlock,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
)
from badban.security.audit import append_audit

ALGORITHM_CODE = "RECONCILIATION_CORE"
ALGORITHM_VERSION = "1"
MATERIALITY_RANK = {"INFO": 0, "WARNING": 1, "MATERIAL": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class ComparisonOutcome:
    status: str
    materiality: str
    reasons: tuple[str, ...]
    differences: tuple[dict[str, Any], ...]
    blocked_commands: tuple[str, ...]


def compare_fields(
    internal: dict[str, str], external: dict[str, str], rules: ReconciliationRules
) -> ComparisonOutcome:
    differences: list[dict[str, Any]] = []
    reasons: list[str] = []
    commands: set[str] = set()
    materiality = "INFO"
    for rule in rules.rules:
        left, right = internal.get(rule.field_code), external.get(rule.field_code)
        if left is None or right is None:
            different = True
        elif rule.comparison_mode in {"DECIMAL_EXACT", "TOLERANCE_BASED"}:
            try:
                a, b = Decimal(left), Decimal(right)
                if not a.is_finite() or not b.is_finite():
                    raise ValueError("nonfinite amount")
                with localcontext() as context:
                    context.prec = max(100, len(left) + len(right) + 10)
                    different = (
                        a != b
                        if rule.comparison_mode == "DECIMAL_EXACT"
                        else abs(a - b) > Decimal(str(rule.tolerance))
                    )
            except (ValueError, ArithmeticError) as exc:
                raise ApiError(
                    409, "RECON_MAPPING_MISMATCH", "Canonical amount is invalid"
                ) from exc
        else:
            different = left != right
        if different:
            differences.append(
                {
                    "rule_code": rule.rule_code,
                    "field_code": rule.field_code,
                    "internal": left,
                    "external": right,
                    "comparison_mode": rule.comparison_mode,
                }
            )
            if rule.comparison_mode != "INFORMATIONAL":
                reasons.append(rule.reason_code)
                commands.update(rule.blocked_commands)
                materiality = max(materiality, rule.materiality, key=MATERIALITY_RANK.__getitem__)
    return ComparisonOutcome(
        "MISMATCH" if reasons else "MATCHED",
        materiality,
        tuple(reasons),
        tuple(differences),
        tuple(sorted(commands)),
    )


def _record_fields(mirror: ExternalLoanMirror) -> dict[str, str]:
    return {
        "external_loan_id": mirror.external_loan_id,
        "original_principal": format(mirror.original_principal, "f"),
        "outstanding_principal": format(mirror.outstanding_principal, "f"),
        "currency": mirror.currency,
        "state": mirror.state,
    }


def _is_fresh(observed_at: datetime | None, at: datetime, max_age: int) -> bool:
    return observed_at is not None and 0 <= (at - observed_at).total_seconds() <= max_age


async def run_lender_reconciliation(
    session: AsyncSession,
    *,
    provider_id: UUID,
    registry: LenderAdapterRegistry,
    actor_id: UUID,
    actor_type: str,
    correlation_id: UUID,
    now: datetime | None = None,
) -> ReconciliationRun:
    timestamp = now or datetime.now(UTC)
    # Serialize snapshots/effects for a provider; no process-local lock or provider callback truth.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"reconciliation:lender:{provider_id}"},
    )
    pack, pack_scope = await resolve_provider_pack(
        session, provider_id=provider_id, effective_at=timestamp
    )
    required_scope = {**pack_scope, "reconciliation_type": "LENDER"}
    policy, rules = await resolve_reconciliation_policy(
        session, pack=pack, required_scope=required_scope
    )
    mirrors = (
        await session.scalars(
            select(ExternalLoanMirror)
            .where(ExternalLoanMirror.provider_id == provider_id)
            .order_by(ExternalLoanMirror.external_loan_id)
            .with_for_update()
        )
    ).all()
    guarantee_ids = [m.guarantee_case_id for m in mirrors if m.guarantee_case_id is not None]
    guarantees = (
        await session.scalars(
            select(GuaranteeCase)
            .where(GuaranteeCase.id.in_(guarantee_ids))
            .order_by(GuaranteeCase.id)
            .with_for_update()
        )
    ).all()
    if any(g.provider_id != provider_id for g in guarantees):
        raise ApiError(409, "RECON_MAPPING_MISMATCH", "Linked guarantee provider differs")
    guarantee_by_id = {g.id: g for g in guarantees}
    internal = {m.external_loan_id: _record_fields(m) for m in mirrors}
    internal_hash = canonical_request_hash(
        {
            m.external_loan_id: {
                "fields": internal[m.external_loan_id],
                "event_at": m.last_provider_event_at,
                "version": m.version,
                "guarantee_case_id": m.guarantee_case_id,
                "guarantee_snapshot": (
                    {
                        "version": guarantee_by_id[m.guarantee_case_id].version,
                        "state": guarantee_by_id[m.guarantee_case_id].state,
                        "issued_amount": guarantee_by_id[
                            m.guarantee_case_id
                        ].issued_guarantee_amount,
                    }
                    if m.guarantee_case_id is not None and m.guarantee_case_id in guarantee_by_id
                    else None
                ),
            }
            for m in mirrors
        }
    )
    adapter_versions: dict[str, str] = {}
    snapshot: LenderReconciliationSnapshot | None = None
    outage: str | None = None
    try:
        adapter = registry.resolve(provider_id)
        manifest = adapter.capability_manifest()
        adapter_versions = {
            "provider_contract_version": manifest.provider_contract_version,
            "adapter_mapping_version": manifest.adapter_mapping_version,
            "inbound_normalization_version": manifest.inbound_normalization_version,
        }
        if not manifest.supports_reconciliation_snapshot:
            raise ApiError(
                409, "RECON_MAPPING_MISMATCH", "Adapter lacks independent reconciliation capability"
            )
        snapshot = await adapter.fetch_reconciliation_snapshot(
            LenderReconciliationScope(provider_id=provider_id)
        )
        # Revalidate even an adapter-created instance (model_construct/copy can bypass validation).
        snapshot = LenderReconciliationSnapshot.model_validate(snapshot.model_dump(mode="json"))
        if snapshot.provider_id != provider_id:
            raise ApiError(409, "RECON_MAPPING_MISMATCH", "Provider snapshot scope differs")
        if (
            not snapshot.source_reference or not snapshot.source_reference.strip()
        ) and not snapshot.evidence_references:
            raise ApiError(409, "RECON_EVIDENCE_MISSING", "Independent source evidence is required")
    except LenderAdapterError as exc:
        outage = exc.code
    except TimeoutError:
        outage = "PROVIDER_TIMEOUT"
    except ValidationError as exc:
        raise ApiError(409, "RECON_MAPPING_MISMATCH", "Snapshot schema is invalid") from exc
    external_ref = (
        None
        if snapshot is None
        else snapshot.source_reference or canonical_request_hash(snapshot.evidence_references)
    )
    ext_payload = None if snapshot is None else snapshot.model_dump(mode="json")
    identity = canonical_request_hash(
        {
            "provider": str(provider_id),
            "pack": str(pack.policy_pack_id),
            "policy": str(policy.id),
            "internal": internal_hash,
            "adapter_versions": adapter_versions,
            "external_ref": external_ref,
            "external_cutoff": snapshot.snapshot_at if snapshot else None,
            # The same evidence can cross an explicit policy freshness boundary.
            # Deduplicate equal evaluations, never reuse a formerly MATCHED run as fresh.
            "freshness_evaluation": {
                "internal": {
                    m.external_loan_id: _is_fresh(
                        m.last_provider_event_at,
                        timestamp,
                        rules.freshness.internal_max_age_seconds,
                    )
                    for m in mirrors
                },
                "snapshot": _is_fresh(
                    snapshot.snapshot_at if snapshot else None,
                    timestamp,
                    rules.freshness.external_max_age_seconds,
                ),
                "external_rows": sorted(
                    (
                        loan.external_loan_id,
                        _is_fresh(
                            loan.observed_at, timestamp, rules.freshness.external_max_age_seconds
                        ),
                    )
                    for loan in snapshot.loans
                )
                if snapshot
                else [],
            },
            "outage": outage,
            "outage_at": timestamp if outage else None,
        }
    )
    content_hash = canonical_request_hash(ext_payload)
    existing = await session.scalar(
        select(ReconciliationRun).where(ReconciliationRun.source_identity == identity)
    )
    if existing is not None:
        if existing.source_content_hash != content_hash:
            raise ApiError(
                409,
                "RECON_SNAPSHOT_CONFLICT",
                "Snapshot identity was reused with changed semantic content",
            )
        return existing
    cutoffs = [m.last_provider_event_at for m in mirrors if m.last_provider_event_at is not None]
    internal_cutoff = max(cutoffs) if cutoffs else timestamp
    run = ReconciliationRun(
        id=uuid4(),
        reconciliation_type="LENDER",
        provider_id=provider_id,
        scope_definition=required_scope,
        source_identity=identity,
        source_content_hash=content_hash,
        policy_pack_id=pack.policy_pack_id,
        policy_pack_version=pack.version_number,
        reconciliation_policy_version_id=policy.id,
        reconciliation_policy_version_number=policy.version_number,
        reconciliation_policy_payload_hash=policy.payload_hash,
        rule_schema_version=policy.schema_version,
        algorithm_code=ALGORITHM_CODE,
        algorithm_version=ALGORITHM_VERSION,
        internal_cutoff=internal_cutoff,
        external_cutoff=snapshot.snapshot_at if snapshot else None,
        source_snapshot_ref=external_ref,
        source_metadata={
            "internal_snapshot_hash": internal_hash,
            "external_snapshot": ext_payload,
            "outage_reason": outage,
            "received_at": timestamp.isoformat(),
            "adapter_versions": adapter_versions,
        },
        status="SOURCE_UNAVAILABLE" if outage else "COMPLETED",
        counts={},
        started_at=timestamp,
        finished_at=timestamp,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
    session.add(run)
    staged: list[Any] = []
    external: dict[str, dict[str, str]] = {}
    duplicates: set[str] = set()
    external_observed: dict[str, datetime] = {}
    if snapshot is not None:
        for loan in snapshot.loans:
            if loan.provider_state not in {
                "PENDING",
                "ACTIVE",
                "DELINQUENT",
                "SETTLED",
                "REPLACED",
            }:
                raise ApiError(409, "RECON_MAPPING_MISMATCH", "Unknown normalized lender state")
            if loan.observed_at > snapshot.snapshot_at:
                raise ApiError(
                    409, "RECON_MAPPING_MISMATCH", "Loan observation exceeds snapshot cutoff"
                )
            if loan.external_loan_id in external:
                duplicates.add(loan.external_loan_id)
            external_observed[loan.external_loan_id] = loan.observed_at
            external[loan.external_loan_id] = {
                "external_loan_id": loan.external_loan_id,
                "original_principal": loan.original_principal,
                "outstanding_principal": loan.outstanding_principal,
                "currency": loan.currency,
                "state": loan.provider_state,
            }
    cases: list[ReconciliationCase] = []
    critical_count = 0
    mirror_by_key = {m.external_loan_id: m for m in mirrors}
    keys = sorted(set(internal) | set(external)) or ["PROVIDER_SCOPE"]
    for key in keys:
        left, right = internal.get(key), external.get(key)
        mirror = mirror_by_key.get(key)
        reasons: list[str] = []
        differences: list[dict[str, Any]] = []
        commands: set[str] = set()
        materiality = "INFO"
        status = "MATCHED"
        # Unavailable, future, old or missing evidence is never matched, including empty scopes.
        age = (timestamp - snapshot.snapshot_at).total_seconds() if snapshot else None
        internal_age = (
            (timestamp - mirror.last_provider_event_at).total_seconds()
            if mirror and mirror.last_provider_event_at
            else None
        )
        stale = (
            snapshot is None
            or age is None
            or age < 0
            or age > rules.freshness.external_max_age_seconds
        )
        stale = stale or (
            mirror is not None
            and (
                internal_age is None
                or internal_age < 0
                or internal_age > rules.freshness.internal_max_age_seconds
            )
        )
        if key in external_observed:
            row_age = (timestamp - external_observed[key]).total_seconds()
            stale = stale or row_age < 0 or row_age > rules.freshness.external_max_age_seconds
        if stale:
            status = "STALE"
            reasons.append("RECON_SOURCE_STALE")
            materiality = rules.freshness.materiality
            commands.update(rules.freshness.blocked_commands)
        if snapshot is not None:
            if not snapshot.loans and not mirrors:
                status = "STALE"
                reasons.append("RECON_EXTERNAL_RECORD_MISSING")
                materiality = max(
                    materiality, rules.missing_record_materiality, key=MATERIALITY_RANK.__getitem__
                )
                commands.update(rules.missing_record_blocked_commands)
            elif key in duplicates or left is None or right is None:
                if status != "STALE":
                    status = "MISMATCH"
                reasons.append(
                    "RECON_DUPLICATE_EXTERNAL_RECORD"
                    if key in duplicates
                    else "RECON_INTERNAL_RECORD_MISSING"
                    if left is None
                    else "RECON_EXTERNAL_RECORD_MISSING"
                )
                materiality = max(
                    materiality, rules.missing_record_materiality, key=MATERIALITY_RANK.__getitem__
                )
                commands.update(rules.missing_record_blocked_commands)
            else:
                outcome = compare_fields(left, right, rules)
                differences.extend(outcome.differences)
                reasons.extend(outcome.reasons)
                commands.update(outcome.blocked_commands)
                materiality = max(
                    materiality, outcome.materiality, key=MATERIALITY_RANK.__getitem__
                )
                if status != "STALE":
                    status = outcome.status
            if (
                mirror
                and mirror.last_provider_event_at
                and mirror.last_provider_event_at > snapshot.snapshot_at
            ):
                if status != "STALE":
                    status = "MISMATCH"
                reasons.append("RECON_CUTOFF_MISMATCH")
                materiality = max(
                    materiality, rules.cutoff_mismatch_materiality, key=MATERIALITY_RANK.__getitem__
                )
                commands.update(rules.cutoff_mismatch_blocked_commands)
            if mirror and mirror.guarantee_case_id is not None and right is not None:
                guarantee = guarantee_by_id.get(mirror.guarantee_case_id)
                if guarantee is None or guarantee.issued_guarantee_amount is None:
                    if status != "STALE":
                        status = "MISMATCH"
                    reasons.append("RECON_GUARANTEE_PRINCIPAL_EVIDENCE_MISSING")
                    materiality = max(
                        materiality,
                        rules.missing_record_materiality,
                        key=MATERIALITY_RANK.__getitem__,
                    )
                    commands.update(rules.missing_record_blocked_commands)
                else:
                    if Decimal(right["original_principal"]) != guarantee.issued_guarantee_amount:
                        materiality = "CRITICAL"
                        if status != "STALE":
                            status = "MISMATCH"
                        reasons.append("RECON_GUARANTEE_LOAN_PRINCIPAL_MISMATCH")
                        commands.update(rules.principal_invariant_blocked_commands)
                        differences.append(
                            {
                                "field_code": "guarantee_loan_principal",
                                "internal": format(guarantee.issued_guarantee_amount, "f"),
                                "external": right["original_principal"],
                            }
                        )
        case = ReconciliationCase(
            id=uuid4(),
            run_id=run.id,
            internal_entity_type="ExternalLoanMirror" if mirror else "ExternalLoan",
            internal_entity_id=str(mirror.id) if mirror else key,
            external_reference=key,
            status=status,
            materiality=materiality,
            mismatch_reason_code=reasons[0] if reasons else None,
            compared_at=timestamp,
            version=1,
        )
        staged.append(case)
        staged.append(
            ReconciliationObservation(
                reconciliation_case_id=case.id,
                internal_value_reference=internal_hash,
                external_value_reference=external_ref,
                difference_payload={
                    "reasons": reasons,
                    "differences": differences,
                    "internal_fields": left,
                    "external_fields": right,
                },
                evidence_references=list(snapshot.evidence_references) if snapshot else [],
                observed_at=timestamp,
            )
        )
        for command in sorted(commands):
            block = ReconciliationBlock(
                reconciliation_case_id=case.id,
                blocked_command_type=command,
                resource_type=case.internal_entity_type,
                resource_id=case.internal_entity_id,
                active=True,
                activated_at=timestamp,
            )
            staged.append(block)
            _emit(
                session,
                run,
                "ReconciliationBlockActivated",
                {
                    "case_id": str(case.id),
                    "command_type": command,
                    "resource_id": case.internal_entity_id,
                },
                timestamp,
            )
        if status in {"MISMATCH", "STALE"}:
            _emit(
                session,
                run,
                "ReconciliationBecameStale"
                if status == "STALE"
                else "ReconciliationMismatchDetected",
                {
                    "case_id": str(case.id),
                    "status": status,
                    "materiality": materiality,
                    "reason_codes": reasons,
                },
                timestamp,
            )
        if materiality == "CRITICAL" and status != "MATCHED":
            critical_count += 1
        cases.append(case)
    run.counts = {
        state: sum(c.status == state for c in cases)
        for state in ["MATCHED", "MISMATCH", "STALE", "DISPUTED"]
    }
    run.counts["CRITICAL"] = critical_count
    _emit(session, run, "ReconciliationRunStarted", {"run_id": str(run.id)}, timestamp)
    _emit(
        session,
        run,
        "ReconciliationRunCompleted",
        {"run_id": str(run.id), "counts": run.counts, "status": run.status},
        timestamp,
    )
    append_audit(
        session,
        aggregate_type="ReconciliationRun",
        aggregate_id=str(run.id),
        aggregate_version=1,
        action="RECONCILIATION_COMPLETED",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=run.id,
        outcome="SUCCESS",
        policy_pack_id=run.policy_pack_id,
        evidence_reference=external_ref,
        new_state={
            "counts": run.counts,
            "policy_version_id": str(policy.id),
            "policy_payload_hash": policy.payload_hash,
        },
        scope=required_scope,
    )
    await session.flush()
    session.add_all(cases)
    await session.flush()
    session.add_all(staged)
    await session.flush()
    return run


def _emit(
    session: AsyncSession,
    run: ReconciliationRun,
    event_type: str,
    payload: dict[str, Any],
    now: datetime,
) -> None:
    session.add(
        OutboxMessage(
            event_type=event_type,
            event_version=1,
            aggregate_type="ReconciliationRun",
            aggregate_id=str(run.id),
            aggregate_version=1,
            payload={
                **payload,
                "policy_pack_id": str(run.policy_pack_id),
                "reconciliation_policy_version_id": str(run.reconciliation_policy_version_id),
                "provider_id": str(run.provider_id),
            },
            correlation_id=run.correlation_id,
            causation_id=run.id,
            occurred_at=now,
        )
    )
