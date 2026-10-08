from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.approval import approval_payload_hash
from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.database import Database
from badban.infrastructure.persistence.models import (
    ApprovalRequest,
    OutboxMessage,
    PolicyVersion,
    ReconciliationBlock,
    ReconciliationCase,
    ReconciliationResolutionProposal,
    ReconciliationRun,
)
from badban.security.audit import append_audit

RESOLUTION_TYPES = frozenset(
    {
        "INTERNAL_CORRECTION",
        "EXTERNAL_CORRECTION",
        "LATE_EVENT_APPLIED",
        "MAPPING_CORRECTION",
        "ACCEPTED_DIFFERENCE",
        "DISPUTE_OUTCOME",
    }
)
_IMMEDIATE_RESOLUTION_TYPES = frozenset({"ACCEPTED_DIFFERENCE", "DISPUTE_OUTCOME"})
_ALLOWED_CHECKER_ROLES = frozenset(
    {"RISK", "FINANCE_RECONCILIATION", "LEGAL_COMPLIANCE", "GOVERNANCE_APPROVER"}
)
_UNRESOLVED_CASE_STATUSES = frozenset({"MISMATCH", "STALE", "DISPUTED"})
_RESOURCE_SOURCES = frozenset({"RECONCILIATION_CASE", "INTERNAL_ENTITY", "EXTERNAL_PROVIDER"})


class ReconciliationResolutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class BlockingRule:
    reason_code: str
    materiality: str
    blocked_command_type: str
    resource_source: str
    resource_type: str


@dataclass(frozen=True, slots=True)
class ResolutionGovernance:
    approval_required: bool
    checker_role: str | None


@dataclass(frozen=True, slots=True)
class RecheckResult:
    run_id: UUID
    resolved: bool


def resolution_payload(
    *,
    case_id: UUID,
    expected_case_version: int,
    resolution_type: str,
    reason: str,
    evidence_references: list[str],
    correction_command_references: list[str],
) -> dict[str, Any]:
    return {
        "case_id": str(case_id),
        "expected_case_version": expected_case_version,
        "resolution_type": resolution_type,
        "reason": reason,
        "evidence_references": evidence_references,
        "correction_command_references": correction_command_references,
    }


async def _policy_for_case(
    session: AsyncSession,
    case: ReconciliationCase,
) -> PolicyVersion:
    policy = await session.get(PolicyVersion, case.rule_policy_version_id)
    if (
        policy is None
        or policy.policy_type != "RECONCILIATION_POLICY"
        or policy.version_number != case.rule_policy_version_number
    ):
        raise ReconciliationResolutionError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation case policy lineage is unavailable or inconsistent",
        )
    if policy.payload_hash is None or canonical_request_hash(policy.payload) != policy.payload_hash:
        raise ReconciliationResolutionError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation Policy payload attestation failed",
        )
    return policy


def _type_rules(policy: PolicyVersion, reconciliation_type: str) -> dict[str, Any]:
    root = policy.payload.get("reconciliation_rules")
    if not isinstance(root, dict):
        raise ReconciliationResolutionError(
            "RECONCILIATION_POLICY_INVALID",
            "Reconciliation Policy must define reconciliation_rules",
        )
    rules = root.get(reconciliation_type)
    if not isinstance(rules, dict):
        raise ReconciliationResolutionError(
            "RECONCILIATION_POLICY_MISSING",
            f"Reconciliation Policy has no rules for {reconciliation_type}",
        )
    return rules


def _blocking_rules(policy: PolicyVersion, case: ReconciliationCase) -> list[BlockingRule]:
    raw_rules = _type_rules(policy, case.reconciliation_type).get("blocking_rules")
    if raw_rules is None:
        return []
    if not isinstance(raw_rules, list):
        raise ReconciliationResolutionError(
            "RECONCILIATION_POLICY_INVALID",
            "blocking_rules must be an explicit list when supplied",
        )
    parsed: list[BlockingRule] = []
    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise ReconciliationResolutionError(
                "RECONCILIATION_POLICY_INVALID",
                "Each blocking rule must be an object",
            )
        reason = raw.get("reason_code")
        materiality = raw.get("materiality")
        command = raw.get("blocked_command_type")
        resource_source = raw.get("resource_source")
        resource_type = raw.get("resource_type")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                reason,
                materiality,
                command,
                resource_source,
                resource_type,
            )
        ):
            raise ReconciliationResolutionError(
                "RECONCILIATION_POLICY_INVALID",
                "Blocking rules require nonblank reason/materiality/command/resource fields",
            )
        if materiality not in {"INFO", "WARNING", "MATERIAL", "CRITICAL"}:
            raise ReconciliationResolutionError(
                "RECONCILIATION_POLICY_INVALID",
                "Blocking rule materiality is invalid",
            )
        if resource_source not in _RESOURCE_SOURCES:
            raise ReconciliationResolutionError(
                "RECONCILIATION_POLICY_INVALID",
                "Blocking rule resource_source is invalid",
            )
        parsed.append(
            BlockingRule(
                reason_code=reason,
                materiality=materiality,
                blocked_command_type=command,
                resource_source=resource_source,
                resource_type=resource_type,
            )
        )
    return parsed


def _resolution_governance(
    policy: PolicyVersion,
    case: ReconciliationCase,
) -> ResolutionGovernance:
    raw = _type_rules(policy, case.reconciliation_type).get("resolution_governance")
    if not isinstance(raw, dict):
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_POLICY_MISSING",
            "Resolution governance must be explicitly configured",
        )
    approval_map = raw.get("approval_required_by_materiality")
    if not isinstance(approval_map, dict) or case.materiality not in approval_map:
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_POLICY_MISSING",
            "Resolution approval requirement is missing for case materiality",
        )
    required = approval_map[case.materiality]
    if not isinstance(required, bool):
        raise ReconciliationResolutionError(
            "RECONCILIATION_POLICY_INVALID",
            "Resolution approval requirement must be boolean",
        )
    if not required:
        return ResolutionGovernance(approval_required=False, checker_role=None)

    checker_map = raw.get("checker_role_by_materiality")
    checker = checker_map.get(case.materiality) if isinstance(checker_map, dict) else None
    if not isinstance(checker, str) or checker not in _ALLOWED_CHECKER_ROLES:
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_POLICY_MISSING",
            "A valid checker role must be explicit when resolution approval is required",
        )
    return ResolutionGovernance(approval_required=True, checker_role=checker)


def _resource_for_rule(
    case: ReconciliationCase,
    rule: BlockingRule,
) -> tuple[str, str]:
    if rule.resource_source == "RECONCILIATION_CASE":
        if rule.resource_type != "ReconciliationCase":
            raise ReconciliationResolutionError(
                "RECONCILIATION_POLICY_INVALID",
                "RECONCILIATION_CASE resource source requires resource_type ReconciliationCase",
            )
        return rule.resource_type, str(case.id)

    if rule.resource_source == "INTERNAL_ENTITY":
        if case.internal_entity_id is None or rule.resource_type != case.internal_entity_type:
            raise ReconciliationResolutionError(
                "RECONCILIATION_POLICY_INVALID",
                "INTERNAL_ENTITY blocking rule does not match case internal entity",
            )
        return rule.resource_type, case.internal_entity_id

    if case.external_provider_id is None or rule.resource_type != "CreditProvider":
        raise ReconciliationResolutionError(
            "RECONCILIATION_POLICY_INVALID",
            "EXTERNAL_PROVIDER blocking rule requires a provider-scoped case",
        )
    return rule.resource_type, str(case.external_provider_id)


def _event(
    *,
    event_type: str,
    case: ReconciliationCase,
    payload: dict[str, Any],
    correlation_id: UUID | None,
) -> OutboxMessage:
    return OutboxMessage(
        event_type=event_type,
        event_version=1,
        aggregate_type="ReconciliationCase",
        aggregate_id=str(case.id),
        aggregate_version=case.version,
        payload=payload,
        correlation_id=correlation_id,
        causation_id=None,
        occurred_at=datetime.now(UTC),
    )


async def sync_case_blocks_from_policy(
    session: AsyncSession,
    *,
    case: ReconciliationCase,
    policy: PolicyVersion | None = None,
    correlation_id: UUID | None = None,
) -> list[ReconciliationBlock]:
    resolved_policy = policy or await _policy_for_case(session, case)
    now = datetime.now(UTC)

    if case.status not in _UNRESOLVED_CASE_STATUSES:
        active = (
            await session.scalars(
                select(ReconciliationBlock)
                .where(
                    ReconciliationBlock.reconciliation_case_id == case.id,
                    ReconciliationBlock.active.is_(True),
                )
                .with_for_update()
            )
        ).all()
        for block in active:
            block.active = False
            block.cleared_at = now
            session.add(
                _event(
                    event_type="ReconciliationBlockCleared",
                    case=case,
                    payload={
                        "case_id": str(case.id),
                        "block_id": str(block.id),
                        "blocked_command_type": block.blocked_command_type,
                        "resource_type": block.resource_type,
                        "resource_id": block.resource_id,
                    },
                    correlation_id=correlation_id,
                )
            )
        return active

    if case.mismatch_reason_code is None:
        return []

    matched_rules = [
        rule
        for rule in _blocking_rules(resolved_policy, case)
        if rule.reason_code == case.mismatch_reason_code and rule.materiality == case.materiality
    ]
    activated: list[ReconciliationBlock] = []
    for rule in matched_rules:
        resource_type, resource_id = _resource_for_rule(case, rule)
        block = await session.scalar(
            select(ReconciliationBlock)
            .where(
                ReconciliationBlock.reconciliation_case_id == case.id,
                ReconciliationBlock.blocked_command_type == rule.blocked_command_type,
                ReconciliationBlock.resource_type == resource_type,
                ReconciliationBlock.resource_id == resource_id,
            )
            .with_for_update()
        )
        if block is None:
            block = ReconciliationBlock(
                reconciliation_case_id=case.id,
                blocked_command_type=rule.blocked_command_type,
                resource_type=resource_type,
                resource_id=resource_id,
                active=True,
                policy_version_id=resolved_policy.id,
                policy_version_number=resolved_policy.version_number,
                activated_at=now,
                cleared_at=None,
            )
            session.add(block)
            await session.flush()
            session.add(
                _event(
                    event_type="ReconciliationBlockActivated",
                    case=case,
                    payload={
                        "case_id": str(case.id),
                        "block_id": str(block.id),
                        "blocked_command_type": block.blocked_command_type,
                        "resource_type": block.resource_type,
                        "resource_id": block.resource_id,
                    },
                    correlation_id=correlation_id,
                )
            )
        elif not block.active:
            block.active = True
            block.activated_at = now
            block.cleared_at = None
            session.add(
                _event(
                    event_type="ReconciliationBlockActivated",
                    case=case,
                    payload={
                        "case_id": str(case.id),
                        "block_id": str(block.id),
                        "blocked_command_type": block.blocked_command_type,
                        "resource_type": block.resource_type,
                        "resource_id": block.resource_id,
                    },
                    correlation_id=correlation_id,
                )
            )
        activated.append(block)
    return activated


async def assert_reconciliation_command_allowed(
    session: AsyncSession,
    *,
    case_id: UUID,
    blocked_command_type: str,
    resource_type: str,
    resource_id: str,
    require_mapping: bool,
) -> None:
    case = await session.get(ReconciliationCase, case_id)
    if case is None:
        raise ReconciliationResolutionError(
            "RECONCILIATION_CASE_NOT_FOUND",
            "Reconciliation case was not found",
        )
    if case.status not in _UNRESOLVED_CASE_STATUSES:
        return

    policy = await _policy_for_case(session, case)
    matching = []
    for rule in _blocking_rules(policy, case):
        if (
            rule.reason_code == case.mismatch_reason_code
            and rule.materiality == case.materiality
            and rule.blocked_command_type == blocked_command_type
        ):
            derived_type, derived_id = _resource_for_rule(case, rule)
            if derived_type == resource_type and derived_id == resource_id:
                matching.append(rule)

    if not matching:
        if require_mapping:
            raise ReconciliationResolutionError(
                "RECONCILIATION_BLOCKING_RULE_MISSING",
                "Required reconciliation blocking rule is not explicitly configured",
            )
        return

    if case.status == "STALE":
        raise ReconciliationResolutionError(
            "EXTERNAL_STATE_STALE",
            "Authoritative external state is stale",
        )
    raise ReconciliationResolutionError(
        "RECONCILIATION_BLOCK",
        "Unresolved reconciliation case blocks this command",
    )


async def propose_resolution(
    session: AsyncSession,
    *,
    case_id: UUID,
    resolution_type: str,
    reason: str,
    evidence_references: list[str],
    correction_command_references: list[str],
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> ReconciliationResolutionProposal:
    case = await session.scalar(
        select(ReconciliationCase).where(ReconciliationCase.id == case_id).with_for_update()
    )
    if case is None:
        raise ReconciliationResolutionError(
            "RECONCILIATION_CASE_NOT_FOUND",
            "Reconciliation case was not found",
        )
    if case.status not in _UNRESOLVED_CASE_STATUSES:
        raise ReconciliationResolutionError(
            "RECONCILIATION_CASE_STATE_CONFLICT",
            "Only unresolved mismatch/stale/disputed cases may be resolved",
        )
    if resolution_type not in RESOLUTION_TYPES:
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_TYPE_INVALID",
            "Resolution type is not authorized",
        )
    if (
        not reason.strip()
        or not evidence_references
        or any(not item.strip() for item in evidence_references)
    ):
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_EVIDENCE_REQUIRED",
            "Resolution requires a nonblank reason and evidence references",
        )
    if any(not item.strip() for item in correction_command_references):
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_REFERENCE_INVALID",
            "Correction command references must not contain blank values",
        )

    policy = await _policy_for_case(session, case)
    governance = _resolution_governance(policy, case)
    payload = resolution_payload(
        case_id=case.id,
        expected_case_version=case.version,
        resolution_type=resolution_type,
        reason=reason.strip(),
        evidence_references=evidence_references,
        correction_command_references=correction_command_references,
    )
    payload_hash = approval_payload_hash(payload)
    existing = await session.scalar(
        select(ReconciliationResolutionProposal)
        .where(
            ReconciliationResolutionProposal.reconciliation_case_id == case.id,
            ReconciliationResolutionProposal.status.in_(("PROPOSED", "APPROVED")),
        )
        .order_by(ReconciliationResolutionProposal.created_at.desc())
        .with_for_update()
    )
    if existing is not None:
        if existing.payload_hash == payload_hash:
            return existing
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_ALREADY_PENDING",
            "A different resolution proposal is already pending for this case",
        )

    approval: ApprovalRequest | None = None
    if governance.approval_required:
        if governance.checker_role is None:
            raise ReconciliationResolutionError(
                "RECONCILIATION_RESOLUTION_POLICY_MISSING",
                "Checker role is required for governed resolution approval",
            )
        scope_type = "PROVIDER" if case.external_provider_id is not None else "GLOBAL"
        approval = ApprovalRequest(
            action_type="RECONCILIATION_RESOLUTION",
            target_type="ReconciliationCase",
            target_id=str(case.id),
            target_aggregate_version=case.version,
            maker_identity_id=actor_id,
            required_checker_role=governance.checker_role,
            scope_type=scope_type,
            scope_id=case.external_provider_id,
            payload_hash=payload_hash,
            reason=reason.strip(),
            evidence_refs=evidence_references,
            status="PENDING",
            expires_at=None,
            version=1,
        )
        session.add(approval)
        await session.flush()

    proposal = ReconciliationResolutionProposal(
        reconciliation_case_id=case.id,
        expected_case_version=case.version,
        resolution_type=resolution_type,
        reason=reason.strip(),
        evidence_references=evidence_references,
        correction_command_references=correction_command_references,
        payload_hash=payload_hash,
        approval_request_id=approval.id if approval is not None else None,
        status="PROPOSED",
        proposed_by=actor_id,
        approved_by=None,
        approved_at=None,
        version=1,
    )
    session.add(proposal)
    await session.flush()
    append_audit(
        session,
        aggregate_type="ReconciliationCase",
        aggregate_id=str(case.id),
        aggregate_version=case.version,
        action="RECONCILIATION_RESOLUTION_PROPOSE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        reason_code=resolution_type,
        evidence_reference=evidence_references[0],
        new_state={
            "proposal_id": str(proposal.id),
            "resolution_type": resolution_type,
            "approval_required": governance.approval_required,
        },
    )
    session.add(
        _event(
            event_type="ReconciliationResolutionProposed",
            case=case,
            payload={
                "case_id": str(case.id),
                "proposal_id": str(proposal.id),
                "resolution_type": resolution_type,
                "approval_request_id": str(approval.id) if approval is not None else None,
            },
            correlation_id=correlation_id,
        )
    )
    return proposal


async def approve_resolution(
    session: AsyncSession,
    *,
    case_id: UUID,
    proposal_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> ReconciliationResolutionProposal:
    proposal = await session.scalar(
        select(ReconciliationResolutionProposal)
        .where(
            ReconciliationResolutionProposal.id == proposal_id,
            ReconciliationResolutionProposal.reconciliation_case_id == case_id,
        )
        .with_for_update()
    )
    if proposal is None:
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_NOT_FOUND",
            "Resolution proposal was not found",
        )
    case = await session.scalar(
        select(ReconciliationCase).where(ReconciliationCase.id == case_id).with_for_update()
    )
    if case is None:
        raise ReconciliationResolutionError(
            "RECONCILIATION_CASE_NOT_FOUND",
            "Reconciliation case was not found",
        )
    if proposal.status == "APPLIED":
        return proposal
    if proposal.status not in {"PROPOSED", "APPROVED"}:
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_STATE_CONFLICT",
            "Resolution proposal cannot be approved from its current state",
        )
    if case.version != proposal.expected_case_version:
        raise ReconciliationResolutionError(
            "RECONCILIATION_CASE_VERSION_CONFLICT",
            "Reconciliation case changed after resolution proposal",
        )

    policy = await _policy_for_case(session, case)
    governance = _resolution_governance(policy, case)
    payload = resolution_payload(
        case_id=case.id,
        expected_case_version=proposal.expected_case_version,
        resolution_type=proposal.resolution_type,
        reason=proposal.reason,
        evidence_references=proposal.evidence_references,
        correction_command_references=proposal.correction_command_references,
    )
    if approval_payload_hash(payload) != proposal.payload_hash:
        raise ReconciliationResolutionError(
            "RECONCILIATION_RESOLUTION_PAYLOAD_CHANGED",
            "Resolution proposal payload attestation failed",
        )

    if governance.approval_required:
        if proposal.approval_request_id is None:
            raise ReconciliationResolutionError(
                "RECONCILIATION_RESOLUTION_APPROVAL_REQUIRED",
                "Resolution proposal is missing required approval",
            )
        approval = await session.scalar(
            select(ApprovalRequest)
            .where(ApprovalRequest.id == proposal.approval_request_id)
            .with_for_update()
        )
        if approval is None:
            raise ReconciliationResolutionError(
                "RECONCILIATION_RESOLUTION_APPROVAL_REQUIRED",
                "Resolution approval request was not found",
            )
        if actor_id == approval.maker_identity_id:
            raise ReconciliationResolutionError(
                "APPROVAL_SELF_APPROVAL_FORBIDDEN",
                "Resolution proposer cannot approve their own proposal",
            )
        if approval.payload_hash != proposal.payload_hash:
            raise ReconciliationResolutionError(
                "APPROVAL_PAYLOAD_CHANGED",
                "Resolution approval payload does not match proposal",
            )
        if approval.target_aggregate_version != case.version:
            raise ReconciliationResolutionError(
                "APPROVAL_TARGET_VERSION_CONFLICT",
                "Reconciliation case version changed after approval request",
            )
        if approval.status == "PENDING":
            approval.checker_identity_id = actor_id
            approval.status = "APPROVED"
            approval.approved_at = datetime.now(UTC)
            approval.version += 1
        elif approval.status == "APPROVED":
            if approval.checker_identity_id != actor_id:
                raise ReconciliationResolutionError(
                    "APPROVAL_CHECKER_CONFLICT",
                    "Resolution was approved by a different checker",
                )
        else:
            raise ReconciliationResolutionError(
                "APPROVAL_NOT_APPROVED",
                "Resolution approval request is not approvable",
            )

    now = datetime.now(UTC)
    proposal.approved_by = actor_id
    proposal.approved_at = now
    proposal.version += 1
    case.resolution_type = proposal.resolution_type
    case.resolution_reference = f"ReconciliationResolutionProposal:{proposal.id}"

    resolved_immediately = proposal.resolution_type in _IMMEDIATE_RESOLUTION_TYPES
    if resolved_immediately:
        proposal.status = "APPLIED"
        case.status = "RESOLVED"
        case.resolved_at = now
        case.version += 1
        await sync_case_blocks_from_policy(
            session,
            case=case,
            policy=policy,
            correlation_id=correlation_id,
        )
    else:
        proposal.status = "APPROVED"
        if case.status != "DISPUTED":
            case.status = "DISPUTED"
            case.version += 1

    append_audit(
        session,
        aggregate_type="ReconciliationCase",
        aggregate_id=str(case.id),
        aggregate_version=case.version,
        action="RECONCILIATION_RESOLUTION_APPROVE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        reason_code=proposal.resolution_type,
        evidence_reference=proposal.evidence_references[0],
        new_state={
            "proposal_id": str(proposal.id),
            "proposal_status": proposal.status,
            "case_status": case.status,
        },
    )
    if resolved_immediately:
        session.add(
            _event(
                event_type="ReconciliationResolved",
                case=case,
                payload={
                    "case_id": str(case.id),
                    "proposal_id": str(proposal.id),
                    "resolution_type": proposal.resolution_type,
                    "case_status": case.status,
                },
                correlation_id=correlation_id,
            )
        )
    return proposal


async def recheck_lender_resolution(
    database: Database,
    lender_adapter_registry: Any,
    *,
    case_id: UUID,
    scope_reference: str | None,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> RecheckResult:
    async with database.session_factory() as session:
        case = await session.get(ReconciliationCase, case_id)
        if case is None:
            raise ReconciliationResolutionError(
                "RECONCILIATION_CASE_NOT_FOUND",
                "Reconciliation case was not found",
            )
        if case.reconciliation_type != "LENDER_EXTERNAL_LOAN":
            raise ReconciliationResolutionError(
                "RECONCILIATION_RECHECK_NOT_SUPPORTED",
                "Sprint 16 recheck supports the lender reconciliation vertical slice only",
            )
        if case.status == "RESOLVED":
            return RecheckResult(run_id=case.run_id, resolved=True)
        proposal = await session.scalar(
            select(ReconciliationResolutionProposal)
            .where(
                ReconciliationResolutionProposal.reconciliation_case_id == case.id,
                ReconciliationResolutionProposal.status == "APPROVED",
            )
            .order_by(ReconciliationResolutionProposal.created_at.desc())
        )
        if proposal is None:
            raise ReconciliationResolutionError(
                "RECONCILIATION_RESOLUTION_NOT_APPROVED",
                "Correction-based resolution requires an approved proposal before recheck",
            )
        run = await session.get(ReconciliationRun, case.run_id)
        if run is None or run.provider_id is None:
            raise ReconciliationResolutionError(
                "RECONCILIATION_RECHECK_CONTEXT_MISSING",
                "Reconciliation run context is unavailable",
            )
        provider_id = run.provider_id
        scope_definition = run.scope_definition
        internal_entity_id = case.internal_entity_id
        external_reference = case.external_reference
        proposal_id = proposal.id

    from badban.application.reconciliation import execute_lender_reconciliation

    run_id = await execute_lender_reconciliation(
        database,
        lender_adapter_registry,
        provider_id=provider_id,
        scope_definition=scope_definition,
        scope_reference=scope_reference,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    async with database.session_factory() as session:
        async with session.begin():
            case = await session.scalar(
                select(ReconciliationCase).where(ReconciliationCase.id == case_id).with_for_update()
            )
            proposal = await session.scalar(
                select(ReconciliationResolutionProposal)
                .where(ReconciliationResolutionProposal.id == proposal_id)
                .with_for_update()
            )
            if case is None or proposal is None:
                raise ReconciliationResolutionError(
                    "RECONCILIATION_RECHECK_CONTEXT_MISSING",
                    "Resolution context disappeared during recheck",
                )
            if case.status == "RESOLVED":
                return RecheckResult(run_id=run_id, resolved=True)
            predicates = [
                ReconciliationCase.run_id == run_id,
                ReconciliationCase.status == "MATCHED",
                ReconciliationCase.reconciliation_type == case.reconciliation_type,
            ]
            if internal_entity_id is not None:
                predicates.append(ReconciliationCase.internal_entity_id == internal_entity_id)
            elif external_reference is not None:
                predicates.append(ReconciliationCase.external_reference == external_reference)
            else:
                raise ReconciliationResolutionError(
                    "RECONCILIATION_RECHECK_CONTEXT_MISSING",
                    "Case has no stable matching identifier for recheck",
                )
            matched = await session.scalar(select(ReconciliationCase).where(*predicates))
            if matched is None:
                return RecheckResult(run_id=run_id, resolved=False)

            now = datetime.now(UTC)
            case.status = "RESOLVED"
            case.resolved_at = now
            case.resolution_type = proposal.resolution_type
            case.resolution_reference = f"ReconciliationResolutionProposal:{proposal.id}"
            case.last_observed_at = now
            case.version += 1
            proposal.status = "APPLIED"
            proposal.version += 1
            policy = await _policy_for_case(session, case)
            await sync_case_blocks_from_policy(
                session,
                case=case,
                policy=policy,
                correlation_id=correlation_id,
            )
            append_audit(
                session,
                aggregate_type="ReconciliationCase",
                aggregate_id=str(case.id),
                aggregate_version=case.version,
                action="RECONCILIATION_RESOLUTION_RECHECK",
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                outcome="SUCCESS",
                reason_code=proposal.resolution_type,
                evidence_reference=proposal.evidence_references[0],
                new_state={
                    "proposal_id": str(proposal.id),
                    "recheck_run_id": str(run_id),
                    "case_status": "RESOLVED",
                },
            )
            session.add(
                _event(
                    event_type="ReconciliationResolved",
                    case=case,
                    payload={
                        "case_id": str(case.id),
                        "proposal_id": str(proposal.id),
                        "recheck_run_id": str(run_id),
                        "resolution_type": proposal.resolution_type,
                    },
                    correlation_id=correlation_id,
                )
            )
    return RecheckResult(run_id=run_id, resolved=True)
