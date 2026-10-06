from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.approval import (
    assert_approval_execution_eligible,
    get_approval_for_update,
)
from badban.infrastructure.persistence.models import (
    CreditProductVersion,
    CreditProvider,
    LegalAuthorization,
    LegalEntity,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    SCOPE_LEGAL_ENTITY,
    SCOPE_PROVIDER,
)

LENDER_ROLE = "LENDER"


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def legal_authorization_verification_payload(
    authorization: LegalAuthorization,
) -> dict[str, Any]:
    return {
        "action_type": "LEGAL_AUTHORIZATION_VERIFY",
        "target_status": "VALID",
        "authorization_id": str(authorization.id),
        "legal_entity_id": str(authorization.legal_entity_id),
        "role_code": authorization.role_code,
        "competent_authority": authorization.competent_authority,
        "authorization_type": authorization.authorization_type,
        "authorization_identifier": authorization.authorization_identifier,
        "scope_definition": authorization.scope_definition,
        "permitted_product_scope": authorization.permitted_product_scope,
        "permitted_asset_type_ids": authorization.permitted_asset_type_ids,
        "evidence_reference": authorization.evidence_reference,
        "effective_from": authorization.effective_from.isoformat(),
        "expires_at": (
            authorization.expires_at.isoformat() if authorization.expires_at is not None else None
        ),
        "last_compliance_review_at": authorization.last_compliance_review_at.isoformat(),
        "version": authorization.version,
    }


def provider_activation_payload(provider: CreditProvider) -> dict[str, Any]:
    return {
        "action_type": "PROVIDER_ACTIVATION",
        "target_status": "ACTIVE",
        "provider_id": str(provider.id),
        "legal_entity_id": str(provider.legal_entity_id),
        "provider_code": provider.provider_code,
        "provider_type": provider.provider_type,
        "integration_mode": provider.integration_mode,
        "authorization_review_state": provider.authorization_review_state,
        "version": provider.version,
    }


async def get_legal_entity(
    session: AsyncSession,
    legal_entity_id: UUID,
) -> LegalEntity:
    entity = await session.get(LegalEntity, legal_entity_id)
    if entity is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Legal Entity was not found")
    return entity


async def get_authorization_for_update(
    session: AsyncSession,
    authorization_id: UUID,
) -> LegalAuthorization:
    authorization = await session.scalar(
        select(LegalAuthorization)
        .where(LegalAuthorization.id == authorization_id)
        .with_for_update()
    )
    if authorization is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Legal Authorization was not found")
    return authorization


def authorization_valid_at(
    authorization: LegalAuthorization,
    *,
    at: datetime,
    required_role: str | None = None,
    require_unscoped: bool = False,
) -> bool:
    if not _aware(at):
        return False
    if authorization.lifecycle_status != "VALID":
        return False
    if required_role is not None and authorization.role_code != required_role:
        return False
    if authorization.effective_from > at:
        return False
    if authorization.expires_at is not None and authorization.expires_at <= at:
        return False
    if require_unscoped and authorization.scope_definition:
        return False
    return True


async def verify_legal_authorization(
    session: AsyncSession,
    *,
    authorization_id: UUID,
    approval_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    now: datetime | None = None,
) -> LegalAuthorization:
    authorization = await get_authorization_for_update(session, authorization_id)
    if authorization.lifecycle_status != "PENDING_VERIFICATION":
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only PENDING_VERIFICATION authorization can become VALID",
        )

    entity = await get_legal_entity(session, authorization.legal_entity_id)
    if entity.status != "ACTIVE":
        raise ApiError(
            409,
            "AUTHORIZATION_INVALID",
            "Legal Entity must be ACTIVE before authorization verification",
        )

    approval = await get_approval_for_update(session, approval_id)
    if (
        approval.action_type != "LEGAL_AUTHORIZATION_VERIFY"
        or approval.target_type != "LegalAuthorization"
        or approval.target_id != str(authorization.id)
        or approval.required_checker_role != ROLE_LEGAL_COMPLIANCE
        or approval.scope_type != SCOPE_LEGAL_ENTITY
        or approval.scope_id != authorization.legal_entity_id
    ):
        raise ApiError(
            409,
            "MAKER_CHECKER_REQUIRED",
            "Authorization verification requires matching LEGAL_COMPLIANCE approval",
        )
    if approval.checker_identity_id is None or approval.checker_identity_id != actor_id:
        raise ApiError(
            409,
            "MAKER_CHECKER_REQUIRED",
            "Authorization verification must be executed by the approved checker",
        )
    if approval.maker_identity_id == actor_id:
        raise ApiError(403, "SELF_APPROVAL_FORBIDDEN", "Maker cannot execute own approval")

    assert_approval_execution_eligible(
        approval,
        payload=legal_authorization_verification_payload(authorization),
        current_target_version=authorization.version,
        now=now,
    )

    verified_at = now or datetime.now(UTC)
    authorization.lifecycle_status = "VALID"
    authorization.verified_by = actor_id
    authorization.verified_at = verified_at
    authorization.version += 1
    append_audit(
        session,
        aggregate_type="LegalAuthorization",
        aggregate_id=str(authorization.id),
        aggregate_version=authorization.version,
        action="LEGAL_AUTHORIZATION_VERIFY",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=authorization.evidence_reference,
        scope={
            "scope_type": SCOPE_LEGAL_ENTITY,
            "scope_id": str(authorization.legal_entity_id),
        },
    )
    await session.flush()
    return authorization


async def suspend_legal_authorization(
    session: AsyncSession,
    *,
    authorization_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> LegalAuthorization:
    authorization = await get_authorization_for_update(session, authorization_id)
    if authorization.lifecycle_status != "VALID":
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only VALID authorization can be suspended",
        )
    authorization.lifecycle_status = "SUSPENDED"
    authorization.version += 1
    append_audit(
        session,
        aggregate_type="LegalAuthorization",
        aggregate_id=str(authorization.id),
        aggregate_version=authorization.version,
        action="LEGAL_AUTHORIZATION_SUSPEND",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        evidence_reference=authorization.evidence_reference,
        scope={
            "scope_type": SCOPE_LEGAL_ENTITY,
            "scope_id": str(authorization.legal_entity_id),
        },
    )
    await session.flush()
    return authorization


async def approve_provider_due_diligence(
    session: AsyncSession,
    *,
    provider_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    now: datetime | None = None,
) -> CreditProvider:
    provider = await session.scalar(
        select(CreditProvider).where(CreditProvider.id == provider_id).with_for_update()
    )
    if provider is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Provider was not found")
    entity = await get_legal_entity(session, provider.legal_entity_id)
    if entity.status != "ACTIVE":
        raise ApiError(
            409,
            "AUTHORIZATION_INVALID",
            "Provider Legal Entity must be ACTIVE",
        )
    if provider.lifecycle_status != "DRAFT":
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only DRAFT provider can be marked APPROVED",
        )
    provider.lifecycle_status = "APPROVED"
    provider.approved_at = now or datetime.now(UTC)
    provider.version += 1
    append_audit(
        session,
        aggregate_type="CreditProvider",
        aggregate_id=str(provider.id),
        aggregate_version=provider.version,
        action="PROVIDER_DUE_DILIGENCE_APPROVE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(provider.id)},
    )
    await session.flush()
    return provider


async def _assert_provider_legal_authorization(
    session: AsyncSession,
    *,
    provider: CreditProvider,
    at: datetime,
) -> LegalAuthorization:
    entity = await get_legal_entity(session, provider.legal_entity_id)
    if entity.status != "ACTIVE":
        raise ApiError(
            409,
            "AUTHORIZATION_INVALID",
            "Provider Legal Entity is not ACTIVE",
        )

    authorizations = (
        await session.scalars(
            select(LegalAuthorization)
            .where(
                LegalAuthorization.legal_entity_id == provider.legal_entity_id,
                LegalAuthorization.role_code == LENDER_ROLE,
                LegalAuthorization.lifecycle_status == "VALID",
                LegalAuthorization.effective_from <= at,
                or_(
                    LegalAuthorization.expires_at.is_(None),
                    LegalAuthorization.expires_at > at,
                ),
            )
            .order_by(LegalAuthorization.effective_from.desc())
        )
    ).all()
    for authorization in authorizations:
        if authorization_valid_at(
            authorization,
            at=at,
            required_role=LENDER_ROLE,
            require_unscoped=True,
        ):
            return authorization

    raise ApiError(
        409,
        "AUTHORIZATION_INVALID",
        "Provider requires a currently VALID unscoped LENDER authorization; "
        "scoped authorization is fail-closed until a capability-matrix matcher is defined",
    )


async def activate_provider(
    session: AsyncSession,
    *,
    provider_id: UUID,
    approval_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    now: datetime | None = None,
) -> CreditProvider:
    provider = await session.scalar(
        select(CreditProvider).where(CreditProvider.id == provider_id).with_for_update()
    )
    if provider is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Provider was not found")
    if provider.provider_type != "EXTERNAL_LENDER":
        raise ApiError(
            409,
            "AUTHORIZATION_INVALID",
            "Direct Lending is disabled for the bounded pilot",
        )
    if provider.lifecycle_status != "APPROVED":
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only APPROVED provider can become ACTIVE",
        )

    activation_time = now or datetime.now(UTC)
    await _assert_provider_legal_authorization(
        session,
        provider=provider,
        at=activation_time,
    )

    approval = await get_approval_for_update(session, approval_id)
    if (
        approval.action_type != "PROVIDER_ACTIVATION"
        or approval.target_type != "CreditProvider"
        or approval.target_id != str(provider.id)
        or approval.required_checker_role != ROLE_GOVERNANCE_APPROVER
        or approval.scope_type != SCOPE_PROVIDER
        or approval.scope_id != provider.id
    ):
        raise ApiError(
            409,
            "MAKER_CHECKER_REQUIRED",
            "Provider activation requires matching GOVERNANCE_APPROVER approval",
        )
    if approval.checker_identity_id is None or approval.checker_identity_id != actor_id:
        raise ApiError(
            409,
            "MAKER_CHECKER_REQUIRED",
            "Provider activation must be executed by the approved checker",
        )
    if approval.maker_identity_id == actor_id:
        raise ApiError(403, "SELF_APPROVAL_FORBIDDEN", "Maker cannot execute own approval")

    assert_approval_execution_eligible(
        approval,
        payload=provider_activation_payload(provider),
        current_target_version=provider.version,
        now=activation_time,
    )

    provider.lifecycle_status = "ACTIVE"
    provider.activated_at = activation_time
    provider.version += 1
    append_audit(
        session,
        aggregate_type="CreditProvider",
        aggregate_id=str(provider.id),
        aggregate_version=provider.version,
        action="PROVIDER_ACTIVATE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(provider.id)},
    )
    await session.flush()
    return provider


async def suspend_provider(
    session: AsyncSession,
    *,
    provider_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    reason: str | None = None,
    now: datetime | None = None,
) -> CreditProvider:
    provider = await session.scalar(
        select(CreditProvider).where(CreditProvider.id == provider_id).with_for_update()
    )
    if provider is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Provider was not found")
    if provider.lifecycle_status != "ACTIVE":
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only ACTIVE provider can be suspended",
        )
    provider.lifecycle_status = "SUSPENDED"
    provider.suspended_at = now or datetime.now(UTC)
    provider.suspension_reason = reason
    provider.version += 1
    append_audit(
        session,
        aggregate_type="CreditProvider",
        aggregate_id=str(provider.id),
        aggregate_version=provider.version,
        action="PROVIDER_SUSPEND",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        reason_code=reason,
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(provider.id)},
    )
    await session.flush()
    return provider


async def create_credit_product_version(
    session: AsyncSession,
    *,
    provider_id: UUID,
    product_code: str,
    version_number: int,
    product_name: str,
    product_type: str,
    currency: str,
    min_principal: Decimal,
    max_principal: Decimal,
    tenor_definition: dict[str, Any],
    repayment_definition: dict[str, Any],
    pricing_definition: dict[str, Any],
    guarantee_mode: str,
    delinquency_definition: dict[str, Any],
    claim_definition: dict[str, Any],
    policy_version_reference: str,
    additional_terms: dict[str, Any],
    effective_from: datetime,
    effective_to: datetime | None,
    created_by: UUID,
) -> CreditProductVersion:
    if version_number <= 0:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product version number must be positive",
        )
    if not product_code or not product_name or not product_type or not currency:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product identity fields must be explicit",
        )
    if min_principal < 0 or max_principal < min_principal:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product principal bounds are invalid",
        )
    definitions = {
        "tenor_definition": tenor_definition,
        "repayment_definition": repayment_definition,
        "pricing_definition": pricing_definition,
        "delinquency_definition": delinquency_definition,
        "claim_definition": claim_definition,
    }
    if any(not value for value in definitions.values()):
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product rule definitions must be explicit and non-empty",
        )
    if guarantee_mode not in {"FIXED", "DECLINING"}:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product guarantee mode is invalid",
        )
    if not policy_version_reference:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product policy version reference is required",
        )
    if not _aware(effective_from) or (effective_to is not None and not _aware(effective_to)):
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product effective timestamps must be timezone-aware",
        )
    if effective_to is not None and effective_to <= effective_from:
        raise ApiError(
            409,
            "POLICY_VALIDATION_FAILED",
            "Credit Product effective window is invalid",
        )

    provider = await session.get(CreditProvider, provider_id)
    if provider is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Provider was not found")

    product = CreditProductVersion(
        provider_id=provider.id,
        lender_of_record_legal_entity_id=provider.legal_entity_id,
        product_code=product_code,
        version_number=version_number,
        product_name=product_name,
        product_type=product_type,
        lifecycle_status="DRAFT",
        currency=currency,
        min_principal=min_principal,
        max_principal=max_principal,
        tenor_definition=tenor_definition,
        repayment_definition=repayment_definition,
        pricing_definition=pricing_definition,
        guarantee_mode=guarantee_mode,
        delinquency_definition=delinquency_definition,
        claim_definition=claim_definition,
        policy_version_reference=policy_version_reference,
        additional_terms=additional_terms,
        effective_from=effective_from,
        effective_to=effective_to,
        created_by=created_by,
        version=1,
    )
    session.add(product)
    await session.flush()
    return product


async def approve_credit_product_version(
    session: AsyncSession,
    *,
    product_version_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    now: datetime | None = None,
) -> CreditProductVersion:
    product = await session.scalar(
        select(CreditProductVersion)
        .where(CreditProductVersion.id == product_version_id)
        .with_for_update()
    )
    if product is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Product Version was not found")
    if product.lifecycle_status != "DRAFT" or product.approved_at is not None:
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only unapproved DRAFT Credit Product Version can be approved",
        )
    product.approved_at = now or datetime.now(UTC)
    product.version += 1
    append_audit(
        session,
        aggregate_type="CreditProductVersion",
        aggregate_id=str(product.id),
        aggregate_version=product.version,
        action="CREDIT_PRODUCT_VERSION_APPROVE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(product.provider_id)},
    )
    await session.flush()
    return product


async def activate_credit_product_version(
    session: AsyncSession,
    *,
    product_version_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
    now: datetime | None = None,
) -> CreditProductVersion:
    product = await session.scalar(
        select(CreditProductVersion)
        .where(CreditProductVersion.id == product_version_id)
        .with_for_update()
    )
    if product is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Product Version was not found")
    if product.lifecycle_status != "DRAFT" or product.approved_at is None:
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only explicitly approved DRAFT Credit Product Version can become ACTIVE",
        )

    activation_time = now or datetime.now(UTC)
    if product.effective_from > activation_time or (
        product.effective_to is not None and product.effective_to <= activation_time
    ):
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Credit Product Version is outside its effective window",
        )

    provider = await session.get(CreditProvider, product.provider_id)
    if provider is None or provider.lifecycle_status != "ACTIVE":
        raise ApiError(
            409,
            "PROVIDER_NOT_ACTIVE",
            "Credit Product Version requires an ACTIVE provider",
        )
    await _assert_provider_legal_authorization(
        session,
        provider=provider,
        at=activation_time,
    )

    product.lifecycle_status = "ACTIVE"
    product.activated_at = activation_time
    product.version += 1
    append_audit(
        session,
        aggregate_type="CreditProductVersion",
        aggregate_id=str(product.id),
        aggregate_version=product.version,
        action="CREDIT_PRODUCT_VERSION_ACTIVATE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(product.provider_id)},
    )
    await session.flush()
    return product


async def suspend_credit_product_version(
    session: AsyncSession,
    *,
    product_version_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> CreditProductVersion:
    product = await session.scalar(
        select(CreditProductVersion)
        .where(CreditProductVersion.id == product_version_id)
        .with_for_update()
    )
    if product is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Product Version was not found")
    if product.lifecycle_status != "ACTIVE":
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only ACTIVE Credit Product Version can be suspended",
        )
    product.lifecycle_status = "SUSPENDED"
    product.version += 1
    append_audit(
        session,
        aggregate_type="CreditProductVersion",
        aggregate_id=str(product.id),
        aggregate_version=product.version,
        action="CREDIT_PRODUCT_VERSION_SUSPEND",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(product.provider_id)},
    )
    await session.flush()
    return product


async def retire_credit_product_version(
    session: AsyncSession,
    *,
    product_version_id: UUID,
    actor_type: str,
    actor_id: UUID,
    correlation_id: UUID,
) -> CreditProductVersion:
    product = await session.scalar(
        select(CreditProductVersion)
        .where(CreditProductVersion.id == product_version_id)
        .with_for_update()
    )
    if product is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Credit Product Version was not found")
    if product.lifecycle_status not in {"ACTIVE", "SUSPENDED"}:
        raise ApiError(
            409,
            "INVALID_STATE_TRANSITION",
            "Only ACTIVE or SUSPENDED Credit Product Version can be retired",
        )
    product.lifecycle_status = "RETIRED"
    product.version += 1
    append_audit(
        session,
        aggregate_type="CreditProductVersion",
        aggregate_id=str(product.id),
        aggregate_version=product.version,
        action="CREDIT_PRODUCT_VERSION_RETIRE",
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        outcome="SUCCESS",
        scope={"scope_type": SCOPE_PROVIDER, "scope_id": str(product.provider_id)},
    )
    await session.flush()
    return product
