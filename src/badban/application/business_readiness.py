from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.policy_resolution import resolve_active_policy_pack
from badban.infrastructure.persistence.models import (
    AssetType,
    CreditProvider,
    OperationalStopControl,
    PortfolioRiskSnapshot,
    ReconciliationBlock,
    ReconciliationCase,
)
from badban.security.audit import append_audit

STOP_NEW_GUARANTEE_RESERVATIONS = "STOP_NEW_GUARANTEE_RESERVATIONS"
STOP_GUARANTEE_ACTIVATION = "STOP_GUARANTEE_ACTIVATION"
SUSPEND_PROVIDER_FOR_NEW_ACTIONS = "SUSPEND_PROVIDER_FOR_NEW_ACTIONS"
SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS = "SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS"
STOP_CLAIM_SETTLEMENT = "STOP_CLAIM_SETTLEMENT"
STOP_COLLATERAL_RELEASE = "STOP_COLLATERAL_RELEASE"

STOP_CONTROL_SCOPE = {
    STOP_NEW_GUARANTEE_RESERVATIONS: "GLOBAL",
    STOP_GUARANTEE_ACTIVATION: "GLOBAL",
    SUSPEND_PROVIDER_FOR_NEW_ACTIONS: "PROVIDER",
    SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS: "ASSET_TYPE",
    STOP_CLAIM_SETTLEMENT: "GLOBAL",
    STOP_COLLATERAL_RELEASE: "GLOBAL",
}
CANONICAL_STOP_CONTROLS = frozenset(STOP_CONTROL_SCOPE)


class BusinessReadinessError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class BusinessReadinessReason:
    code: str
    source_type: str
    source_reference: str | None
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BusinessReadinessResult:
    status: str
    evaluated_at: datetime
    policy_pack_id: UUID | None
    risk_snapshot_id: UUID | None
    reasons: tuple[BusinessReadinessReason, ...]


def assert_stop_scope(
    *,
    control_type: str,
    scope_type: str,
    scope_id: UUID | None,
) -> None:
    expected_scope = STOP_CONTROL_SCOPE.get(control_type)
    if expected_scope is None:
        raise BusinessReadinessError(
            "STOP_CONTROL_TYPE_INVALID",
            "Stop control type is not authorized",
        )
    if scope_type != expected_scope:
        raise BusinessReadinessError(
            "STOP_CONTROL_SCOPE_INVALID",
            "Stop control scope does not match the control type",
        )
    if scope_type == "GLOBAL" and scope_id is not None:
        raise BusinessReadinessError(
            "STOP_CONTROL_SCOPE_INVALID",
            "GLOBAL stop control must not include scope_id",
        )
    if scope_type != "GLOBAL" and scope_id is None:
        raise BusinessReadinessError(
            "STOP_CONTROL_SCOPE_INVALID",
            "Scoped stop control requires scope_id",
        )


async def _assert_scope_target_exists(
    session: AsyncSession,
    *,
    scope_type: str,
    scope_id: UUID | None,
) -> None:
    if scope_type == "PROVIDER":
        if scope_id is None or await session.get(CreditProvider, scope_id) is None:
            raise BusinessReadinessError(
                "STOP_CONTROL_TARGET_NOT_FOUND",
                "Provider stop-control target was not found",
            )
    elif scope_type == "ASSET_TYPE":
        if scope_id is None or await session.get(AssetType, scope_id) is None:
            raise BusinessReadinessError(
                "STOP_CONTROL_TARGET_NOT_FOUND",
                "Asset Type stop-control target was not found",
            )


def _lock_key(control_type: str, scope_type: str, scope_id: UUID | None) -> str:
    return f"operational-stop:{control_type}:{scope_type}:{scope_id or 'GLOBAL'}"


async def activate_stop_control(
    session: AsyncSession,
    *,
    control_type: str,
    scope_type: str,
    scope_id: UUID | None,
    reason: str,
    evidence_reference: str | None,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> OperationalStopControl:
    assert_stop_scope(
        control_type=control_type,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    if not reason.strip():
        raise BusinessReadinessError(
            "STOP_CONTROL_REASON_REQUIRED",
            "Stop-control activation requires a nonblank reason",
        )
    if evidence_reference is not None and not evidence_reference.strip():
        raise BusinessReadinessError(
            "STOP_CONTROL_EVIDENCE_INVALID",
            "Evidence reference must be nonblank when supplied",
        )
    await _assert_scope_target_exists(
        session,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": _lock_key(control_type, scope_type, scope_id)},
    )
    existing = await session.scalar(
        select(OperationalStopControl)
        .where(
            OperationalStopControl.control_type == control_type,
            OperationalStopControl.scope_type == scope_type,
            OperationalStopControl.scope_id.is_(None)
            if scope_id is None
            else OperationalStopControl.scope_id == scope_id,
            OperationalStopControl.active.is_(True),
        )
        .order_by(OperationalStopControl.activated_at.desc())
        .limit(1)
        .with_for_update()
    )
    normalized_reason = reason.strip()
    normalized_evidence = evidence_reference.strip() if evidence_reference is not None else None
    if existing is not None:
        if (
            existing.reason == normalized_reason
            and existing.evidence_reference == normalized_evidence
        ):
            return existing
        raise BusinessReadinessError(
            "STOP_CONTROL_ALREADY_ACTIVE",
            "A different active stop control already exists for this type and scope",
        )

    now = datetime.now(UTC)
    control = OperationalStopControl(
        control_type=control_type,
        scope_type=scope_type,
        scope_id=scope_id,
        active=True,
        reason=normalized_reason,
        evidence_reference=normalized_evidence,
        activated_by=actor_id,
        activated_at=now,
        cleared_by=None,
        cleared_at=None,
        version=1,
    )
    session.add(control)
    await session.flush()
    append_audit(
        session,
        aggregate_type="OperationalStopControl",
        aggregate_id=str(control.id),
        aggregate_version=control.version,
        action="STOP_CONTROL_ACTIVATE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        reason_code=control.control_type,
        evidence_reference=control.evidence_reference,
        new_state={
            "control_type": control.control_type,
            "scope_type": control.scope_type,
            "scope_id": str(control.scope_id) if control.scope_id is not None else None,
            "active": True,
        },
        scope={
            "scope_type": control.scope_type,
            "scope_id": str(control.scope_id) if control.scope_id is not None else None,
        },
    )
    return control


async def clear_stop_control(
    session: AsyncSession,
    *,
    control_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> OperationalStopControl:
    control = await session.scalar(
        select(OperationalStopControl)
        .where(OperationalStopControl.id == control_id)
        .with_for_update()
    )
    if control is None:
        raise BusinessReadinessError(
            "STOP_CONTROL_NOT_FOUND",
            "Stop control was not found",
        )
    if not control.active:
        return control

    control.active = False
    control.cleared_by = actor_id
    control.cleared_at = datetime.now(UTC)
    control.version += 1
    append_audit(
        session,
        aggregate_type="OperationalStopControl",
        aggregate_id=str(control.id),
        aggregate_version=control.version,
        action="STOP_CONTROL_CLEAR",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        reason_code=control.control_type,
        evidence_reference=control.evidence_reference,
        previous_state={
            "control_type": control.control_type,
            "scope_type": control.scope_type,
            "scope_id": str(control.scope_id) if control.scope_id is not None else None,
            "active": True,
        },
        new_state={
            "control_type": control.control_type,
            "scope_type": control.scope_type,
            "scope_id": str(control.scope_id) if control.scope_id is not None else None,
            "active": False,
        },
        scope={
            "scope_type": control.scope_type,
            "scope_id": str(control.scope_id) if control.scope_id is not None else None,
        },
    )
    return control


async def assert_stop_control_allows(
    session: AsyncSession,
    *,
    control_type: str,
    scope_type: str,
    scope_id: UUID | None,
) -> None:
    assert_stop_scope(
        control_type=control_type,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    active = await session.scalar(
        select(OperationalStopControl.id)
        .where(
            OperationalStopControl.control_type == control_type,
            OperationalStopControl.scope_type == scope_type,
            OperationalStopControl.scope_id.is_(None)
            if scope_id is None
            else OperationalStopControl.scope_id == scope_id,
            OperationalStopControl.active.is_(True),
        )
        .limit(1)
    )
    if active is not None:
        raise BusinessReadinessError(
            "STOP_CONTROL_ACTIVE",
            "The requested new action is blocked by an active operational stop control",
        )


async def evaluate_business_readiness(
    session: AsyncSession,
    *,
    policy_scope_definition: dict[str, object],
    provider_id: UUID | None,
    asset_type_id: UUID | None,
    provider_health: str | None,
    evaluated_at: datetime | None = None,
) -> BusinessReadinessResult:
    now = evaluated_at or datetime.now(UTC)
    reasons: list[BusinessReadinessReason] = []

    stop_predicates = [
        (OperationalStopControl.scope_type == "GLOBAL")
        & (OperationalStopControl.scope_id.is_(None))
    ]
    if provider_id is not None:
        stop_predicates.append(
            (OperationalStopControl.scope_type == "PROVIDER")
            & (OperationalStopControl.scope_id == provider_id)
        )
    if asset_type_id is not None:
        stop_predicates.append(
            (OperationalStopControl.scope_type == "ASSET_TYPE")
            & (OperationalStopControl.scope_id == asset_type_id)
        )
    controls = (
        await session.scalars(
            select(OperationalStopControl)
            .where(
                OperationalStopControl.active.is_(True),
                or_(*stop_predicates),
            )
            .order_by(OperationalStopControl.activated_at, OperationalStopControl.id)
        )
    ).all()
    for control in controls:
        reasons.append(
            BusinessReadinessReason(
                code="STOP_CONTROL_ACTIVE",
                source_type="OperationalStopControl",
                source_reference=str(control.id),
                details={
                    "control_type": control.control_type,
                    "scope_type": control.scope_type,
                    "scope_id": str(control.scope_id) if control.scope_id is not None else None,
                },
            )
        )

    if provider_id is not None:
        provider = await session.get(CreditProvider, provider_id)
        if provider is None:
            reasons.append(
                BusinessReadinessReason(
                    code="PROVIDER_NOT_FOUND",
                    source_type="CreditProvider",
                    source_reference=str(provider_id),
                    details={},
                )
            )
        elif provider.lifecycle_status != "ACTIVE":
            reasons.append(
                BusinessReadinessReason(
                    code="PROVIDER_NOT_ACTIVE",
                    source_type="CreditProvider",
                    source_reference=str(provider.id),
                    details={"lifecycle_status": provider.lifecycle_status},
                )
            )

        if provider_health is None:
            reasons.append(
                BusinessReadinessReason(
                    code="PROVIDER_HEALTH_UNAVAILABLE",
                    source_type="LenderAdapter",
                    source_reference=str(provider_id),
                    details={},
                )
            )
        elif provider_health not in {
            "AVAILABLE",
            "DEGRADED",
            "UNAVAILABLE",
            "AUTH_FAILURE",
            "CONTRACT_MISMATCH",
        }:
            reasons.append(
                BusinessReadinessReason(
                    code="PROVIDER_HEALTH_INVALID",
                    source_type="LenderAdapter",
                    source_reference=str(provider_id),
                    details={"health": provider_health},
                )
            )
        elif provider_health in {"UNAVAILABLE", "AUTH_FAILURE", "CONTRACT_MISMATCH"}:
            reasons.append(
                BusinessReadinessReason(
                    code="PROVIDER_UNAVAILABLE",
                    source_type="LenderAdapter",
                    source_reference=str(provider_id),
                    details={"health": provider_health},
                )
            )

    if asset_type_id is not None:
        asset_type = await session.get(AssetType, asset_type_id)
        if asset_type is None:
            reasons.append(
                BusinessReadinessReason(
                    code="ASSET_TYPE_NOT_FOUND",
                    source_type="AssetType",
                    source_reference=str(asset_type_id),
                    details={},
                )
            )
        elif asset_type.status != "ACTIVE":
            reasons.append(
                BusinessReadinessReason(
                    code="ASSET_TYPE_NOT_ACTIVE",
                    source_type="AssetType",
                    source_reference=str(asset_type.id),
                    details={"status": asset_type.status},
                )
            )

    policy_pack_id: UUID | None = None
    try:
        policy = await resolve_active_policy_pack(
            session,
            scope_definition=policy_scope_definition,
            effective_at=now,
        )
        policy_pack_id = policy.policy_pack_id
    except ApiError as exc:
        reasons.append(
            BusinessReadinessReason(
                code="POLICY_NOT_READY",
                source_type="PilotPolicyPack",
                source_reference=None,
                details={"source_error_code": exc.code},
            )
        )

    risk_snapshot = await session.scalar(
        select(PortfolioRiskSnapshot)
        .where(PortfolioRiskSnapshot.evaluated_inputs["scope_definition"] == policy_scope_definition)
        .order_by(
            PortfolioRiskSnapshot.evaluated_at.desc(),
            PortfolioRiskSnapshot.created_at.desc(),
            PortfolioRiskSnapshot.id.desc(),
        )
        .limit(1)
    )
    risk_snapshot_id: UUID | None = None
    if risk_snapshot is None:
        reasons.append(
            BusinessReadinessReason(
                code="PORTFOLIO_RISK_UNAVAILABLE",
                source_type="PortfolioRiskSnapshot",
                source_reference=None,
                details={},
            )
        )
    else:
        risk_snapshot_id = risk_snapshot.id
        if policy_pack_id is not None and risk_snapshot.policy_pack_id != policy_pack_id:
            reasons.append(
                BusinessReadinessReason(
                    code="PORTFOLIO_RISK_POLICY_MISMATCH",
                    source_type="PortfolioRiskSnapshot",
                    source_reference=str(risk_snapshot.id),
                    details={
                        "risk_policy_pack_id": str(risk_snapshot.policy_pack_id),
                        "active_policy_pack_id": str(policy_pack_id),
                    },
                )
            )
        if risk_snapshot.risk_state == "RED":
            reasons.append(
                BusinessReadinessReason(
                    code="PORTFOLIO_RISK_RED",
                    source_type="PortfolioRiskSnapshot",
                    source_reference=str(risk_snapshot.id),
                    details={},
                )
            )

    block_statement = (
        select(ReconciliationBlock, ReconciliationCase)
        .join(
            ReconciliationCase,
            ReconciliationCase.id == ReconciliationBlock.reconciliation_case_id,
        )
        .where(ReconciliationBlock.active.is_(True))
    )
    stale_statement = select(ReconciliationCase).where(ReconciliationCase.status == "STALE")
    if provider_id is not None:
        block_statement = block_statement.where(
            ReconciliationCase.external_provider_id == provider_id
        )
        stale_statement = stale_statement.where(
            ReconciliationCase.external_provider_id == provider_id
        )
    block_row = (await session.execute(block_statement.limit(1))).first()
    if block_row is not None:
        block, case = block_row
        reasons.append(
            BusinessReadinessReason(
                code="RECONCILIATION_BLOCK_ACTIVE",
                source_type="ReconciliationBlock",
                source_reference=str(block.id),
                details={"case_id": str(case.id)},
            )
        )
    stale_case = await session.scalar(
        stale_statement.order_by(
            ReconciliationCase.last_observed_at.desc(),
            ReconciliationCase.id.desc(),
        ).limit(1)
    )
    if stale_case is not None:
        reasons.append(
            BusinessReadinessReason(
                code="RECONCILIATION_SOURCE_STALE",
                source_type="ReconciliationCase",
                source_reference=str(stale_case.id),
                details={},
            )
        )

    return BusinessReadinessResult(
        status="READY" if not reasons else "NOT_READY",
        evaluated_at=now,
        policy_pack_id=policy_pack_id,
        risk_snapshot_id=risk_snapshot_id,
        reasons=tuple(reasons),
    )
