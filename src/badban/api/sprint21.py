from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.reserve_metrics import (
    ReserveMetricsError,
    create_reserve_metrics_snapshot,
    reserve_metrics_reference,
)
from badban.infrastructure.persistence.models import GuaranteeReserveMetricsSnapshot
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_RISK,
    SCOPE_LEGAL_ENTITY,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/finance", tags=["reserve-metrics"])

DecimalString = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
]


class ReserveMetricsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_entity_id: UUID
    currency: str = Field(min_length=1, max_length=16)


class ReserveMetricsView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legal_entity_id: UUID
    currency: str
    cash_control_balance: DecimalString
    designated_balance: DecimalString
    source_journal_count: int
    source_posting_count: int
    source_journal_ids: list[str]
    source_posting_ids: list[str]
    source_fingerprint: str
    algorithm_code: str
    algorithm_version: str
    actor_type: str
    actor_id: UUID
    correlation_id: UUID
    evaluated_at: object
    created_at: object
    reserve_metrics_reference: str


async def _authorize(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    legal_entity_id: UUID,
    action: str,
    target_id: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=SCOPE_LEGAL_ENTITY,
            scope_id=legal_entity_id,
            allow_global=True,
            action=action,
            target_type="GuaranteeReserveMetricsSnapshot",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for reserve metrics scope") from exc


def _view(snapshot: GuaranteeReserveMetricsSnapshot) -> ReserveMetricsView:
    return ReserveMetricsView(
        id=snapshot.id,
        legal_entity_id=snapshot.legal_entity_id,
        currency=snapshot.currency,
        cash_control_balance=snapshot.cash_control_balance,
        designated_balance=snapshot.designated_balance,
        source_journal_count=snapshot.source_journal_count,
        source_posting_count=snapshot.source_posting_count,
        source_journal_ids=snapshot.source_journal_ids,
        source_posting_ids=snapshot.source_posting_ids,
        source_fingerprint=snapshot.source_fingerprint,
        algorithm_code=snapshot.algorithm_code,
        algorithm_version=snapshot.algorithm_version,
        actor_type=snapshot.actor_type,
        actor_id=snapshot.actor_id,
        correlation_id=snapshot.correlation_id,
        evaluated_at=snapshot.evaluated_at,
        created_at=snapshot.created_at,
        reserve_metrics_reference=reserve_metrics_reference(snapshot),
    )


@router.post("/reserve-metrics/snapshots", response_model=ReserveMetricsView)
async def create_snapshot(
    body: ReserveMetricsCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ReserveMetricsView:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_FINANCE_RECONCILIATION, ROLE_RISK},
        legal_entity_id=body.legal_entity_id,
        action="RESERVE_METRICS_SNAPSHOT_CREATE",
        target_id=str(body.legal_entity_id),
        correlation_id=correlation_id,
    )
    try:
        snapshot = await create_reserve_metrics_snapshot(
            session,
            legal_entity_id=body.legal_entity_id,
            currency=body.currency,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    except ReserveMetricsError as exc:
        if exc.code == "RESERVE_METRICS_LEGAL_ENTITY_NOT_FOUND":
            raise ApiError(404, exc.code, str(exc)) from exc
        raise ApiError(422, exc.code, str(exc)) from exc
    await session.commit()
    return _view(snapshot)


@router.get("/reserve-metrics/snapshots/{snapshot_id}", response_model=ReserveMetricsView)
async def get_snapshot(
    snapshot_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ReserveMetricsView:
    snapshot = await session.get(GuaranteeReserveMetricsSnapshot, snapshot_id)
    if snapshot is None:
        raise ApiError(404, "RESERVE_METRICS_SNAPSHOT_NOT_FOUND", "Reserve metrics snapshot not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_FINANCE_RECONCILIATION, ROLE_RISK, ROLE_AUDITOR},
        legal_entity_id=snapshot.legal_entity_id,
        action="RESERVE_METRICS_SNAPSHOT_READ",
        target_id=str(snapshot.id),
        correlation_id=correlation_id,
    )
    return _view(snapshot)
