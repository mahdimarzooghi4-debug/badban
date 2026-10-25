from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.idempotency import canonical_request_hash
from badban.application.reconciliation_sources import (
    InternalValuationObservationRecord,
    InternalValuationObservationSnapshot,
    ReconciliationSourceAcquisitionError,
    ReconciliationSourcePort,
    ReconciliationSourceUnavailable,
    SourceCapability,
    SourceTarget,
)
from badban.infrastructure.persistence.models import AssetPosition, ValuationObservation


class InternalValuationObservationSource(ReconciliationSourcePort):
    """Read recorded valuation observations without assessing their validity."""

    def __init__(self, session: AsyncSession, *, program_id: UUID) -> None:
        self._session = session
        self._program_id = program_id

    def capability(self) -> SourceCapability:
        return SourceCapability(
            source_id=self._program_id,
            reconciliation_type="INTERNAL_VALUATION_OBSERVATION",
            contract_version="internal-valuation-observation-v1",
            mapping_version="recorded-valuation-fields-v1",
            schema_version="reconciliation-source-v1",
        )

    async def fetch_reconciliation_snapshot(
        self, target: SourceTarget, scope: dict[str, str]
    ) -> InternalValuationObservationSnapshot:
        if (
            target.reconciliation_type != "INTERNAL_VALUATION_OBSERVATION"
            or target.program_id != self._program_id
            or target.provider_id is not None
            or target.source_legal_entity_id is not None
            or scope != {"program_id": str(self._program_id)}
        ):
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

        cutoff = select(func.statement_timestamp()).scalar_subquery()
        rows = (
            await self._session.execute(
                select(ValuationObservation, AssetPosition, cutoff.label("snapshot_at"))
                .join(AssetPosition, AssetPosition.id == ValuationObservation.asset_position_id)
                .where(
                    AssetPosition.program_id == self._program_id,
                    ValuationObservation.received_at <= cutoff,
                )
                .order_by(
                    ValuationObservation.observed_at,
                    ValuationObservation.id,
                )
                .limit(1001)
            )
        ).all()
        if not rows:
            raise ReconciliationSourceUnavailable()

        snapshot_at = rows[0][2]
        records: list[InternalValuationObservationRecord] = []
        for observation, position, _ in rows:
            if (
                position.program_id != self._program_id
                or observation.asset_position_id != position.id
                or observation.observed_at > snapshot_at
                or observation.received_at > snapshot_at
            ):
                raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
            quantities = (
                Decimal(observation.valued_quantity),
                Decimal(observation.unit_price),
                Decimal(observation.gross_market_value),
            )
            fx_rate = Decimal(observation.fx_rate) if observation.fx_rate is not None else None
            if any(not value.is_finite() or value < 0 for value in quantities):
                raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
            if fx_rate is not None and (not fx_rate.is_finite() or fx_rate <= 0):
                raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
            records.append(
                InternalValuationObservationRecord(
                    observed_at=observation.observed_at,
                    observation_id=observation.id,
                    asset_position_id=position.id,
                    program_id=position.program_id,
                    valued_quantity=format(quantities[0], "f"),
                    unit_price=format(quantities[1], "f"),
                    valuation_currency=observation.valuation_currency,
                    fx_rate=format(fx_rate, "f") if fx_rate is not None else None,
                    gross_market_value=format(quantities[2], "f"),
                    source_name=observation.source_name,
                    source_reference=observation.source_reference,
                    source_version_reference=observation.source_version_reference,
                    received_at=observation.received_at,
                    valid_until=observation.valid_until,
                    freshness_status=observation.freshness_status,
                    evidence_reference=observation.evidence_reference,
                )
            )

        return build_internal_valuation_snapshot(
            records,
            program_id=self._program_id,
            snapshot_at=snapshot_at,
            received_at=datetime.now(UTC),
        )


def build_internal_valuation_snapshot(
    records: list[InternalValuationObservationRecord],
    *,
    program_id: UUID,
    snapshot_at: datetime,
    received_at: datetime,
) -> InternalValuationObservationSnapshot:
    if not records:
        raise ReconciliationSourceUnavailable()
    if any(
        record.program_id != program_id
        or record.observed_at > snapshot_at
        or record.received_at > snapshot_at
        for record in records
    ):
        raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
    if len({record.observation_id for record in records}) != len(records):
        raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
    if len(records) > 1000:
        raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

    evidence = tuple(sorted(f"valuation-observation:{record.observation_id}" for record in records))
    draft = InternalValuationObservationSnapshot.model_construct(
        source_id=program_id,
        reconciliation_type="INTERNAL_VALUATION_OBSERVATION",
        scope_definition={"program_id": str(program_id)},
        snapshot_at=snapshot_at,
        received_at=received_at,
        source_reference=f"badban:valuation-observations:program:{program_id}:{snapshot_at.isoformat()}",
        schema_version="reconciliation-source-v1",
        contract_version="internal-valuation-observation-v1",
        mapping_version="recorded-valuation-fields-v1",
        normalization_version=None,
        evidence_references=evidence,
        coverage_from=min(record.observed_at for record in records),
        coverage_to=snapshot_at,
        watermark=snapshot_at.isoformat(),
        content_hash="0" * 64,
        records=tuple(records),
    )
    payload = draft.model_dump(mode="json")
    payload["content_hash"] = canonical_request_hash(draft.semantic_payload())
    return InternalValuationObservationSnapshot.model_validate(payload)
