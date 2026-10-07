from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.errors import ApiError
from badban.application.idempotency import canonical_request_hash
from badban.application.reconciliation_sources import (
    LedgerRecord,
    SourceTarget,
    canonical_fields,
    stable_key,
)
from badban.infrastructure.persistence.models import (
    AssetPosition,
    AssetType,
    CreditProductVersion,
    ExternalLoanMirror,
    GuaranteeCase,
    JournalAccountTaxonomy,
    JournalEntry,
    JournalPosting,
)


@dataclass(frozen=True)
class InternalRecord:
    key: str
    resource_type: str
    resource_id: str
    fields: dict[str, str]
    observed_at: datetime | None
    version: int | None
    invariant_facts: dict[str, object] | None = None


@dataclass(frozen=True)
class InternalSnapshot:
    records: tuple[InternalRecord, ...]
    available: bool
    gap: str | None = None

    @property
    def content_hash(self) -> str:
        return canonical_request_hash(
            {
                "available": self.available,
                "gap": self.gap,
                "records": [vars(r) for r in self.records],
            }
        )


async def build_internal_snapshot(
    session: AsyncSession, target: SourceTarget, *, legal_entity_id: UUID | None
) -> InternalSnapshot:
    if target.reconciliation_type == "LENDER":
        mirrors = (
            await session.scalars(
                select(ExternalLoanMirror)
                .where(ExternalLoanMirror.provider_id == target.identity)
                .order_by(ExternalLoanMirror.id)
                .with_for_update()
            )
        ).all()
        ids = [m.guarantee_case_id for m in mirrors if m.guarantee_case_id is not None]
        guarantees = (
            await session.scalars(
                select(GuaranteeCase)
                .where(GuaranteeCase.id.in_(ids))
                .order_by(GuaranteeCase.id)
                .with_for_update()
            )
        ).all()
        if any(g.provider_id != target.identity for g in guarantees):
            raise ApiError(409, "RECON_MAPPING_MISMATCH", "Linked guarantee provider differs")
        by_id = {g.id: g for g in guarantees}
        records = []
        for mirror in mirrors:
            guarantee = (
                by_id.get(mirror.guarantee_case_id)
                if mirror.guarantee_case_id is not None
                else None
            )
            facts = (
                None
                if mirror.guarantee_case_id is None
                else {
                    "guarantee_id": mirror.guarantee_case_id,
                    "version": guarantee.version if guarantee else None,
                    "state": guarantee.state if guarantee else None,
                    "amount": format(guarantee.issued_guarantee_amount, "f")
                    if guarantee and guarantee.issued_guarantee_amount is not None
                    else None,
                }
            )
            records.append(
                InternalRecord(
                    mirror.external_loan_id,
                    "ExternalLoanMirror",
                    str(mirror.id),
                    {
                        "external_loan_id": mirror.external_loan_id,
                        "original_principal": format(mirror.original_principal, "f"),
                        "outstanding_principal": format(mirror.outstanding_principal, "f"),
                        "currency": mirror.currency,
                        "state": mirror.state,
                    },
                    mirror.last_provider_event_at,
                    mirror.version,
                    facts,
                )
            )
        return InternalSnapshot(tuple(records), True)
    if target.reconciliation_type == "GUARANTEE_ISSUER":
        rows = (
            await session.execute(
                select(GuaranteeCase, CreditProductVersion)
                .join(
                    CreditProductVersion,
                    GuaranteeCase.credit_product_version_id == CreditProductVersion.id,
                )
                .where(GuaranteeCase.legal_guarantee_issuer_id == legal_entity_id)
                .order_by(GuaranteeCase.id)
                .with_for_update(of=GuaranteeCase)
            )
        ).all()
        records = []
        for case, product in rows:
            fields = {
                "state": case.state,
                "currency": product.currency,
                "beneficiary": str(product.lender_of_record_legal_entity_id),
            }
            if case.legal_guarantee_external_id is not None:
                fields["external_guarantee_id"] = case.legal_guarantee_external_id
            if case.issued_guarantee_amount is not None:
                fields["issued_amount"] = format(case.issued_guarantee_amount, "f")
            # updated_at is evidence freshness, never an invented legal issue timestamp.
            records.append(
                InternalRecord(
                    case.legal_guarantee_external_id or f"internal:{case.id}",
                    "GuaranteeCase",
                    str(case.id),
                    fields,
                    case.updated_at,
                    case.version,
                )
            )
        return InternalSnapshot(tuple(records), True)
    if target.reconciliation_type == "CUSTODY":
        rows = (
            await session.execute(
                select(AssetPosition, AssetType)
                .join(AssetType, AssetPosition.asset_type_id == AssetType.id)
                .where(AssetPosition.custodian_legal_entity_id == legal_entity_id)
                .order_by(AssetPosition.id)
                .with_for_update(of=AssetPosition)
            )
        ).all()
        records = []
        for position, asset in rows:
            fields = {
                "asset_position_id": str(position.id),
                "asset_type": asset.asset_code,
                "quantity": format(position.quantity, "f"),
                "unit_code": position.unit_code,
                "state": position.lifecycle_status,
            }
            if position.source_reference is not None:
                fields["custody_reference"] = position.source_reference
            key = (
                canonical_request_hash([str(position.id), position.source_reference])
                if position.source_reference
                else f"internal:{position.id}"
            )
            records.append(
                InternalRecord(
                    key,
                    "AssetPosition",
                    str(position.id),
                    fields,
                    position.updated_at,
                    position.version,
                )
            )
        return InternalSnapshot(tuple(records), True)
    if target.reconciliation_type == "LEDGER":
        rows = (
            await session.execute(
                select(JournalPosting, JournalEntry, JournalAccountTaxonomy)
                .join(JournalEntry, JournalPosting.journal_entry_id == JournalEntry.id)
                .outerjoin(
                    JournalAccountTaxonomy,
                    JournalPosting.account_code == JournalAccountTaxonomy.account_code,
                )
                .where(
                    JournalEntry.state == "POSTED",
                    JournalEntry.legal_entity_id == legal_entity_id,
                    JournalPosting.program_id == target.program_id,
                )
                .order_by(JournalPosting.id)
            )
        ).all()
        groups: dict[str, tuple[LedgerRecord, Decimal]] = {}
        with localcontext() as context:
            context.prec = 100
            for posting, entry, account in rows:
                if posting.legal_entity_id != legal_entity_id or posting.currency != entry.currency:
                    raise ApiError(
                        409, "RECON_MAPPING_MISMATCH", "Posting scope disagrees with posted journal"
                    )
                if account is None or account.normal_balance == "MEMO" or entry.posted_at is None:
                    raise ApiError(
                        409,
                        "RECON_LEDGER_CONTRACT_MISSING",
                        "Account taxonomy/normal-balance contract is required",
                    )
                delta = posting.debit_amount - posting.credit_amount
                if account.normal_balance == "CREDIT":
                    delta = -delta
                record = LedgerRecord(
                    account_code=posting.account_code,
                    currency=posting.currency,
                    economic_owner_type=posting.economic_owner_type,
                    economic_owner_id=posting.economic_owner_id,
                    participant_id=posting.participant_id,
                    program_id=target.identity,
                    provider_id=posting.provider_id,
                    asset_position_id=posting.asset_position_id,
                    guarantee_case_id=posting.guarantee_case_id,
                    claim_id=posting.claim_id,
                    reserve_account_id=posting.reserve_account_id,
                    ledger_layer=cast(
                        Literal["MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"],
                        account.ledger_layer,
                    ),
                    normal_balance=cast(Literal["DEBIT", "CREDIT", "MEMO"], account.normal_balance),
                    balance=format(delta, "f"),
                    observed_at=entry.posted_at,
                )
                key = stable_key(record)
                if key in groups:
                    old, value = groups[key]
                    record = record.model_copy(
                        update={"observed_at": max(old.observed_at, record.observed_at)}
                    )
                    delta += value
                groups[key] = (record, delta)
            records = tuple(
                InternalRecord(
                    key,
                    "JournalBalance",
                    key,
                    canonical_fields(record.model_copy(update={"balance": format(value, "f")})),
                    record.observed_at,
                    None,
                )
                for key, (record, value) in sorted(groups.items())
            )
        return InternalSnapshot(records, True)
    # No current cash-settlement mapping or legal registration model exists.
    # An empty result here would conceal an absent acquisition implementation.
    return InternalSnapshot(
        (),
        False,
        "RECON_INTERNAL_SETTLEMENT_CONTRACT_MISSING"
        if target.reconciliation_type == "SETTLEMENT"
        else "RECON_INTERNAL_REGISTRY_CONTRACT_MISSING",
    )
