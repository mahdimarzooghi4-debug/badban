from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.idempotency import canonical_request_hash
from badban.application.reconciliation_sources import (
    InternalAssetInventoryRecord,
    InternalAssetInventorySnapshot,
    ReconciliationSourceAcquisitionError,
    ReconciliationSourcePort,
    ReconciliationSourceUnavailable,
    SourceCapability,
    SourceTarget,
)
from badban.infrastructure.persistence.models import AssetPosition, AssetType, ParticipationEpisode


class InternalAssetInventorySource(ReconciliationSourcePort):
    """Read-only snapshot of Badban's own asset-position inventory."""

    def __init__(self, session: AsyncSession, *, program_id: UUID) -> None:
        self._session = session
        self._program_id = program_id

    def capability(self) -> SourceCapability:
        return SourceCapability(
            source_id=self._program_id,
            reconciliation_type="INTERNAL_ASSET_INVENTORY",
            contract_version="internal-asset-inventory-v1",
            mapping_version="asset-position-fields-v1",
            schema_version="reconciliation-source-v1",
        )

    async def fetch_reconciliation_snapshot(
        self, target: SourceTarget, scope: dict[str, str]
    ) -> InternalAssetInventorySnapshot:
        if (
            target.reconciliation_type != "INTERNAL_ASSET_INVENTORY"
            or target.program_id != self._program_id
            or target.provider_id is not None
            or target.source_legal_entity_id is not None
            or scope != {"program_id": str(self._program_id)}
        ):
            raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

        cutoff = select(func.statement_timestamp()).scalar_subquery()
        rows = (
            await self._session.execute(
                select(AssetPosition, AssetType, ParticipationEpisode, cutoff.label("snapshot_at"))
                .join(AssetType, AssetType.id == AssetPosition.asset_type_id)
                .join(
                    ParticipationEpisode,
                    ParticipationEpisode.id == AssetPosition.participation_episode_id,
                )
                .where(
                    AssetPosition.program_id == self._program_id,
                    AssetPosition.updated_at <= cutoff,
                    AssetType.updated_at <= cutoff,
                    ParticipationEpisode.updated_at <= cutoff,
                )
                .order_by(AssetPosition.id)
            )
        ).all()
        if not rows:
            raise ReconciliationSourceUnavailable()

        snapshot_at = rows[0][3]
        records: list[InternalAssetInventoryRecord] = []
        for position, asset_type, episode, _ in rows:
            if (
                position.program_id != self._program_id
                or episode.program_id != self._program_id
                or position.participation_episode_id != episode.id
                or position.asset_type_id != asset_type.id
                or position.version < 1
                or asset_type.version < 1
                or episode.version < 1
            ):
                raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
            if position.ownership_funding_type not in {
                "PARTICIPANT_OWNED",
                "PROGRAM_ATTRIBUTED",
            }:
                raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
            quantity = Decimal(position.quantity)
            if not quantity.is_finite() or quantity < 0:
                raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
            try:
                record = InternalAssetInventoryRecord(
                    observed_at=position.updated_at,
                    asset_position_id=position.id,
                    position_version=position.version,
                    participation_episode_id=episode.id,
                    asset_type_id=asset_type.id,
                    asset_type_code=asset_type.asset_code,
                    asset_type_status=asset_type.status,
                    program_id=position.program_id,
                    ownership_funding_type=cast(
                        Literal["PARTICIPANT_OWNED", "PROGRAM_ATTRIBUTED"],
                        position.ownership_funding_type,
                    ),
                    legal_owner_entity_id=position.legal_owner_entity_id,
                    legal_owner_participant_id=position.legal_owner_participant_id,
                    custodian_legal_entity_id=position.custodian_legal_entity_id,
                    quantity=format(quantity, "f"),
                    unit_code=position.unit_code,
                    lifecycle_status=position.lifecycle_status,
                    source_reference=position.source_reference,
                )
            except ValueError as exc:
                raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID") from exc
            records.append(record)

        return build_internal_asset_inventory_snapshot(
            records,
            program_id=self._program_id,
            snapshot_at=snapshot_at,
            received_at=datetime.now(UTC),
        )


def build_internal_asset_inventory_snapshot(
    records: list[InternalAssetInventoryRecord],
    *,
    program_id: UUID,
    snapshot_at: datetime,
    received_at: datetime,
) -> InternalAssetInventorySnapshot:
    if not records:
        raise ReconciliationSourceUnavailable()
    if any(
        record.program_id != program_id or record.observed_at > snapshot_at for record in records
    ):
        raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
    if len({record.asset_position_id for record in records}) != len(records):
        raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")
    if len(records) > 10000:
        raise ReconciliationSourceAcquisitionError("SOURCE_CONTRACT_INVALID")

    evidence = tuple(sorted(f"asset-position:{record.asset_position_id}" for record in records))
    draft = InternalAssetInventorySnapshot.model_construct(
        source_id=program_id,
        reconciliation_type="INTERNAL_ASSET_INVENTORY",
        scope_definition={"program_id": str(program_id)},
        snapshot_at=snapshot_at,
        received_at=received_at,
        source_reference=f"badban:asset-positions:program:{program_id}:{snapshot_at.isoformat()}",
        schema_version="reconciliation-source-v1",
        contract_version="internal-asset-inventory-v1",
        mapping_version="asset-position-fields-v1",
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
    return InternalAssetInventorySnapshot.model_validate(payload)
