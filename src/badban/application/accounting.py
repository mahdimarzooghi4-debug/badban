from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import (
    JournalAccountTaxonomy,
    LegalEntityAccountMapping,
)

TEMPLATE_VERSION_V1 = 1


class AccountingConfigurationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PostingTemplateSpec:
    code: str
    version: int
    technical_section: str
    creates_monetary_journal: bool
    permitted_account_codes: frozenset[str] | None = None
    control_effect: bool = False
    external_mirror_effect: bool = False
    dedicated_workflow_only: bool = False

    @property
    def reference(self) -> str:
        return f"{self.code}@{self.version}"


CONTROLLED_CASH_ACCOUNTS = frozenset(
    {
        "1000.SETTLEMENT_CASH_CONTROL",
        "1010.PROGRAM_CASH_CONTROL",
        "1020.GUARANTEE_RESERVE_CASH_CONTROL",
        "1030.RECOVERY_CASH_CONTROL",
        "1050.OTHER_APPROVED_CONTROLLED_ASSET",
    }
)

POSTING_TEMPLATES: dict[tuple[str, int], PostingTemplateSpec] = {
    ("RESERVATION", 1): PostingTemplateSpec(
        code="RESERVATION",
        version=1,
        technical_section="Technical 05 §7",
        creates_monetary_journal=False,
        control_effect=True,
    ),
    ("GUARANTEE_ISSUANCE", 1): PostingTemplateSpec(
        code="GUARANTEE_ISSUANCE",
        version=1,
        technical_section="Technical 05 §8",
        creates_monetary_journal=False,
        control_effect=True,
    ),
    ("GUARANTEED_LOAN_ACTIVATION", 1): PostingTemplateSpec(
        code="GUARANTEED_LOAN_ACTIVATION",
        version=1,
        technical_section="Technical 05 §9",
        creates_monetary_journal=False,
        control_effect=True,
        external_mirror_effect=True,
    ),
    ("EXTERNAL_LENDER_REPAYMENT", 1): PostingTemplateSpec(
        code="EXTERNAL_LENDER_REPAYMENT",
        version=1,
        technical_section="Technical 05 §10",
        creates_monetary_journal=False,
        control_effect=True,
        external_mirror_effect=True,
    ),
    ("RECOGNIZED_RETURN", 1): PostingTemplateSpec(
        code="RECOGNIZED_RETURN",
        version=1,
        technical_section="Technical 05 §11",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "3000.RECOGNIZED_RETURN_CLEARING",
                "1000.SETTLEMENT_CASH_CONTROL",
                "1010.PROGRAM_CASH_CONTROL",
                "1050.OTHER_APPROVED_CONTROLLED_ASSET",
            }
        ),
    ),
    ("RETURN_ALLOCATION", 1): PostingTemplateSpec(
        code="RETURN_ALLOCATION",
        version=1,
        technical_section="Technical 05 §12",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "3000.RECOGNIZED_RETURN_CLEARING",
                "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
                "2010.LIVELIHOOD_PAYABLE",
                "2020.FUTURE_FINANCIAL_ENTITLEMENT",
                "3020.CAPITAL_GROWTH_CLEARING",
                "2050.SOCIAL_REINVESTMENT_BALANCE",
                "2060.RETURN_CARRY_FORWARD_BALANCE",
            }
        ),
    ),
    ("CAPITAL_GROWTH", 1): PostingTemplateSpec(
        code="CAPITAL_GROWTH",
        version=1,
        technical_section="Technical 05 §13",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "3020.CAPITAL_GROWTH_CLEARING",
                "2000.PARTICIPANT_PAYABLE_BALANCE",
                "2030.PROGRAM_CAPITAL_BALANCE",
            }
        ),
    ),
    ("LIVELIHOOD_PAYMENT", 1): PostingTemplateSpec(
        code="LIVELIHOOD_PAYMENT",
        version=1,
        technical_section="Technical 05 §14",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset({"2010.LIVELIHOOD_PAYABLE"}) | CONTROLLED_CASH_ACCOUNTS,
    ),
    ("FUTURE_FINANCIAL_PAYMENT", 1): PostingTemplateSpec(
        code="FUTURE_FINANCIAL_PAYMENT",
        version=1,
        technical_section="Technical 05 §15",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset({"2020.FUTURE_FINANCIAL_ENTITLEMENT"})
        | CONTROLLED_CASH_ACCOUNTS,
    ),
    ("RESERVE_DESIGNATION_RECLASSIFICATION", 1): PostingTemplateSpec(
        code="RESERVE_DESIGNATION_RECLASSIFICATION",
        version=1,
        technical_section="Technical 05 §16",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "2030.PROGRAM_CAPITAL_BALANCE",
                "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
            }
        ),
    ),
    ("RESERVE_CASH_SEGREGATION", 1): PostingTemplateSpec(
        code="RESERVE_CASH_SEGREGATION",
        version=1,
        technical_section="Technical 05 §16",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "1010.PROGRAM_CASH_CONTROL",
                "1020.GUARANTEE_RESERVE_CASH_CONTROL",
            }
        ),
    ),
    ("CLAIM_APPROVAL", 1): PostingTemplateSpec(
        code="CLAIM_APPROVAL",
        version=1,
        technical_section="Technical 05 §17",
        creates_monetary_journal=False,
        control_effect=True,
    ),
    ("CLAIM_SETTLEMENT", 1): PostingTemplateSpec(
        code="CLAIM_SETTLEMENT",
        version=1,
        technical_section="Technical 05 §18",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL",
                "1020.GUARANTEE_RESERVE_CASH_CONTROL",
            }
        ),
        control_effect=True,
    ),
    ("RECOVERY_CASH_RECEIPT", 1): PostingTemplateSpec(
        code="RECOVERY_CASH_RECEIPT",
        version=1,
        technical_section="Technical 05 §19",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "1030.RECOVERY_CASH_CONTROL",
                "1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL",
                "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
                "1020.GUARANTEE_RESERVE_CASH_CONTROL",
            }
        ),
    ),
    ("FINAL_RESIDUAL_LOSS", 1): PostingTemplateSpec(
        code="FINAL_RESIDUAL_LOSS",
        version=1,
        technical_section="Technical 05 §21",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "4000.GUARANTEE_FINAL_RESIDUAL_LOSS",
                "1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL",
            }
        ),
    ),
    ("COLLATERAL_REALIZATION_RECOVERY", 1): PostingTemplateSpec(
        code="COLLATERAL_REALIZATION_RECOVERY",
        version=1,
        technical_section="Technical 05 §20",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "1030.RECOVERY_CASH_CONTROL",
                "1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL",
                "2000.PARTICIPANT_PAYABLE_BALANCE",
                "2070.PARTICIPANT_RELEASE_PAYABLE",
                "2030.PROGRAM_CAPITAL_BALANCE",
                "2080.PROGRAM_RECYCLABLE_BALANCE",
            }
        ),
    ),
    ("ENFORCEMENT_COST", 1): PostingTemplateSpec(
        code="ENFORCEMENT_COST",
        version=1,
        technical_section="Technical 05 §22",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset({"4010.ENFORCEMENT_COST"}) | CONTROLLED_CASH_ACCOUNTS,
    ),
    ("PARTICIPANT_COLLATERAL_RESTRICTION_RELEASE", 1): PostingTemplateSpec(
        code="PARTICIPANT_COLLATERAL_RESTRICTION_RELEASE",
        version=1,
        technical_section="Technical 05 §23 Case A",
        creates_monetary_journal=False,
        control_effect=True,
    ),
    ("PARTICIPANT_RELEASE_PAYABLE_RECLASSIFICATION", 1): PostingTemplateSpec(
        code="PARTICIPANT_RELEASE_PAYABLE_RECLASSIFICATION",
        version=1,
        technical_section="Technical 05 §23 Case B",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "2000.PARTICIPANT_PAYABLE_BALANCE",
                "2070.PARTICIPANT_RELEASE_PAYABLE",
            }
        ),
    ),
    ("PARTICIPANT_RELEASE_PAYMENT", 1): PostingTemplateSpec(
        code="PARTICIPANT_RELEASE_PAYMENT",
        version=1,
        technical_section="Technical 05 §23 Case B",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset({"2070.PARTICIPANT_RELEASE_PAYABLE"})
        | CONTROLLED_CASH_ACCOUNTS,
    ),
    ("PROGRAM_ATTRIBUTED_CAPITAL_RECYCLING", 1): PostingTemplateSpec(
        code="PROGRAM_ATTRIBUTED_CAPITAL_RECYCLING",
        version=1,
        technical_section="Technical 05 §24",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset(
            {
                "2030.PROGRAM_CAPITAL_BALANCE",
                "2080.PROGRAM_RECYCLABLE_BALANCE",
            }
        ),
    ),
    ("SOCIAL_REINVESTMENT", 1): PostingTemplateSpec(
        code="SOCIAL_REINVESTMENT",
        version=1,
        technical_section="Technical 05 §25",
        creates_monetary_journal=True,
        permitted_account_codes=frozenset({"2050.SOCIAL_REINVESTMENT_BALANCE"})
        | CONTROLLED_CASH_ACCOUNTS,
    ),
    ("REVERSAL", 1): PostingTemplateSpec(
        code="REVERSAL",
        version=1,
        technical_section="Technical 05 §26",
        creates_monetary_journal=True,
        permitted_account_codes=None,
        dedicated_workflow_only=True,
    ),
}


def resolve_posting_template(code: str, version: int) -> PostingTemplateSpec:
    template = POSTING_TEMPLATES.get((code, version))
    if template is None:
        raise AccountingConfigurationError(
            "POSTING_TEMPLATE_NOT_FOUND",
            f"Posting template {code}@{version} is not registered",
        )
    return template


def validate_template_accounts(
    template: PostingTemplateSpec,
    *,
    account_codes: set[str],
) -> None:
    if not template.creates_monetary_journal:
        raise AccountingConfigurationError(
            "POSTING_TEMPLATE_NO_MONETARY_JOURNAL",
            f"{template.reference} does not authorize a Badban monetary journal",
        )
    if template.permitted_account_codes is None:
        return
    unexpected = sorted(account_codes - template.permitted_account_codes)
    if unexpected:
        raise AccountingConfigurationError(
            "POSTING_TEMPLATE_ACCOUNT_INVALID",
            f"{template.reference} does not permit accounts: {','.join(unexpected)}",
        )


async def resolve_product_account(
    session: AsyncSession,
    *,
    account_code: str,
    require_active: bool = True,
) -> JournalAccountTaxonomy:
    account = await session.get(JournalAccountTaxonomy, account_code)
    if account is None:
        raise AccountingConfigurationError(
            "PRODUCT_ACCOUNT_NOT_FOUND",
            f"Unknown Badban product account: {account_code}",
        )
    if require_active and not account.active:
        raise AccountingConfigurationError(
            "PRODUCT_ACCOUNT_INACTIVE",
            f"Badban product account is inactive: {account_code}",
        )
    return account


async def resolve_legal_entity_account_mapping(
    session: AsyncSession,
    *,
    legal_entity_id: UUID,
    product_account_code: str,
    effective_at: datetime,
) -> LegalEntityAccountMapping:
    await resolve_product_account(
        session,
        account_code=product_account_code,
        require_active=True,
    )
    matches = (
        await session.scalars(
            select(LegalEntityAccountMapping).where(
                LegalEntityAccountMapping.legal_entity_id == legal_entity_id,
                LegalEntityAccountMapping.product_account_code == product_account_code,
                LegalEntityAccountMapping.effective_from <= effective_at,
                or_(
                    LegalEntityAccountMapping.effective_to.is_(None),
                    LegalEntityAccountMapping.effective_to > effective_at,
                ),
            )
        )
    ).all()
    if not matches:
        raise AccountingConfigurationError(
            "ACCOUNT_MAPPING_MISSING",
            "No legal-entity account mapping exists for the product account and effective time",
        )
    if len(matches) > 1:
        raise AccountingConfigurationError(
            "ACCOUNT_MAPPING_AMBIGUOUS",
            "Multiple legal-entity account mappings match the product account and effective time",
        )
    return matches[0]


async def resolve_legal_entity_account_mapping_set(
    session: AsyncSession,
    *,
    legal_entity_id: UUID,
    product_account_codes: set[str],
    effective_at: datetime,
) -> dict[str, LegalEntityAccountMapping]:
    if not product_account_codes:
        raise AccountingConfigurationError(
            "ACCOUNT_MAPPING_SET_EMPTY",
            "At least one product account is required to resolve an account mapping set",
        )

    mappings: dict[str, LegalEntityAccountMapping] = {}
    for account_code in sorted(product_account_codes):
        mappings[account_code] = await resolve_legal_entity_account_mapping(
            session,
            legal_entity_id=legal_entity_id,
            product_account_code=account_code,
            effective_at=effective_at,
        )

    versions = {mapping.mapping_version for mapping in mappings.values()}
    if len(versions) != 1:
        raise AccountingConfigurationError(
            "ACCOUNT_MAPPING_VERSION_MISMATCH",
            "All product accounts in one journal must resolve to one legal-entity mapping version",
        )
    return mappings


def account_mapping_reference(mapping: LegalEntityAccountMapping) -> str:
    return f"{mapping.legal_entity_id}@{mapping.mapping_version}"
