from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_resolution import ResolvedPolicyPack
from badban.infrastructure.persistence.models import (
    GuaranteeCase,
    OutboxMessage,
    PolicyVersion,
    PortfolioRiskSnapshot,
)
from badban.security.audit import append_audit

RISK_ALGORITHM_CODE = "PORTFOLIO_RISK"
RISK_ALGORITHM_VERSION = "PORTFOLIO_RISK_V1"
RISK_STATES = frozenset({"GREEN", "AMBER", "RED"})
_STATE_SEVERITY = {"GREEN": 0, "AMBER": 1, "RED": 2}


class RiskEvaluationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RiskPolicyRules:
    approved_portfolio_limit: Decimal
    committed_exposure_mode: str
    utilization_warning_ratio: Decimal
    utilization_stop_ratio: Decimal
    reserve_coverage_target_ratio: Decimal
    reserve_coverage_warning_ratio: Decimal
    reserve_coverage_hard_minimum_ratio: Decimal
    require_stress_result: bool


@dataclass(frozen=True, slots=True)
class RiskEvaluationInputs:
    total_active_exposure: Decimal
    total_reserved_exposure: Decimal
    reserve_requirement: Decimal
    reserve_available: Decimal
    reserve_metrics_reference: str
    concentration_state: str
    concentration_metrics_reference: str
    stress_state: str | None
    stress_result_reference: str | None
    authoritative_input_references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RiskEvaluationResult:
    risk_state: str
    committed_exposure: Decimal
    approved_portfolio_limit: Decimal
    utilization_ratio: Decimal
    reserve_coverage_ratio: Decimal | None
    gate_states: dict[str, str]


@dataclass(frozen=True, slots=True)
class ResolvedRiskPolicy:
    policy_pack_id: UUID
    policy_pack_version: int
    scope_definition: dict[str, Any]
    risk_policy_version_id: UUID
    risk_policy_code: str
    risk_policy_version_number: int
    rules: RiskPolicyRules


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _parse_decimal(value: object, *, field: str, positive: bool = False) -> Decimal:
    if not isinstance(value, str):
        raise RiskEvaluationError("RISK_POLICY_INVALID", f"{field} must be a decimal string")
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise RiskEvaluationError(\n            "RISK_POLICY_INVALID", f"{field} must be a decimal string"\n        ) from exc
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        qualifier = "positive" if positive else "non-negative"
        raise RiskEvaluationError("RISK_POLICY_INVALID", f"{field} must be finite and {qualifier}")
    return parsed


def _storage_decimal(value: Decimal, *, field: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise RiskEvaluationError(\n            "RISK_INPUT_INVALID", f"{field} must be a finite non-negative Decimal"\n        )
    sign, digits, exponent = value.as_tuple()
    del sign
    scale = max(0, -exponent)
    integer_digits = max(0, len(digits) - scale)
    if scale > 18 or integer_digits > 20:
        raise RiskEvaluationError(
            "RISK_INPUT_INVALID",
            f"{field} exceeds NUMERIC(38,18) storage precision",
        )
    return value


def parse_risk_policy_rules(payload: dict[str, Any]) -> RiskPolicyRules:
    required = {
        "approved_portfolio_limit",
        "committed_exposure_mode",
        "utilization_warning_ratio",
        "utilization_stop_ratio",
        "reserve_coverage_target_ratio",
        "reserve_coverage_warning_ratio",
        "reserve_coverage_hard_minimum_ratio",
        "require_stress_result",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise RiskEvaluationError(
            "RISK_POLICY_INVALID",
            f"Risk Appetite Policy is missing required fields: {','.join(missing)}",
        )

    approved_limit = _parse_decimal(
        payload["approved_portfolio_limit"],
        field="approved_portfolio_limit",
        positive=True,
    )
    warning = _parse_decimal(
        payload["utilization_warning_ratio"],
        field="utilization_warning_ratio",
    )
    stop = _parse_decimal(
        payload["utilization_stop_ratio"],
        field="utilization_stop_ratio",
    )
    reserve_target = _parse_decimal(
        payload["reserve_coverage_target_ratio"],
        field="reserve_coverage_target_ratio",
    )
    reserve_warning = _parse_decimal(
        payload["reserve_coverage_warning_ratio"],
        field="reserve_coverage_warning_ratio",
    )
    reserve_hard = _parse_decimal(
        payload["reserve_coverage_hard_minimum_ratio"],
        field="reserve_coverage_hard_minimum_ratio",
    )
    mode = payload["committed_exposure_mode"]
    if mode not in {"ACTIVE_ONLY", "ACTIVE_PLUS_RESERVED"}:
        raise RiskEvaluationError(
            "RISK_POLICY_INVALID",
            "committed_exposure_mode must be ACTIVE_ONLY or ACTIVE_PLUS_RESERVED",
        )
    if warning >= stop:
        raise RiskEvaluationError(
            "RISK_POLICY_INVALID",
            "utilization_warning_ratio must be lower than utilization_stop_ratio",
        )
    if not (reserve_hard <= reserve_warning <= reserve_target):
        raise RiskEvaluationError(
            "RISK_POLICY_INVALID",
            "reserve coverage thresholds must satisfy hard minimum <= warning <= target",
        )
    require_stress = payload["require_stress_result"]
    if not isinstance(require_stress, bool):
        raise RiskEvaluationError(
            "RISK_POLICY_INVALID",
            "require_stress_result must be boolean",
        )
    return RiskPolicyRules(
        approved_portfolio_limit=approved_limit,
        committed_exposure_mode=mode,
        utilization_warning_ratio=warning,
        utilization_stop_ratio=stop,
        reserve_coverage_target_ratio=reserve_target,
        reserve_coverage_warning_ratio=reserve_warning,
        reserve_coverage_hard_minimum_ratio=reserve_hard,
        require_stress_result=require_stress,
    )


def _require_gate_state(value: str, *, field: str) -> str:
    if value not in RISK_STATES:
        raise RiskEvaluationError("RISK_INPUT_INVALID", f"{field} must be GREEN, AMBER, or RED")
    return value


def calculate_portfolio_risk(
    *,
    rules: RiskPolicyRules,
    inputs: RiskEvaluationInputs,
) -> RiskEvaluationResult:
    active = _storage_decimal(inputs.total_active_exposure, field="total_active_exposure")
    reserved = _storage_decimal(inputs.total_reserved_exposure, field="total_reserved_exposure")
    reserve_requirement = _storage_decimal(inputs.reserve_requirement, field="reserve_requirement")
    reserve_available = _storage_decimal(inputs.reserve_available, field="reserve_available")
    _storage_decimal(rules.approved_portfolio_limit, field="approved_portfolio_limit")

    if not inputs.reserve_metrics_reference.strip():
        raise RiskEvaluationError("RISK_INPUT_INVALID", "reserve_metrics_reference is required")
    if not inputs.concentration_metrics_reference.strip():
        raise RiskEvaluationError(
            "RISK_INPUT_INVALID",
            "concentration_metrics_reference is required",
        )
    concentration_state = _require_gate_state(
        inputs.concentration_state,
        field="concentration_state",
    )
    if (inputs.stress_state is None) != (inputs.stress_result_reference is None):
        raise RiskEvaluationError(
            "RISK_INPUT_INVALID",
            "stress_state and stress_result_reference must be supplied together",
        )
    if rules.require_stress_result and inputs.stress_state is None:
        raise RiskEvaluationError(
            "RISK_INPUT_INVALID",
            "Risk Appetite Policy requires a stress result",
        )
    stress_state = (
        _require_gate_state(inputs.stress_state, field="stress_state")
        if inputs.stress_state is not None
        else "GREEN"
    )

    committed = active if rules.committed_exposure_mode == "ACTIVE_ONLY" else active + reserved
    _storage_decimal(committed, field="committed_exposure")
    utilization = committed / rules.approved_portfolio_limit

    exposure_state = "GREEN"
    if utilization >= rules.utilization_stop_ratio:
        exposure_state = "RED"
    elif utilization >= rules.utilization_warning_ratio:
        exposure_state = "AMBER"

    coverage: Decimal | None = None
    reserve_state = "GREEN"
    if reserve_requirement > 0:
        coverage = reserve_available / reserve_requirement
        if coverage < rules.reserve_coverage_hard_minimum_ratio:
            reserve_state = "RED"
        elif coverage < rules.reserve_coverage_warning_ratio:
            reserve_state = "AMBER"

    gate_states = {
        "exposure": exposure_state,
        "reserve": reserve_state,
        "concentration": concentration_state,
        "stress": stress_state,
    }
    risk_state = max(gate_states.values(), key=lambda value: _STATE_SEVERITY[value])
    return RiskEvaluationResult(
        risk_state=risk_state,
        committed_exposure=committed,
        approved_portfolio_limit=rules.approved_portfolio_limit,
        utilization_ratio=utilization,
        reserve_coverage_ratio=coverage,
        gate_states=gate_states,
    )


async def resolve_risk_policy(
    session: AsyncSession,
    *,
    resolved_policy_pack: ResolvedPolicyPack,
) -> ResolvedRiskPolicy:
    pack = await session.get(PolicyVersion, resolved_policy_pack.policy_pack_id)
    if pack is None or pack.policy_type != "PILOT_POLICY_PACK" or pack.lifecycle_status != "ACTIVE":
        raise ApiError(
            409,
            "POLICY_PACK_NOT_ACTIVE",
            "Resolved Pilot Policy Pack is no longer ACTIVE",
        )

    if not resolved_policy_pack.component_version_ids:
        raise ApiError(
            409,
            "POLICY_COMPONENT_MISSING",
            "Pilot Policy Pack does not reference a Risk Appetite Policy",
        )

    risk_policies = (
        await session.scalars(
            select(PolicyVersion).where(
                PolicyVersion.id.in_(resolved_policy_pack.component_version_ids),
                PolicyVersion.policy_type == "RISK_APPETITE_POLICY",
            )
        )
    ).all()
    if not risk_policies:
        raise ApiError(
            409,
            "POLICY_COMPONENT_MISSING",
            "Pilot Policy Pack does not reference a Risk Appetite Policy",
        )
    if len(risk_policies) != 1:
        raise ApiError(
            409,
            "POLICY_COMPONENT_INCOMPATIBLE",
            "Pilot Policy Pack must reference exactly one Risk Appetite Policy",
            {"risk_policy_version_ids": sorted(str(policy.id) for policy in risk_policies)},
        )
    policy = risk_policies[0]
    if policy.scope_definition != pack.scope_definition:
        raise ApiError(
            409,
            "POLICY_COMPONENT_INCOMPATIBLE",
            "Risk Appetite Policy scope does not match the Pilot Policy Pack scope",
        )
    if policy.lifecycle_status not in {"APPROVED", "ACTIVE", "SUPERSEDED", "RETIRED"}:
        raise ApiError(
            409,
            "POLICY_COMPONENT_INCOMPATIBLE",
            "Risk Appetite Policy has not reached an approved immutable lineage state",
        )
    if policy.payload_hash is None or policy.payload_hash != canonical_request_hash(policy.payload):
        raise ApiError(
            409,
            "POLICY_RESOLUTION_UNAVAILABLE",
            "Risk Appetite Policy failed payload integrity verification",
        )
    try:
        rules = parse_risk_policy_rules(policy.payload)
    except RiskEvaluationError as exc:
        raise ApiError(409, exc.code, str(exc)) from exc

    return ResolvedRiskPolicy(
        policy_pack_id=pack.id,
        policy_pack_version=pack.version_number,
        scope_definition=pack.scope_definition,
        risk_policy_version_id=policy.id,
        risk_policy_code=policy.policy_code,
        risk_policy_version_number=policy.version_number,
        rules=rules,
    )


async def read_authoritative_exposure(
    session: AsyncSession,
    *,
    evaluated_at: datetime,
) -> tuple[Decimal, Decimal]:
    active_value = await session.scalar(
        select(func.coalesce(func.sum(GuaranteeCase.current_guarantee_exposure), 0))
    )
    total_active = Decimal(active_value or 0)

    reserved_rows = (
        await session.execute(
            select(
                GuaranteeCase.reserved_guarantee_amount,
                GuaranteeCase.reservation_expires_at,
            ).where(GuaranteeCase.state == "RESERVED")
        )
    ).all()
    total_reserved = Decimal("0")
    for amount, expires_at in reserved_rows:
        if amount is None or expires_at is None:
            raise RiskEvaluationError(
                "RISK_EXPOSURE_SOURCE_INVALID",
                "RESERVED GuaranteeCase is missing amount or reservation expiry",
            )
        if expires_at > evaluated_at:
            total_reserved += Decimal(amount)
    _storage_decimal(total_active, field="total_active_exposure")
    _storage_decimal(total_reserved, field="total_reserved_exposure")
    return total_active, total_reserved


def _snapshot_payload(snapshot: PortfolioRiskSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "policy_pack_id": str(snapshot.policy_pack_id),
        "policy_pack_version": snapshot.policy_pack_version,
        "risk_policy_version_id": str(snapshot.risk_policy_version_id),
        "risk_policy_code": snapshot.risk_policy_code,
        "risk_policy_version_number": snapshot.risk_policy_version_number,
        "risk_state": snapshot.risk_state,
        "total_active_exposure": _decimal_text(snapshot.total_active_exposure),
        "total_reserved_exposure": _decimal_text(snapshot.total_reserved_exposure),
        "committed_exposure": _decimal_text(snapshot.committed_exposure),
        "approved_portfolio_limit": _decimal_text(snapshot.approved_portfolio_limit),
        "reserve_requirement": _decimal_text(snapshot.reserve_requirement),
        "reserve_available": _decimal_text(snapshot.reserve_available),
        "reserve_metrics_reference": snapshot.reserve_metrics_reference,
        "concentration_metrics_reference": snapshot.concentration_metrics_reference,
        "stress_result_reference": snapshot.stress_result_reference,
        "evaluated_inputs": snapshot.evaluated_inputs,
        "input_hash": snapshot.input_hash,
        "algorithm_code": snapshot.algorithm_code,
        "algorithm_version": snapshot.algorithm_version,
        "actor_type": snapshot.actor_type,
        "actor_id": str(snapshot.actor_id),
        "correlation_id": str(snapshot.correlation_id),
        "evaluated_at": snapshot.evaluated_at.isoformat(),
    }


async def evaluate_and_snapshot_portfolio_risk(
    session: AsyncSession,
    *,
    resolved_policy_pack: ResolvedPolicyPack,
    reserve_requirement: Decimal,
    reserve_available: Decimal,
    reserve_metrics_reference: str,
    concentration_state: str,
    concentration_metrics_reference: str,
    stress_state: str | None,
    stress_result_reference: str | None,
    authoritative_input_references: tuple[str, ...],
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    evaluated_at: datetime | None = None,
) -> PortfolioRiskSnapshot:
    timestamp = evaluated_at or datetime.now(UTC)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('portfolio-risk:evaluate', 0))")
    )
    resolved_risk = await resolve_risk_policy(
        session,
        resolved_policy_pack=resolved_policy_pack,
    )
    total_active, total_reserved = await read_authoritative_exposure(
        session,
        evaluated_at=timestamp,
    )
    inputs = RiskEvaluationInputs(
        total_active_exposure=total_active,
        total_reserved_exposure=total_reserved,
        reserve_requirement=reserve_requirement,
        reserve_available=reserve_available,
        reserve_metrics_reference=reserve_metrics_reference,
        concentration_state=concentration_state,
        concentration_metrics_reference=concentration_metrics_reference,
        stress_state=stress_state,
        stress_result_reference=stress_result_reference,
        authoritative_input_references=authoritative_input_references,
    )
    result = calculate_portfolio_risk(rules=resolved_risk.rules, inputs=inputs)
    evaluated_inputs = {
        "scope_definition": resolved_risk.scope_definition,
        "total_active_exposure": _decimal_text(total_active),
        "total_reserved_exposure": _decimal_text(total_reserved),
        "committed_exposure": _decimal_text(result.committed_exposure),
        "reserve_requirement": _decimal_text(reserve_requirement),
        "reserve_available": _decimal_text(reserve_available),
        "reserve_metrics_reference": reserve_metrics_reference,
        "concentration_state": concentration_state,
        "concentration_metrics_reference": concentration_metrics_reference,
        "stress_state": stress_state,
        "stress_result_reference": stress_result_reference,
        "authoritative_input_references": list(authoritative_input_references),
        "utilization_ratio": _decimal_text(result.utilization_ratio),
        "reserve_coverage_ratio": (
            _decimal_text(result.reserve_coverage_ratio)
            if result.reserve_coverage_ratio is not None
            else None
        ),
        "gate_states": result.gate_states,
    }
    previous = await session.scalar(
        select(PortfolioRiskSnapshot)
        .order_by(
            PortfolioRiskSnapshot.evaluated_at.desc(),
            PortfolioRiskSnapshot.created_at.desc(),
            PortfolioRiskSnapshot.id.desc(),
        )
        .limit(1)
    )
    snapshot = PortfolioRiskSnapshot(
        policy_pack_id=resolved_risk.policy_pack_id,
        policy_pack_version=resolved_risk.policy_pack_version,
        risk_policy_version_id=resolved_risk.risk_policy_version_id,
        risk_policy_code=resolved_risk.risk_policy_code,
        risk_policy_version_number=resolved_risk.risk_policy_version_number,
        risk_state=result.risk_state,
        total_active_exposure=total_active,
        total_reserved_exposure=total_reserved,
        committed_exposure=result.committed_exposure,
        approved_portfolio_limit=result.approved_portfolio_limit,
        reserve_requirement=reserve_requirement,
        reserve_available=reserve_available,
        reserve_metrics_reference=reserve_metrics_reference,
        concentration_metrics_reference=concentration_metrics_reference,
        stress_result_reference=stress_result_reference,
        evaluated_inputs=evaluated_inputs,
        input_hash=canonical_request_hash(evaluated_inputs),
        algorithm_code=RISK_ALGORITHM_CODE,
        algorithm_version=RISK_ALGORITHM_VERSION,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        evaluated_at=timestamp,
    )
    session.add(snapshot)
    await session.flush()

    payload = _snapshot_payload(snapshot)
    append_audit(
        session,
        aggregate_type="PortfolioRiskSnapshot",
        aggregate_id=str(snapshot.id),
        aggregate_version=1,
        action="PORTFOLIO_RISK_EVALUATED",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=payload,
        policy_pack_id=resolved_risk.policy_pack_id,
        scope=resolved_risk.scope_definition,
        occurred_at=timestamp,
    )
    session.add(
        OutboxMessage(
            event_type="PortfolioRiskEvaluated",
            event_version=1,
            aggregate_type="PortfolioRiskSnapshot",
            aggregate_id=str(snapshot.id),
            aggregate_version=1,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=None,
            occurred_at=timestamp,
        )
    )
    if previous is not None and previous.risk_state != snapshot.risk_state:
        session.add(
            OutboxMessage(
                event_type="PortfolioRiskStateChanged",
                event_version=1,
                aggregate_type="PortfolioRiskSnapshot",
                aggregate_id=str(snapshot.id),
                aggregate_version=1,
                payload={
                    "snapshot_id": str(snapshot.id),
                    "previous_snapshot_id": str(previous.id),
                    "previous_state": previous.risk_state,
                    "risk_state": snapshot.risk_state,
                    "policy_pack_id": str(snapshot.policy_pack_id),
                    "risk_policy_version_id": str(snapshot.risk_policy_version_id),
                },
                correlation_id=correlation_id,
                causation_id=None,
                occurred_at=timestamp,
            )
        )
    await session.flush()
    return snapshot
