from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.infrastructure.persistence.models import PolicyVersion


@dataclass(frozen=True, slots=True)
class ResolvedPolicyPack:
    policy_pack_id: UUID
    policy_code: str
    version_number: int
    component_version_ids: tuple[UUID, ...]


async def _resolve_component_version_ids(
    session: AsyncSession,
    policy: PolicyVersion,
) -> tuple[UUID, ...]:
    raw_component_ids = policy.payload.get("component_version_ids")
    if not isinstance(raw_component_ids, list) or not all(
        isinstance(value, str) for value in raw_component_ids
    ):
        raise ApiError(
            409,
            "POLICY_RESOLUTION_UNAVAILABLE",
            "ACTIVE Pilot Policy Pack has an invalid component manifest",
        )

    try:
        component_ids = tuple(UUID(value) for value in raw_component_ids)
    except ValueError as exc:
        raise ApiError(
            409,
            "POLICY_RESOLUTION_UNAVAILABLE",
            "ACTIVE Pilot Policy Pack has an invalid component manifest",
        ) from exc

    if not component_ids:
        return component_ids

    components = (
        await session.scalars(select(PolicyVersion).where(PolicyVersion.id.in_(component_ids)))
    ).all()
    components_by_id = {component.id: component for component in components}

    missing_ids = [
        str(component_id) for component_id in component_ids if component_id not in components_by_id
    ]
    if missing_ids:
        raise ApiError(
            409,
            "POLICY_COMPONENT_MISSING",
            "Pilot Policy Pack references missing PolicyVersion components",
            {"component_version_ids": missing_ids},
        )

    incompatible_ids = [
        str(component_id)
        for component_id in component_ids
        if components_by_id[component_id].policy_type == "PILOT_POLICY_PACK"
    ]
    if incompatible_ids:
        raise ApiError(
            409,
            "POLICY_COMPONENT_INCOMPATIBLE",
            "Pilot Policy Pack references incompatible component versions",
            {"component_version_ids": incompatible_ids},
        )

    return component_ids


async def resolve_active_policy_pack(
    session: AsyncSession,
    *,
    scope_definition: dict[str, object],
    effective_at: datetime,
) -> ResolvedPolicyPack:
    matches = (
        await session.scalars(
            select(PolicyVersion).where(
                PolicyVersion.policy_type == "PILOT_POLICY_PACK",
                PolicyVersion.lifecycle_status == "ACTIVE",
                PolicyVersion.scope_definition == scope_definition,
                or_(
                    PolicyVersion.effective_from.is_(None),
                    PolicyVersion.effective_from <= effective_at,
                ),
                or_(
                    PolicyVersion.effective_to.is_(None),
                    PolicyVersion.effective_to > effective_at,
                ),
            )
        )
    ).all()

    if not matches:
        raise ApiError(
            409,
            "POLICY_SCOPE_NOT_FOUND",
            "No ACTIVE Pilot Policy Pack matches the exact scope and effective time",
        )

    if len(matches) > 1:
        raise ApiError(
            409,
            "POLICY_SCOPE_AMBIGUOUS",
            "Multiple ACTIVE Pilot Policy Packs match the exact scope and effective time",
            {"policy_pack_ids": sorted(str(policy.id) for policy in matches)},
        )

    policy = matches[0]
    if policy.payload_hash is None or policy.payload_hash != canonical_request_hash(policy.payload):
        raise ApiError(
            409,
            "POLICY_RESOLUTION_UNAVAILABLE",
            "ACTIVE Pilot Policy Pack failed payload integrity verification",
        )
    component_version_ids = await _resolve_component_version_ids(session, policy)
    return ResolvedPolicyPack(
        policy_pack_id=policy.id,
        policy_code=policy.policy_code,
        version_number=policy.version_number,
        component_version_ids=component_version_ids,
    )
