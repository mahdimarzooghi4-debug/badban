from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.application.backing_source_inventory import (
    BackingSourceInventory,
    build_backing_source_inventory,
)
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    CreditProductVersion,
    CreditProvider,
    GuaranteeCase,
    ParticipationEpisode,
    ValuationObservation,
)


class RequestEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RequestBoundBackingEvidence:
    """Observed request/source lineage. NOT reservation eligibility or authorization."""

    guarantee_case_id: UUID
    guarantee_version: int
    guarantee_state: str
    requested_principal: Decimal
    guarantee_mode: str
    episode_id: UUID
    program_id: UUID
    provider_id: UUID
    provider_version: int
    provider_code: str
    provider_lifecycle_status: str
    provider_legal_entity_id: UUID
    credit_product_version_id: UUID
    product_aggregate_version: int
    product_version_number: int
    product_code: str
    product_lifecycle_status: str
    product_currency: str
    product_guarantee_mode: str
    product_policy_version_reference: str
    product_lender_of_record_legal_entity_id: UUID
    product_min_principal: Decimal
    product_max_principal: Decimal
    backing: BackingSourceInventory

    @property
    def evidence_fingerprint(self) -> str:
        """Hash of observed facts only: not signed proof or a concurrency control."""
        canonical = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


async def read_request_bound_backing_evidence(
    session: AsyncSession,
    *,
    guarantee_case_id: UUID,
    program_id: UUID,
) -> RequestBoundBackingEvidence:
    """One-statement, read-only guarantee/source projection for a REQUESTED case.

    Internal primitive, no HTTP or implicit authorization. Any future caller must
    enforce actor/program authorization. Does not determine any reservation,
    eligibility, policy scope or risk snapshot freshness.
    """
    rows = (
        await session.execute(
            select(
                GuaranteeCase,
                ParticipationEpisode,
                CreditProvider,
                CreditProductVersion,
                AssetPosition,
                AssetType,
                ValuationObservation,
            )
            .join(
                ParticipationEpisode,
                ParticipationEpisode.id == GuaranteeCase.participation_episode_id,
            )
            .join(CreditProvider, CreditProvider.id == GuaranteeCase.provider_id)
            .join(
                CreditProductVersion,
                CreditProductVersion.id == GuaranteeCase.credit_product_version_id,
            )
            .outerjoin(
                AssetPosition,
                AssetPosition.participation_episode_id == ParticipationEpisode.id,
            )
            .outerjoin(AssetType, AssetType.id == AssetPosition.asset_type_id)
            .outerjoin(
                ValuationObservation,
                ValuationObservation.asset_position_id == AssetPosition.id,
            )
            .where(
                GuaranteeCase.id == guarantee_case_id,
                ParticipationEpisode.program_id == program_id,
            )
            .execution_options(populate_existing=True)
        )
    ).all()
    if not rows:
        raise RequestEvidenceError(
            "REQUEST_EVIDENCE_NOT_FOUND", "Guarantee request or required source is missing"
        )
    guarantee, episode, provider, product, *_ = rows[0]
    if episode.program_id != program_id or guarantee.participation_episode_id != episode.id:
        raise RequestEvidenceError(
            "REQUEST_EVIDENCE_SCOPE_CONFLICT", "Guarantee request is outside the requested program"
        )
    if (
        guarantee.provider_id != provider.id
        or guarantee.credit_product_version_id != product.id
        or product.provider_id != provider.id
        or guarantee.guarantee_mode != product.guarantee_mode
    ):
        raise RequestEvidenceError(
            "REQUEST_EVIDENCE_LINEAGE_CONFLICT",
            "Guarantee/provider/captured product lineage is contradictory",
        )
    if (
        guarantee.version < 1
        or provider.version < 1
        or product.version < 1
        or product.version_number < 1
    ):
        raise RequestEvidenceError(
            "REQUEST_EVIDENCE_VERSION_INVALID", "Request source versions are invalid"
        )
    if guarantee.state != "REQUESTED":
        raise RequestEvidenceError(
            "REQUEST_EVIDENCE_STATE_UNSUPPORTED", "Only REQUESTED evidence may be inspected"
        )
    if (
        guarantee.reserved_guarantee_amount is not None
        or guarantee.issued_guarantee_amount is not None
        or guarantee.current_guarantee_exposure != Decimal("0")
        or guarantee.reservation_expires_at is not None
        or guarantee.risk_snapshot_id is not None
    ):
        raise RequestEvidenceError(
            "REQUEST_EVIDENCE_STATE_CONFLICT", "REQUESTED case has reservation or exposure fields"
        )

    source_rows = [(row[1], row[4], row[5], row[6]) for row in rows]
    backing = build_backing_source_inventory(
        source_rows, episode_id=episode.id, program_id=program_id
    )
    return RequestBoundBackingEvidence(
        guarantee_case_id=guarantee.id,
        guarantee_version=guarantee.version,
        guarantee_state=guarantee.state,
        requested_principal=guarantee.requested_principal,
        guarantee_mode=guarantee.guarantee_mode,
        episode_id=episode.id,
        program_id=episode.program_id,
        provider_id=provider.id,
        provider_version=provider.version,
        provider_code=provider.provider_code,
        provider_lifecycle_status=provider.lifecycle_status,
        provider_legal_entity_id=provider.legal_entity_id,
        credit_product_version_id=product.id,
        product_aggregate_version=product.version,
        product_version_number=product.version_number,
        product_code=product.product_code,
        product_lifecycle_status=product.lifecycle_status,
        product_currency=product.currency,
        product_guarantee_mode=product.guarantee_mode,
        product_policy_version_reference=product.policy_version_reference,
        product_lender_of_record_legal_entity_id=product.lender_of_record_legal_entity_id,
        product_min_principal=product.min_principal,
        product_max_principal=product.max_principal,
        backing=backing,
    )
