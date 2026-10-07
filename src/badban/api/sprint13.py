from __future__ import annotations

from datetime import datetime
from typing import Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.external_loan import accept_lender_inbound_request
from badban.application.lender_adapter import LenderAdapterError
from badban.infrastructure.persistence.models import CreditProvider, ExternalLoanMirror
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_OPERATIONS,
    SCOPE_PROVIDER,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(tags=["lender-integration"])


class LenderInboundAcceptedView(BaseModel):
    status: Literal["ACCEPTED", "DUPLICATE"]
    inbox_message_id: UUID
    event_type: str
    external_loan_id: str


class ExternalLoanView(BaseModel):
    id: UUID
    guarantee_case_id: UUID | None
    provider_id: UUID
    lender_legal_entity_id: UUID
    lender_provider_code: str
    lender_display_name: str
    external_loan_id: str
    state: str
    original_principal: str
    outstanding_principal: str
    currency: str
    disbursed_at: datetime | None
    settled_at: datetime | None
    delinquency_state: str | None
    last_provider_event_at: datetime | None
    last_provider_event_sequence: int | None
    last_synced_at: datetime | None
    reconciliation_status: str | None
    version: int
    created_at: datetime
    updated_at: datetime


def _raise_adapter_error(exc: LenderAdapterError) -> NoReturn:
    if exc.code == "PROVIDER_NOT_FOUND":
        raise ApiError(404, exc.code, str(exc)) from exc
    if exc.code in {
        "PROVIDER_AUTHENTICATION_FAILED",
        "EVENT_AUTHENTICATION_FAILED",
    }:
        raise ApiError(401, exc.code, str(exc)) from exc
    if exc.code == "EVENT_SCOPE_INVALID":
        raise ApiError(403, exc.code, str(exc)) from exc
    if exc.code in {
        "LENDER_ADAPTER_NOT_CONFIGURED",
        "PROVIDER_TIMEOUT",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_OUTCOME_UNKNOWN",
    }:
        raise ApiError(503, exc.code, str(exc)) from exc
    raise ApiError(422, exc.code, str(exc)) from exc


async def _authorize_read(
    session: AsyncSession,
    *,
    principal: Principal,
    provider_id: UUID,
    loan_id: UUID,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_OPERATIONS, ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR},
            scope_type=SCOPE_PROVIDER,
            scope_id=provider_id,
            allow_global=True,
            action="EXTERNAL_LOAN_READ",
            target_type="ExternalLoanMirror",
            target_id=str(loan_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for External Loan") from exc


@router.post(
    "/api/v1/integrations/lenders/{provider_id}/events",
    response_model=LenderInboundAcceptedView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_lender_event(
    provider_id: UUID,
    request: Request,
    correlation_id: UUID = Depends(get_correlation_id),
) -> LenderInboundAcceptedView:
    raw_body = await request.body()
    registry = request.app.state.lender_adapter_registry
    try:
        accepted = await accept_lender_inbound_request(
            request.app.state.database,
            registry,
            provider_id=provider_id,
            body=raw_body,
            headers={key: value for key, value in request.headers.items()},
            correlation_id=correlation_id,
        )
    except LenderAdapterError as exc:
        _raise_adapter_error(exc)

    return LenderInboundAcceptedView(
        status="ACCEPTED" if accepted.created else "DUPLICATE",
        inbox_message_id=accepted.inbox_message_id,
        event_type=accepted.event_type,
        external_loan_id=accepted.external_loan_id,
    )


@router.get(
    "/api/v1/external-loans/{loan_id}",
    response_model=ExternalLoanView,
)
async def get_external_loan(
    loan_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ExternalLoanView:
    mirror = await session.get(ExternalLoanMirror, loan_id)
    if mirror is None:
        raise ApiError(404, "EXTERNAL_LOAN_NOT_FOUND", "External Loan Mirror was not found")

    provider = await session.get(CreditProvider, mirror.provider_id)
    if provider is None:
        raise ApiError(
            409,
            "EXTERNAL_LOAN_PROVIDER_NOT_FOUND",
            "External Loan Mirror references a missing lender provider",
        )

    await _authorize_read(
        session,
        principal=principal,
        provider_id=mirror.provider_id,
        loan_id=mirror.id,
        correlation_id=correlation_id,
    )

    return ExternalLoanView(
        id=mirror.id,
        guarantee_case_id=mirror.guarantee_case_id,
        provider_id=mirror.provider_id,
        lender_legal_entity_id=provider.legal_entity_id,
        lender_provider_code=provider.provider_code,
        lender_display_name=provider.display_name,
        external_loan_id=mirror.external_loan_id,
        state=mirror.state,
        original_principal=format(mirror.original_principal, "f"),
        outstanding_principal=format(mirror.outstanding_principal, "f"),
        currency=mirror.currency,
        disbursed_at=mirror.disbursed_at,
        settled_at=mirror.settled_at,
        delinquency_state=mirror.delinquency_state,
        last_provider_event_at=mirror.last_provider_event_at,
        last_provider_event_sequence=mirror.last_provider_event_sequence,
        last_synced_at=mirror.last_synced_at,
        reconciliation_status=mirror.reconciliation_status,
        version=mirror.version,
        created_at=mirror.created_at,
        updated_at=mirror.updated_at,
    )
