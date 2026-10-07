from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.reconciliation import (
    ALGORITHM_CODE,
    ALGORITHM_VERSION,
    MATERIALITY_RANK,
    _emit,
    _is_fresh,
    compare_fields,
)
from badban.application.reconciliation_internal import build_internal_snapshot
from badban.application.reconciliation_policy import (
    resolve_provider_pack,
    resolve_reconciliation_policy,
)
from badban.application.reconciliation_scope import resolve_source_context
from badban.application.reconciliation_sources import (
    SNAPSHOT_ADAPTER,
    CanonicalSnapshot,
    LedgerSnapshot,
    ReconciliationSourceRegistry,
    ReconciliationSourceUnavailable,
    SourceTarget,
    canonical_fields,
    stable_key,
)
from badban.infrastructure.persistence.models import (
    ReconciliationBlock,
    ReconciliationCase,
    ReconciliationObservation,
    ReconciliationRun,
)
from badban.security.audit import append_audit


async def run_source_reconciliation(
    session: AsyncSession,
    *,
    target: SourceTarget,
    registry: ReconciliationSourceRegistry,
    actor_id: UUID,
    actor_type: str,
    correlation_id: UUID,
    now: datetime | None = None,
) -> ReconciliationRun:
    timestamp = now or datetime.now(UTC)
    started_at = timestamp
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"reconciliation:{target.reconciliation_type}:{target.identity}"},
    )
    if target.reconciliation_type == "LENDER":
        pack, lender_scope = await resolve_provider_pack(
            session, provider_id=target.identity, effective_at=timestamp
        )
        pack_scope = {key: str(value) for key, value in lender_scope.items()}
        legal_id = None
    else:
        pack, pack_scope, legal_id = await resolve_source_context(session, target, at=timestamp)
    scope = {**pack_scope, "reconciliation_type": target.reconciliation_type}
    policy, rules = await resolve_reconciliation_policy(
        session, pack=pack, required_scope=dict(scope)
    )
    internal = await build_internal_snapshot(session, target, legal_entity_id=legal_id)
    snapshot: CanonicalSnapshot | None = None
    outage: str | None = None
    versions: dict[str, str] = {}
    try:
        port = registry.resolve(target)
        capability = port.capability()
        if (
            capability.source_id != target.identity
            or capability.reconciliation_type != target.reconciliation_type
        ):
            raise ApiError(
                409, "RECON_MAPPING_MISMATCH", "Registered source capability disagrees with target"
            )
        versions = {
            "contract_version": capability.contract_version,
            "mapping_version": capability.mapping_version,
            "schema_version": capability.schema_version,
        }
        if capability.normalization_version is not None:
            versions["normalization_version"] = capability.normalization_version
        raw = await port.fetch_reconciliation_snapshot(target, scope)
        if set(vars(raw)) - set(type(raw).model_fields):
            raise ApiError(409, "RECON_MAPPING_MISMATCH", "Unexpected canonical snapshot fields")
        if any(set(vars(record)) - set(type(record).model_fields) for record in raw.records):
            raise ApiError(409, "RECON_MAPPING_MISMATCH", "Unexpected canonical record fields")
        snapshot = SNAPSHOT_ADAPTER.validate_python(raw.model_dump(mode="json"))
        if (
            snapshot.reconciliation_type != target.reconciliation_type
            or snapshot.source_id != target.identity
            or snapshot.scope_definition != scope
            or snapshot.contract_version != capability.contract_version
            or snapshot.mapping_version != capability.mapping_version
            or snapshot.schema_version != capability.schema_version
            or snapshot.normalization_version != capability.normalization_version
        ):
            raise ApiError(
                409,
                "RECON_MAPPING_MISMATCH",
                "Canonical source identity/type/scope/version mismatch",
            )
        if any(record.observed_at > snapshot.snapshot_at for record in snapshot.records):
            raise ApiError(
                409, "RECON_MAPPING_MISMATCH", "Record observation exceeds source cutoff"
            )
        if isinstance(snapshot, LedgerSnapshot) and any(
            record.program_id != target.identity for record in snapshot.records
        ):
            raise ApiError(
                409, "RECON_MAPPING_MISMATCH", "Sub-ledger record belongs to another program"
            )
    except ReconciliationSourceUnavailable as exc:
        outage = exc.code
    except TimeoutError:
        outage = "SOURCE_TIMEOUT"
    except OSError:
        outage = "SOURCE_TRANSPORT_ERROR"
    except (ValidationError, AttributeError) as exc:
        raise ApiError(409, "RECON_MAPPING_MISMATCH", "Invalid strict canonical snapshot") from exc
    timestamp = now or datetime.now(UTC)
    content_hash = snapshot.content_hash if snapshot else canonical_request_hash(None)
    authority_identity = canonical_request_hash(
        {
            "target": target.model_dump(mode="json"),
            "scope": scope,
            "versions": versions,
            "reference": snapshot.source_reference if snapshot else None,
            "cutoff": snapshot.snapshot_at if snapshot else None,
        }
    )
    if snapshot:
        conflicting = await session.scalar(
            select(ReconciliationRun.id)
            .where(
                ReconciliationRun.source_metadata["authority_identity"].astext
                == authority_identity,
                ReconciliationRun.source_content_hash != content_hash,
            )
            .limit(1)
        )
        if conflicting:
            raise ApiError(
                409,
                "RECON_SNAPSHOT_CONFLICT",
                "Authoritative snapshot identity reused with changed content",
            )
    freshness = {
        "internal": {
            r.key: _is_fresh(r.observed_at, timestamp, rules.freshness.internal_max_age_seconds)
            for r in internal.records
        },
        "external": sorted(
            (
                stable_key(r),
                _is_fresh(r.observed_at, timestamp, rules.freshness.external_max_age_seconds),
            )
            for r in snapshot.records
        )
        if snapshot
        else [],
        "snapshot": _is_fresh(
            snapshot.snapshot_at if snapshot else None,
            timestamp,
            rules.freshness.external_max_age_seconds,
        ),
        "received": snapshot.received_at <= timestamp if snapshot else False,
    }
    identity = canonical_request_hash(
        {
            "authority": authority_identity,
            "algorithm": {"code": ALGORITHM_CODE, "version": ALGORITHM_VERSION},
            "rule_schema": policy.schema_version,
            "internal": internal.content_hash,
            "pack": pack.policy_pack_id,
            "policy": policy.id,
            "freshness": freshness,
            "outage_at": timestamp if outage else None,
        }
    )
    existing = await session.scalar(
        select(ReconciliationRun).where(ReconciliationRun.source_identity == identity)
    )
    if existing:
        return existing
    internal_by_key = {r.key: r for r in internal.records}
    external_by_key = {}
    duplicates: set[str] = set()
    if snapshot:
        for record in snapshot.records:
            key = stable_key(record)
            if key in external_by_key:
                duplicates.add(key)
            external_by_key[key] = record
    cutoffs = [r.observed_at for r in internal.records if r.observed_at is not None]
    run = ReconciliationRun(
        id=uuid4(),
        reconciliation_type=target.reconciliation_type,
        provider_id=target.provider_id,
        source_legal_entity_id=target.source_legal_entity_id,
        program_id=target.program_id,
        scope_definition=scope,
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
        internal_cutoff=max(cutoffs) if cutoffs else None,
        external_cutoff=snapshot.snapshot_at if snapshot else None,
        source_snapshot_ref=snapshot.source_reference if snapshot else None,
        source_metadata={
            "authority_identity": authority_identity,
            "internal_snapshot_hash": internal.content_hash,
            "external_snapshot": snapshot.model_dump(mode="json") if snapshot else None,
            "source_versions": versions,
            "outage_reason": outage,
            "internal_contract_gap": internal.gap,
            "acquired_at": timestamp.isoformat(),
        },
        counts={},
        status="SOURCE_UNAVAILABLE" if outage or not internal.available else "COMPLETED",
        started_at=started_at,
        finished_at=datetime.now(UTC) if now is None else timestamp,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
    cases = []
    children: list[Any] = []
    for key in sorted(set(internal_by_key) | set(external_by_key)) or ["SOURCE_SCOPE"]:
        left_record, right_record = internal_by_key.get(key), external_by_key.get(key)
        left = left_record.fields if left_record else None
        right = canonical_fields(right_record) if right_record else None
        status, materiality = "MATCHED", "INFO"
        reasons: list[str] = []
        differences: list[dict[str, Any]] = []
        commands: set[str] = set()
        stale = (
            snapshot is None
            or not internal.available
            or not freshness["snapshot"]
            or not freshness["received"]
            or (
                left_record is not None
                and not _is_fresh(
                    left_record.observed_at, timestamp, rules.freshness.internal_max_age_seconds
                )
            )
            or (
                right_record is not None
                and not _is_fresh(
                    right_record.observed_at, timestamp, rules.freshness.external_max_age_seconds
                )
            )
        )
        if stale:
            status = "STALE"
            reasons.append(internal.gap or "RECON_SOURCE_STALE")
            materiality = rules.freshness.materiality
            commands.update(rules.freshness.blocked_commands)
        if left is None or right is None or key in duplicates:
            if not stale:
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
            materiality = max(materiality, outcome.materiality, key=MATERIALITY_RANK.__getitem__)
            if not stale:
                status = outcome.status
        if (
            left_record
            and snapshot
            and left_record.observed_at
            and left_record.observed_at > snapshot.snapshot_at
        ):
            if not stale:
                status = "MISMATCH"
            reasons.append("RECON_CUTOFF_MISMATCH")
            materiality = max(
                materiality, rules.cutoff_mismatch_materiality, key=MATERIALITY_RANK.__getitem__
            )
            commands.update(rules.cutoff_mismatch_blocked_commands)
        if (
            target.reconciliation_type == "LENDER"
            and left_record
            and left_record.invariant_facts is not None
            and right
        ):
            amount = left_record.invariant_facts.get("amount")
            if amount is None:
                if not stale:
                    status = "MISMATCH"
                reasons.append("RECON_GUARANTEE_PRINCIPAL_EVIDENCE_MISSING")
                materiality = max(
                    materiality, rules.missing_record_materiality, key=MATERIALITY_RANK.__getitem__
                )
                commands.update(rules.missing_record_blocked_commands)
            elif Decimal(str(amount)) != Decimal(right["original_principal"]):
                if not stale:
                    status = "MISMATCH"
                materiality = "CRITICAL"
                reasons.append("RECON_GUARANTEE_LOAN_PRINCIPAL_MISMATCH")
                commands.update(rules.principal_invariant_blocked_commands)
                differences.append(
                    {
                        "field_code": "guarantee_loan_principal",
                        "internal": str(amount),
                        "external": right["original_principal"],
                    }
                )
        if (
            target.reconciliation_type == "CUSTODY"
            and left_record is not None
            and snapshot is not None
            and right_record is None
            and rules.custody_missing_external_transient_lag is not True
        ):
            materiality = "CRITICAL"
            reasons.append("RECON_CUSTODY_POSITION_MISSING")
        if not internal_by_key and not external_by_key:
            status = "STALE"
            reasons.append("RECON_SOURCE_EVIDENCE_EMPTY")
            materiality = max(
                materiality, rules.missing_record_materiality, key=MATERIALITY_RANK.__getitem__
            )
        persisted_key = key if len(key) <= 255 else canonical_request_hash(key)
        case = ReconciliationCase(
            id=uuid4(),
            run_id=run.id,
            internal_entity_type=left_record.resource_type
            if left_record
            else target.reconciliation_type,
            internal_entity_id=left_record.resource_id if left_record else persisted_key,
            external_reference=persisted_key,
            status=status,
            materiality=materiality,
            mismatch_reason_code=reasons[0] if reasons else None,
            compared_at=timestamp,
            version=1,
        )
        cases.append(case)
        children.append(
            ReconciliationObservation(
                reconciliation_case_id=case.id,
                internal_value_reference=internal.content_hash,
                external_value_reference=run.source_snapshot_ref,
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
            children.append(
                ReconciliationBlock(
                    reconciliation_case_id=case.id,
                    blocked_command_type=command,
                    resource_type=case.internal_entity_type,
                    resource_id=case.internal_entity_id,
                    active=True,
                    activated_at=timestamp,
                )
            )
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
        if status in {"STALE", "MISMATCH"}:
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
    run.counts = {
        state: sum(c.status == state for c in cases)
        for state in ["MATCHED", "MISMATCH", "STALE", "DISPUTED"]
    }
    run.counts["CRITICAL"] = sum(
        c.materiality == "CRITICAL" and c.status != "MATCHED" for c in cases
    )
    session.add(run)
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
        policy_pack_id=pack.policy_pack_id,
        evidence_reference=run.source_snapshot_ref
        if run.source_snapshot_ref is None or len(run.source_snapshot_ref) <= 255
        else "sha256:" + canonical_request_hash(run.source_snapshot_ref),
        new_state={
            "counts": run.counts,
            "policy_version_id": str(policy.id),
            "policy_payload_hash": policy.payload_hash,
        },
        scope=scope,
    )
    await session.flush()
    session.add_all(cases)
    await session.flush()
    session.add_all(children)
    await session.flush()
    return run
