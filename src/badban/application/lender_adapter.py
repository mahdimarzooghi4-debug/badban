from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CANONICAL_LENDER_EVENTS = frozenset(
    {
        "LOAN_APPROVED",
        "LOAN_DISBURSED",
        "REPAYMENT_RECEIVED",
        "LOAN_DELINQUENT",
        "LOAN_SETTLED",
        "LOAN_CORRECTED",
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


class LenderAdapterError(RuntimeError):
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


class LenderCapabilityManifest(BaseModel):
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
        unknown = set(value) - CANONICAL_LENDER_EVENTS
        if unknown:
            raise ValueError(f"unsupported canonical lender events: {sorted(unknown)}")
        return value


@dataclass(frozen=True, slots=True)
class LenderInboundRequest:
    provider_id: UUID
    body: bytes
    headers: dict[str, str]
    received_at: datetime
    correlation_id: UUID


class NormalizedLenderEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    external_event_id: str = Field(min_length=1, max_length=200)
    event_type: Literal[
        "LOAN_APPROVED",
        "LOAN_DISBURSED",
        "REPAYMENT_RECEIVED",
        "LOAN_DELINQUENT",
        "LOAN_SETTLED",
        "LOAN_CORRECTED",
    ]
    schema_version: int = Field(ge=1)
    external_loan_id: str = Field(min_length=1, max_length=255)
    event_time: datetime
    received_at: datetime
    original_principal: str = Field(
        pattern=r"^\d+(?:\.\d+)?$",
        max_length=80,
    )
    disbursed_principal: str | None = Field(
        default=None,
        pattern=r"^\d+(?:\.\d+)?$",
        max_length=80,
    )
    outstanding_principal: str = Field(
        pattern=r"^\d+(?:\.\d+)?$",
        max_length=80,
    )
    currency: str = Field(min_length=1, max_length=16)
    repayment_reference: str | None = Field(default=None, min_length=1, max_length=255)
    delinquency_state: str | None = Field(default=None, min_length=1, max_length=80)
    evidence_references: list[str] = Field(default_factory=list)
    payload_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$", min_length=64, max_length=64)
    provider_contract_version: str = Field(min_length=1, max_length=80)
    adapter_mapping_version: str = Field(min_length=1, max_length=80)
    inbound_normalization_version: str = Field(min_length=1, max_length=80)
    provider_event_sequence: int | None = Field(default=None, ge=0)
    guarantee_case_id: UUID | None = None
    correlation_id: UUID | None = None

    @field_validator("event_time", "received_at")
    @classmethod
    def timestamps_are_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("lender event timestamps must be timezone-aware")
        return value

    @field_validator("evidence_references")
    @classmethod
    def evidence_references_are_nonblank(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence references must not contain blank values")
        return value

    @model_validator(mode="after")
    def validate_authoritative_fields(self) -> NormalizedLenderEvent:
        try:
            original = Decimal(self.original_principal)
            outstanding = Decimal(self.outstanding_principal)
            disbursed = (
                Decimal(self.disbursed_principal) if self.disbursed_principal is not None else None
            )
        except InvalidOperation as exc:
            raise ValueError("lender monetary fields must be decimal strings") from exc

        if not original.is_finite() or original <= 0:
            raise ValueError("original_principal must be finite and positive")
        if not outstanding.is_finite() or outstanding < 0:
            raise ValueError("outstanding_principal must be finite and non-negative")
        _validate_decimal_storage_boundary("original_principal", original)
        _validate_decimal_storage_boundary("outstanding_principal", outstanding)
        if outstanding > original:
            raise ValueError("outstanding_principal cannot exceed original_principal")
        if disbursed is not None:
            if not disbursed.is_finite() or disbursed < 0:
                raise ValueError("disbursed_principal must be finite and non-negative")
            _validate_decimal_storage_boundary("disbursed_principal", disbursed)
        if self.event_type == "LOAN_DISBURSED" and (disbursed is None or disbursed <= 0):
            raise ValueError("LOAN_DISBURSED requires positive disbursed_principal")
        if self.event_type == "REPAYMENT_RECEIVED" and self.repayment_reference is None:
            raise ValueError("REPAYMENT_RECEIVED requires repayment_reference")
        if self.event_type == "LOAN_DELINQUENT" and self.delinquency_state is None:
            raise ValueError("LOAN_DELINQUENT requires delinquency_state")
        return self

    def original_principal_decimal(self) -> Decimal:
        return Decimal(self.original_principal)

    def outstanding_principal_decimal(self) -> Decimal:
        return Decimal(self.outstanding_principal)


class LenderOutboundCommand(BaseModel):
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


class LenderOperationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: OperationState
    provider_request_id: str | None = None
    provider_entity_id: str | None = None
    external_status: str | None = None
    observed_at: datetime | None = None


class LenderStateQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    external_loan_id: str = Field(min_length=1, max_length=255)


class LenderProviderState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    external_loan_id: str = Field(min_length=1, max_length=255)
    provider_state: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    evidence_references: list[str] = Field(default_factory=list)

    @field_validator("observed_at")
    @classmethod
    def observed_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("lender provider-state timestamp must be timezone-aware")
        return value

    @field_validator("evidence_references")
    @classmethod
    def provider_state_evidence_references_are_nonblank(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence references must not contain blank values")
        return value


class LenderReconciliationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    scope_reference: str | None = None


class LenderReconciliationLoan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_loan_id: str = Field(min_length=1, max_length=255)
    original_principal: str = Field(pattern=r"^\d+(?:\.\d+)?$", max_length=80)
    outstanding_principal: str = Field(pattern=r"^\d+(?:\.\d+)?$", max_length=80)
    currency: str = Field(min_length=1, max_length=16)
    provider_state: str = Field(min_length=1, max_length=120)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def observed_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reconciliation loan timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_reconciliation_money(self) -> LenderReconciliationLoan:
        try:
            original = Decimal(self.original_principal)
            outstanding = Decimal(self.outstanding_principal)
        except InvalidOperation as exc:
            raise ValueError("reconciliation monetary fields must be decimal strings") from exc

        if not original.is_finite() or original <= 0:
            raise ValueError("original_principal must be finite and positive")
        if not outstanding.is_finite() or outstanding < 0:
            raise ValueError("outstanding_principal must be finite and non-negative")
        _validate_decimal_storage_boundary("original_principal", original)
        _validate_decimal_storage_boundary("outstanding_principal", outstanding)
        if outstanding > original:
            raise ValueError("outstanding_principal cannot exceed original_principal")
        return self


class LenderReconciliationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: UUID
    snapshot_at: datetime
    source_reference: str | None = Field(default=None, min_length=1, max_length=500)
    evidence_references: list[str] = Field(default_factory=list)
    loans: list[LenderReconciliationLoan]

    @field_validator("snapshot_at")
    @classmethod
    def snapshot_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reconciliation snapshot timestamp must be timezone-aware")
        return value

    @field_validator("evidence_references")
    @classmethod
    def reconciliation_evidence_references_are_nonblank(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evidence references must not contain blank values")
        return value


class TranslatedProviderError(BaseModel):
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


class LenderAdapter(Protocol):
    def capability_manifest(self) -> LenderCapabilityManifest: ...

    async def submit_command(self, command: LenderOutboundCommand) -> LenderOperationResult: ...

    async def fetch_state(self, query: LenderStateQuery) -> LenderProviderState: ...

    async def fetch_reconciliation_snapshot(
        self,
        scope: LenderReconciliationScope,
    ) -> LenderReconciliationSnapshot: ...

    async def verify_and_normalize(
        self,
        request: LenderInboundRequest,
    ) -> NormalizedLenderEvent: ...

    def translate_error(self, error: Exception) -> TranslatedProviderError: ...

    async def health_check(self) -> AdapterHealth: ...


class LenderAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[UUID, LenderAdapter] = {}

    def register(self, provider_id: UUID, adapter: LenderAdapter) -> None:
        self._adapters[provider_id] = adapter

    def unregister(self, provider_id: UUID) -> None:
        self._adapters.pop(provider_id, None)

    def resolve(self, provider_id: UUID) -> LenderAdapter:
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            raise LenderAdapterError(
                "LENDER_ADAPTER_NOT_CONFIGURED",
                "No authenticated lender adapter is configured for this provider",
            )
        return adapter
