from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import (
    CreditProductVersion,
    CreditProvider,
    GuaranteeCase,
    ParticipationEpisode,
)
from badban.security.audit import append_audit
from badban.security.authorization import SCOPE_PROGRAM


async def create_guarantee_request(
    session: AsyncSession,
    *,
    participation_episode_id: UUID,
    provider_id: UUID,
    credit_product_version_id: UUID,
    requested_principal: Decimal,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> GuaranteeCase:
    episode = await session.get(ParticipationEpisode, participation_episode_id)
    if episode is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Participation Episode was not found")

    provider = await session.get(CreditProvider, provider_id)
    if provider is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Provider was not found")

    product = await session.get(CreditProductVersion, credit_product_version_id)
    if product is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Product Version was not found")

    if product.provider_id != provider.id:
        raise ApiError(
            422,
            "GUARANTEE_REQUEST_INVALID",
            "Credit Product Version does not belong to the selected provider",
        )
    if requested_principal <= 0:
        raise ApiError(
            422,
            "GUARANTEE_REQUEST_INVALID",
            "Requested principal must be greater than zero",
        )
    if requested_principal < product.min_principal or requested_principal > product.max_principal:
        raise ApiError(
            422,
            "GUARANTEE_REQUEST_INVALID",
            "Requested principal is outside the selected product version bounds",
        )

    guarantee = GuaranteeCase(
        participation_episode_id=episode.id,
        provider_id=provider.id,
        credit_product_version_id=product.id,
        policy_pack_id=None,
        state="REQUESTED",
        requested_principal=requested_principal,
        reserved_guarantee_amount=None,
        issued_guarantee_amount=None,
        current_guarantee_exposure=Decimal("0"),
        guarantee_mode=product.guarantee_mode,
        reservation_expires_at=None,
        legal_guarantee_external_id=None,
        legal_guarantee_issuer_id=None,
        external_loan_mirror_id=None,
        risk_snapshot_id=None,
        version=1,
    )
    session.add(guarantee)
    await session.flush()

    append_audit(
        session,
        aggregate_type="GuaranteeCase",
        aggregate_id=str(guarantee.id),
        aggregate_version=guarantee.version,
        action="GUARANTEE_REQUEST_CREATE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state={
            "state": guarantee.state,
            "participation_episode_id": str(guarantee.participation_episode_id),
            "provider_id": str(guarantee.provider_id),
            "credit_product_version_id": str(guarantee.credit_product_version_id),
            "requested_principal": str(guarantee.requested_principal),
            "guarantee_mode": guarantee.guarantee_mode,
            "policy_pack_id": None,
        },
        scope={"scope_type": SCOPE_PROGRAM, "scope_id": str(episode.program_id)},
    )
    await session.flush()
    return guarantee
