from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import AuditEvent
from badban.security.authorization import (
    ROLE_AUDITOR,
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/audit", tags=["governed-audit-trail"])


class AuditReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuditEventMetadata(AuditReadModel):
    """Deliberately excludes generic previous/new-state JSON and arbitrary scope JSON."""

    id: UUID
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int | None
    action: str
    actor_type: str
    actor_id: UUID
    reason_code: str | None
    policy_pack_id: UUID | None
    evidence_reference: str | None
    correlation_id: UUID
    causation_id: UUID | None
    outcome: str
    occurred_at: datetime


class AuditEventPage(AuditReadModel):
    program_id: UUID | None
    items: list[AuditEventMetadata]
    next_cursor: UUID | None


def _metadata(event: AuditEvent) -> AuditEventMetadata:
    return AuditEventMetadata(
        id=event.id,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        aggregate_version=event.aggregate_version,
        action=event.action,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        reason_code=event.reason_code,
        policy_pack_id=event.policy_pack_id,
        evidence_reference=event.evidence_reference,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        outcome=event.outcome,
        occurred_at=event.occurred_at,
    )


async def _authorized_filters(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
    program_id: UUID | None,
) -> list:
    """A Program grant sees only explicitly PROGRAM-tagged rows; no guessed lineage.

    Unscoped/global records (including legacy events lacking scope) require an
    actual GLOBAL AUDITOR grant. A Program grant never upgrades to that scope.
    """
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_AUDITOR},
            scope_type=SCOPE_PROGRAM if program_id is not None else SCOPE_GLOBAL,
            scope_id=program_id,
            allow_global=program_id is not None,
            action="AUDIT_TRAIL_READ",
            target_type="AuditEvent",
            target_id=str(program_id) if program_id is not None else "GLOBAL",
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for audit scope") from exc

    if program_id is None:
        return []
    # JSONB scope is append-time metadata, not a reason to infer a scope
    # from aggregate_type/id, actor_id or an untrusted request parameter.
    return [
        AuditEvent.scope["scope_type"].astext == SCOPE_PROGRAM,
        AuditEvent.scope["scope_id"].astext == str(program_id),
    ]


async def _query_page(
    session: AsyncSession,
    *,
    filters: list,
    program_id: UUID | None,
    limit: int,
    after: UUID | None,
) -> AuditEventPage:
    stmt = select(AuditEvent).where(*filters)
    if after is not None:
        anchor = await session.scalar(
            select(AuditEvent).where(AuditEvent.id == after, *filters)
        )
        if anchor is None:
            raise ApiError(
                422, "AUDIT_CURSOR_INVALID", "Cursor is not in the authorized filtered stream"
            )
        stmt = stmt.where(
            tuple_(AuditEvent.occurred_at, AuditEvent.id)
            > tuple_(anchor.occurred_at, anchor.id)
        )

    rows = (
        await session.scalars(
            stmt.order_by(AuditEvent.occurred_at, AuditEvent.id).limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    return AuditEventPage(
        program_id=program_id,
        items=[_metadata(item) for item in page],
        next_cursor=page[-1].id if len(rows) > limit and page else None,
    )


@router.get(
    "/events",
    response_model=AuditEventPage,
    description=(
        "Read-only, immutable audit event metadata. Requires an active AUDITOR grant "
        "for the exact Program (or GLOBAL) scope; omitting program_id requires a "
        "GLOBAL AUDITOR grant. A program-scoped query includes only explicitly "
        "PROGRAM-tagged events from that program, never global or legacy unscoped "
        "records. Previous/new-state JSON, arbitrary scope JSON and evidence "
        "content are never returned. Stable (occurred_at,id) keyset cursor is "
        "bound to the entire authorized filter set."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        422: {"description": "AUDIT_CURSOR_INVALID or invalid query"},
    },
)
async def list_audit_events(
    program_id: UUID | None = None,
    aggregate_type: str | None = Query(default=None, min_length=1, max_length=120),
    aggregate_id: str | None = Query(default=None, min_length=1, max_length=160),
    action: str | None = Query(default=None, min_length=1, max_length=160),
    correlation: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    after: UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AuditEventPage:
    filters = await _authorized_filters(
        session, principal=principal, correlation_id=correlation_id, program_id=program_id
    )
    if aggregate_type is not None:
        filters.append(AuditEvent.aggregate_type == aggregate_type)
    if aggregate_id is not None:
        filters.append(AuditEvent.aggregate_id == aggregate_id)
    if action is not None:
        filters.append(AuditEvent.action == action)
    if correlation is not None:
        filters.append(AuditEvent.correlation_id == correlation)
    return await _query_page(
        session, filters=filters, program_id=program_id, limit=limit, after=after
    )


@router.get(
    "/aggregates/{aggregate_type}/{aggregate_id}",
    response_model=AuditEventPage,
    description=(
        "Immutable audit-event metadata for the exact aggregate type and ID. "
        "Enforces the same Program/GLOBAL AUDITOR scope and exact-stream cursor "
        "rules as /audit/events; no raw state payloads or command execution."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        422: {"description": "AUDIT_CURSOR_INVALID or invalid query"},
    },
)
async def read_aggregate_audit(
    aggregate_type: str = Path(min_length=1, max_length=120),
    aggregate_id: str = Path(min_length=1, max_length=160),
    program_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    after: UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> AuditEventPage:
    filters = await _authorized_filters(
        session, principal=principal, correlation_id=correlation_id, program_id=program_id
    )
    filters.extend(
        (
            AuditEvent.aggregate_type == aggregate_type,
            AuditEvent.aggregate_id == aggregate_id,
        )
    )
    return await _query_page(
        session, filters=filters, program_id=program_id, limit=limit, after=after
    )
