from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import PolicyVersion


@dataclass(frozen=True, slots=True)
class ResolvedPolicyPack:
    policy_pack_id: UUID
    policy_code: str
    version_number: int


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
    return ResolvedPolicyPack(
        policy_pack_id=policy.id,
        policy_code=policy.policy_code,
        version_number=policy.version_number,
    )
