from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.policy_resolution import ResolvedPolicyPack, resolve_active_policy_pack
from badban.application.reconciliation_sources import SourceTarget
from badban.application.registry import authorization_valid_at
from badban.infrastructure.persistence.models import (
    LegalAuthorization,
    LegalEntity,
    PolicyVersion,
    Program,
)

SOURCE_ROLES = {
    "GUARANTEE_ISSUER": "GUARANTEE_ISSUER",
    "CUSTODY": "CUSTODIAN",
    "SETTLEMENT": "PAYMENT_PROVIDER",
    "COLLATERAL_REGISTRY": "COLLATERAL_REGISTRY_OPERATOR",
}


async def resolve_source_context(
    session: AsyncSession, target: SourceTarget, *, at: datetime
) -> tuple[ResolvedPolicyPack, dict[str, str], UUID]:
    if target.reconciliation_type == "LEDGER":
        program = await session.scalar(
            select(Program).where(Program.id == target.program_id).with_for_update()
        )
        if program is None or program.status != "ACTIVE" or program.legal_entity_id is None:
            raise ApiError(
                409,
                "RECON_LEDGER_SCOPE_INVALID",
                "Active Program with an explicit legal entity is required",
            )
        legal_id = program.legal_entity_id
        binding = {"program_id": str(program.id), "legal_entity_id": str(legal_id)}
    else:
        assert target.source_legal_entity_id is not None
        legal_id = target.source_legal_entity_id
        role = SOURCE_ROLES[target.reconciliation_type]
        binding = {"legal_entity_id": str(legal_id), "role_code": role}
        authorizations = (
            await session.scalars(
                select(LegalAuthorization)
                .where(
                    LegalAuthorization.legal_entity_id == legal_id,
                    LegalAuthorization.role_code == role,
                    LegalAuthorization.lifecycle_status == "VALID",
                    LegalAuthorization.effective_from <= at,
                    or_(
                        LegalAuthorization.expires_at.is_(None), LegalAuthorization.expires_at > at
                    ),
                )
                .order_by(LegalAuthorization.id)
                .with_for_update()
            )
        ).all()
        if not any(
            authorization_valid_at(a, at=at, required_role=role, require_unscoped=True)
            for a in authorizations
        ):
            raise ApiError(
                409,
                "RECON_SOURCE_AUTHORIZATION_INVALID",
                "Currently valid unscoped source legal role is required",
            )
    entity = await session.scalar(
        select(LegalEntity).where(LegalEntity.id == legal_id).with_for_update()
    )
    if entity is None or entity.status != "ACTIVE":
        raise ApiError(
            409, "RECON_SOURCE_IDENTITY_INVALID", "Active source LegalEntity is required"
        )
    conditions = [
        PolicyVersion.scope_definition[key].astext == value for key, value in binding.items()
    ]
    packs = (
        await session.scalars(
            select(PolicyVersion)
            .where(
                PolicyVersion.policy_type == "PILOT_POLICY_PACK",
                PolicyVersion.lifecycle_status == "ACTIVE",
                *conditions,
                or_(PolicyVersion.effective_from.is_(None), PolicyVersion.effective_from <= at),
                or_(PolicyVersion.effective_to.is_(None), PolicyVersion.effective_to > at),
            )
            .order_by(PolicyVersion.id)
            .with_for_update()
        )
    ).all()
    if len(packs) != 1:
        raise ApiError(
            409,
            "RECON_SCOPE_NOT_FOUND" if not packs else "RECON_SCOPE_AMBIGUOUS",
            "Exactly one bound active pack is required",
        )
    scope = packs[0].scope_definition
    if (
        set(scope) != {"pilot_scope", *binding}
        or not isinstance(scope.get("pilot_scope"), str)
        or not scope["pilot_scope"].strip()
    ):
        raise ApiError(409, "RECON_SCOPE_INVALID", "Unsupported source pack dimensions")
    resolved = await resolve_active_policy_pack(session, scope_definition=scope, effective_at=at)
    return resolved, {key: str(value) for key, value in scope.items()}, legal_id
