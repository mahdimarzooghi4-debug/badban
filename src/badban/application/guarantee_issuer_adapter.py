from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CANONICAL_GUARANTEE_ISSUER_EVENTS = frozenset(
    {
        "GUARANTEE_ISSUED",
        "GUARANTEE_CANCELLED",
        "GUARANTEE_RELEASED",
        "CLAIM_ACKNOWLEDGED",
        "CLAIM_SETTLEMENT_CONFIRMED",
    }
)

AdapterHealth = Literal[
    "AVAILABLE",
    "DEGRADED",
    "UNAVAILABLE",
    "AUTH_FAILURE",
    "CONTRACT_MISMATCH",
]
ErrorClassification = Literal["RETRYABLE", "NON_RETRYABLE", "UNKNOWN_OUTCOME"]
OperationState = Literal[
    "PENDING",
    "SENT",
    "ACKNOWLEDGED",
    "CONFIRMED",
    "RETRYABLE_FAILED",
    "NON_RETRYABLE_FAILED",
    "UNKNOWN_OUTCOME",
    "EXPIRED",
    "CANCELLED",
]

_MAX_DECIMAL_INTEGER_DIGITS = 20
_MAX_DECIMAL_SCALE = 18


def _validate_decimal_storage_boundary(name: str, value: Decimal) -> None:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError(f"{name} must use a finite decimal exponent")
    scale = max(-exponent, 0)
    integer_digits = max(value.adjusted() + 1, 0)
    if scale > _MAX_DECIMAL_SCALE or integer_digits > _MAX_DECIMAL_INTEGER_DIGITS:
        raise ValueError(f"{name} exceeds NUMERIC(38,18) precision")


class GuaranteeIssuerAdapterError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        classification: ErrorClassification = "NON_RETRYABLE",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.classification = classification


class GuaranteeIssuerCapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    integration_modes: frozenset[
        Literal["API", "WEBHOOK_CALLBACK", "POLLING", "SECURE_BATCH_FILE", "CONTROLLED_MANUAL"]
    ]
    supported_commands: frozenset[str] = frozenset()
    supported_inbound_events: frozenset[str]
    authentication_method: str
    supports_polling: bool
    supports_webhook: bool
    supports_reconciliation_snapshot: bool
    supports_idempotency_key: bool
    supports_event_sequence: bool
    rate_limit_policy_reference: str | None = None
    provider_contract_version: str
    adapter_mapping_version: str
    inbound_normalization_version: str
    outbound_mapping_version: str

    @field_validator(
        "authentication_method",
        "provider_contract_version",
        "adapter_mapping_version",
        "inbound_normalization_version",
        "outbound_mapping_version",
    )
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("adapter manifest text fields must not be blank")
        return value

    @field_validator("supported_inbound_events")
    @classmethod
    def supported_events_are_canonical(cls, value: frozenset[str]) -> frozenset[str]:
        unknown = set(value) - CANONICAL_GUARANTEE_ISSUER_EVENTS
        if unknown:
            raise ValueError(f"unsupported canonical guarantee issuer events: {sorted(unknown)}")
        return value


@dataclass(frozen=True, slots=True)
class GuaranteeIssuerInboundRequest:
    provider_id: UUID
    body: bytes
    headers: dict[str, str]
    received_at: datetime
    correlation_id: UUID


class NormalizedGuaranteeIssuerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    external_event_id: str = Field(min_length=1, max_length=200)
    event_type: Literal[
        "GUARANTEE_ISSUED",
        "GUARANTEE_CANCELLED",
        "GUARANTEE_RELEASED",
        "CLAIM_ACKNOWLEDGED",
        "CLAIM_SETTLEMENT_CONFIRMED",
    ]
    schema_version: int = Field(ge=1)
    external_guarantee_id: str = Field(min_length=1, max_length=255)
    issued_amount: str = Field(pattern=r"^\d+(?:\.\d+)?$", max_length=80)
    beneficiary_lender_reference: str = Field(min_length=1, max_length=255)
    issue_date: datetime
    provider_state: str = Field(min_length=1, max_length=120)
    claim_reference: str | None = Field(default=None, min_length=1, max_length=255)
    settlement_reference: str | None = Field(default=None, min_length=1, max_length=255)
    event_time: datetime
    received_at: datetime
    evidence_references: list[str] = Field(min_length=1)
    payload_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$", min_length=64, max_length=64)
    provider_contract_version: str = Field(min_length=1, max_length=80)
    adapter_mapping_version: str = Field(min_length=1, max_length=80)
    inbound_normalization_version: str = Field(min_length=1, max_length=80)
    provider_event_sequence: int | None = Field(default=None, ge=0)
    correlation_id: UUID | None = None

    @field_validator("issue_date", "event_time", "received_at")
    @classmethod
    def timestamps_are_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("guarantee issuer timestamps must be timezone-aware")
        return value

    @field_validator("evidence_references")
    @classmethod
    def evidence_references_are_nonblank(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence references must not contain blank values")
        return value

    @model_validator(mode="after")
    def validate_authoritative_fields(self) -> NormalizedGuaranteeIssuerEvent:
        try:
            issued_amount = Decimal(self.issued_amount)
        except InvalidOperation as exc:
            raise ValueError("issued_amount must be a decimal string") from exc
        if not issued_amount.is_finite() or issued_amount <= 0:
            raise ValueError("issued_amount must be finite and positive")
        _validate_decimal_storage_boundary("issued_amount", issued_amount)
        if self.event_type == "CLAIM_ACKNOWLEDGED" and self.claim_reference is None:
            raise ValueError("CLAIM_ACKNOWLEDGED requires claim_reference")
        if self.event_type == "CLAIM_SETTLEMENT_CONFIRMED":
            if self.claim_reference is None:
                raise ValueError("CLAIM_SETTLEMENT_CONFIRMED requires claim_reference")
            if self.settlement_reference is None:
                raise ValueError("CLAIM_SETTLEMENT_CONFIRMED requires settlement_reference")
        return self

    def issued_amount_decimal(self) -> Decimal:
        return Decimal(self.issued_amount)


class GuaranteeIssuerOutboundCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    provider_id: UUID
    operation_type: str = Field(min_length=1, max_length=120)
    business_reference: str = Field(min_length=1, max_length=255)
    idempotency_key: str = Field(min_length=1, max_length=200)
    correlation_id: UUID
    effective_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_references: list[str] = Field(default_factory=list)


class GuaranteeIssuerOperationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: OperationState
    provider_request_id: str | None = None
    provider_entity_id: str | None = None
    external_status: str | None = None
    observed_at: datetime | None = None


class GuaranteeIssuerStateQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    external_guarantee_id: str = Field(min_length=1, max_length=255)


class GuaranteeIssuerProviderState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    external_guarantee_id: str = Field(min_length=1, max_length=255)
    provider_state: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    evidence_references: list[str] = Field(default_factory=list)

    @field_validator("observed_at")
    @classmethod
    def observed_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("guarantee issuer state timestamp must be timezone-aware")
        return value

    @field_validator("evidence_references")
    @classmethod
    def provider_state_evidence_references_are_nonblank(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence references must not contain blank values")
        return value


class GuaranteeIssuerReconciliationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    scope_reference: str | None = None


class GuaranteeIssuerReconciliationGuarantee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_guarantee_id: str = Field(min_length=1, max_length=255)
    issued_amount: str = Field(pattern=r"^\d+(?:\.\d+)?$", max_length=80)
    beneficiary_lender_reference: str = Field(min_length=1, max_length=255)
    issue_date: datetime
    provider_state: str = Field(min_length=1, max_length=120)
    claim_reference: str | None = Field(default=None, min_length=1, max_length=255)
    settlement_reference: str | None = Field(default=None, min_length=1, max_length=255)
    observed_at: datetime
    evidence_references: list[str] = Field(default_factory=list)

    @field_validator("issue_date", "observed_at")
    @classmethod
    def timestamps_are_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("guarantee issuer reconciliation timestamps must be timezone-aware")
        return value

    @field_validator("evidence_references")
    @classmethod
    def reconciliation_evidence_references_are_nonblank(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence references must not contain blank values")
        return value

    @model_validator(mode="after")
    def validate_issued_amount(self) -> GuaranteeIssuerReconciliationGuarantee:
        try:
            issued_amount = Decimal(self.issued_amount)
        except InvalidOperation as exc:
            raise ValueError("issued_amount must be a decimal string") from exc
        if not issued_amount.is_finite() or issued_amount <= 0:
            raise ValueError("issued_amount must be finite and positive")
        _validate_decimal_storage_boundary("issued_amount", issued_amount)
        return self


class GuaranteeIssuerReconciliationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    snapshot_at: datetime
    source_reference: str | None = Field(default=None, min_length=1, max_length=500)
    evidence_references: list[str] = Field(default_factory=list)
    guarantees: list[GuaranteeIssuerReconciliationGuarantee]

    @field_validator("snapshot_at")
    @classmethod
    def snapshot_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "guarantee issuer reconciliation snapshot timestamp must be timezone-aware"
            )
        return value

    @field_validator("evidence_references")
    @classmethod
    def snapshot_evidence_references_are_nonblank(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence references must not contain blank values")
        return value

    @model_validator(mode="after")
    def require_source_or_evidence(self) -> GuaranteeIssuerReconciliationSnapshot:
        if self.source_reference is None and not self.evidence_references:
            raise ValueError("reconciliation snapshot requires source or evidence reference")
        return self


class TranslatedGuaranteeIssuerError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "PROVIDER_AUTHENTICATION_FAILED",
        "PROVIDER_TIMEOUT",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_SCHEMA_REJECTED",
        "PROVIDER_BUSINESS_REJECTED",
        "PROVIDER_REFERENCE_NOT_FOUND",
        "PROVIDER_DUPLICATE_REQUEST",
        "PROVIDER_OUTCOME_UNKNOWN",
        "PROVIDER_CONTRACT_MISMATCH",
    ]
    classification: ErrorClassification


class GuaranteeIssuerAdapter(Protocol):
    def capability_manifest(self) -> GuaranteeIssuerCapabilityManifest: ...

    async def submit_command(
        self,
        command: GuaranteeIssuerOutboundCommand,
    ) -> GuaranteeIssuerOperationResult: ...

    async def fetch_state(
        self,
        query: GuaranteeIssuerStateQuery,
    ) -> GuaranteeIssuerProviderState: ...

    async def fetch_reconciliation_snapshot(
        self,
        scope: GuaranteeIssuerReconciliationScope,
    ) -> GuaranteeIssuerReconciliationSnapshot: ...

    async def verify_and_normalize(
        self,
        request: GuaranteeIssuerInboundRequest,
    ) -> NormalizedGuaranteeIssuerEvent: ...

    def translate_error(self, error: Exception) -> TranslatedGuaranteeIssuerError: ...

    async def health_check(self) -> AdapterHealth: ...


class GuaranteeIssuerAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[UUID, GuaranteeIssuerAdapter] = {}

    def register(self, provider_id: UUID, adapter: GuaranteeIssuerAdapter) -> None:
        self._adapters[provider_id] = adapter

    def unregister(self, provider_id: UUID) -> None:
        self._adapters.pop(provider_id, None)

    def resolve(self, provider_id: UUID) -> GuaranteeIssuerAdapter:
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            raise GuaranteeIssuerAdapterError(
                "GUARANTEE_ISSUER_ADAPTER_NOT_CONFIGURED",
                "No authenticated guarantee issuer adapter is configured for this provider",
            )
        return adapter
