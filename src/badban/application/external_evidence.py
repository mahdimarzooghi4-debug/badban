from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from badban.infrastructure.persistence.models import ExternalEvidenceSource

EvidencePurpose = Literal["VALUATION", "RESTRICTION", "ENCUMBRANCE"]
EvidenceResultStatus = Literal["VALID", "UNAVAILABLE", "INVALID"]
RestrictionState = Literal["CLEAR", "BLOCKED", "UNKNOWN"]


class EvidenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_position_id: UUID
    asset_type_id: UUID
    evidence_purpose: EvidencePurpose
    observed_at: AwareDatetime
    received_at: AwareDatetime
    status: EvidenceResultStatus
    evidence_reference: str | None = Field(default=None, min_length=1, max_length=500)
    contract_version: str
    schema_version: str
    source_value: Decimal | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=16)
    restriction_state: RestrictionState | None = None
    encumbrance_reference: str | None = Field(default=None, min_length=1, max_length=500)
    error_code: Literal[
        "SOURCE_UNAVAILABLE", "SOURCE_TIMEOUT", "SOURCE_TRANSPORT_ERROR", "SOURCE_CONTRACT_INVALID"
    ] | None = None

    @model_validator(mode="after")
    def validate_purpose_payload(self) -> EvidenceContract:
        if self.received_at < self.observed_at:
            raise ValueError("evidence receipt cannot predate source observation")
        if self.status == "VALID":
            if self.evidence_reference is None or self.error_code is not None:
                raise ValueError("valid evidence needs a reference and cannot include an error")
            if self.evidence_purpose == "VALUATION":
                if self.source_value is None or self.source_value <= 0 or self.currency is None:
                    raise ValueError("valid valuation evidence needs a positive value and currency")
                if self.restriction_state is not None or self.encumbrance_reference is not None:
                    raise ValueError("valuation evidence contains unrelated restriction fields")
            elif self.evidence_purpose == "RESTRICTION":
                if self.restriction_state is None:
                    raise ValueError("restriction evidence needs an explicit state")
                if self.source_value is not None or self.currency is not None:
                    raise ValueError("restriction evidence contains valuation fields")
            elif self.evidence_purpose == "ENCUMBRANCE":
                if self.encumbrance_reference is None:
                    raise ValueError("encumbrance evidence needs an explicit reference or CLEAR marker")
                if self.source_value is not None or self.currency is not None:
                    raise ValueError("encumbrance evidence contains valuation fields")
        else:
            if self.error_code is None:
                raise ValueError("unavailable or invalid evidence needs a stable error code")
            if any(
                value is not None
                for value in (
                    self.evidence_reference,
                    self.source_value,
                    self.currency,
                    self.restriction_state,
                    self.encumbrance_reference,
                )
            ):
                raise ValueError("failed evidence cannot carry authoritative facts")
        return self


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    asset_position_id: UUID
    asset_type_id: UUID
    evidence_purpose: EvidencePurpose


@dataclass(frozen=True, slots=True)
class EvidenceSourceDefinition:
    source_id: UUID
    source_key: str
    adapter_key: str
    evidence_purpose: EvidencePurpose
    asset_type_id: UUID
    contract_version: str
    schema_version: str

    @classmethod
    def from_record(cls, source: ExternalEvidenceSource) -> EvidenceSourceDefinition:
        return cls(
            source_id=source.id,
            source_key=source.source_key,
            adapter_key=source.adapter_key,
            evidence_purpose=source.evidence_purpose,  # type: ignore[arg-type]
            asset_type_id=source.asset_type_id,
            contract_version=source.contract_version,
            schema_version=source.schema_version,
        )


class ExternalEvidenceAdapter(Protocol):
    async def acquire(
        self,
        source: EvidenceSourceDefinition,
        request: EvidenceRequest,
    ) -> EvidenceContract: ...


class EvidenceAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ExternalEvidenceAdapter] = {}

    def register(self, adapter_key: str, adapter: ExternalEvidenceAdapter) -> None:
        normalized = adapter_key.strip()
        if not normalized or len(normalized) > 100:
            raise ValueError("adapter_key must be non-empty and at most 100 characters")
        if normalized in self._adapters:
            raise ValueError("evidence adapter is already registered")
        self._adapters[normalized] = adapter

    def resolve(self, adapter_key: str) -> ExternalEvidenceAdapter | None:
        return self._adapters.get(adapter_key)


def _failure(
    source: EvidenceSourceDefinition,
    request: EvidenceRequest,
    error_code: Literal[
        "SOURCE_UNAVAILABLE", "SOURCE_TIMEOUT", "SOURCE_TRANSPORT_ERROR", "SOURCE_CONTRACT_INVALID"
    ],
) -> EvidenceContract:
    return EvidenceContract(
        asset_position_id=request.asset_position_id,
        asset_type_id=request.asset_type_id,
        evidence_purpose=request.evidence_purpose,
        observed_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        status="INVALID" if error_code == "SOURCE_CONTRACT_INVALID" else "UNAVAILABLE",
        contract_version=source.contract_version,
        schema_version=source.schema_version,
        error_code=error_code,
    )


async def acquire_from_sources(
    registry: EvidenceAdapterRegistry,
    *,
    sources: tuple[EvidenceSourceDefinition, ...],
    request: EvidenceRequest,
) -> tuple[EvidenceContract, ...]:
    """Acquire independent source results in deterministic source order.

    This function never combines or chooses results. Callers must apply an
    explicitly approved policy before treating any valuation as eligible.
    """
    ordered = tuple(sorted(sources, key=lambda item: (item.source_key, str(item.source_id))))
    if any(
        source.asset_type_id != request.asset_type_id
        or source.evidence_purpose != request.evidence_purpose
        for source in ordered
    ):
        return tuple(
            _failure(source, request, "SOURCE_CONTRACT_INVALID") for source in ordered
        )

    async def acquire_one(source: EvidenceSourceDefinition) -> EvidenceContract:
        adapter = registry.resolve(source.adapter_key)
        if adapter is None:
            return _failure(source, request, "SOURCE_UNAVAILABLE")
        try:
            result = await adapter.acquire(source, request)
        except TimeoutError:
            return _failure(source, request, "SOURCE_TIMEOUT")
        except Exception:
            return _failure(source, request, "SOURCE_TRANSPORT_ERROR")
        try:
            validated = EvidenceContract.model_validate(result.model_dump(mode="python"))
        except Exception:
            return _failure(source, request, "SOURCE_CONTRACT_INVALID")
        if (
            validated.asset_position_id != request.asset_position_id
            or validated.asset_type_id != request.asset_type_id
            or validated.evidence_purpose != request.evidence_purpose
            or validated.contract_version != source.contract_version
            or validated.schema_version != source.schema_version
        ):
            return _failure(source, request, "SOURCE_CONTRACT_INVALID")
        return validated

    return tuple(await asyncio.gather(*(acquire_one(source) for source in ordered)))
