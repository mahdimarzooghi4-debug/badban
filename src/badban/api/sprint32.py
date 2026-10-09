from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import InboxMessage, OutboxMessage
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_SYSTEM_OPERATOR,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/integration-delivery", tags=["integration-delivery-operations"])
OutboxStatus = Literal["QUEUED", "RETRY_SCHEDULED", "DEAD_LETTERED", "PUBLISHED"]
InboxStatus = Literal["PENDING", "PROCESSED"]


class DeliveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OutboxDeliveryView(DeliveryModel):
    id: UUID
    event_type: str
    event_version: int
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    correlation_id: UUID | None
    causation_id: UUID | None
    occurred_at: datetime
    created_at: datetime
    status: OutboxStatus
    published_at: datetime | None
    publish_attempts: int
    next_attempt_at: datetime | None
    dead_lettered_at: datetime | None
    replay_count: int


class InboxDeliveryView(DeliveryModel):
    id: UUID
    source_id: str
    event_type: str
    external_event_id: str
    received_at: datetime
    processed_at: datetime | None
    status: InboxStatus


class OutboxDeliveryPage(DeliveryModel):
    observed_at: datetime
    items: list[OutboxDeliveryView]
    next_cursor: UUID | None


class InboxDeliveryPage(DeliveryModel):
    observed_at: datetime
    items: list[InboxDeliveryView]
    next_cursor: UUID | None


class DeliveryStatusSummary(DeliveryModel):
    observed_at: datetime
    outbox: dict[str, int]
    inbox: dict[str, int]


async def _authorize_global(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_AUDITOR, ROLE_SYSTEM_OPERATOR},
            scope_type=SCOPE_GLOBAL,
            scope_id=None,
            allow_global=False,
            action="INTEGRATION_DELIVERY_READ",
            target_type="IntegrationDelivery",
            target_id="GLOBAL",
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(
            403, exc.code, "Global integration-delivery read permission required"
        ) from exc


def _outbox_status(row: OutboxMessage, observed_at: datetime) -> OutboxStatus:
    if row.published_at is not None:
        return "PUBLISHED"
    if row.dead_lettered_at is not None:
        return "DEAD_LETTERED"
    if row.next_attempt_at is not None and row.next_attempt_at > observed_at:
        return "RETRY_SCHEDULED"
    return "QUEUED"


def _outbox_predicate(status: OutboxStatus, observed_at: datetime):
    if status == "PUBLISHED":
        return OutboxMessage.published_at.is_not(None)
    if status == "DEAD_LETTERED":
        return OutboxMessage.dead_lettered_at.is_not(None)
    unpublished = OutboxMessage.published_at.is_(None) & OutboxMessage.dead_lettered_at.is_(None)
    if status == "RETRY_SCHEDULED":
        return unpublished & (OutboxMessage.next_attempt_at > observed_at)
    return unpublished & or_(
        OutboxMessage.next_attempt_at.is_(None),
        OutboxMessage.next_attempt_at <= observed_at,
    )


def _inbox_predicate(status: InboxStatus):
    return (
        InboxMessage.processed_at.is_not(None)
        if status == "PROCESSED"
        else InboxMessage.processed_at.is_(None)
    )


def _outbox_view(row: OutboxMessage, observed_at: datetime) -> OutboxDeliveryView:
    return OutboxDeliveryView(
        id=row.id,
        event_type=row.event_type,
        event_version=row.event_version,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        aggregate_version=row.aggregate_version,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        status=_outbox_status(row, observed_at),
        published_at=row.published_at,
        publish_attempts=row.publish_attempts,
        next_attempt_at=row.next_attempt_at,
        dead_lettered_at=row.dead_lettered_at,
        replay_count=row.replay_count,
    )


def _inbox_view(row: InboxMessage) -> InboxDeliveryView:
    return InboxDeliveryView(
        id=row.id,
        source_id=row.source_id,
        event_type=row.event_type,
        external_event_id=row.external_event_id,
        received_at=row.received_at,
        processed_at=row.processed_at,
        status="PROCESSED" if row.processed_at is not None else "PENDING",
    )


@router.get(
    "/outbox",
    response_model=OutboxDeliveryPage,
    description=(
        "GLOBAL AUDITOR/SYSTEM_OPERATOR only. Immutable business-envelope metadata "
        "and observed delivery lifecycle; no event payload, free-text failure "
        "reason, credential or replay action. Stable filtered keyset pagination."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        422: {"description": "DELIVERY_CURSOR_INVALID or invalid filter"},
    },
)
async def list_outbox_delivery(
    status: OutboxStatus | None = None,
    event_type: str | None = Query(default=None, min_length=1, max_length=160),
    aggregate_type: str | None = Query(default=None, min_length=1, max_length=120),
    correlation_id_filter: UUID | None = Query(default=None, alias="correlation_id"),
    limit: int = Query(default=50, ge=1, le=100),
    after: UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> OutboxDeliveryPage:
    await _authorize_global(session, principal=principal, correlation_id=correlation_id)
    observed_at = datetime.now(UTC)
    filters = []
    if status is not None:
        filters.append(_outbox_predicate(status, observed_at))
    if event_type is not None:
        filters.append(OutboxMessage.event_type == event_type)
    if aggregate_type is not None:
        filters.append(OutboxMessage.aggregate_type == aggregate_type)
    if correlation_id_filter is not None:
        filters.append(OutboxMessage.correlation_id == correlation_id_filter)
    stmt = select(OutboxMessage).where(*filters)
    if after is not None:
        anchor = await session.scalar(
            select(OutboxMessage).where(OutboxMessage.id == after, *filters)
        )
        if anchor is None:
            raise ApiError(422, "DELIVERY_CURSOR_INVALID", "Cursor is outside filtered outbox")
        stmt = stmt.where(
            tuple_(OutboxMessage.created_at, OutboxMessage.id)
            > tuple_(anchor.created_at, anchor.id)
        )
    rows = (
        await session.scalars(
            stmt.order_by(OutboxMessage.created_at, OutboxMessage.id).limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    return OutboxDeliveryPage(
        observed_at=observed_at,
        items=[_outbox_view(row, observed_at) for row in page],
        next_cursor=page[-1].id if len(rows) > limit and page else None,
    )


@router.get(
    "/inbox",
    response_model=InboxDeliveryPage,
    description=(
        "GLOBAL AUDITOR/SYSTEM_OPERATOR only. Authenticated inbox processing "
        "metadata without normalized/raw provider payloads or evidence content. "
        "Cursor is bound to the full authorized filtered stream."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        422: {"description": "DELIVERY_CURSOR_INVALID or invalid filter"},
    },
)
async def list_inbox_delivery(
    status: InboxStatus | None = None,
    source_id: str | None = Query(default=None, min_length=1, max_length=160),
    event_type: str | None = Query(default=None, min_length=1, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    after: UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> InboxDeliveryPage:
    await _authorize_global(session, principal=principal, correlation_id=correlation_id)
    observed_at = datetime.now(UTC)
    filters = []
    if status is not None:
        filters.append(_inbox_predicate(status))
    if source_id is not None:
        filters.append(InboxMessage.source_id == source_id)
    if event_type is not None:
        filters.append(InboxMessage.event_type == event_type)
    stmt = select(InboxMessage).where(*filters)
    if after is not None:
        anchor = await session.scalar(
            select(InboxMessage).where(InboxMessage.id == after, *filters)
        )
        if anchor is None:
            raise ApiError(422, "DELIVERY_CURSOR_INVALID", "Cursor is outside filtered inbox")
        stmt = stmt.where(
            tuple_(InboxMessage.received_at, InboxMessage.id)
            > tuple_(anchor.received_at, anchor.id)
        )
    rows = (
        await session.scalars(
            stmt.order_by(InboxMessage.received_at, InboxMessage.id).limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    return InboxDeliveryPage(
        observed_at=observed_at,
        items=[_inbox_view(row) for row in page],
        next_cursor=page[-1].id if len(rows) > limit and page else None,
    )


@router.get(
    "/outbox/{message_id}",
    response_model=OutboxDeliveryView,
    description="GLOBAL AUDITOR/SYSTEM_OPERATOR; read-only delivery metadata, no payload.",
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "OUTBOX_MESSAGE_NOT_FOUND"},
    },
)
async def get_outbox_delivery(
    message_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> OutboxDeliveryView:
    await _authorize_global(session, principal=principal, correlation_id=correlation_id)
    row = await session.get(OutboxMessage, message_id)
    if row is None:
        raise ApiError(404, "OUTBOX_MESSAGE_NOT_FOUND", "Outbox message was not found")
    return _outbox_view(row, datetime.now(UTC))


@router.get(
    "/inbox/{message_id}",
    response_model=InboxDeliveryView,
    description="GLOBAL AUDITOR/SYSTEM_OPERATOR, read-only inbox metadata; no provider payload.",
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "INBOX_MESSAGE_NOT_FOUND"},
    },
)
async def get_inbox_delivery(
    message_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> InboxDeliveryView:
    await _authorize_global(session, principal=principal, correlation_id=correlation_id)
    row = await session.get(InboxMessage, message_id)
    if row is None:
        raise ApiError(404, "INBOX_MESSAGE_NOT_FOUND", "Inbox message was not found")
    return _inbox_view(row)


@router.get(
    "/summary",
    response_model=DeliveryStatusSummary,
    description=(
        "GLOBAL AUDITOR/SYSTEM_OPERATOR: observed counts of persisted outbox/inbox "
        "delivery states; NOT an operational health PASS or transaction authorization. "
        "No invented age limits or alert thresholds."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
    },
)
async def get_delivery_summary(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> DeliveryStatusSummary:
    await _authorize_global(session, principal=principal, correlation_id=correlation_id)
    observed_at = datetime.now(UTC)
    outbox = {}
    for state in ("QUEUED", "RETRY_SCHEDULED", "DEAD_LETTERED", "PUBLISHED"):
        outbox[state] = int(
            await session.scalar(
                select(func.count())
                .select_from(OutboxMessage)
                .where(_outbox_predicate(state, observed_at))
            )
            or 0
        )
    inbox = {}
    for state in ("PENDING", "PROCESSED"):
        inbox[state] = int(
            await session.scalar(
                select(func.count()).select_from(InboxMessage).where(_inbox_predicate(state))
            )
            or 0
        )
    return DeliveryStatusSummary(observed_at=observed_at, outbox=outbox, inbox=inbox)
