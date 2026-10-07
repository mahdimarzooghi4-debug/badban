from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.policy_resolution import ResolvedPolicyPack, resolve_active_policy_pack
from badban.infrastructure.persistence.models import PolicyVersion

RECON_SCHEMA = "reconciliation-rules-v1"
RECON_TYPES = frozenset(
    {"LENDER", "GUARANTEE_ISSUER", "CUSTODY", "SETTLEMENT", "COLLATERAL_REGISTRY", "LEDGER"}
)
FIELDS = {
    "LENDER": {
        "external_loan_id",
        "original_principal",
        "outstanding_principal",
        "currency",
        "state",
    },
    "GUARANTEE_ISSUER": {
        "external_guarantee_id",
        "issued_amount",
        "currency",
        "state",
        "beneficiary",
    },
    "CUSTODY": {"asset_type", "quantity", "custody_reference", "state"},
    "SETTLEMENT": {"settlement_reference", "amount", "currency", "state", "value_date"},
    "COLLATERAL_REGISTRY": {"registration_id", "secured_amount", "state"},
    "LEDGER": {"account_code", "balance", "currency"},
}
DECIMAL_FIELDS = frozenset(
    {
        "original_principal",
        "outstanding_principal",
        "issued_amount",
        "quantity",
        "amount",
        "secured_amount",
        "balance",
    }
)
BLOCK_COMMANDS = frozenset(
    {
        "ReserveGuaranteeCapacity",
        "ActivateGuaranteedLoan",
        "ReduceGuaranteeExposure",
        "ReleaseBacking",
        "ApproveClaim",
        "SettleClaim",
        "CloseGuaranteeCase",
        "FinalizeParticipantExit",
        "MarkPaymentPaid",
        "CompleteReserveReplenishment",
        "CloseRecoveryCase",
    }
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ComparisonRule(StrictModel):
    rule_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,79}$")
    field_code: str
    comparison_mode: Literal["EXACT", "DECIMAL_EXACT", "TOLERANCE_BASED", "INFORMATIONAL"]
    materiality: Literal["INFO", "WARNING", "MATERIAL", "CRITICAL"]
    reason_code: str = Field(pattern=r"^RECON_[A-Z0-9_]{1,100}$")
    blocked_commands: tuple[str, ...]
    tolerance: str | None = Field(default=None, pattern=r"^\d+(?:\.\d+)?$", max_length=80)

    @model_validator(mode="after")
    def validate_rule(self) -> ComparisonRule:
        if (self.comparison_mode == "TOLERANCE_BASED") != (self.tolerance is not None):
            raise ValueError("only tolerance-based rules require an explicit tolerance")
        if self.comparison_mode in {"DECIMAL_EXACT", "TOLERANCE_BASED"}:
            if self.field_code not in DECIMAL_FIELDS:
                raise ValueError("decimal comparison requires a canonical decimal field")
        if self.tolerance is not None:
            value = Decimal(self.tolerance)
            if not value.is_finite() or value < 0:
                raise ValueError("tolerance must be finite and nonnegative")
        if self.comparison_mode == "INFORMATIONAL" and self.blocked_commands:
            raise ValueError("informational differences cannot block commands")
        if set(self.blocked_commands) - BLOCK_COMMANDS:
            raise ValueError("unknown blocked command type")
        return self


class SourceFreshness(StrictModel):
    internal_max_age_seconds: int = Field(strict=True, ge=0)
    external_max_age_seconds: int = Field(strict=True, ge=0)
    materiality: Literal["INFO", "WARNING", "MATERIAL", "CRITICAL"]
    blocked_commands: tuple[str, ...]

    @model_validator(mode="after")
    def validate_commands(self) -> SourceFreshness:
        if set(self.blocked_commands) - BLOCK_COMMANDS:
            raise ValueError("unknown blocked command type")
        return self


class ReconciliationRules(StrictModel):
    schema_version: Literal["reconciliation-rules-v1"]
    reconciliation_type: str
    rules: tuple[ComparisonRule, ...] = Field(min_length=1)
    freshness: SourceFreshness
    missing_record_materiality: Literal["INFO", "WARNING", "MATERIAL", "CRITICAL"]
    missing_record_blocked_commands: tuple[str, ...]
    cutoff_mismatch_materiality: Literal["INFO", "WARNING", "MATERIAL", "CRITICAL"]
    cutoff_mismatch_blocked_commands: tuple[str, ...]
    principal_invariant_blocked_commands: tuple[str, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> ReconciliationRules:
        if self.reconciliation_type not in RECON_TYPES:
            raise ValueError("unsupported reconciliation type")
        codes = [r.rule_code for r in self.rules]
        fields = [r.field_code for r in self.rules]
        if len(set(codes)) != len(codes) or len(set(fields)) != len(fields):
            raise ValueError("rules require unique identities and canonical fields")
        if set(fields) - FIELDS[self.reconciliation_type]:
            raise ValueError("unknown canonical reconciliation field")
        for commands in (
            self.missing_record_blocked_commands,
            self.cutoff_mismatch_blocked_commands,
            self.principal_invariant_blocked_commands,
        ):
            if set(commands) - BLOCK_COMMANDS:
                raise ValueError("unknown blocked command type")
        return self


def validate_reconciliation_component(
    policy: PolicyVersion, *, governed: bool
) -> ReconciliationRules:
    if governed:
        if (
            policy.lifecycle_status not in {"APPROVED", "ACTIVE", "SUPERSEDED", "RETIRED"}
            or policy.approved_at is None
            or policy.approved_by is None
            or policy.payload_hash != canonical_request_hash(policy.payload)
        ):
            raise ApiError(
                409,
                "RECON_POLICY_INTEGRITY_INVALID",
                "Reconciliation policy lacks valid approval/integrity proof",
            )
    try:
        rules = ReconciliationRules.model_validate(policy.payload)
    except ValidationError as exc:
        raise ApiError(
            409, "RECON_POLICY_INVALID", "Reconciliation policy schema is invalid"
        ) from exc
    if (
        policy.schema_version != RECON_SCHEMA
        or rules.reconciliation_type != policy.scope_definition.get("reconciliation_type")
        or not isinstance(policy.scope_definition.get("pilot_scope"), str)
        or not policy.scope_definition["pilot_scope"].strip()
    ):
        raise ApiError(
            409,
            "RECON_POLICY_SCOPE_INVALID",
            "Reconciliation policy scope/schema disagrees with payload",
        )
    return rules


async def validate_pack_reconciliation_components(
    session: AsyncSession, pack: PolicyVersion
) -> None:
    if pack.policy_type != "PILOT_POLICY_PACK":
        return
    ids = [UUID(x) for x in pack.payload["component_version_ids"]]
    components = (
        await session.scalars(
            select(PolicyVersion)
            .where(PolicyVersion.id.in_(ids), PolicyVersion.policy_type == "RECONCILIATION_POLICY")
            .with_for_update()
        )
    ).all()
    for component in components:
        validate_reconciliation_component(component, governed=True)


async def resolve_provider_pack(
    session: AsyncSession,
    *,
    provider_id: UUID,
    effective_at: datetime,
) -> tuple[ResolvedPolicyPack, dict[str, object]]:
    # Explicit provider binding; never accept caller-authored pilot_scope or global fallback.
    candidates = (
        await session.scalars(
            select(PolicyVersion).where(
                PolicyVersion.policy_type == "PILOT_POLICY_PACK",
                PolicyVersion.lifecycle_status == "ACTIVE",
                PolicyVersion.scope_definition["provider_id"].astext == str(provider_id),
                or_(
                    PolicyVersion.effective_from.is_(None),
                    PolicyVersion.effective_from <= effective_at,
                ),
                or_(
                    PolicyVersion.effective_to.is_(None), PolicyVersion.effective_to > effective_at
                ),
            )
        )
    ).all()
    if len(candidates) != 1:
        code = "RECON_SCOPE_NOT_FOUND" if not candidates else "RECON_SCOPE_AMBIGUOUS"
        raise ApiError(409, code, "Exactly one explicit provider-bound active pack is required")
    scope = candidates[0].scope_definition
    if (
        set(scope) != {"pilot_scope", "provider_id"}
        or not isinstance(scope["pilot_scope"], str)
        or not scope["pilot_scope"].strip()
    ):
        raise ApiError(
            409,
            "RECON_SCOPE_INVALID",
            "Provider reconciliation needs explicit pilot/provider scope",
        )
    pack = await resolve_active_policy_pack(
        session, scope_definition=scope, effective_at=effective_at
    )
    return pack, scope


async def resolve_reconciliation_policy(
    session: AsyncSession,
    *,
    pack: ResolvedPolicyPack,
    required_scope: dict[str, object],
) -> tuple[PolicyVersion, ReconciliationRules]:
    policies = (
        await session.scalars(
            select(PolicyVersion)
            .where(
                PolicyVersion.id.in_(pack.component_version_ids),
                PolicyVersion.policy_type == "RECONCILIATION_POLICY",
                PolicyVersion.scope_definition == required_scope,
            )
            .with_for_update()
        )
    ).all()
    if len(policies) != 1:
        code = "RECON_POLICY_NOT_FOUND" if not policies else "RECON_POLICY_AMBIGUOUS"
        raise ApiError(409, code, "Exactly one matching pinned reconciliation policy is required")
    policy = policies[0]
    return policy, validate_reconciliation_component(policy, governed=True)
