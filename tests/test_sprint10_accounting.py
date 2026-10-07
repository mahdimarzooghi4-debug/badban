from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError

from badban.api.app import create_app
from badban.application.accounting import (
    AccountingConfigurationError,
    account_mapping_reference,
    resolve_legal_entity_account_mapping,
    resolve_legal_entity_account_mapping_set,
    resolve_posting_template,
    resolve_product_account,
    validate_template_accounts,
)
from badban.application.journal import JournalError, JournalLine, post_governed_journal
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    JournalAccountTaxonomy,
    JournalEntry,
    LegalEntity,
    LegalEntityAccountMapping,
)

EXPECTED_ACCOUNT_CODES = {
    "1000.SETTLEMENT_CASH_CONTROL",
    "1010.PROGRAM_CASH_CONTROL",
    "1020.GUARANTEE_RESERVE_CASH_CONTROL",
    "1030.RECOVERY_CASH_CONTROL",
    "1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL",
    "1050.OTHER_APPROVED_CONTROLLED_ASSET",
    "2000.PARTICIPANT_PAYABLE_BALANCE",
    "2010.LIVELIHOOD_PAYABLE",
    "2020.FUTURE_FINANCIAL_ENTITLEMENT",
    "2030.PROGRAM_CAPITAL_BALANCE",
    "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
    "2050.SOCIAL_REINVESTMENT_BALANCE",
    "2060.RETURN_CARRY_FORWARD_BALANCE",
    "2070.PARTICIPANT_RELEASE_PAYABLE",
    "2080.PROGRAM_RECYCLABLE_BALANCE",
    "3000.RECOGNIZED_RETURN_CLEARING",
    "3010.RETURN_ALLOCATION_CLEARING",
    "3020.CAPITAL_GROWTH_CLEARING",
    "4000.GUARANTEE_FINAL_RESIDUAL_LOSS",
    "4010.ENFORCEMENT_COST",
    "4020.APPROVED_FINANCIAL_ADJUSTMENT_LOSS",
    "9000.GUARANTEE_CAPACITY_RESERVED_MEMO",
    "9010.ACTIVE_GUARANTEE_EXPOSURE_MEMO",
    "9020.BACKING_ENCUMBERED_MEMO",
    "9030.CLAIM_APPROVED_PENDING_SETTLEMENT_MEMO",
    "9040.CLAIM_SETTLED_RECOVERY_OPEN_MEMO",
    "9050.EXTERNAL_LOAN_PRINCIPAL_MIRROR_MEMO",
    "9060.EXTERNAL_LOAN_OUTSTANDING_MIRROR_MEMO",
}


@pytest.mark.integration
async def test_migration_seeds_exact_product_taxonomy_without_statutory_mappings(
    database,
    clean_sprint10_accounting_tables,
) -> None:
    async with database.session_factory() as session:
        rows = (
            await session.scalars(
                select(JournalAccountTaxonomy).order_by(JournalAccountTaxonomy.account_code)
            )
        ).all()
        mapping_count = await session.scalar(
            select(func.count()).select_from(LegalEntityAccountMapping)
        )

    assert {row.account_code for row in rows} == EXPECTED_ACCOUNT_CODES
    assert len(rows) == len(EXPECTED_ACCOUNT_CODES)
    assert mapping_count == 0

    monetary = {row.account_code for row in rows if row.ledger_layer == "MONETARY"}
    memorandum = {row.account_code for row in rows if row.ledger_layer == "MEMORANDUM_CONTROL"}
    external_mirror = {row.account_code for row in rows if row.ledger_layer == "EXTERNAL_MIRROR"}
    assert not monetary.intersection(memorandum | external_mirror)
    assert external_mirror == {
        "9050.EXTERNAL_LOAN_PRINCIPAL_MIRROR_MEMO",
        "9060.EXTERNAL_LOAN_OUTSTANDING_MIRROR_MEMO",
    }


@pytest.mark.integration
async def test_accounting_configuration_history_is_database_protected(
    database,
    clean_sprint10_accounting_tables,
) -> None:
    entity = LegalEntity(
        legal_name="Immutable Mapping Entity",
        registration_identifier=f"IMMUTABLE-{uuid4()}",
        entity_type="TEST",
        status="ACTIVE",
        created_by=uuid4(),
        version=1,
    )
    effective_from = datetime.now(UTC) - timedelta(days=1)

    async with database.session_factory() as session:
        async with session.begin():
            session.add(entity)
            await session.flush()
            mapping = LegalEntityAccountMapping(
                legal_entity_id=entity.id,
                product_account_code="3000.RECOGNIZED_RETURN_CLEARING",
                external_chart_account_code="EXT-3000-V1",
                mapping_version=1,
                effective_from=effective_from,
                effective_to=None,
            )
            session.add(mapping)
            await session.flush()
            mapping_id = mapping.id

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(LegalEntityAccountMapping)
                    .where(LegalEntityAccountMapping.id == mapping_id)
                    .values(external_chart_account_code="MUTATED")
                )

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    delete(LegalEntityAccountMapping).where(
                        LegalEntityAccountMapping.id == mapping_id
                    )
                )

    async with database.session_factory() as session:
        with pytest.raises(DBAPIError):
            async with session.begin():
                await session.execute(
                    update(JournalAccountTaxonomy)
                    .where(
                        JournalAccountTaxonomy.account_code
                        == "3000.RECOGNIZED_RETURN_CLEARING"
                    )
                    .values(account_class="CONTROLLED_ASSET")
                )

    async with database.session_factory() as session:
        stored = await session.get(LegalEntityAccountMapping, mapping_id)
        account = await session.get(
            JournalAccountTaxonomy,
            "3000.RECOGNIZED_RETURN_CLEARING",
        )

    assert stored is not None
    assert stored.external_chart_account_code == "EXT-3000-V1"
    assert account is not None
    assert account.account_class == "RETURN_OR_INCOME_CLEARING"


def test_posting_template_registry_preserves_no_monetary_boundaries() -> None:
    for code in {
        "RESERVATION",
        "GUARANTEE_ISSUANCE",
        "GUARANTEED_LOAN_ACTIVATION",
        "EXTERNAL_LENDER_REPAYMENT",
        "CLAIM_APPROVAL",
        "PARTICIPANT_COLLATERAL_RESTRICTION_RELEASE",
    }:
        template = resolve_posting_template(code, 1)
        assert template.reference == f"{code}@1"
        assert template.creates_monetary_journal is False
        with pytest.raises(AccountingConfigurationError) as exc:
            validate_template_accounts(
                template,
                account_codes={"1000.SETTLEMENT_CASH_CONTROL"},
            )
        assert exc.value.code == "POSTING_TEMPLATE_NO_MONETARY_JOURNAL"

    allocation = resolve_posting_template("RETURN_ALLOCATION", 1)
    validate_template_accounts(
        allocation,
        account_codes={
            "3000.RECOGNIZED_RETURN_CLEARING",
            "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
        },
    )

    with pytest.raises(AccountingConfigurationError) as wrong_account:
        validate_template_accounts(
            allocation,
            account_codes={"1000.SETTLEMENT_CASH_CONTROL"},
        )
    assert wrong_account.value.code == "POSTING_TEMPLATE_ACCOUNT_INVALID"

    with pytest.raises(AccountingConfigurationError) as missing:
        resolve_posting_template("UNKNOWN", 1)
    assert missing.value.code == "POSTING_TEMPLATE_NOT_FOUND"


@pytest.mark.integration
async def test_legal_entity_mapping_resolution_is_version_coherent_and_fail_closed(
    database,
    clean_sprint10_accounting_tables,
) -> None:
    now = datetime.now(UTC)
    entity = LegalEntity(
        legal_name="Sprint 10 Entity",
        registration_identifier=f"SPRINT10-{uuid4()}",
        entity_type="TEST",
        status="ACTIVE",
        created_by=uuid4(),
        version=1,
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(entity)
            await session.flush()
            session.add_all(
                [
                    LegalEntityAccountMapping(
                        legal_entity_id=entity.id,
                        product_account_code="3000.RECOGNIZED_RETURN_CLEARING",
                        external_chart_account_code="EXT-3000",
                        mapping_version=7,
                        effective_from=now - timedelta(days=1),
                        effective_to=None,
                    ),
                    LegalEntityAccountMapping(
                        legal_entity_id=entity.id,
                        product_account_code="2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
                        external_chart_account_code="EXT-2040",
                        mapping_version=7,
                        effective_from=now - timedelta(days=1),
                        effective_to=None,
                    ),
                ]
            )

    async with database.session_factory() as session:
        mappings = await resolve_legal_entity_account_mapping_set(
            session,
            legal_entity_id=entity.id,
            product_account_codes={
                "3000.RECOGNIZED_RETURN_CLEARING",
                "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
            },
            effective_at=now,
        )
        reference = account_mapping_reference(mappings["3000.RECOGNIZED_RETURN_CLEARING"])

    assert reference == f"{entity.id}@7"

    async with database.session_factory() as session:
        with pytest.raises(AccountingConfigurationError) as missing:
            await resolve_legal_entity_account_mapping(
                session,
                legal_entity_id=entity.id,
                product_account_code="2010.LIVELIHOOD_PAYABLE",
                effective_at=now,
            )
    assert missing.value.code == "ACCOUNT_MAPPING_MISSING"

    async with database.session_factory() as session:
        async with session.begin():
            session.add(
                LegalEntityAccountMapping(
                    legal_entity_id=entity.id,
                    product_account_code="3000.RECOGNIZED_RETURN_CLEARING",
                    external_chart_account_code="EXT-3000-ALT",
                    mapping_version=8,
                    effective_from=now - timedelta(hours=1),
                    effective_to=None,
                )
            )

    async with database.session_factory() as session:
        with pytest.raises(AccountingConfigurationError) as ambiguous:
            await resolve_legal_entity_account_mapping(
                session,
                legal_entity_id=entity.id,
                product_account_code="3000.RECOGNIZED_RETURN_CLEARING",
                effective_at=now,
            )
    assert ambiguous.value.code == "ACCOUNT_MAPPING_AMBIGUOUS"


@pytest.mark.integration
async def test_journal_keeps_explicit_template_and_mapping_references_after_later_mapping(
    database,
    clean_sprint10_accounting_tables,
) -> None:
    now = datetime.now(UTC)
    actor_id = uuid4()
    entity = LegalEntity(
        legal_name="Historical Mapping Entity",
        registration_identifier=f"HIST-{uuid4()}",
        entity_type="TEST",
        status="ACTIVE",
        created_by=actor_id,
        version=1,
    )

    async with database.session_factory() as session:
        async with session.begin():
            session.add(entity)
            await session.flush()
            session.add_all(
                [
                    LegalEntityAccountMapping(
                        legal_entity_id=entity.id,
                        product_account_code="3000.RECOGNIZED_RETURN_CLEARING",
                        external_chart_account_code="EXT-3000-V1",
                        mapping_version=1,
                        effective_from=now - timedelta(days=1),
                        effective_to=now + timedelta(hours=1),
                    ),
                    LegalEntityAccountMapping(
                        legal_entity_id=entity.id,
                        product_account_code="2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
                        external_chart_account_code="EXT-2040-V1",
                        mapping_version=1,
                        effective_from=now - timedelta(days=1),
                        effective_to=now + timedelta(hours=1),
                    ),
                ]
            )

    async with database.session_factory() as session:
        async with session.begin():
            entry = await post_governed_journal(
                session,
                template_code="RETURN_ALLOCATION",
                template_version=1,
                business_event_type="SPRINT10_TEMPLATE_REFERENCE_TEST",
                business_event_id=str(uuid4()),
                legal_entity_id=entity.id,
                currency="IRR",
                idempotency_key=f"sprint10-{uuid4()}",
                actor_reference=actor_id,
                correlation_id=uuid4(),
                policy_version_reference="policy:test:v1",
                require_account_mapping=True,
                lines=[
                    JournalLine(
                        account_code="3000.RECOGNIZED_RETURN_CLEARING",
                        economic_owner_type="PROGRAM",
                        debit_amount=Decimal("10"),
                    ),
                    JournalLine(
                        account_code="2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
                        economic_owner_type="PROGRAM",
                        credit_amount=Decimal("10"),
                    ),
                ],
            )
            entry_id = entry.id

    async with database.session_factory() as session:
        async with session.begin():
            session.add_all(
                [
                    LegalEntityAccountMapping(
                        legal_entity_id=entity.id,
                        product_account_code="3000.RECOGNIZED_RETURN_CLEARING",
                        external_chart_account_code="EXT-3000-V2",
                        mapping_version=2,
                        effective_from=now + timedelta(hours=1),
                        effective_to=None,
                    ),
                    LegalEntityAccountMapping(
                        legal_entity_id=entity.id,
                        product_account_code="2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
                        external_chart_account_code="EXT-2040-V2",
                        mapping_version=2,
                        effective_from=now + timedelta(hours=1),
                        effective_to=None,
                    ),
                ]
            )

    async with database.session_factory() as session:
        stored = await session.get(JournalEntry, entry_id)

    assert stored is not None
    assert stored.policy_version_reference == "policy:test:v1"
    assert stored.posting_template_reference == "RETURN_ALLOCATION@1"
    assert stored.account_mapping_reference == f"{entity.id}@1"


@pytest.mark.integration
async def test_governed_journal_fails_closed_for_non_monetary_template(
    database,
    clean_sprint10_accounting_tables,
) -> None:
    async with database.session_factory() as session:
        with pytest.raises(JournalError) as exc:
            async with session.begin():
                await post_governed_journal(
                    session,
                    template_code="RESERVATION",
                    template_version=1,
                    business_event_type="SHOULD_NOT_POST",
                    business_event_id=str(uuid4()),
                    legal_entity_id=uuid4(),
                    currency="IRR",
                    idempotency_key=f"sprint10-no-post-{uuid4()}",
                    actor_reference=uuid4(),
                    correlation_id=uuid4(),
                    policy_version_reference="policy:test:v1",
                    lines=[
                        JournalLine(
                            account_code="1000.SETTLEMENT_CASH_CONTROL",
                            economic_owner_type="PROGRAM",
                            debit_amount=Decimal("1"),
                        ),
                        JournalLine(
                            account_code="3000.RECOGNIZED_RETURN_CLEARING",
                            economic_owner_type="PROGRAM",
                            credit_amount=Decimal("1"),
                        ),
                    ],
                )
    assert exc.value.code == "POSTING_TEMPLATE_NO_MONETARY_JOURNAL"

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(JournalEntry))
    assert count == 0


@pytest.mark.integration
async def test_governed_reversal_template_cannot_bypass_dedicated_workflow(
    database,
    clean_sprint10_accounting_tables,
) -> None:
    async with database.session_factory() as session:
        with pytest.raises(JournalError) as exc:
            async with session.begin():
                await post_governed_journal(
                    session,
                    template_code="REVERSAL",
                    template_version=1,
                    business_event_type="REVERSAL",
                    business_event_id=str(uuid4()),
                    legal_entity_id=uuid4(),
                    currency="IRR",
                    idempotency_key=f"sprint10-reversal-bypass-{uuid4()}",
                    actor_reference=uuid4(),
                    correlation_id=uuid4(),
                    policy_version_reference="policy:test:v1",
                    lines=[
                        JournalLine(
                            account_code="1000.SETTLEMENT_CASH_CONTROL",
                            economic_owner_type="PROGRAM",
                            debit_amount=Decimal("1"),
                        ),
                        JournalLine(
                            account_code="3000.RECOGNIZED_RETURN_CLEARING",
                            economic_owner_type="PROGRAM",
                            credit_amount=Decimal("1"),
                        ),
                    ],
                )
    assert exc.value.code == "POSTING_TEMPLATE_DEDICATED_WORKFLOW_REQUIRED"

    async with database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(JournalEntry))
    assert count == 0


@pytest.mark.integration
async def test_product_account_lookup_rejects_unknown_code(
    database,
    clean_sprint10_accounting_tables,
) -> None:
    async with database.session_factory() as session:
        with pytest.raises(AccountingConfigurationError) as exc:
            await resolve_product_account(
                session,
                account_code="9999.NOT_A_BADBAN_ACCOUNT",
            )
    assert exc.value.code == "PRODUCT_ACCOUNT_NOT_FOUND"


def test_no_generic_journal_create_api_is_introduced(settings: Settings) -> None:
    schema = create_app(settings).openapi()
    operations = schema["paths"]["/api/v1/finance/journals"]
    assert set(operations) == {"get"}
