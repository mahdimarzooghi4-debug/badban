from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, PlainSerializer
from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.internal_ledger_source import InternalPostedJournalSource
from badban.application.reconciliation_sources import (
    LedgerSnapshot,
    ReconciliationSourceAcquisitionError,
    ReconciliationSourceUnavailable,
    SourceTarget,
)
from badban.infrastructure.persistence.models import (
    JournalAccountTaxonomy,
    JournalEntry,
    JournalPosting,
    Program,
)
from badban.security.audit import append_audit
from badban.security.authorization import (
    ROLE_SUPPORT_INSTITUTION_OPERATOR,
    SCOPE_PROGRAM,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(
    prefix="/api/v1/support-institution/programs",
    tags=["support-institution-financial-read"],
)

DecimalString = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
]


class ReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinancialHistoryPostingView(ReadModel):
    account_code: str
    account_name: str
    account_class: str
    economic_owner_type: str
    normal_balance: Literal["DEBIT", "CREDIT", "MEMO"]
    ledger_layer: Literal["MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"]
    debit_amount: DecimalString
    credit_amount: DecimalString
    currency: str


class FinancialHistoryEntryView(ReadModel):
    id: UUID
    state: Literal["POSTED"]
    business_event_type: str
    currency: str
    effective_at: datetime
    posted_at: datetime
    reversal_of_entry_id: UUID | None
    policy_version_reference: str | None
    posting_template_reference: str | None
    evidence_reference: str | None
    postings: list[FinancialHistoryPostingView]


class FinancialHistoryPageView(ReadModel):
    source_type: Literal["INTERNAL_BADBAN_POSTED_JOURNAL"]
    program_id: UUID
    legal_entity_id: UUID
    items: list[FinancialHistoryEntryView]
    limit: int
    offset: int
    total_entries: int


class FinancialStatementRowView(ReadModel):
    account_code: str
    account_name: str
    account_class: str
    currency: str
    legal_entity_id: UUID
    economic_owner_type: str
    ledger_layer: Literal["MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"]
    normal_balance: Literal["DEBIT", "CREDIT", "MEMO"]
    balance: str


class FinancialStatementView(ReadModel):
    source_type: Literal["INTERNAL_BADBAN_POSTED_JOURNAL"]
    program_id: UUID
    legal_entity_id: UUID
    snapshot_at: datetime
    received_at: datetime
    source_reference: str
    schema_version: str
    contract_version: str
    mapping_version: str
    content_hash: str
    evidence_references: list[str]
    items: list[FinancialStatementRowView]
    limit: int
    offset: int
    total_rows: int


async def _authorized_program(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
    program_id: UUID,
    action: str,
) -> Program:
    try:
        await authorize(
            session,
            principal=principal,
            roles={ROLE_SUPPORT_INSTITUTION_OPERATOR},
            scope_type=SCOPE_PROGRAM,
            scope_id=program_id,
            allow_global=False,
            action=action,
            target_type="SupportingInstitutionProgram",
            target_id=str(program_id),
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(
            403,
            exc.code,
            "Program-scoped supporting institution access is required",
        ) from exc

    program = await session.get(Program, program_id)
    if program is None or program.status != "ACTIVE" or program.legal_entity_id is None:
        raise ApiError(
            404,
            "SUPPORTING_PROGRAM_NOT_FOUND",
            "Active supporting institution program was not found",
        )
    return program


def _audit_read(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
    program_id: UUID,
    action: str,
    outcome: Literal["SUCCESS", "UNAVAILABLE", "FAILED"],
    scope: dict[str, object],
    reason_code: str | None = None,
) -> None:
    append_audit(
        session,
        aggregate_type="SupportingInstitutionProgram",
        aggregate_id=str(program_id),
        aggregate_version=None,
        action=action,
        actor_type=principal.identity_type,
        actor_id=principal.identity_id,
        correlation_id=correlation_id,
        outcome=outcome,
        reason_code=reason_code,
        scope={"program_id": str(program_id), **scope},
    )


def _source_contract_error() -> ApiError:
    return ApiError(
        409,
        "SOURCE_CONTRACT_INVALID",
        "Posted journal evidence does not satisfy the exact program and legal-entity contract",
    )


async def _fail_source_contract(
    session: AsyncSession,
    *,
    principal: Principal,
    correlation_id: UUID,
    program_id: UUID,
    action: str,
    scope: dict[str, object],
) -> NoReturn:
    _audit_read(
        session,
        principal=principal,
        correlation_id=correlation_id,
        program_id=program_id,
        action=action,
        outcome="FAILED",
        reason_code="SOURCE_CONTRACT_INVALID",
        scope=scope,
    )
    await session.commit()
    raise _source_contract_error()


def _complete_program_entry_predicates(
    program_id: UUID,
    legal_entity_id: UUID,
) -> tuple[ColumnElement[bool], ...]:
    has_program_posting = exists(
        select(JournalPosting.id).where(
            JournalPosting.journal_entry_id == JournalEntry.id,
            JournalPosting.program_id == program_id,
        )
    )
    has_out_of_scope_posting = exists(
        select(JournalPosting.id).where(
            JournalPosting.journal_entry_id == JournalEntry.id,
            or_(
                JournalPosting.program_id.is_distinct_from(program_id),
                JournalPosting.legal_entity_id != legal_entity_id,
                JournalPosting.currency != JournalEntry.currency,
            ),
        )
    )
    return (
        JournalEntry.state == "POSTED",
        JournalEntry.posted_at.is_not(None),
        JournalEntry.legal_entity_id == legal_entity_id,
        has_program_posting,
        ~has_out_of_scope_posting,
    )


@router.get("/{program_id}/financial-history", response_model=FinancialHistoryPageView)
async def read_program_financial_history(
    program_id: UUID,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> FinancialHistoryPageView:
    action = "SUPPORT_INSTITUTION_PROGRAM_FINANCIAL_HISTORY_READ"
    program = await _authorized_program(
        session,
        principal=principal,
        correlation_id=correlation_id,
        program_id=program_id,
        action=action,
    )
    assert program.legal_entity_id is not None
    predicates = _complete_program_entry_predicates(program_id, program.legal_entity_id)
    total_entries = int(
        await session.scalar(select(func.count()).select_from(JournalEntry).where(*predicates)) or 0
    )
    if total_entries == 0:
        _audit_read(
            session,
            principal=principal,
            correlation_id=correlation_id,
            program_id=program_id,
            action=action,
            outcome="UNAVAILABLE",
            reason_code="SOURCE_UNAVAILABLE",
            scope={"limit": limit, "offset": offset, "returned_count": 0},
        )
        await session.commit()
        raise ApiError(
            503,
            "SOURCE_UNAVAILABLE",
            "No complete POSTED journal evidence is available for this program",
        )

    entries = (
        await session.scalars(
            select(JournalEntry)
            .where(*predicates)
            .order_by(JournalEntry.posted_at.desc(), JournalEntry.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    entry_ids = [entry.id for entry in entries]
    rows = []
    if entry_ids:
        rows = (
            await session.execute(
                select(JournalEntry, JournalPosting, JournalAccountTaxonomy)
                .join(JournalPosting, JournalPosting.journal_entry_id == JournalEntry.id)
                .outerjoin(
                    JournalAccountTaxonomy,
                    JournalAccountTaxonomy.account_code == JournalPosting.account_code,
                )
                .where(JournalEntry.id.in_(entry_ids))
                .order_by(
                    JournalEntry.posted_at.desc(),
                    JournalEntry.id,
                    JournalPosting.created_at,
                    JournalPosting.id,
                )
            )
        ).all()

    postings_by_entry: dict[UUID, list[FinancialHistoryPostingView]] = defaultdict(list)
    totals_by_entry: dict[UUID, tuple[Decimal, Decimal]] = {}
    for entry, posting, taxonomy in rows:
        if (
            taxonomy is None
            or entry.state != "POSTED"
            or entry.posted_at is None
            or entry.legal_entity_id != program.legal_entity_id
            or posting.program_id != program_id
            or posting.legal_entity_id != program.legal_entity_id
            or posting.currency != entry.currency
            or taxonomy.account_code != posting.account_code
        ):
            await _fail_source_contract(
                session,
                principal=principal,
                correlation_id=correlation_id,
                program_id=program_id,
                action=action,
                scope={"limit": limit, "offset": offset},
            )
        if taxonomy.normal_balance not in {
            "DEBIT",
            "CREDIT",
            "MEMO",
        } or taxonomy.ledger_layer not in {"MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"}:
            await _fail_source_contract(
                session,
                principal=principal,
                correlation_id=correlation_id,
                program_id=program_id,
                action=action,
                scope={"limit": limit, "offset": offset},
            )
        debit = Decimal(posting.debit_amount)
        credit = Decimal(posting.credit_amount)
        prior_debit, prior_credit = totals_by_entry.get(entry.id, (Decimal(0), Decimal(0)))
        totals_by_entry[entry.id] = (prior_debit + debit, prior_credit + credit)
        postings_by_entry[entry.id].append(
            FinancialHistoryPostingView(
                account_code=posting.account_code,
                account_name=taxonomy.name,
                account_class=taxonomy.account_class,
                economic_owner_type=posting.economic_owner_type,
                normal_balance=cast(Literal["DEBIT", "CREDIT", "MEMO"], taxonomy.normal_balance),
                ledger_layer=cast(
                    Literal["MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"],
                    taxonomy.ledger_layer,
                ),
                debit_amount=debit,
                credit_amount=credit,
                currency=posting.currency,
            )
        )

    result_entries: list[FinancialHistoryEntryView] = []
    for entry in entries:
        postings = postings_by_entry.get(entry.id, [])
        totals = totals_by_entry.get(entry.id)
        if (
            len(postings) < 2
            or totals is None
            or totals[0] <= 0
            or totals[0] != totals[1]
            or entry.posted_at is None
        ):
            await _fail_source_contract(
                session,
                principal=principal,
                correlation_id=correlation_id,
                program_id=program_id,
                action=action,
                scope={"limit": limit, "offset": offset},
            )
        result_entries.append(
            FinancialHistoryEntryView(
                id=entry.id,
                state="POSTED",
                business_event_type=entry.business_event_type,
                currency=entry.currency,
                effective_at=entry.effective_at,
                posted_at=entry.posted_at,
                reversal_of_entry_id=entry.reversal_of_entry_id,
                policy_version_reference=entry.policy_version_reference,
                posting_template_reference=entry.posting_template_reference,
                evidence_reference=entry.evidence_reference,
                postings=postings,
            )
        )

    _audit_read(
        session,
        principal=principal,
        correlation_id=correlation_id,
        program_id=program_id,
        action=action,
        outcome="SUCCESS",
        scope={
            "limit": limit,
            "offset": offset,
            "total_entries": total_entries,
            "returned_count": len(result_entries),
        },
    )
    await session.commit()
    return FinancialHistoryPageView(
        source_type="INTERNAL_BADBAN_POSTED_JOURNAL",
        program_id=program_id,
        legal_entity_id=program.legal_entity_id,
        items=result_entries,
        limit=limit,
        offset=offset,
        total_entries=total_entries,
    )


async def _assert_snapshot_entries_are_complete(
    session: AsyncSession,
    *,
    snapshot: LedgerSnapshot,
    program_id: UUID,
    legal_entity_id: UUID,
) -> None:
    entry_ids: set[UUID] = set()
    for reference in snapshot.evidence_references:
        prefix = "journal-entry:"
        if not reference.startswith(prefix):
            raise _source_contract_error()
        try:
            entry_ids.add(UUID(reference[len(prefix) :]))
        except ValueError as exc:
            raise _source_contract_error() from exc
    if not entry_ids:
        raise _source_contract_error()

    rows = (
        await session.execute(
            select(JournalEntry, JournalPosting)
            .join(JournalPosting, JournalPosting.journal_entry_id == JournalEntry.id)
            .where(JournalEntry.id.in_(entry_ids))
        )
    ).all()
    found_ids = {entry.id for entry, _posting in rows}
    if found_ids != entry_ids:
        raise _source_contract_error()
    for entry, posting in rows:
        if (
            entry.state != "POSTED"
            or entry.posted_at is None
            or entry.legal_entity_id != legal_entity_id
            or posting.program_id != program_id
            or posting.legal_entity_id != legal_entity_id
            or posting.currency != entry.currency
        ):
            raise _source_contract_error()


@router.get("/{program_id}/financial-statement", response_model=FinancialStatementView)
async def read_program_financial_statement(
    program_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> FinancialStatementView:
    action = "SUPPORT_INSTITUTION_PROGRAM_FINANCIAL_STATEMENT_READ"
    program = await _authorized_program(
        session,
        principal=principal,
        correlation_id=correlation_id,
        program_id=program_id,
        action=action,
    )
    assert program.legal_entity_id is not None
    source = InternalPostedJournalSource(session, program_id=program_id)
    try:
        snapshot = await source.fetch_reconciliation_snapshot(
            SourceTarget(reconciliation_type="LEDGER", program_id=program_id),
            {"program_id": str(program_id)},
        )
    except ReconciliationSourceUnavailable as exc:
        _audit_read(
            session,
            principal=principal,
            correlation_id=correlation_id,
            program_id=program_id,
            action=action,
            outcome="UNAVAILABLE",
            reason_code=exc.code,
            scope={"limit": limit, "offset": offset, "returned_count": 0},
        )
        await session.commit()
        raise ApiError(
            503,
            "SOURCE_UNAVAILABLE",
            "No POSTED internal journal evidence is available for this program",
        ) from exc
    except ReconciliationSourceAcquisitionError as exc:
        _audit_read(
            session,
            principal=principal,
            correlation_id=correlation_id,
            program_id=program_id,
            action=action,
            outcome="FAILED",
            reason_code=exc.code,
            scope={"limit": limit, "offset": offset},
        )
        await session.commit()
        if exc.code == "SOURCE_UNAVAILABLE":
            raise ApiError(503, exc.code, "Internal journal source is unavailable") from exc
        raise _source_contract_error() from exc

    try:
        if any(record.legal_entity_id != program.legal_entity_id for record in snapshot.records):
            raise _source_contract_error()
        await _assert_snapshot_entries_are_complete(
            session,
            snapshot=snapshot,
            program_id=program_id,
            legal_entity_id=program.legal_entity_id,
        )
        account_codes = sorted({record.account_code for record in snapshot.records})
        taxonomy_rows = (
            await session.scalars(
                select(JournalAccountTaxonomy).where(
                    JournalAccountTaxonomy.account_code.in_(account_codes)
                )
            )
        ).all()
        taxonomy_by_code = {row.account_code: row for row in taxonomy_rows}
        if set(taxonomy_by_code) != set(account_codes):
            raise _source_contract_error()

        grouped: dict[tuple[str, str, UUID, str, str, str], Decimal] = defaultdict(Decimal)
        for record in snapshot.records:
            taxonomy = taxonomy_by_code[record.account_code]
            if (
                taxonomy.normal_balance != record.normal_balance
                or taxonomy.ledger_layer != record.ledger_layer
                or record.program_id != program_id
                or record.legal_entity_id != program.legal_entity_id
            ):
                raise _source_contract_error()
            key = (
                record.account_code,
                record.currency,
                record.legal_entity_id,
                record.economic_owner_type,
                record.ledger_layer,
                record.normal_balance,
            )
            grouped[key] += Decimal(record.balance)
    except ApiError as exc:
        if exc.code != "SOURCE_CONTRACT_INVALID":
            raise
        _audit_read(
            session,
            principal=principal,
            correlation_id=correlation_id,
            program_id=program_id,
            action=action,
            outcome="FAILED",
            reason_code=exc.code,
            scope={"limit": limit, "offset": offset},
        )
        await session.commit()
        raise

    all_rows = [
        FinancialStatementRowView(
            account_code=key[0],
            account_name=taxonomy_by_code[key[0]].name,
            account_class=taxonomy_by_code[key[0]].account_class,
            currency=key[1],
            legal_entity_id=key[2],
            economic_owner_type=key[3],
            ledger_layer=cast(
                Literal["MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"], key[4]
            ),
            normal_balance=cast(Literal["DEBIT", "CREDIT", "MEMO"], key[5]),
            balance=format(balance, "f"),
        )
        for key, balance in sorted(grouped.items(), key=lambda item: item[0])
    ]
    total_rows = len(all_rows)
    items = all_rows[offset : offset + limit]

    _audit_read(
        session,
        principal=principal,
        correlation_id=correlation_id,
        program_id=program_id,
        action=action,
        outcome="SUCCESS",
        scope={
            "limit": limit,
            "offset": offset,
            "total_rows": total_rows,
            "returned_count": len(items),
            "evidence_reference_count": len(snapshot.evidence_references),
        },
    )
    await session.commit()
    return FinancialStatementView(
        source_type="INTERNAL_BADBAN_POSTED_JOURNAL",
        program_id=program_id,
        legal_entity_id=program.legal_entity_id,
        snapshot_at=snapshot.snapshot_at,
        received_at=snapshot.received_at,
        source_reference=snapshot.source_reference,
        schema_version=snapshot.schema_version,
        contract_version=snapshot.contract_version,
        mapping_version=snapshot.mapping_version,
        content_hash=snapshot.content_hash,
        evidence_references=list(snapshot.evidence_references),
        items=items,
        limit=limit,
        offset=offset,
        total_rows=total_rows,
    )
