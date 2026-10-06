from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.idempotency import acquire_idempotency, complete_idempotency
from badban.application.registry import (
    activate_provider,
    get_legal_entity,
    suspend_legal_authorization,
    suspend_provider,
    verify_legal_authorization,
)
from badban.infrastructure.persistence.models import (
    CreditProvider,
    LegalAuthorization,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    SCOPE_GLOBAL,
    SCOPE_LEGAL_ENTITY,
    SCOPE_PROVIDER,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1/admin")


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_entity_id: UUID
    provider_code: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=255)


class ApprovalExecution(BaseModel):
    approval_id: UUID


class ProviderView(OrmModel):
    id: UUID
    legal_entity_id: UUID
    provider_code: str
    display_name: str
    provider_type: str
    lifecycle_status: str
    approved_at: datetime | None
    activated_at: datetime | None
    suspended_at: datetime | None
    created_by: UUID
    version: int
    created_at: datetime
    updated_at: datetime


class ProviderListView(BaseModel):
    items: list[ProviderView]
    next_cursor: UUID | None


class LegalAuthorizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_code: str = Field(min_length=1, max_length=120)
    competent_authority: str = Field(min_length=1, max_length=255)
    authorization_type: str = Field(min_length=1, max_length=160)
    authorization_identifier: str = Field(min_length=1, max_length=200)
    permitted_product_scope: dict[str, Any]
    permitted_asset_type_ids: list[UUID] = Field(default_factory=list)
    evidence_reference: str = Field(min_length=1, max_length=500)
    effective_from: datetime
    expires_at: datetime | None = None
    last_compliance_review_at: datetime

    @model_validator(mode="after")
    def validate_window(self) -> LegalAuthorizationCreate:
        if self.expires_at is not None and self.expires_at <= self.effective_from:
            raise ValueError("expires_at must be later than effective_from")
        return self


class LegalAuthorizationView(OrmModel):
    id: UUID
    legal_entity_id: UUID
    role_code: str
    competent_authority: str
    authorization_type: str
    authorization_identifier: str
    permitted_product_scope: dict[str, Any]
    permitted_asset_type_ids: list[str]
    evidence_reference: str
    effective_from: datetime
    expires_at: datetime | None
    last_compliance_review_at: datetime
    lifecycle_status: str
    verified_by: UUID | None
    verified_at: datetime | None
    created_by: UUID
    version: int
    created_at: datetime
    updated_at: datetime


async def _authorize(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    scope_type: str,
    scope_id: UUID | None,
    allow_global: bool,
    action: str,
    target_type: str,
    target_id: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=scope_type,
            scope_id=scope_id,
            allow_global=allow_global,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for requested registry operation") from exc


@router.get("/providers", response_model=ProviderListView)
async def list_providers(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    cursor: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> ProviderListView:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER, ROLE_LEGAL_COMPLIANCE, ROLE_AUDITOR},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="PROVIDER_LIST",
        target_type="CreditProvider",
        target_id="provider-collection",
        correlation_id=correlation_id,
    )
    statement = select(CreditProvider).order_by(CreditProvider.id).limit(limit)
    if cursor is not None:
        statement = statement.where(CreditProvider.id > cursor)
    providers = (await session.scalars(statement)).all()
    return ProviderListView(
        items=[ProviderView.model_validate(provider) for provider in providers],
        next_cursor=providers[-1].id if len(providers) == limit else None,
    )


@router.post(
    "/providers",
    response_model=ProviderView,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    body: ProviderCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ProviderView:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_LEGAL_COMPLIANCE},
        scope_type=SCOPE_GLOBAL,
        scope_id=None,
        allow_global=False,
        action="PROVIDER_CREATE",
        target_type="CreditProvider",
        target_id=body.provider_code,
        correlation_id=correlation_id,
    )
    await get_legal_entity(session, body.legal_entity_id)
    record, replay = await acquire_idempotency(
        session,
        scope=f"provider:create:{principal.identity_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return ProviderView.model_validate(replay)

    existing = await session.scalar(
        select(CreditProvider.id).where(CreditProvider.provider_code == body.provider_code)
    )
    if existing is not None:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "Provider code already exists")

    provider = CreditProvider(
        legal_entity_id=body.legal_entity_id,
        provider_code=body.provider_code,
        display_name=body.display_name,
        provider_type="EXTERNAL_LENDER",
        lifecycle_status="DRAFT",
        created_by=principal.identity_id,
        version=1,
    )
    session.add(provider)
    await session.flush()
    view = ProviderView.model_validate(provider)
    append_audit(
        session,
        aggregate_type="CreditProvider",
        aggregate_id=str(provider.id),
        aggregate_version=provider.version,
        action="PROVIDER_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=view.model_dump(mode="json"),
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(provider.id)},
    )
    complete_idempotency(record, status_code=201, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.get("/providers/{provider_id}", response_model=ProviderView)
async def get_provider(
    provider_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ProviderView:
    provider = await session.get(CreditProvider, provider_id)
    if provider is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Provider was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER, ROLE_LEGAL_COMPLIANCE, ROLE_AUDITOR},
        scope_type=SCOPE_PROVIDER,
        scope_id=provider.id,
        allow_global=True,
        action="PROVIDER_READ",
        target_type="CreditProvider",
        target_id=str(provider.id),
        correlation_id=correlation_id,
    )
    return ProviderView.model_validate(provider)


@router.post("/providers/{provider_id}/activate", response_model=ProviderView)
async def activate_provider_endpoint(
    provider_id: UUID,
    body: ApprovalExecution,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ProviderView:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_PROVIDER,
        scope_id=provider_id,
        allow_global=True,
        action="PROVIDER_ACTIVATE",
        target_type="CreditProvider",
        target_id=str(provider_id),
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"provider:activate:{provider_id}:{principal.identity_id}",
        key=idempotency_key,
        payload={"provider_id": str(provider_id), "approval_id": str(body.approval_id)},
    )
    if replay is not None:
        return ProviderView.model_validate(replay)
    provider = await activate_provider(
        session,
        provider_id=provider_id,
        approval_id=body.approval_id,
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
    )
    await session.refresh(provider)
    view = ProviderView.model_validate(provider)
    complete_idempotency(record, status_code=200, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.post("/providers/{provider_id}/suspend", response_model=ProviderView)
async def suspend_provider_endpoint(
    provider_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ProviderView:
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_PROVIDER,
        scope_id=provider_id,
        allow_global=True,
        action="PROVIDER_SUSPEND",
        target_type="CreditProvider",
        target_id=str(provider_id),
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"provider:suspend:{provider_id}:{principal.identity_id}",
        key=idempotency_key,
        payload={"provider_id": str(provider_id)},
    )
    if replay is not None:
        return ProviderView.model_validate(replay)
    provider = await suspend_provider(
        session,
        provider_id=provider_id,
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
    )
    await session.refresh(provider)
    view = ProviderView.model_validate(provider)
    complete_idempotency(record, status_code=200, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.get(
    "/legal-entities/{legal_entity_id}/authorizations",
    response_model=list[LegalAuthorizationView],
)
async def list_legal_authorizations(
    legal_entity_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> list[LegalAuthorizationView]:
    await get_legal_entity(session, legal_entity_id)
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_LEGAL_COMPLIANCE, ROLE_AUDITOR, ROLE_GOVERNANCE_APPROVER},
        scope_type=SCOPE_LEGAL_ENTITY,
        scope_id=legal_entity_id,
        allow_global=True,
        action="LEGAL_AUTHORIZATION_LIST",
        target_type="LegalEntity",
        target_id=str(legal_entity_id),
        correlation_id=correlation_id,
    )
    authorizations = (
        await session.scalars(
            select(LegalAuthorization)
            .where(LegalAuthorization.legal_entity_id == legal_entity_id)
            .order_by(LegalAuthorization.created_at, LegalAuthorization.id)
        )
    ).all()
    return [
        LegalAuthorizationView.model_validate(authorization)
        for authorization in authorizations
    ]


@router.post(
    "/legal-entities/{legal_entity_id}/authorizations",
    response_model=LegalAuthorizationView,
    status_code=status.HTTP_201_CREATED,
)
async def create_legal_authorization(
    legal_entity_id: UUID,
    body: LegalAuthorizationCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> LegalAuthorizationView:
    await get_legal_entity(session, legal_entity_id)
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_LEGAL_COMPLIANCE},
        scope_type=SCOPE_LEGAL_ENTITY,
        scope_id=legal_entity_id,
        allow_global=True,
        action="LEGAL_AUTHORIZATION_CREATE",
        target_type="LegalEntity",
        target_id=str(legal_entity_id),
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"legal_authorization:create:{legal_entity_id}:{principal.identity_id}",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay is not None:
        return LegalAuthorizationView.model_validate(replay)

    authorization = LegalAuthorization(
        legal_entity_id=legal_entity_id,
        role_code=body.role_code,
        competent_authority=body.competent_authority,
        authorization_type=body.authorization_type,
        authorization_identifier=body.authorization_identifier,
        permitted_product_scope=body.permitted_product_scope,
        permitted_asset_type_ids=[
            str(asset_type_id) for asset_type_id in body.permitted_asset_type_ids
        ],
        evidence_reference=body.evidence_reference,
        effective_from=body.effective_from,
        expires_at=body.expires_at,
        last_compliance_review_at=body.last_compliance_review_at,
        lifecycle_status="PENDING_VERIFICATION",
        created_by=principal.identity_id,
        version=1,
    )
    session.add(authorization)
    await session.flush()
    view = LegalAuthorizationView.model_validate(authorization)
    append_audit(
        session,
        aggregate_type="LegalAuthorization",
        aggregate_id=str(authorization.id),
        aggregate_version=authorization.version,
        action="LEGAL_AUTHORIZATION_CREATE",
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        new_state=view.model_dump(mode="json"),
        evidence_reference=authorization.evidence_reference,
        scope={"scope_type": SCOPE_LEGAL_ENTITY, "scope_id": str(legal_entity_id)},
    )
    complete_idempotency(record, status_code=201, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.post("/authorizations/{authorization_id}/verify", response_model=LegalAuthorizationView)
async def verify_authorization_endpoint(
    authorization_id: UUID,
    body: ApprovalExecution,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> LegalAuthorizationView:
    authorization = await session.get(LegalAuthorization, authorization_id)
    if authorization is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Legal Authorization was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_LEGAL_COMPLIANCE},
        scope_type=SCOPE_LEGAL_ENTITY,
        scope_id=authorization.legal_entity_id,
        allow_global=True,
        action="LEGAL_AUTHORIZATION_VERIFY",
        target_type="LegalAuthorization",
        target_id=str(authorization.id),
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"legal_authorization:verify:{authorization_id}:{principal.identity_id}",
        key=idempotency_key,
        payload={
            "authorization_id": str(authorization_id),
            "approval_id": str(body.approval_id),
        },
    )
    if replay is not None:
        return LegalAuthorizationView.model_validate(replay)
    authorization = await verify_legal_authorization(
        session,
        authorization_id=authorization_id,
        approval_id=body.approval_id,
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
    )
    await session.refresh(authorization)
    view = LegalAuthorizationView.model_validate(authorization)
    complete_idempotency(record, status_code=200, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view


@router.post("/authorizations/{authorization_id}/suspend", response_model=LegalAuthorizationView)
async def suspend_authorization_endpoint(
    authorization_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> LegalAuthorizationView:
    authorization = await session.get(LegalAuthorization, authorization_id)
    if authorization is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Legal Authorization was not found")
    await _authorize(
        session,
        principal=principal,
        roles={ROLE_LEGAL_COMPLIANCE},
        scope_type=SCOPE_LEGAL_ENTITY,
        scope_id=authorization.legal_entity_id,
        allow_global=True,
        action="LEGAL_AUTHORIZATION_SUSPEND",
        target_type="LegalAuthorization",
        target_id=str(authorization.id),
        correlation_id=correlation_id,
    )
    record, replay = await acquire_idempotency(
        session,
        scope=f"legal_authorization:suspend:{authorization_id}:{principal.identity_id}",
        key=idempotency_key,
        payload={"authorization_id": str(authorization_id)},
    )
    if replay is not None:
        return LegalAuthorizationView.model_validate(replay)
    authorization = await suspend_legal_authorization(
        session,
        authorization_id=authorization_id,
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
    )
    await session.refresh(authorization)
    view = LegalAuthorizationView.model_validate(authorization)
    complete_idempotency(record, status_code=200, response_payload=view.model_dump(mode="json"))
    await session.commit()
    return view
