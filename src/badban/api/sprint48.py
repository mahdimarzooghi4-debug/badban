from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    CreditProductVersion,
    ExternalLoanMirror,
    GuaranteeCase,
    Identity,
    Participant,
    ParticipationEpisode,
    Program,
    RoleGrant,
    ValuationObservation,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    HUMAN_IDENTITY_TYPES,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_SUPPORT_INSTITUTION_OPERATOR,
    SCOPE_GLOBAL,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

admin_router = APIRouter(
    prefix="/api/v1/admin/support-institution",
    tags=["admin-support-institution"],
)
institution_router = APIRouter(
    prefix="/api/v1/support-institution",
    tags=["support-institution"],
)


class ProgramRoleGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: UUID
    program_id: UUID
    valid_from: datetime
    valid_until: datetime | None = None
    reason_reference: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_window(self) -> ProgramRoleGrantCreate:
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise ValueError("valid_from must be timezone-aware")
        if self.valid_until is not None:
            if self.valid_until.tzinfo is None or self.valid_until.utcoffset() is None:
                raise ValueError("valid_until must be timezone-aware")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be later than valid_from")
        return self


class ProgramRoleGrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_reference: str = Field(min_length=1, max_length=255)


class ProgramRoleGrantView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identity_id: UUID
    role_code: str
    scope_type: str
    scope_id: UUID | None
    valid_from: datetime
    valid_until: datetime | None
    status: str
    granted_by: UUID | None
    reason_ref: str | None
    version: int


class SupportingRoleGrantListView(BaseModel):
    items: list[ProgramRoleGrantView]
    status: str
    limit: int
    offset: int


class SupportingProgramView(BaseModel):
    program_id: UUID
    code: str
    name: str
    status: str


class SupportingProgramsView(BaseModel):
    items: list[SupportingProgramView]
    limit: int
    offset: int


class SupportedPersonView(BaseModel):
    participant_id: UUID
    episode_id: UUID
    participation_status: str
    consent_state: str
    started_at: datetime
    ended_at: datetime | None


class SupportedPeopleView(BaseModel):
    program_id: UUID
    items: list[SupportedPersonView]
    limit: int
    offset: int



class SupportedAssetValuationView(BaseModel):
    id: UUID
    source_name: str
    source_reference: str
    source_version_reference: str | None
    observed_at: datetime
    freshness_status: str
    valuation_currency: str
    unit_price: Decimal
    gross_market_value: Decimal
    valid_until: datetime | None


class SupportedAssetPositionView(BaseModel):
    id: UUID
    asset_code: str
    asset_name: str
    ownership_funding_type: str
    quantity: Decimal
    unit_code: str
    lifecycle_status: str
    valuation_observations: list[SupportedAssetValuationView]


class SupportedGuaranteeView(BaseModel):
    id: UUID
    provider_id: UUID
    state: str
    requested_principal: Decimal
    reserved_guarantee_amount: Decimal | None
    issued_guarantee_amount: Decimal | None
    current_guarantee_exposure: Decimal
    guarantee_mode: str
    currency: str
    loan_state: str | None
    outstanding_principal: Decimal | None
    loan_currency: str | None
    last_synced_at: datetime | None
    reconciliation_status: str | None


class SupportedFinancialCaseView(BaseModel):
    program_id: UUID
    participant_id: UUID
    episode_id: UUID
    assets: list[SupportedAssetPositionView]
    guarantees: list[SupportedGuaranteeView]
    profit_share_status: Literal["NOT_AVAILABLE_FOR_PROGRAM_SCOPE"]



async def _authorize_global_governance(
    session: AsyncSession,
    principal: Principal,
    correlation_id: UUID,
    action: str,
    target_id: str,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_GOVERNANCE_APPROVER},
            scope_type=SCOPE_GLOBAL,
            scope_id=None,
            allow_global=False,
            action=action,
            target_type="SupportingInstitutionRoleGrant",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Global governance approval permission required") from exc


@admin_router.get("/grants", response_model=SupportingRoleGrantListView)
async def list_supporting_institution_grants(
    grant_status: Literal["REQUESTED", "ACTIVE", "REVOKED"] = Query(
        default="REQUESTED", alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportingRoleGrantListView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "SUPPORT_INSTITUTION_ROLE_GRANT_LIST",
        grant_status,
    )
    grants = (
        await session.scalars(
            select(RoleGrant)
            .where(
                RoleGrant.role_code == ROLE_SUPPORT_INSTITUTION_OPERATOR,
                RoleGrant.scope_type == SCOPE_PROGRAM,
                RoleGrant.status == grant_status,
            )
            .order_by(RoleGrant.created_at.desc(), RoleGrant.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="SupportingInstitutionRoleGrantQueue",
        aggregate_id=grant_status,
        aggregate_version=None,
        action="SUPPORT_INSTITUTION_ROLE_GRANT_LIST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={
            "status": grant_status,
            "returned_count": len(grants),
            "limit": limit,
            "offset": offset,
        },
    )
    await session.commit()
    return SupportingRoleGrantListView(
        items=[ProgramRoleGrantView.model_validate(grant) for grant in grants],
        status=grant_status,
        limit=limit,
        offset=offset,
    )


@admin_router.post(
    "/grants",
    response_model=ProgramRoleGrantView,
    status_code=status.HTTP_201_CREATED,
)
async def request_supporting_institution_access(
    body: ProgramRoleGrantCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramRoleGrantView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "SUPPORT_INSTITUTION_ROLE_GRANT_REQUEST",
        str(body.identity_id),
    )
    identity = await session.get(Identity, body.identity_id)
    if (
        identity is None
        or identity.status != "ACTIVE"
        or identity.identity_type not in HUMAN_IDENTITY_TYPES
    ):
        raise ApiError(404, "HUMAN_IDENTITY_NOT_FOUND", "Active human identity was not found")
    program = await session.get(Program, body.program_id)
    if program is None or program.status != "ACTIVE" or program.legal_entity_id is None:
        raise ApiError(
            404,
            "SUPPORTING_PROGRAM_NOT_FOUND",
            "Active supporting institution program was not found",
        )
    existing = await session.scalar(
        select(RoleGrant.id).where(
            RoleGrant.identity_id == body.identity_id,
            RoleGrant.role_code == ROLE_SUPPORT_INSTITUTION_OPERATOR,
            RoleGrant.scope_type == SCOPE_PROGRAM,
            RoleGrant.scope_id == body.program_id,
            RoleGrant.status.in_(["REQUESTED", "ACTIVE"]),
        )
    )
    if existing is not None:
        raise ApiError(
            409,
            "SUPPORT_INSTITUTION_ROLE_GRANT_EXISTS",
            "A pending or active grant already exists",
        )
    grant = RoleGrant(
        identity_id=body.identity_id,
        role_code=ROLE_SUPPORT_INSTITUTION_OPERATOR,
        scope_type=SCOPE_PROGRAM,
        scope_id=body.program_id,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        status="REQUESTED",
        granted_by=principal.identity_id,
        reason_ref=body.reason_reference,
    )
    session.add(grant)
    await session.flush()
    append_audit(
        session,
        aggregate_type="SupportingInstitutionRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SUPPORT_INSTITUTION_ROLE_GRANT_REQUEST",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"program_id": str(body.program_id), "identity_id": str(body.identity_id)},
    )
    await session.commit()
    return ProgramRoleGrantView.model_validate(grant)


@admin_router.post("/grants/{grant_id}/approve", response_model=ProgramRoleGrantView)
async def approve_supporting_institution_access(
    grant_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramRoleGrantView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "SUPPORT_INSTITUTION_ROLE_GRANT_APPROVE",
        str(grant_id),
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    if (
        grant is None
        or grant.scope_type != SCOPE_PROGRAM
        or grant.role_code != ROLE_SUPPORT_INSTITUTION_OPERATOR
        or grant.scope_id is None
    ):
        raise ApiError(
            404, "SUPPORT_INSTITUTION_GRANT_NOT_FOUND", "Supporting institution grant was not found"
        )
    if grant.status != "REQUESTED":
        raise ApiError(
            409,
            "SUPPORT_INSTITUTION_GRANT_NOT_REQUESTED",
            "Only a requested grant can be approved",
        )
    if grant.granted_by == principal.identity_id:
        raise ApiError(
            403,
            "MAKER_CHECKER_REQUIRED",
            "The requester cannot approve the supporting institution grant",
        )
    program = await session.get(Program, grant.scope_id)
    if program is None or program.status != "ACTIVE" or program.legal_entity_id is None:
        raise ApiError(
            409,
            "SUPPORTING_PROGRAM_UNAVAILABLE",
            "The supporting institution program is no longer active",
        )
    grant.status = "ACTIVE"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="SupportingInstitutionRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SUPPORT_INSTITUTION_ROLE_GRANT_APPROVE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=grant.reason_ref,
        scope={"program_id": str(grant.scope_id), "role_code": grant.role_code},
    )
    await session.commit()
    return ProgramRoleGrantView.model_validate(grant)


@admin_router.post("/grants/{grant_id}/revoke", response_model=ProgramRoleGrantView)
async def revoke_supporting_institution_access(
    grant_id: UUID,
    body: ProgramRoleGrantRevoke,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProgramRoleGrantView:
    await _authorize_global_governance(
        session,
        principal,
        correlation_id,
        "SUPPORT_INSTITUTION_ROLE_GRANT_REVOKE",
        str(grant_id),
    )
    grant = await session.scalar(
        select(RoleGrant).where(RoleGrant.id == grant_id).with_for_update()
    )
    if (
        grant is None
        or grant.scope_type != SCOPE_PROGRAM
        or grant.role_code != ROLE_SUPPORT_INSTITUTION_OPERATOR
    ):
        raise ApiError(
            404, "SUPPORT_INSTITUTION_GRANT_NOT_FOUND", "Supporting institution grant was not found"
        )
    if grant.status not in {"REQUESTED", "ACTIVE"}:
        raise ApiError(
            409,
            "SUPPORT_INSTITUTION_GRANT_NOT_REVOCABLE",
            "Grant is no longer active or pending",
        )
    grant.status = "REVOKED"
    grant.version += 1
    append_audit(
        session,
        aggregate_type="SupportingInstitutionRoleGrant",
        aggregate_id=str(grant.id),
        aggregate_version=grant.version,
        action="SUPPORT_INSTITUTION_ROLE_GRANT_REVOKE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=body.reason_reference,
        scope={"program_id": str(grant.scope_id), "role_code": grant.role_code},
    )
    await session.commit()
    return ProgramRoleGrantView.model_validate(grant)


@institution_router.get("/programs", response_model=SupportingProgramsView)
async def read_authorized_programs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportingProgramsView:
    if principal.identity_type not in HUMAN_IDENTITY_TYPES:
        append_audit(
            session,
            aggregate_type="SupportingInstitutionWorkspace",
            aggregate_id=str(principal.identity_id),
            aggregate_version=None,
            action="SUPPORT_INSTITUTION_PROGRAM_LIST_READ",
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
            outcome="DENIED",
            reason_code="AUTHORIZATION_DENIED",
            scope={"scope_type": SCOPE_PROGRAM},
        )
        await session.commit()
        raise ApiError(403, "AUTHORIZATION_DENIED", "Human institution operator identity required")
    now = datetime.now(UTC)
    programs = (
        await session.scalars(
            select(Program)
            .join(RoleGrant, RoleGrant.scope_id == Program.id)
            .where(
                RoleGrant.identity_id == principal.identity_id,
                RoleGrant.role_code == ROLE_SUPPORT_INSTITUTION_OPERATOR,
                RoleGrant.scope_type == SCOPE_PROGRAM,
                RoleGrant.status == "ACTIVE",
                RoleGrant.valid_from <= now,
                (RoleGrant.valid_until.is_(None) | (RoleGrant.valid_until > now)),
                Program.status == "ACTIVE",
                Program.legal_entity_id.is_not(None),
            )
            .distinct()
            .order_by(Program.name, Program.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="SupportingInstitutionWorkspace",
        aggregate_id=str(principal.identity_id),
        aggregate_version=None,
        action="SUPPORT_INSTITUTION_PROGRAM_LIST_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(programs), "limit": limit, "offset": offset},
    )
    await session.commit()
    return SupportingProgramsView(
        items=[
            SupportingProgramView(
                program_id=program.id,
                code=program.code,
                name=program.name,
                status=program.status,
            )
            for program in programs
        ],
        limit=limit,
        offset=offset,
    )


@institution_router.get(
    "/programs/{program_id}/beneficiaries",
    response_model=SupportedPeopleView,
)
async def read_program_beneficiaries(
    program_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportedPeopleView:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_SUPPORT_INSTITUTION_OPERATOR},
            scope_type=SCOPE_PROGRAM,
            scope_id=program_id,
            allow_global=False,
            action="SUPPORT_INSTITUTION_BENEFICIARIES_READ",
            target_type="SupportingInstitutionProgram",
            target_id=str(program_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(
            403, exc.code, "Program-scoped supporting institution access is required"
        ) from exc

    rows = (
        await session.execute(
            select(ParticipationEpisode, Participant)
            .join(Participant, Participant.id == ParticipationEpisode.participant_id)
            .join(Program, Program.id == ParticipationEpisode.program_id)
            .where(
                ParticipationEpisode.program_id == program_id,
                Program.status == "ACTIVE",
                Program.legal_entity_id.is_not(None),
            )
            .order_by(ParticipationEpisode.started_at.desc(), ParticipationEpisode.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    append_audit(
        session,
        aggregate_type="SupportingInstitutionProgram",
        aggregate_id=str(program_id),
        aggregate_version=None,
        action="SUPPORT_INSTITUTION_BENEFICIARIES_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"returned_count": len(rows), "limit": limit, "offset": offset},
    )
    await session.commit()
    return SupportedPeopleView(
        program_id=program_id,
        items=[
            SupportedPersonView(
                participant_id=participant.id,
                episode_id=episode.id,
                participation_status=episode.status,
                consent_state=episode.consent_state,
                started_at=episode.started_at,
                ended_at=episode.ended_at,
            )
            for episode, participant in rows
        ],
        limit=limit,
        offset=offset,
    )



@institution_router.get(
    "/programs/{program_id}/beneficiaries/{participant_id}/episodes/{episode_id}/financial-case",
    response_model=SupportedFinancialCaseView,
)
async def read_program_beneficiary_financial_case(
    program_id: UUID,
    participant_id: UUID,
    episode_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> SupportedFinancialCaseView:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_SUPPORT_INSTITUTION_OPERATOR},
            scope_type=SCOPE_PROGRAM,
            scope_id=program_id,
            allow_global=False,
            action="SUPPORT_INSTITUTION_BENEFICIARY_FINANCIAL_CASE_READ",
            target_type="SupportingInstitutionProgram",
            target_id=str(program_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(
            403, exc.code, "Program-scoped supporting institution access is required"
        ) from exc

    episode = await session.scalar(
        select(ParticipationEpisode).where(
            ParticipationEpisode.id == episode_id,
            ParticipationEpisode.program_id == program_id,
            ParticipationEpisode.participant_id == participant_id,
        )
    )
    program = await session.get(Program, program_id)
    if (
        episode is None
        or program is None
        or program.status != "ACTIVE"
        or program.legal_entity_id is None
    ):
        raise ApiError(
            404,
            "SUPPORTING_BENEFICIARY_NOT_FOUND",
            "Beneficiary episode was not found in this active program",
        )

    asset_rows = (
        await session.execute(
            select(AssetPosition, AssetType)
            .join(AssetType, AssetType.id == AssetPosition.asset_type_id)
            .where(
                AssetPosition.program_id == program_id,
                AssetPosition.participation_episode_id == episode_id,
            )
            .order_by(AssetPosition.created_at.desc(), AssetPosition.id)
            .limit(limit)
        )
    ).all()
    position_ids = [position.id for position, _asset_type in asset_rows]
    valuation_rows = []
    if position_ids:
        valuation_rows = (
            await session.scalars(
                select(ValuationObservation)
                .where(ValuationObservation.asset_position_id.in_(position_ids))
                .order_by(
                    ValuationObservation.observed_at.desc(),
                    ValuationObservation.id,
                )
                .limit(500)
            )
        ).all()

    valuations_by_position: dict[UUID, list[SupportedAssetValuationView]] = {}
    for observation in valuation_rows:
        valuations_by_position.setdefault(observation.asset_position_id, []).append(
            SupportedAssetValuationView(
                id=observation.id,
                source_name=observation.source_name,
                source_reference=observation.source_reference,
                source_version_reference=observation.source_version_reference,
                observed_at=observation.observed_at,
                freshness_status=observation.freshness_status,
                valuation_currency=observation.valuation_currency,
                unit_price=observation.unit_price,
                gross_market_value=observation.gross_market_value,
                valid_until=observation.valid_until,
            )
        )

    guarantee_rows = (
        await session.execute(
            select(GuaranteeCase, CreditProductVersion, ExternalLoanMirror)
            .join(
                ParticipationEpisode,
                ParticipationEpisode.id == GuaranteeCase.participation_episode_id,
            )
            .join(
                CreditProductVersion,
                CreditProductVersion.id == GuaranteeCase.credit_product_version_id,
            )
            .outerjoin(
                ExternalLoanMirror,
                (ExternalLoanMirror.id == GuaranteeCase.external_loan_mirror_id)
                & (ExternalLoanMirror.provider_id == GuaranteeCase.provider_id),
            )
            .where(
                ParticipationEpisode.id == episode_id,
                ParticipationEpisode.program_id == program_id,
                ParticipationEpisode.participant_id == participant_id,
                GuaranteeCase.participation_episode_id == episode_id,
                CreditProductVersion.provider_id == GuaranteeCase.provider_id,
            )
            .order_by(GuaranteeCase.created_at.desc(), GuaranteeCase.id)
            .limit(limit)
        )
    ).all()

    append_audit(
        session,
        aggregate_type="SupportingInstitutionBeneficiaryFinancialCase",
        aggregate_id=str(episode_id),
        aggregate_version=None,
        action="SUPPORT_INSTITUTION_BENEFICIARY_FINANCIAL_CASE_READ",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={
            "program_id": str(program_id),
            "participant_id": str(participant_id),
            "episode_id": str(episode_id),
            "asset_count": len(asset_rows),
            "guarantee_count": len(guarantee_rows),
        },
    )
    await session.commit()

    return SupportedFinancialCaseView(
        program_id=program_id,
        participant_id=participant_id,
        episode_id=episode_id,
        assets=[
            SupportedAssetPositionView(
                id=position.id,
                asset_code=asset_type.asset_code,
                asset_name=asset_type.name,
                ownership_funding_type=position.ownership_funding_type,
                quantity=position.quantity,
                unit_code=position.unit_code,
                lifecycle_status=position.lifecycle_status,
                valuation_observations=valuations_by_position.get(position.id, []),
            )
            for position, asset_type in asset_rows
        ],
        guarantees=[
            SupportedGuaranteeView(
                id=case.id,
                provider_id=case.provider_id,
                state=case.state,
                requested_principal=case.requested_principal,
                reserved_guarantee_amount=case.reserved_guarantee_amount,
                issued_guarantee_amount=case.issued_guarantee_amount,
                current_guarantee_exposure=case.current_guarantee_exposure,
                guarantee_mode=case.guarantee_mode,
                currency=product.currency,
                loan_state=loan.state if loan is not None else None,
                outstanding_principal=(
                    loan.outstanding_principal if loan is not None else None
                ),
                loan_currency=loan.currency if loan is not None else None,
                last_synced_at=loan.last_synced_at if loan is not None else None,
                reconciliation_status=(
                    loan.reconciliation_status if loan is not None else None
                ),
            )
            for case, product, loan in guarantee_rows
        ],
        profit_share_status="NOT_AVAILABLE_FOR_PROGRAM_SCOPE",
    )
