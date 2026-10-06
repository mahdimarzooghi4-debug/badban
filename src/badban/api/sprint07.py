from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.guarantee_request import create_guarantee_request
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.infrastructure.persistence.models import GuaranteeCase, ParticipationEpisode
from badban.security.authorization import (
    ROLE_OPERATIONS,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1")


class GuaranteeRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participation_episode_id: UUID
    provider_id: UUID
    credit_product_version_id: UUID
    requested_principal: Decimal = Field(gt=0)


class GuaranteeCaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participation_episode_id: UUID
    provider_id: UUID
    credit_product_version_id: UUID
    policy_pack_id: UUID | None
    state: str
    requested_principal: Decimal
    reserved_guarantee_amount: Decimal | None
    issued_guarantee_amount: Decimal | None
    current_guarantee_exposure: Decimal
    guarantee_mode: str
    reservation_expires_at: object | None
    legal_guarantee_external_id: str | None
    legal_guarantee_issuer_id: UUID | None
    external_loan_mirror_id: UUID | None
    risk_snapshot_id: UUID | None
    version: int


async def _authorize_create(
    session: AsyncSession,
    *,
    principal: Principal,
    episode: ParticipationEpisode,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_OPERATIONS},
            scope_type=SCOPE_PROGRAM,
            scope_id=episode.program_id,
            allow_global=True,
            action="GUARANTEE_REQUEST_CREATE",
            target_type="ParticipationEpisode",
            target_id=str(episode.id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(
            403,
            exc.code,
            "Authorization denied for guarantee request creation",
        ) from exc


@router.post(
    "/guarantees",
    response_model=GuaranteeCaseView,
    status_code=status.HTTP_201_CREATED,
)
async def create_guarantee_request_endpoint(
    body: GuaranteeRequestCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> GuaranteeCaseView:
    episode = await session.get(ParticipationEpisode, body.participation_episode_id)
    if episode is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Participation Episode was not found")

    await _authorize_create(
        session,
        principal=principal,
        episode=episode,
        correlation_id=correlation_id,
    )

    record, replay = await acquire_idempotency(
        session,
        scope=f"guarantee:create:{principal.identity_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return GuaranteeCaseView.model_validate(replay)

    guarantee = await create_guarantee_request(
        session,
        participation_episode_id=body.participation_episode_id,
        provider_id=body.provider_id,
        credit_product_version_id=body.credit_product_version_id,
        requested_principal=body.requested_principal,
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
    )
    await session.refresh(guarantee)
    view = GuaranteeCaseView.model_validate(guarantee)
    complete_idempotency(
        record,
        status_code=status.HTTP_201_CREATED,
        response_payload=view.model_dump(mode="json"),
    )
    await session.commit()
    return view
