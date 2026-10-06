from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from badban.application.capacity import (
    CAPACITY_ALGORITHM_CODE,
    CAPACITY_ALGORITHM_VERSION,
    CapacityInputError,
    CapacityPositionRequest,
    PositionCapacityInput,
    calculate_and_snapshot_guarantee_capacity,
    calculate_guarantee_capacity,
    calculate_position_capacity,
)
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_resolution import ResolvedPolicyPack
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    DecisionSnapshot,
    Identity,
    JournalEntry,
    Participant,
    ParticipationEpisode,
    PolicyVersion,
    Program,
    ValuationObservation,
)


def _resolved_pack() -> ResolvedPolicyPack:
    return ResolvedPolicyPack(
        policy_pack_id=uuid4(),
        policy_code="SYNTHETIC_CAPACITY_PACK",
        version_number=7,
        component_version_ids=(uuid4(), uuid4()),
    )


def _position(
    *,
    quantity: Decimal = Decimal("2"),
    price: Decimal = Decimal("10"),
    fx: Decimal | None = Decimal("3"),
    fx_required: bool = True,
    pledgeable_fraction: Decimal = Decimal("0.75"),
    advance_rate: Decimal = Decimal("0.5"),
    freshness_status: str = "FRESH",
    valid_until: datetime | None = None,
) -> PositionCapacityInput:
    return PositionCapacityInput(
        valuation_observation_id=uuid4(),
        eligible_quantity=quantity,
        approved_price=price,
        approved_fx_conversion=fx,
        fx_required=fx_required,
        pledgeable_fraction=pledgeable_fraction,
        advance_rate=advance_rate,
        freshness_status=freshness_status,
        valid_until=valid_until or datetime.now(UTC) + timedelta(hours=1),
    )


def test_position_capacity_uses_exact_decimal_formula_without_quantization() -> None:
    effective_at = datetime.now(UTC)
    result = calculate_position_capacity(
        _position(
            quantity=Decimal("2.125"),
            price=Decimal("10.015"),
            fx=Decimal("1.125"),
            pledgeable_fraction=Decimal("0.875"),
            advance_rate=Decimal("0.625"),
        ),
        effective_at=effective_at,
    )

    expected_gross = Decimal("2.125") * Decimal("10.015") * Decimal("1.125")
    expected_pledgeable = expected_gross * Decimal("0.875")
    expected_backing = expected_pledgeable * Decimal("0.625")

    assert result.gross_market_value == expected_gross
    assert result.pledgeable_market_value == expected_pledgeable
    assert result.position_backing_capacity == expected_backing
    assert result.new_capacity_contribution == expected_backing
    assert result.freshness_eligible is True


def test_stale_expired_or_unknown_valuation_creates_no_new_capacity() -> None:
    effective_at = datetime.now(UTC)
    stale = calculate_position_capacity(
        _position(freshness_status="STALE"),
        effective_at=effective_at,
    )
    expired = calculate_position_capacity(
        _position(valid_until=effective_at - timedelta(seconds=1)),
        effective_at=effective_at,
    )
    unknown = PositionCapacityInput(
        valuation_observation_id=uuid4(),
        eligible_quantity=Decimal("2"),
        approved_price=Decimal("10"),
        approved_fx_conversion=None,
        fx_required=False,
        pledgeable_fraction=Decimal("0.75"),
        advance_rate=Decimal("0.5"),
        freshness_status="UNKNOWN",
        valid_until=None,
    )
    unknown_result = calculate_position_capacity(unknown, effective_at=effective_at)

    assert stale.position_backing_capacity > 0
    assert stale.new_capacity_contribution == 0
    assert expired.new_capacity_contribution == 0
    assert unknown_result.new_capacity_contribution == 0


def test_capacity_aggregate_subtracts_utilization_and_floors_at_zero() -> None:
    effective_at = datetime.now(UTC)
    pack = _resolved_pack()
    positions = [
        _position(quantity=Decimal("2"), price=Decimal("10"), fx=None, fx_required=False),
        _position(quantity=Decimal("1"), price=Decimal("20"), fx=None, fx_required=False),
    ]
    result = calculate_guarantee_capacity(
        positions=positions,
        resolved_policy_pack=pack,
        capped_gross_backing_capacity=Decimal("12"),
        reserved_guarantee_capacity=Decimal("4"),
        active_guarantee_exposure=Decimal("5"),
        other_approved_capacity_holds=Decimal("1"),
        effective_at=effective_at,
    )
    exhausted = calculate_guarantee_capacity(
        positions=positions,
        resolved_policy_pack=pack,
        capped_gross_backing_capacity=Decimal("12"),
        reserved_guarantee_capacity=Decimal("8"),
        active_guarantee_exposure=Decimal("5"),
        other_approved_capacity_holds=Decimal("1"),
        effective_at=effective_at,
    )

    assert result.uncapped_gross_backing_capacity == Decimal("15.000")
    assert result.available_guarantee_capacity == Decimal("2")
    assert exhausted.available_guarantee_capacity == Decimal("0")
    assert result.policy_pack_id == pack.policy_pack_id
    assert result.policy_pack_version == 7
    assert result.component_version_ids == pack.component_version_ids
    assert result.algorithm_code == CAPACITY_ALGORITHM_CODE
    assert result.algorithm_version == CAPACITY_ALGORITHM_VERSION


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pledgeable_fraction", Decimal("1.01")),
        ("advance_rate", Decimal("-0.01")),
        ("eligible_quantity", Decimal("-1")),
    ],
)
def test_invalid_position_values_fail_closed(field: str, value: Decimal) -> None:
    kwargs = {field: value}
    with pytest.raises(CapacityInputError):
        calculate_position_capacity(
            _position(**kwargs),  # type: ignore[arg-type]
            effective_at=datetime.now(UTC),
        )


def test_float_and_missing_required_fx_are_rejected() -> None:
    with pytest.raises(CapacityInputError):
        calculate_position_capacity(
            _position(quantity=1.5),  # type: ignore[arg-type]
            effective_at=datetime.now(UTC),
        )

    with pytest.raises(CapacityInputError):
        calculate_position_capacity(
            _position(fx=None, fx_required=True),
            effective_at=datetime.now(UTC),
        )


def test_missing_or_invalid_cap_and_negative_utilization_fail_closed() -> None:
    pack = _resolved_pack()
    position = _position(fx=None, fx_required=False)
    with pytest.raises(CapacityInputError):
        calculate_guarantee_capacity(
            positions=[position],
            resolved_policy_pack=pack,
            capped_gross_backing_capacity=Decimal("100"),
            reserved_guarantee_capacity=Decimal("0"),
            active_guarantee_exposure=Decimal("0"),
            other_approved_capacity_holds=Decimal("0"),
            effective_at=datetime.now(UTC),
        )

    with pytest.raises(CapacityInputError):
        calculate_guarantee_capacity(
            positions=[position],
            resolved_policy_pack=pack,
            capped_gross_backing_capacity=Decimal("5"),
            reserved_guarantee_capacity=Decimal("-1"),
            active_guarantee_exposure=Decimal("0"),
            other_approved_capacity_holds=Decimal("0"),
            effective_at=datetime.now(UTC),
        )

    with pytest.raises(CapacityInputError):
        calculate_guarantee_capacity(
            positions=[position],
            resolved_policy_pack=pack,
            capped_gross_backing_capacity=None,  # type: ignore[arg-type]
            reserved_guarantee_capacity=Decimal("0"),
            active_guarantee_exposure=Decimal("0"),
            other_approved_capacity_holds=Decimal("0"),
            effective_at=datetime.now(UTC),
        )


def test_same_inputs_and_versions_reproduce_same_result() -> None:
    effective_at = datetime.now(UTC)
    pack = _resolved_pack()
    position = _position(fx=None, fx_required=False)
    kwargs = {
        "positions": [position],
        "resolved_policy_pack": pack,
        "capped_gross_backing_capacity": Decimal("5"),
        "reserved_guarantee_capacity": Decimal("1"),
        "active_guarantee_exposure": Decimal("1"),
        "other_approved_capacity_holds": Decimal("1"),
        "effective_at": effective_at,
    }

    assert calculate_guarantee_capacity(**kwargs) == calculate_guarantee_capacity(**kwargs)


async def _seed_capacity_evidence(
    database,
    *,
    stale: bool = False,
) -> tuple[Identity, AssetPosition, ValuationObservation, ResolvedPolicyPack]:
    actor = Identity(
        identity_type="SYSTEM",
        external_subject=f"capacity-system-{uuid4()}",
        status="ACTIVE",
    )
    participant = Participant(
        external_reference=f"capacity-participant-{uuid4()}",
        lifecycle_status="ACTIVE",
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all([actor, participant])
            await session.flush()
            program = Program(
                code=f"CAP-{uuid4().hex[:8]}",
                name="Capacity Test Program",
                status="ACTIVE",
                created_by=actor.id,
            )
            asset_type = AssetType(
                asset_code=f"ASSET-{uuid4().hex[:8]}",
                name="Synthetic Capacity Asset",
                status="ACTIVE",
                unit_code="UNIT",
                quantity_scale=18,
                currency_or_valuation_currency="IRR",
                eligibility_metadata={},
                custody_restriction_metadata={},
                created_by=actor.id,
            )
            session.add_all([program, asset_type])
            await session.flush()
            episode = ParticipationEpisode(
                participant_id=participant.id,
                program_id=program.id,
                status="ACTIVE",
                consent_state="ACCEPTED",
                started_at=datetime.now(UTC) - timedelta(days=1),
                created_by=actor.id,
            )
            session.add(episode)
            await session.flush()
            position = AssetPosition(
                participation_episode_id=episode.id,
                program_id=program.id,
                asset_type_id=asset_type.id,
                ownership_funding_type="PARTICIPANT_OWNED",
                legal_owner_participant_id=participant.id,
                legal_owner_entity_id=None,
                quantity=Decimal("2"),
                unit_code="UNIT",
                lifecycle_status="ACTIVE",
                source_reference="synthetic-capacity-position",
                created_by=actor.id,
            )
            session.add(position)
            await session.flush()

            now = datetime.now(UTC)
            observation = ValuationObservation(
                asset_position_id=position.id,
                valued_quantity=Decimal("2"),
                unit_price=Decimal("10"),
                valuation_currency="IRR",
                fx_rate=None,
                gross_market_value=Decimal("20"),
                source_name="synthetic-approved-source",
                source_reference="quote:capacity:1",
                source_version_reference="source:v1",
                observed_at=now - (timedelta(hours=2) if stale else timedelta(seconds=1)),
                received_at=now,
                valid_until=(now - timedelta(minutes=1) if stale else now + timedelta(hours=1)),
                freshness_status="STALE" if stale else "FRESH",
                evidence_reference="evidence://capacity/1",
                created_by=actor.id,
            )
            session.add(observation)

            pack_payload = {"component_version_ids": []}
            pack = PolicyVersion(
                policy_type="PILOT_POLICY_PACK",
                policy_code="CAPACITY_TEST_PACK",
                version_number=1,
                lifecycle_status="ACTIVE",
                scope_definition={"pilot_scope": "bounded-pilot"},
                payload=pack_payload,
                payload_hash=canonical_request_hash(pack_payload),
                schema_version="1",
                activated_at=now,
                created_by=actor.id,
                approved_by=actor.id,
                approved_at=now,
                version=4,
            )
            session.add(pack)
            await session.flush()

            resolved = ResolvedPolicyPack(
                policy_pack_id=pack.id,
                policy_code=pack.policy_code,
                version_number=pack.version_number,
                component_version_ids=(),
            )
            return actor, position, observation, resolved


@pytest.mark.integration
async def test_capacity_application_service_captures_snapshot_without_financial_side_effects(
    database,
    clean_sprint03_tables,
    clean_sprint04_policy_tables,
) -> None:
    actor, position, observation, resolved = await _seed_capacity_evidence(database)
    effective_at = datetime.now(UTC)

    async with database.session_factory() as session:
        async with session.begin():
            result, snapshot = await calculate_and_snapshot_guarantee_capacity(
                session,
                business_entity_type="PARTICIPATION_EPISODE",
                business_entity_id=str(position.participation_episode_id),
                position_requests=[
                    CapacityPositionRequest(
                        valuation_observation_id=observation.id,
                        eligible_quantity=Decimal("2"),
                        pledgeable_fraction=Decimal("0.75"),
                        advance_rate=Decimal("0.5"),
                        fx_required=False,
                    )
                ],
                capacity_currency="IRR",
                resolved_policy_pack=resolved,
                capped_gross_backing_capacity=Decimal("7"),
                reserved_guarantee_capacity=Decimal("1"),
                active_guarantee_exposure=Decimal("2"),
                other_approved_capacity_holds=Decimal("1"),
                effective_at=effective_at,
                actor_type=actor.identity_type,
                actor_id=actor.id,
            )
            snapshot_id = snapshot.id

    async with database.session_factory() as session:
        stored_snapshot = await session.get(DecisionSnapshot, snapshot_id)
        journal_count = await session.scalar(select(func.count()).select_from(JournalEntry))
        stored_position = await session.get(AssetPosition, position.id)

    assert result.uncapped_gross_backing_capacity == Decimal("7.500")
    assert result.available_guarantee_capacity == Decimal("3")
    assert stored_snapshot is not None
    assert stored_snapshot.decision_type == "GUARANTEE_CAPACITY"
    assert stored_snapshot.policy_pack_id == resolved.policy_pack_id
    assert stored_snapshot.algorithm_code == CAPACITY_ALGORITHM_CODE
    assert stored_snapshot.algorithm_version == CAPACITY_ALGORITHM_VERSION
    assert stored_snapshot.valuation_observation_ids == [str(observation.id)]
    assert stored_snapshot.authoritative_external_references == [
        "quote:capacity:1",
        "evidence://capacity/1",
    ]
    assert stored_snapshot.material_input_payload["positions"][0]["approved_price"] == "10"
    assert stored_snapshot.material_output_payload["available_guarantee_capacity"] == "3"
    assert journal_count == 0
    assert stored_position is not None
    assert stored_position.quantity == Decimal("2")


@pytest.mark.integration
async def test_capacity_service_fails_closed_for_stale_observation_and_missing_fx(
    database,
    clean_sprint03_tables,
    clean_sprint04_policy_tables,
) -> None:
    actor, position, observation, resolved = await _seed_capacity_evidence(database, stale=True)

    async with database.session_factory() as session:
        async with session.begin():
            result, _ = await calculate_and_snapshot_guarantee_capacity(
                session,
                business_entity_type="ASSET_POSITION",
                business_entity_id=str(position.id),
                position_requests=[
                    CapacityPositionRequest(
                        valuation_observation_id=observation.id,
                        eligible_quantity=Decimal("2"),
                        pledgeable_fraction=Decimal("0.75"),
                        advance_rate=Decimal("0.5"),
                        fx_required=False,
                    )
                ],
                capacity_currency="IRR",
                resolved_policy_pack=resolved,
                capped_gross_backing_capacity=Decimal("0"),
                reserved_guarantee_capacity=Decimal("0"),
                active_guarantee_exposure=Decimal("0"),
                other_approved_capacity_holds=Decimal("0"),
                effective_at=datetime.now(UTC),
                actor_type=actor.identity_type,
                actor_id=actor.id,
            )

    assert result.uncapped_gross_backing_capacity == Decimal("0")
    assert result.available_guarantee_capacity == Decimal("0")

    async with database.session_factory() as session:
        with pytest.raises(CapacityInputError):
            async with session.begin():
                await calculate_and_snapshot_guarantee_capacity(
                    session,
                    business_entity_type="ASSET_POSITION",
                    business_entity_id=str(position.id),
                    position_requests=[
                        CapacityPositionRequest(
                            valuation_observation_id=observation.id,
                            eligible_quantity=Decimal("2"),
                            pledgeable_fraction=Decimal("0.75"),
                            advance_rate=Decimal("0.5"),
                            fx_required=True,
                        )
                    ],
                    capacity_currency="IRR",
                    resolved_policy_pack=resolved,
                    capped_gross_backing_capacity=Decimal("0"),
                    reserved_guarantee_capacity=Decimal("0"),
                    active_guarantee_exposure=Decimal("0"),
                    other_approved_capacity_holds=Decimal("0"),
                    effective_at=datetime.now(UTC),
                    actor_type=actor.identity_type,
                    actor_id=actor.id,
                )
