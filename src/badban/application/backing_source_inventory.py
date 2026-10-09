from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    ParticipationEpisode,
    ValuationObservation,
)


class BackingInventoryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValuationSource:
    observation_id: UUID
    asset_position_id: UUID
    valued_quantity: Decimal
    unit_price: Decimal
    valuation_currency: str
    fx_rate: Decimal | None
    gross_market_value: Decimal
    source_name: str
    source_reference: str
    source_version_reference: str | None
    observed_at: datetime
    received_at: datetime
    valid_until: datetime | None
    recorded_freshness_status: str
    evidence_reference: str | None


@dataclass(frozen=True, slots=True)
class AssetSource:
    position_id: UUID
    position_version: int
    asset_type_id: UUID
    asset_type_version: int
    asset_type_code: str
    asset_type_status: str
    episode_id: UUID
    program_id: UUID
    ownership_funding_type: str
    legal_owner_participant_id: UUID | None
    legal_owner_entity_id: UUID | None
    custodian_legal_entity_id: UUID | None
    quantity: Decimal
    unit_code: str
    lifecycle_status: str
    source_reference: str | None
    valuation_history: tuple[ValuationSource, ...]


@dataclass(frozen=True, slots=True)
class BackingSourceInventory:
    episode_id: UUID
    episode_version: int
    episode_status: str
    participant_id: UUID
    program_id: UUID
    episode_consent_state: str
    sources: tuple[AssetSource, ...]

    @property
    def source_fingerprint(self) -> str:
        """Fingerprint this read projection, not an eligibility or reservation attestation."""
        encoded = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _valuation_source(value: ValuationObservation) -> ValuationSource:
    return ValuationSource(
        observation_id=value.id,
        asset_position_id=value.asset_position_id,
        valued_quantity=value.valued_quantity,
        unit_price=value.unit_price,
        valuation_currency=value.valuation_currency,
        fx_rate=value.fx_rate,
        gross_market_value=value.gross_market_value,
        source_name=value.source_name,
        source_reference=value.source_reference,
        source_version_reference=value.source_version_reference,
        observed_at=value.observed_at,
        received_at=value.received_at,
        valid_until=value.valid_until,
        recorded_freshness_status=value.freshness_status,
        evidence_reference=value.evidence_reference,
    )


def _asset_source(
    *,
    episode: ParticipationEpisode,
    position: AssetPosition,
    asset_type: AssetType | None,
    observations: tuple[ValuationSource, ...],
) -> AssetSource:
    if position.participation_episode_id != episode.id or position.program_id != episode.program_id:
        raise BackingInventoryError(
            "BACKING_SOURCE_SCOPE_CONFLICT", "AssetPosition episode/program lineage is inconsistent"
        )
    if asset_type is None or asset_type.id != position.asset_type_id:
        raise BackingInventoryError(
            "BACKING_SOURCE_TYPE_MISSING", "AssetPosition has no matching AssetType source"
        )
    if asset_type.unit_code != position.unit_code:
        raise BackingInventoryError(
            "BACKING_SOURCE_UNIT_CONFLICT", "AssetPosition unit differs from AssetType unit"
        )
    if position.ownership_funding_type == "PARTICIPANT_OWNED":
        if (
            position.legal_owner_participant_id != episode.participant_id
            or position.legal_owner_entity_id is not None
        ):
            raise BackingInventoryError(
                "BACKING_SOURCE_OWNER_CONFLICT",
                "Participant-owned AssetPosition does not match its ParticipationEpisode",
            )
    elif position.ownership_funding_type == "PROGRAM_ATTRIBUTED":
        if (
            position.legal_owner_entity_id is None
            or position.legal_owner_participant_id is not None
        ):
            raise BackingInventoryError(
                "BACKING_SOURCE_OWNER_CONFLICT", "Program-attributed source has invalid owner"
            )
    else:
        raise BackingInventoryError(
            "BACKING_SOURCE_OWNER_CONFLICT", "Unknown asset ownership classification"
        )
    if position.version < 1 or asset_type.version < 1:
        raise BackingInventoryError(
            "BACKING_SOURCE_VERSION_INVALID", "Backing source has no valid aggregate version"
        )
    return AssetSource(
        position_id=position.id,
        position_version=position.version,
        asset_type_id=asset_type.id,
        asset_type_version=asset_type.version,
        asset_type_code=asset_type.asset_code,
        asset_type_status=asset_type.status,
        episode_id=position.participation_episode_id,
        program_id=position.program_id,
        ownership_funding_type=position.ownership_funding_type,
        legal_owner_participant_id=position.legal_owner_participant_id,
        legal_owner_entity_id=position.legal_owner_entity_id,
        custodian_legal_entity_id=position.custodian_legal_entity_id,
        quantity=position.quantity,
        unit_code=position.unit_code,
        lifecycle_status=position.lifecycle_status,
        source_reference=position.source_reference,
        valuation_history=observations,
    )


async def read_backing_source_inventory(
    session: AsyncSession,
    *,
    episode_id: UUID,
    program_id: UUID,
) -> BackingSourceInventory:
    """Read all observed source facts in one DB statement; never decide capacity or allocate.

    An empty list or missing valuation is *unknown/not established*, never a PASS.
    This unprivileged application primitive is internal only; an eventual API
    caller must enforce role/participant/program authorization separately.
    """
    rows = (
        await session.execute(
            select(ParticipationEpisode, AssetPosition, AssetType, ValuationObservation)
            .outerjoin(
                AssetPosition,
                AssetPosition.participation_episode_id == ParticipationEpisode.id,
            )
            .outerjoin(AssetType, AssetType.id == AssetPosition.asset_type_id)
            .outerjoin(
                ValuationObservation,
                ValuationObservation.asset_position_id == AssetPosition.id,
            )
            .where(ParticipationEpisode.id == episode_id)
        )
    ).all()
    if not rows:
        raise BackingInventoryError(
            "BACKING_SOURCE_EPISODE_NOT_FOUND", "ParticipationEpisode source does not exist"
        )
    episode = rows[0][0]
    if episode.program_id != program_id:
        raise BackingInventoryError(
            "BACKING_SOURCE_SCOPE_CONFLICT", "ParticipationEpisode is outside the requested program"
        )
    if episode.version < 1:
        raise BackingInventoryError(
            "BACKING_SOURCE_VERSION_INVALID", "ParticipationEpisode version is invalid"
        )

    positions: dict[UUID, tuple[AssetPosition, AssetType | None]] = {}
    observations: dict[UUID, dict[UUID, ValuationSource]] = {}
    for _episode, position, asset_type, observation in rows:
        if position is None:
            continue
        if position.id in positions:
            previous = positions[position.id]
            if previous[0].version != position.version:
                raise BackingInventoryError(
                    "BACKING_SOURCE_VERSION_INVALID", "Inconsistent asset version in source view"
                )
        else:
            positions[position.id] = (position, asset_type)
        if observation is not None:
            observations.setdefault(position.id, {})[observation.id] = _valuation_source(
                observation
            )

    sources = tuple(
        _asset_source(
            episode=episode,
            position=position,
            asset_type=asset_type,
            observations=tuple(
                sorted(
                    observations.get(position_id, {}).values(),
                    key=lambda value: (value.observed_at, str(value.observation_id)),
                )
            ),
        )
        for position_id, (position, asset_type) in sorted(
            positions.items(), key=lambda item: str(item[0])
        )
    )
    return BackingSourceInventory(
        episode_id=episode.id,
        episode_version=episode.version,
        episode_status=episode.status,
        participant_id=episode.participant_id,
        program_id=episode.program_id,
        episode_consent_state=episode.consent_state,
        sources=sources,
    )
