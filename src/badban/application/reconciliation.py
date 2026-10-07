from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.lender_adapter import (
    LenderAdapterRegistry,
)
from badban.application.reconciliation_policy import (
    ReconciliationRules,
)
from badban.infrastructure.persistence.models import (
    OutboxMessage,
    ReconciliationRun,
)

ALGORITHM_CODE = "RECONCILIATION_CORE"
ALGORITHM_VERSION = "2"
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
    from badban.application.reconciliation_lender_source import LenderSourceRegistry
    from badban.application.reconciliation_multisource import run_source_reconciliation
    from badban.application.reconciliation_sources import SourceTarget

    return await run_source_reconciliation(
        session,
        target=SourceTarget(reconciliation_type="LENDER", provider_id=provider_id),
        registry=LenderSourceRegistry(registry, at=now),
        actor_id=actor_id,
        actor_type=actor_type,
        correlation_id=correlation_id,
        now=now,
    )


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
                "provider_id": str(run.provider_id) if run.provider_id else None,
                "source_legal_entity_id": str(run.source_legal_entity_id)
                if run.source_legal_entity_id
                else None,
                "program_id": str(run.program_id) if run.program_id else None,
                "reconciliation_type": run.reconciliation_type,
            },
            correlation_id=run.correlation_id,
            causation_id=run.id,
            occurred_at=now,
        )
    )
