from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.decision_snapshot import create_decision_snapshot
from badban.application.policy_resolution import ResolvedPolicyPack
from badban.infrastructure.persistence.models import (
    AssetPosition,
    DecisionSnapshot,
    ValuationObservation,
)

CAPACITY_ALGORITHM_CODE = "GUARANTEE_CAPACITY"
CAPACITY_ALGORITHM_VERSION = "CAPACITY_V1"

_ALLOWED_FRESHNESS = {"FRESH", "STALE", "UNKNOWN"}


class CapacityInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PositionCapacityInput:
    valuation_observation_id: UUID
    eligible_quantity: Decimal
    approved_price: Decimal
    approved_fx_conversion: Decimal | None
    fx_required: bool
    pledgeable_fraction: Decimal
    advance_rate: Decimal
    freshness_status: str
    valid_until: datetime | None


@dataclass(frozen=True, slots=True)
class PositionCapacityResult:
    valuation_observation_id: UUID
    gross_market_value: Decimal
    pledgeable_market_value: Decimal
    position_backing_capacity: Decimal
    new_capacity_contribution: Decimal
    freshness_eligible: bool


@dataclass(frozen=True, slots=True)
class CapacityCalculationResult:
    policy_pack_id: UUID
    policy_pack_version: int
    component_version_ids: tuple[UUID, ...]
    algorithm_code: str
    algorithm_version: str
    position_results: tuple[PositionCapacityResult, ...]
    uncapped_gross_backing_capacity: Decimal
    capped_gross_backing_capacity: Decimal
    reserved_guarantee_capacity: Decimal
    active_guarantee_exposure: Decimal
    other_approved_capacity_holds: Decimal
    available_guarantee_capacity: Decimal


@dataclass(frozen=True, slots=True)
class CapacityPositionRequest:
    valuation_observation_id: UUID
    eligible_quantity: Decimal
    pledgeable_fraction: Decimal
    advance_rate: Decimal
    fx_required: bool


def _require_decimal(name: str, value: object, *, non_negative: bool = True) -> Decimal:
    if not isinstance(value, Decimal):
        raise CapacityInputError(f"{name} must be Decimal")
    if not value.is_finite():
        raise CapacityInputError(f"{name} must be finite")
    if non_negative and value < 0:
        raise CapacityInputError(f"{name} must be non-negative")
    return value


def _require_fraction(name: str, value: object) -> Decimal:
    decimal_value = _require_decimal(name, value)
    if decimal_value > 1:
        raise CapacityInputError(f"{name} must be within [0,1]")
    return decimal_value


def _working_precision(values: Sequence[Decimal]) -> int:
    return max(32, sum(max(1, len(value.as_tuple().digits)) for value in values) + 16)


def _require_aware_datetime(name: str, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CapacityInputError(f"{name} must be timezone-aware")
    return value


def calculate_position_capacity(
    position: PositionCapacityInput,
    *,
    effective_at: datetime,
) -> PositionCapacityResult:
    decision_time = _require_aware_datetime("effective_at", effective_at)
    quantity = _require_decimal("eligible_quantity", position.eligible_quantity)
    price = _require_decimal("approved_price", position.approved_price)
    pledgeable_fraction = _require_fraction("pledgeable_fraction", position.pledgeable_fraction)
    advance_rate = _require_fraction("advance_rate", position.advance_rate)

    if position.freshness_status not in _ALLOWED_FRESHNESS:
        raise CapacityInputError("freshness_status must be FRESH, STALE, or UNKNOWN")

    if position.approved_fx_conversion is None:
        if position.fx_required:
            raise CapacityInputError("approved FX conversion is required")
        fx = Decimal("1")
    else:
        fx = _require_decimal(
            "approved_fx_conversion",
            position.approved_fx_conversion,
            non_negative=False,
        )
        if fx <= 0:
            raise CapacityInputError("approved_fx_conversion must be positive")

    valid_until = position.valid_until
    if valid_until is not None:
        _require_aware_datetime("valid_until", valid_until)

    freshness_eligible = (
        position.freshness_status == "FRESH"
        and valid_until is not None
        and decision_time <= valid_until
    )

    operands = [quantity, price, fx, pledgeable_fraction, advance_rate]
    with localcontext() as context:
        context.prec = _working_precision(operands)
        gross_market_value = quantity * price * fx
        pledgeable_market_value = gross_market_value * pledgeable_fraction
        position_backing_capacity = pledgeable_market_value * advance_rate

    return PositionCapacityResult(
        valuation_observation_id=position.valuation_observation_id,
        gross_market_value=gross_market_value,
        pledgeable_market_value=pledgeable_market_value,
        position_backing_capacity=position_backing_capacity,
        new_capacity_contribution=(
            position_backing_capacity if freshness_eligible else Decimal("0")
        ),
        freshness_eligible=freshness_eligible,
    )


def calculate_guarantee_capacity(
    *,
    positions: Sequence[PositionCapacityInput],
    resolved_policy_pack: ResolvedPolicyPack,
    capped_gross_backing_capacity: Decimal,
    reserved_guarantee_capacity: Decimal,
    active_guarantee_exposure: Decimal,
    other_approved_capacity_holds: Decimal,
    effective_at: datetime,
) -> CapacityCalculationResult:
    capped = _require_decimal("capped_gross_backing_capacity", capped_gross_backing_capacity)
    reserved = _require_decimal("reserved_guarantee_capacity", reserved_guarantee_capacity)
    exposure = _require_decimal("active_guarantee_exposure", active_guarantee_exposure)
    holds = _require_decimal(
        "other_approved_capacity_holds",
        other_approved_capacity_holds,
    )

    results = tuple(
        calculate_position_capacity(position, effective_at=effective_at) for position in positions
    )
    contributions = [result.new_capacity_contribution for result in results]
    with localcontext() as context:
        context.prec = _working_precision([*contributions, capped, reserved, exposure, holds])
        uncapped = sum(contributions, Decimal("0"))
        if capped > uncapped:
            raise CapacityInputError(
                "capped_gross_backing_capacity cannot exceed uncapped gross backing capacity"
            )
        remainder = capped - reserved - exposure - holds
        available = max(Decimal("0"), remainder)

    return CapacityCalculationResult(
        policy_pack_id=resolved_policy_pack.policy_pack_id,
        policy_pack_version=resolved_policy_pack.version_number,
        component_version_ids=resolved_policy_pack.component_version_ids,
        algorithm_code=CAPACITY_ALGORITHM_CODE,
        algorithm_version=CAPACITY_ALGORITHM_VERSION,
        position_results=results,
        uncapped_gross_backing_capacity=uncapped,
        capped_gross_backing_capacity=capped,
        reserved_guarantee_capacity=reserved,
        active_guarantee_exposure=exposure,
        other_approved_capacity_holds=holds,
        available_guarantee_capacity=available,
    )


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _capacity_input_payload(
    *,
    observations: Sequence[ValuationObservation],
    asset_positions: Sequence[AssetPosition],
    requests: Sequence[CapacityPositionRequest],
    capacity_currency: str,
    capped_gross_backing_capacity: Decimal,
    reserved_guarantee_capacity: Decimal,
    active_guarantee_exposure: Decimal,
    other_approved_capacity_holds: Decimal,
) -> dict[str, Any]:
    requests_by_id = {request.valuation_observation_id: request for request in requests}
    positions_by_id = {position.id: position for position in asset_positions}
    return {
        "capacity_currency": capacity_currency,
        "positions": [
            {
                "valuation_observation_id": str(observation.id),
                "asset_position_id": str(observation.asset_position_id),
                "asset_type_id": str(positions_by_id[observation.asset_position_id].asset_type_id),
                "asset_position_quantity": _decimal_text(
                    positions_by_id[observation.asset_position_id].quantity
                ),
                "asset_position_version": positions_by_id[observation.asset_position_id].version,
                "unit_code": positions_by_id[observation.asset_position_id].unit_code,
                "eligible_quantity": _decimal_text(
                    requests_by_id[observation.id].eligible_quantity
                ),
                "approved_price": _decimal_text(observation.unit_price),
                "approved_fx_conversion": (
                    _decimal_text(observation.fx_rate) if observation.fx_rate is not None else None
                ),
                "fx_required": requests_by_id[observation.id].fx_required,
                "valuation_currency": observation.valuation_currency,
                "valuation_source_name": observation.source_name,
                "valuation_source_reference": observation.source_reference,
                "valuation_source_version_reference": observation.source_version_reference,
                "valuation_observed_at": observation.observed_at.isoformat(),
                "valuation_received_at": observation.received_at.isoformat(),
                "pledgeable_fraction": _decimal_text(
                    requests_by_id[observation.id].pledgeable_fraction
                ),
                "advance_rate": _decimal_text(requests_by_id[observation.id].advance_rate),
                "freshness_status": observation.freshness_status,
                "valid_until": (
                    observation.valid_until.isoformat()
                    if observation.valid_until is not None
                    else None
                ),
            }
            for observation in observations
        ],
        "capped_gross_backing_capacity": _decimal_text(capped_gross_backing_capacity),
        "reserved_guarantee_capacity": _decimal_text(reserved_guarantee_capacity),
        "active_guarantee_exposure": _decimal_text(active_guarantee_exposure),
        "other_approved_capacity_holds": _decimal_text(other_approved_capacity_holds),
    }


def _capacity_output_payload(result: CapacityCalculationResult) -> dict[str, Any]:
    return {
        "algorithm_code": result.algorithm_code,
        "algorithm_version": result.algorithm_version,
        "uncapped_gross_backing_capacity": _decimal_text(result.uncapped_gross_backing_capacity),
        "capped_gross_backing_capacity": _decimal_text(result.capped_gross_backing_capacity),
        "reserved_guarantee_capacity": _decimal_text(result.reserved_guarantee_capacity),
        "active_guarantee_exposure": _decimal_text(result.active_guarantee_exposure),
        "other_approved_capacity_holds": _decimal_text(result.other_approved_capacity_holds),
        "available_guarantee_capacity": _decimal_text(result.available_guarantee_capacity),
        "positions": [
            {
                "valuation_observation_id": str(position.valuation_observation_id),
                "gross_market_value": _decimal_text(position.gross_market_value),
                "pledgeable_market_value": _decimal_text(position.pledgeable_market_value),
                "position_backing_capacity": _decimal_text(position.position_backing_capacity),
                "new_capacity_contribution": _decimal_text(position.new_capacity_contribution),
                "freshness_eligible": position.freshness_eligible,
            }
            for position in result.position_results
        ],
    }


async def calculate_and_snapshot_guarantee_capacity(
    session: AsyncSession,
    *,
    business_entity_type: str,
    business_entity_id: str,
    position_requests: Sequence[CapacityPositionRequest],
    capacity_currency: str,
    resolved_policy_pack: ResolvedPolicyPack,
    capped_gross_backing_capacity: Decimal,
    reserved_guarantee_capacity: Decimal,
    active_guarantee_exposure: Decimal,
    other_approved_capacity_holds: Decimal,
    effective_at: datetime,
    actor_type: str,
    actor_id: UUID,
) -> tuple[CapacityCalculationResult, DecisionSnapshot]:
    if not capacity_currency:
        raise CapacityInputError("capacity_currency is required")
    decision_time = _require_aware_datetime("effective_at", effective_at)

    observation_ids = [request.valuation_observation_id for request in position_requests]
    if len(observation_ids) != len(set(observation_ids)):
        raise CapacityInputError("valuation observations cannot be duplicated")

    rows = (
        await session.scalars(
            select(ValuationObservation).where(ValuationObservation.id.in_(observation_ids))
        )
    ).all()
    observations_by_id = {row.id: row for row in rows}
    missing = [
        str(observation_id)
        for observation_id in observation_ids
        if observation_id not in observations_by_id
    ]
    if missing:
        raise CapacityInputError(f"valuation observations are missing: {','.join(missing)}")

    observations = [observations_by_id[observation_id] for observation_id in observation_ids]
    asset_position_ids = [observation.asset_position_id for observation in observations]
    if len(asset_position_ids) != len(set(asset_position_ids)):
        raise CapacityInputError("only one valuation observation per Asset Position is allowed")

    position_rows = (
        await session.scalars(select(AssetPosition).where(AssetPosition.id.in_(asset_position_ids)))
    ).all()
    positions_by_id = {row.id: row for row in position_rows}
    missing_positions = [
        str(position_id)
        for position_id in asset_position_ids
        if position_id not in positions_by_id
    ]
    if missing_positions:
        raise CapacityInputError(f"Asset Positions are missing: {','.join(missing_positions)}")

    asset_positions = [positions_by_id[position_id] for position_id in asset_position_ids]

    position_inputs: list[PositionCapacityInput] = []
    for request, observation in zip(position_requests, observations, strict=True):
        if observation.valuation_currency != capacity_currency:
            raise CapacityInputError(
                "all valuation observations must use the explicit capacity currency"
            )

        _require_aware_datetime("valuation observed_at", observation.observed_at)
        _require_aware_datetime("valuation received_at", observation.received_at)
        if observation.observed_at > decision_time or observation.received_at > decision_time:
            raise CapacityInputError(
                "valuation observation cannot be newer than the decision effective timestamp"
            )
        if observation.valid_until is not None:
            _require_aware_datetime("valuation valid_until", observation.valid_until)

        asset_position = positions_by_id[observation.asset_position_id]
        eligible_quantity = _require_decimal("eligible_quantity", request.eligible_quantity)
        if eligible_quantity > observation.valued_quantity:
            raise CapacityInputError(
                "eligible_quantity cannot exceed the immutable valued quantity"
            )
        if eligible_quantity > asset_position.quantity:
            raise CapacityInputError(
                "eligible_quantity cannot exceed the current Asset Position quantity"
            )

        position_inputs.append(
            PositionCapacityInput(
                valuation_observation_id=observation.id,
                eligible_quantity=eligible_quantity,
                approved_price=observation.unit_price,
                approved_fx_conversion=observation.fx_rate,
                fx_required=request.fx_required,
                pledgeable_fraction=request.pledgeable_fraction,
                advance_rate=request.advance_rate,
                freshness_status=observation.freshness_status,
                valid_until=observation.valid_until,
            )
        )

    result = calculate_guarantee_capacity(
        positions=position_inputs,
        resolved_policy_pack=resolved_policy_pack,
        capped_gross_backing_capacity=capped_gross_backing_capacity,
        reserved_guarantee_capacity=reserved_guarantee_capacity,
        active_guarantee_exposure=active_guarantee_exposure,
        other_approved_capacity_holds=other_approved_capacity_holds,
        effective_at=effective_at,
    )
    material_input_payload = _capacity_input_payload(
        observations=observations,
        asset_positions=asset_positions,
        requests=position_requests,
        capacity_currency=capacity_currency,
        capped_gross_backing_capacity=capped_gross_backing_capacity,
        reserved_guarantee_capacity=reserved_guarantee_capacity,
        active_guarantee_exposure=active_guarantee_exposure,
        other_approved_capacity_holds=other_approved_capacity_holds,
    )
    material_output_payload = _capacity_output_payload(result)
    external_references = [
        reference
        for observation in observations
        for reference in (
            observation.source_reference,
            observation.source_version_reference,
            observation.evidence_reference,
        )
        if reference is not None
    ]

    snapshot = await create_decision_snapshot(
        session,
        business_entity_type=business_entity_type,
        business_entity_id=business_entity_id,
        decision_type="GUARANTEE_CAPACITY",
        resolved_policy_pack=resolved_policy_pack,
        algorithm_code=result.algorithm_code,
        algorithm_version=result.algorithm_version,
        material_input_payload=material_input_payload,
        material_output_payload=material_output_payload,
        effective_at=decision_time,
        actor_type=actor_type,
        actor_id=actor_id,
        valuation_observation_ids=observation_ids,
        authoritative_external_references=external_references,
    )
    return result, snapshot
