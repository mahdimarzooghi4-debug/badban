"""Sprint 10 product account taxonomy and legal entity mappings.

Revision ID: 20261007_0011
Revises: 20261007_0010
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_0011"
down_revision: str | None = "20261007_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ACCOUNT_ROWS = [
    (
        "1000.SETTLEMENT_CASH_CONTROL",
        "SETTLEMENT_CASH_CONTROL",
        "CONTROLLED_ASSET",
        "DEBIT",
        "MONETARY",
    ),
    (
        "1010.PROGRAM_CASH_CONTROL",
        "PROGRAM_CASH_CONTROL",
        "CONTROLLED_ASSET",
        "DEBIT",
        "MONETARY",
    ),
    (
        "1020.GUARANTEE_RESERVE_CASH_CONTROL",
        "GUARANTEE_RESERVE_CASH_CONTROL",
        "CONTROLLED_ASSET",
        "DEBIT",
        "MONETARY",
    ),
    (
        "1030.RECOVERY_CASH_CONTROL",
        "RECOVERY_CASH_CONTROL",
        "CONTROLLED_ASSET",
        "DEBIT",
        "MONETARY",
    ),
    (
        "1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL",
        "CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL",
        "CONTROLLED_ASSET",
        "DEBIT",
        "MONETARY",
    ),
    (
        "1050.OTHER_APPROVED_CONTROLLED_ASSET",
        "OTHER_APPROVED_CONTROLLED_ASSET",
        "CONTROLLED_ASSET",
        "DEBIT",
        "MONETARY",
    ),
    (
        "2000.PARTICIPANT_PAYABLE_BALANCE",
        "PARTICIPANT_PAYABLE_BALANCE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2010.LIVELIHOOD_PAYABLE",
        "LIVELIHOOD_PAYABLE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2020.FUTURE_FINANCIAL_ENTITLEMENT",
        "FUTURE_FINANCIAL_ENTITLEMENT",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2030.PROGRAM_CAPITAL_BALANCE",
        "PROGRAM_CAPITAL_BALANCE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE",
        "GUARANTEE_RESERVE_DESIGNATED_BALANCE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2050.SOCIAL_REINVESTMENT_BALANCE",
        "SOCIAL_REINVESTMENT_BALANCE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2060.RETURN_CARRY_FORWARD_BALANCE",
        "RETURN_CARRY_FORWARD_BALANCE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2070.PARTICIPANT_RELEASE_PAYABLE",
        "PARTICIPANT_RELEASE_PAYABLE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "2080.PROGRAM_RECYCLABLE_BALANCE",
        "PROGRAM_RECYCLABLE_BALANCE",
        "OWNER_OR_ENTITLEMENT_BALANCE",
        "CREDIT",
        "MONETARY",
    ),
    (
        "3000.RECOGNIZED_RETURN_CLEARING",
        "RECOGNIZED_RETURN_CLEARING",
        "RETURN_OR_INCOME_CLEARING",
        "CREDIT",
        "MONETARY",
    ),
    (
        "3010.RETURN_ALLOCATION_CLEARING",
        "RETURN_ALLOCATION_CLEARING",
        "RETURN_OR_INCOME_CLEARING",
        "CREDIT",
        "MONETARY",
    ),
    (
        "3020.CAPITAL_GROWTH_CLEARING",
        "CAPITAL_GROWTH_CLEARING",
        "RETURN_OR_INCOME_CLEARING",
        "CREDIT",
        "MONETARY",
    ),
    (
        "4000.GUARANTEE_FINAL_RESIDUAL_LOSS",
        "GUARANTEE_FINAL_RESIDUAL_LOSS",
        "LOSS_OR_COST_CONTROL",
        "DEBIT",
        "MONETARY",
    ),
    (
        "4010.ENFORCEMENT_COST",
        "ENFORCEMENT_COST",
        "LOSS_OR_COST_CONTROL",
        "DEBIT",
        "MONETARY",
    ),
    (
        "4020.APPROVED_FINANCIAL_ADJUSTMENT_LOSS",
        "APPROVED_FINANCIAL_ADJUSTMENT_LOSS",
        "LOSS_OR_COST_CONTROL",
        "DEBIT",
        "MONETARY",
    ),
    (
        "9000.GUARANTEE_CAPACITY_RESERVED_MEMO",
        "GUARANTEE_CAPACITY_RESERVED_MEMO",
        "MEMORANDUM_CONTROL",
        "MEMO",
        "MEMORANDUM_CONTROL",
    ),
    (
        "9010.ACTIVE_GUARANTEE_EXPOSURE_MEMO",
        "ACTIVE_GUARANTEE_EXPOSURE_MEMO",
        "MEMORANDUM_CONTROL",
        "MEMO",
        "MEMORANDUM_CONTROL",
    ),
    (
        "9020.BACKING_ENCUMBERED_MEMO",
        "BACKING_ENCUMBERED_MEMO",
        "MEMORANDUM_CONTROL",
        "MEMO",
        "MEMORANDUM_CONTROL",
    ),
    (
        "9030.CLAIM_APPROVED_PENDING_SETTLEMENT_MEMO",
        "CLAIM_APPROVED_PENDING_SETTLEMENT_MEMO",
        "MEMORANDUM_CONTROL",
        "MEMO",
        "MEMORANDUM_CONTROL",
    ),
    (
        "9040.CLAIM_SETTLED_RECOVERY_OPEN_MEMO",
        "CLAIM_SETTLED_RECOVERY_OPEN_MEMO",
        "MEMORANDUM_CONTROL",
        "MEMO",
        "MEMORANDUM_CONTROL",
    ),
    (
        "9050.EXTERNAL_LOAN_PRINCIPAL_MIRROR_MEMO",
        "EXTERNAL_LOAN_PRINCIPAL_MIRROR_MEMO",
        "MEMORANDUM_CONTROL",
        "MEMO",
        "EXTERNAL_MIRROR",
    ),
    (
        "9060.EXTERNAL_LOAN_OUTSTANDING_MIRROR_MEMO",
        "EXTERNAL_LOAN_OUTSTANDING_MIRROR_MEMO",
        "MEMORANDUM_CONTROL",
        "MEMO",
        "EXTERNAL_MIRROR",
    ),
]


def upgrade() -> None:
    op.create_table(
        "journal_account_taxonomy",
        sa.Column("account_code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("account_class", sa.String(length=80), nullable=False),
        sa.Column("normal_balance", sa.String(length=16), nullable=False),
        sa.Column("ledger_layer", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_class IN ("
            "'CONTROLLED_ASSET','OWNER_OR_ENTITLEMENT_BALANCE',"
            "'RETURN_OR_INCOME_CLEARING','LOSS_OR_COST_CONTROL','MEMORANDUM_CONTROL'"
            ")",
            name="ck_journal_account_taxonomy_class",
        ),
        sa.CheckConstraint(
            "normal_balance IN ('DEBIT','CREDIT','MEMO')",
            name="ck_journal_account_taxonomy_normal_balance",
        ),
        sa.CheckConstraint(
            "ledger_layer IN ('MONETARY','MEMORANDUM_CONTROL','EXTERNAL_MIRROR')",
            name="ck_journal_account_taxonomy_layer",
        ),
        sa.PrimaryKeyConstraint("account_code"),
    )

    taxonomy = sa.table(
        "journal_account_taxonomy",
        sa.column("account_code", sa.String(length=80)),
        sa.column("name", sa.String(length=160)),
        sa.column("account_class", sa.String(length=80)),
        sa.column("normal_balance", sa.String(length=16)),
        sa.column("ledger_layer", sa.String(length=40)),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        taxonomy,
        [
            {
                "account_code": code,
                "name": name,
                "account_class": account_class,
                "normal_balance": normal_balance,
                "ledger_layer": ledger_layer,
                "active": True,
            }
            for code, name, account_class, normal_balance, ledger_layer in _ACCOUNT_ROWS
        ],
    )

    op.create_table(
        "legal_entity_account_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_account_code", sa.String(length=80), nullable=False),
        sa.Column("external_chart_account_code", sa.String(length=160), nullable=False),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mapping_version > 0",
            name="ck_legal_entity_account_mapping_version_positive",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_legal_entity_account_mapping_window",
        ),
        sa.ForeignKeyConstraint(
            ["legal_entity_id"],
            ["legal_entities.id"],
            name="fk_legal_entity_account_mapping_entity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_account_code"],
            ["journal_account_taxonomy.account_code"],
            name="fk_legal_entity_account_mapping_product_account",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "legal_entity_id",
            "product_account_code",
            "mapping_version",
            name="uq_legal_entity_account_mapping_version",
        ),
    )
    op.create_index(
        "ix_legal_entity_account_mapping_lookup",
        "legal_entity_account_mappings",
        ["legal_entity_id", "product_account_code", "effective_from", "effective_to"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_protect_journal_account_taxonomy()
        RETURNS trigger AS $
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'journal_account_taxonomy definitions cannot be deleted';
            END IF;
            IF NEW.account_code IS DISTINCT FROM OLD.account_code
                OR NEW.name IS DISTINCT FROM OLD.name
                OR NEW.account_class IS DISTINCT FROM OLD.account_class
                OR NEW.normal_balance IS DISTINCT FROM OLD.normal_balance
                OR NEW.ledger_layer IS DISTINCT FROM OLD.ledger_layer
            THEN
                RAISE EXCEPTION 'journal_account_taxonomy definitions are immutable';
            END IF;
            RETURN NEW;
        END;
        $ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_account_taxonomy_immutable
        BEFORE UPDATE OR DELETE ON journal_account_taxonomy
        FOR EACH ROW EXECUTE FUNCTION badban_protect_journal_account_taxonomy()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_legal_entity_account_mapping_mutation()
        RETURNS trigger AS $
        BEGIN
            RAISE EXCEPTION 'legal_entity_account_mappings are append-only';
        END;
        $ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_legal_entity_account_mappings_append_only
        BEFORE UPDATE OR DELETE ON legal_entity_account_mappings
        FOR EACH ROW EXECUTE FUNCTION badban_reject_legal_entity_account_mapping_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_legal_entity_account_mappings_append_only "
        "ON legal_entity_account_mappings"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_legal_entity_account_mapping_mutation")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_journal_account_taxonomy_immutable ON journal_account_taxonomy"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_protect_journal_account_taxonomy")
    op.drop_index(
        "ix_legal_entity_account_mapping_lookup",
        table_name="legal_entity_account_mappings",
    )
    op.drop_table("legal_entity_account_mappings")
    op.drop_table("journal_account_taxonomy")
