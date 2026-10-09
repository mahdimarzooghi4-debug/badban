from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.api.sprint07 import GuaranteeCaseView
from badban.api.sprint07 import _view as guarantee_view
from badban.api.sprint26 import (
    RequestBoundEvidenceView,
    _authorized_guarantee,
    _decimal_to_string,
)
from badban.application.backing_source_inventory import BackingInventoryError
from badban.application.request_bound_backing_evidence import (
    RequestEvidenceError,
    read_request_bound_backing_evidence,
)
from badban.infrastructure.persistence.models import (
    CreditProductVersion,
    CreditProvider,
    ExternalLoanMirror,
    GuaranteeCase,
    ParticipationEpisode,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_OPERATIONS,
    ROLE_RISK,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/guarantees", tags=["guarantee-operations-queries"])

_READ_ROLES = {ROLE_OPERATIONS, ROLE_RISK, ROLE_FINANCE_RECONCILIATION, ROLE_AUDITOR}


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GuaranteeListView(QueryModel):
    program_id: UUID
    items: list[GuaranteeCaseView]
    next_cursor: UUID | None


class ObservedProviderView(QueryModel):
    id: UUID
    version: int
    code: str
    lifecycle_status: str
    legal_entity_id: UUID


class CapturedProductView(QueryModel):
    id: UUID
    aggregate_version: int
    version_number: int
    provider_id: UUID
    code: str
    lifecycle_status: str
    currency: str
    guarantee_mode: str
    policy_version_reference: str


class ExternalLoanObservedView(QueryModel):
    id: UUID
    provider_id: UUID
    external_loan_id: str
    version: int
    state: str
    original_principal: str = Field(json_schema_extra={"format": "decimal"})
    outstanding_principal: str = Field(json_schema_extra={"format": "decimal"})
    currency: str
    last_provider_event_at: datetime | None
    reconciliation_status: str | None


class GuaranteeWorkspaceFoundationView(QueryModel):
    """Observed context. No permissions to act, no financial readiness inference."""

    guarantee: GuaranteeCaseView
    program_id: UUID
    participant_id: UUID
    episode_version: int
    episode_status: str
    provider: ObservedProviderView
    captured_product: CapturedProductView
    external_loan: ExternalLoanObservedView | None
    request_evidence: RequestBoundEvidenceView | None
    backing_allocation_contract_available: bool = False
    claim_recovery_contract_available: bool = False
    action_eligibility_evaluated: bool = False


@router.get(
    "",
    response_model=GuaranteeListView,
    description=(
        "Read only persisted guarantee cases within ONE authorized Program. "
        "Stable UUID cursor and bounded page; no cross-program enumeration. "
        "Requires scoped OPERATIONS, RISK, FINANCE_RECONCILIATION, or AUDITOR "
        "or their authorized GLOBAL grant. Does not calculate eligibility."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        422: {"description": "Invalid query parameters"},
    },
)
async def list_guarantees(
    program_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    after: UUID | None = None,
    state: str | None = Query(default=None, min_length=1, max_length=40),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> GuaranteeListView:
    try:
        await authorize(
            session,
            principal=principal,
            roles=_READ_ROLES,
            scope_type=SCOPE_PROGRAM,
            scope_id=program_id,
            allow_global=True,
            action="GUARANTEE_LIST_READ",
            target_type="Program",
            target_id=str(program_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for guarantee list") from exc

    stmt = (
        select(GuaranteeCase)
        .join(
            ParticipationEpisode,
            ParticipationEpisode.id == GuaranteeCase.participation_episode_id,
        )
        .where(ParticipationEpisode.program_id == program_id)
        .order_by(GuaranteeCase.id.asc())
        .limit(limit + 1)
        .execution_options(populate_existing=True)
    )
    if after is not None:
        stmt = stmt.where(GuaranteeCase.id > after)
    if state is not None:
        stmt = stmt.where(GuaranteeCase.state == state)
    rows = (await session.scalars(stmt)).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    return GuaranteeListView(
        program_id=program_id,
        items=[guarantee_view(case) for case in page],
        next_cursor=page[-1].id if has_more and page else None,
    )


@router.get(
    "/{guarantee_id}/workspace",
    response_model=GuaranteeWorkspaceFoundationView,
    description=(
        "Authorized foundation of a guarantee operations workspace: actual "
        "case/program, captured product/provider, recorded external loan and "
        "REQUESTED-only source observations. Missing commercial modules stay "
        "explicitly unavailable. No actions, risk PASS, backing allocations "
        "or financial readiness are inferred."
    ),
    responses={
        401: {"description": "AUTHENTICATION_REQUIRED"},
        403: {"description": "AUTHORIZATION_DENIED"},
        404: {"description": "GUARANTEE_NOT_FOUND"},
        409: {"description": "Observed lineage inconsistent or unsupported evidence state"},
    },
)
async def read_guarantee_workspace(
    guarantee_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> GuaranteeWorkspaceFoundationView:
    authorized = await _authorized_guarantee(
        session,
        principal=principal,
        guarantee_id=guarantee_id,
        correlation_id=correlation_id,
        action="GUARANTEE_WORKSPACE_READ",
    )
    authorized_episode = await session.get(
        ParticipationEpisode, authorized.participation_episode_id
    )
    if authorized_episode is None:
        raise ApiError(409, "GUARANTEE_WORKSPACE_LINEAGE_CONFLICT", "Episode is missing")
    authorized_program_id = authorized_episode.program_id
    row = (
        await session.execute(
            select(
                GuaranteeCase,
                ParticipationEpisode,
                CreditProvider,
                CreditProductVersion,
                ExternalLoanMirror,
            )
            .join(
                ParticipationEpisode,
                ParticipationEpisode.id == GuaranteeCase.participation_episode_id,
            )
            .join(CreditProvider, CreditProvider.id == GuaranteeCase.provider_id)
            .join(
                CreditProductVersion,
                CreditProductVersion.id == GuaranteeCase.credit_product_version_id,
            )
            .outerjoin(
                ExternalLoanMirror,
                (ExternalLoanMirror.id == GuaranteeCase.external_loan_mirror_id)
                & (ExternalLoanMirror.guarantee_case_id == GuaranteeCase.id),
            )
            .where(
                GuaranteeCase.id == guarantee_id,
                ParticipationEpisode.program_id == authorized_program_id,
            )
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise ApiError(
            409,
            "GUARANTEE_WORKSPACE_LINEAGE_CONFLICT",
            "Observed guarantee/provider/product/program lineage is incomplete",
        )
    guarantee, episode, provider, product, external_loan = row
    if (
        guarantee.participation_episode_id != episode.id
        or guarantee.provider_id != provider.id
        or guarantee.credit_product_version_id != product.id
        or product.provider_id != provider.id
        or guarantee.guarantee_mode != product.guarantee_mode
        or (guarantee.external_loan_mirror_id is not None and external_loan is None)
        or (
            external_loan is not None
            and (
                external_loan.provider_id != provider.id
                or external_loan.guarantee_case_id != guarantee.id
            )
        )
    ):
        raise ApiError(
            409, "GUARANTEE_WORKSPACE_LINEAGE_CONFLICT", "Captured sources are inconsistent"
        )
    if min(guarantee.version, episode.version, provider.version, product.version) < 1:
        raise ApiError(409, "GUARANTEE_WORKSPACE_VERSION_INVALID", "Source versions are invalid")

    evidence_view = None
    if guarantee.state == "REQUESTED":
        try:
            evidence = await read_request_bound_backing_evidence(
                session,
                guarantee_case_id=guarantee.id,
                program_id=authorized_program_id,
            )
        except (RequestEvidenceError, BackingInventoryError) as exc:
            raise ApiError(409, exc.code, str(exc)) from exc
        evidence_data = asdict(evidence)
        evidence_data["backing"]["source_fingerprint"] = evidence.backing.source_fingerprint
        evidence_data["evidence_fingerprint"] = evidence.evidence_fingerprint
        evidence_view = RequestBoundEvidenceView.model_validate(_decimal_to_string(evidence_data))

    loan_view = None
    if external_loan is not None:
        loan_view = ExternalLoanObservedView(
            id=external_loan.id,
            provider_id=external_loan.provider_id,
            external_loan_id=external_loan.external_loan_id,
            version=external_loan.version,
            state=external_loan.state,
            original_principal=format(external_loan.original_principal, "f"),
            outstanding_principal=format(external_loan.outstanding_principal, "f"),
            currency=external_loan.currency,
            last_provider_event_at=external_loan.last_provider_event_at,
            reconciliation_status=external_loan.reconciliation_status,
        )

    return GuaranteeWorkspaceFoundationView(
        guarantee=guarantee_view(guarantee),
        program_id=episode.program_id,
        participant_id=episode.participant_id,
        episode_version=episode.version,
        episode_status=episode.status,
        provider=ObservedProviderView(
            id=provider.id,
            version=provider.version,
            code=provider.provider_code,
            lifecycle_status=provider.lifecycle_status,
            legal_entity_id=provider.legal_entity_id,
        ),
        captured_product=CapturedProductView(
            id=product.id,
            aggregate_version=product.version,
            version_number=product.version_number,
            provider_id=product.provider_id,
            code=product.product_code,
            lifecycle_status=product.lifecycle_status,
            currency=product.currency,
            guarantee_mode=product.guarantee_mode,
            policy_version_reference=product.policy_version_reference,
        ),
        external_loan=loan_view,
        request_evidence=evidence_view,
    )
