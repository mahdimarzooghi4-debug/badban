from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
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
    requested_principal: str = Field(min_length=1, max_length=80)


class GuaranteeCaseView(BaseModel):
    id: UUID
    participation_episode_id: UUID
    provider_id: UUID
    credit_product_version_id: UUID
    policy_pack_id: UUID | None
    state: str
    requested_principal: str
    reserved_guarantee_amount: str | None
    issued_guarantee_amount: str | None
    current_guarantee_exposure: str
    guarantee_mode: str
    reservation_expires_at: datetime | None
    legal_guarantee_external_id: str | None
    legal_guarantee_issuer_id: UUID | None
    external_loan_mirror_id: UUID | None
    risk_snapshot_id: UUID | None
    version: int


def _parse_decimal_string(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ApiError(
            422,
            "GUARANTEE_REQUEST_INVALID",
            "Requested principal must be a decimal string",
        ) from exc
    if not parsed.is_finite():
        raise ApiError(
            422,
            "GUARANTEE_REQUEST_INVALID",
            "Requested principal must be a finite decimal string",
        )
    return parsed


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")


def _view(guarantee: GuaranteeCase) -> GuaranteeCaseView:
    return GuaranteeCaseView(
        id=guarantee.id,
        participation_episode_id=guarantee.participation_episode_id,
        provider_id=guarantee.provider_id,
        credit_product_version_id=guarantee.credit_product_version_id,
        policy_pack_id=guarantee.policy_pack_id,
        state=guarantee.state,
        requested_principal=_decimal_string(guarantee.requested_principal),
        reserved_guarantee_amount=(
            _decimal_string(guarantee.reserved_guarantee_amount)
            if guarantee.reserved_guarantee_amount is not None
            else None
        ),
        issued_guarantee_amount=(
            _decimal_string(guarantee.issued_guarantee_amount)
            if guarantee.issued_guarantee_amount is not None
            else None
        ),
        current_guarantee_exposure=_decimal_string(guarantee.current_guarantee_exposure),
        guarantee_mode=guarantee.guarantee_mode,
        reservation_expires_at=guarantee.reservation_expires_at,
        legal_guarantee_external_id=guarantee.legal_guarantee_external_id,
        legal_guarantee_issuer_id=guarantee.legal_guarantee_issuer_id,
        external_loan_mirror_id=guarantee.external_loan_mirror_id,
        risk_snapshot_id=guarantee.risk_snapshot_id,
        version=guarantee.version,
    )


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
    summary="Create guarantee request",
    description=(
        "Requires OPERATIONS authorization in the ParticipationEpisode program scope. "
        "Creates REQUESTED only; it does not reserve capacity or create exposure. "
        "requested_principal must be encoded as a decimal string."
    ),
    responses={
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "Referenced resource not found"},
        409: {"description": "IDEMPOTENCY_CONFLICT or IDEMPOTENCY_IN_PROGRESS"},
        422: {"description": "GUARANTEE_REQUEST_INVALID or invalid request schema"},
    },
)
async def create_guarantee_request_endpoint(
    body: GuaranteeRequestCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=200,
        description="Opaque retry key for guarantee request creation",
    ),
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
        requested_principal=_parse_decimal_string(body.requested_principal),
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
    )
    await session.refresh(guarantee)
    view = _view(guarantee)
    complete_idempotency(
        record,
        status_code=status.HTTP_201_CREATED,
        response_payload=view.model_dump(mode="json"),
    )
    await session.commit()
    return view
