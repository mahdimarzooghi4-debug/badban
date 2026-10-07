from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.lender_adapter import (
    LenderAdapterError,
    LenderAdapterRegistry,
    LenderReconciliationScope,
    LenderReconciliationSnapshot,
)
from badban.application.reconciliation_sources import (
    LenderRecord,
    LenderSnapshot,
    ReconciliationSourcePort,
    ReconciliationSourceRegistry,
    ReconciliationSourceUnavailable,
    SourceCapability,
    SourceTarget,
)


class LenderReconciliationSource:
    """Read-only bridge to the existing configured lender adapter; no real implementation."""

    def __init__(
        self, provider_id: UUID, registry: LenderAdapterRegistry, *, at: datetime | None = None
    ):
        self.provider_id = provider_id
        self.registry = registry
        self.at = at

    def capability(self) -> SourceCapability:
        try:
            manifest = self.registry.resolve(self.provider_id).capability_manifest()
        except LenderAdapterError as exc:
            raise ReconciliationSourceUnavailable() from exc
        if not manifest.supports_reconciliation_snapshot:
            raise ApiError(
                409, "RECON_MAPPING_MISMATCH", "Adapter lacks independent reconciliation capability"
            )
        return SourceCapability(
            self.provider_id,
            "LENDER",
            manifest.provider_contract_version,
            manifest.adapter_mapping_version,
            normalization_version=manifest.inbound_normalization_version,
        )

    async def fetch_reconciliation_snapshot(
        self, target: SourceTarget, scope: dict[str, str]
    ) -> LenderSnapshot:
        capability = self.capability()
        try:
            legacy = await self.registry.resolve(self.provider_id).fetch_reconciliation_snapshot(
                LenderReconciliationScope(provider_id=self.provider_id)
            )
        except LenderAdapterError as exc:
            raise ReconciliationSourceUnavailable() from exc
        legacy = LenderReconciliationSnapshot.model_validate(legacy.model_dump(mode="json"))
        if legacy.provider_id != self.provider_id:
            raise ApiError(409, "RECON_MAPPING_MISMATCH", "Provider snapshot scope differs")
        if not legacy.evidence_references and not (
            legacy.source_reference and legacy.source_reference.strip()
        ):
            raise ApiError(409, "RECON_EVIDENCE_MISSING", "Independent source evidence is required")
        records = [
            LenderRecord(
                external_loan_id=loan.external_loan_id,
                original_principal=loan.original_principal,
                outstanding_principal=loan.outstanding_principal,
                currency=loan.currency,
                state=cast(
                    Literal["PENDING", "ACTIVE", "DELINQUENT", "SETTLED", "REPLACED"],
                    loan.provider_state,
                ),
                observed_at=loan.observed_at,
            ).model_dump(mode="json")
            for loan in legacy.loans
        ]
        data = dict(
            source_id=str(self.provider_id),
            scope_definition=scope,
            reconciliation_type="LENDER",
            snapshot_at=legacy.model_dump(mode="json")["snapshot_at"],
            received_at=(self.at or datetime.now(UTC)).isoformat().replace("+00:00", "Z"),
            source_reference=legacy.source_reference
            if legacy.source_reference and legacy.source_reference.strip()
            else canonical_request_hash(legacy.evidence_references),
            schema_version="reconciliation-source-v1",
            contract_version=capability.contract_version,
            mapping_version=capability.mapping_version,
            normalization_version=capability.normalization_version,
            evidence_references=legacy.evidence_references or [legacy.source_reference],
            coverage_from=None,
            coverage_to=None,
            watermark=None,
            records=records,
        )
        data["content_hash"] = canonical_request_hash(
            {k: v for k, v in data.items() if k != "received_at"}
        )
        return LenderSnapshot.model_validate(data)


class LenderSourceRegistry(ReconciliationSourceRegistry):
    def __init__(self, registry: LenderAdapterRegistry, *, at: datetime | None = None):
        super().__init__()
        self.lenders = registry
        self.at = at

    def resolve(self, target: SourceTarget) -> ReconciliationSourcePort:
        return LenderReconciliationSource(target.identity, self.lenders, at=self.at)
