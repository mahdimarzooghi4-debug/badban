from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_resolution import ResolvedPolicyPack
from badban.infrastructure.persistence.models import DecisionSnapshot


async def create_decision_snapshot(
    session: AsyncSession,
    *,
    business_entity_type: str,
    business_entity_id: str,
    decision_type: str,
    resolved_policy_pack: ResolvedPolicyPack,
    algorithm_code: str,
    algorithm_version: str,
    material_input_payload: dict[str, Any],
    material_output_payload: dict[str, Any],
    effective_at: datetime,
    actor_type: str,
    actor_id: UUID,
    valuation_observation_ids: Sequence[UUID] = (),
    authoritative_external_references: Sequence[str] = (),
    risk_snapshot_id: UUID | None = None,
) -> DecisionSnapshot:
    snapshot = DecisionSnapshot(
        business_entity_type=business_entity_type,
        business_entity_id=business_entity_id,
        decision_type=decision_type,
        policy_pack_id=resolved_policy_pack.policy_pack_id,
        policy_pack_version=resolved_policy_pack.version_number,
        component_version_ids=[
            str(component_id) for component_id in resolved_policy_pack.component_version_ids
        ],
        algorithm_code=algorithm_code,
        algorithm_version=algorithm_version,
        material_input_payload=material_input_payload,
        material_output_payload=material_output_payload,
        input_hash=canonical_request_hash(material_input_payload),
        output_hash=canonical_request_hash(material_output_payload),
        valuation_observation_ids=[
            str(observation_id) for observation_id in valuation_observation_ids
        ],
        authoritative_external_references=list(authoritative_external_references),
        risk_snapshot_id=risk_snapshot_id,
        effective_at=effective_at,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def get_decision_snapshot(
    session: AsyncSession,
    snapshot_id: UUID,
) -> DecisionSnapshot:
    snapshot = await session.get(DecisionSnapshot, snapshot_id)
    if snapshot is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "DecisionSnapshot was not found")
    return snapshot
