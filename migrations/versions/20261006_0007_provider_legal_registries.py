"""Sprint 06 provider/product and legal authorization registries.

Revision ID: 20261006_0007
Revises: 20261006_0006
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261006_0007"
down_revision: str | None = "20261006_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legal_roles",
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    legal_roles = sa.table("legal_roles", sa.column("code", sa.String(length=120)))
    op.bulk_insert(
        legal_roles,
        [
            {"code": "GUARANTEE_ISSUER"},
            {"code": "LENDER"},
            {"code": "CUSTODIAN"},
            {"code": "ASSET_MANAGER"},
            {"code": "PAYMENT_PROVIDER"},
            {"code": "COLLATERAL_REGISTRY_OPERATOR"},
            {"code": "BADBAN_CORE"},
        ],
    )

    op.create_table(
        "legal_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("registration_identifier", sa.String(length=160), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registration_identifier"),
    )
    op.create_table(
        "legal_authorizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_code", sa.String(length=120), nullable=False),
        sa.Column("competent_authority", sa.String(length=255), nullable=False),
        sa.Column("authorization_type", sa.String(length=160), nullable=False),
        sa.Column("authorization_identifier", sa.String(length=200), nullable=False),
        sa.Column(
            "scope_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "permitted_product_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "permitted_asset_type_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("evidence_reference", sa.String(length=500), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_compliance_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "lifecycle_status IN "
            "('PENDING_VERIFICATION','VALID','SUSPENDED','EXPIRED','REVOKED','SUPERSEDED')",
            name="ck_legal_authorization_status",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > effective_from",
            name="ck_legal_authorization_effective_window",
        ),
        sa.ForeignKeyConstraint(["legal_entity_id"], ["legal_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_code"], ["legal_roles.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_legal_authorizations_entity_role_status",
        "legal_authorizations",
        ["legal_entity_id", "role_code", "lifecycle_status"],
        unique=False,
    )
    op.create_index(
        "ix_legal_authorizations_expires_at",
        "legal_authorizations",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_legal_authorizations_authority",
        "legal_authorizations",
        ["competent_authority"],
        unique=False,
    )
    op.create_table(
        "credit_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_code", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=80), nullable=False),
        sa.Column("integration_mode", sa.String(length=40), nullable=False),
        sa.Column("authorization_review_state", sa.String(length=80), nullable=False),
        sa.Column("suspension_reason", sa.String(length=500), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "provider_type = 'EXTERNAL_LENDER'",
            name="ck_credit_provider_bounded_pilot_type",
        ),
        sa.CheckConstraint(
            "integration_mode IN "
            "('API','WEBHOOK_CALLBACK','POLLING','SECURE_BATCH_FILE','CONTROLLED_MANUAL')",
            name="ck_credit_provider_integration_mode",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','APPROVED','ACTIVE','SUSPENDED','EXPIRED','TERMINATED')",
            name="ck_credit_provider_status",
        ),
        sa.ForeignKeyConstraint(["legal_entity_id"], ["legal_entities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_code"),
    )
    op.create_index(
        "ix_credit_providers_legal_entity",
        "credit_providers",
        ["legal_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_credit_providers_status",
        "credit_providers",
        ["lifecycle_status"],
        unique=False,
    )
    op.create_table(
        "credit_product_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "lender_of_record_legal_entity_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("product_code", sa.String(length=120), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("product_type", sa.String(length=120), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("min_principal", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("max_principal", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("tenor_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("repayment_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pricing_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("guarantee_mode", sa.String(length=40), nullable=False),
        sa.Column(
            "delinquency_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("claim_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_version_reference", sa.String(length=200), nullable=False),
        sa.Column("additional_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version_number > 0", name="ck_credit_product_version_positive"),
        sa.CheckConstraint("min_principal >= 0", name="ck_credit_product_min_nonnegative"),
        sa.CheckConstraint(
            "max_principal >= min_principal",
            name="ck_credit_product_max_not_below_min",
        ),
        sa.CheckConstraint(
            "guarantee_mode IN ('FIXED','DECLINING')",
            name="ck_credit_product_guarantee_mode",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','ACTIVE','SUSPENDED','RETIRED')",
            name="ck_credit_product_status",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_credit_product_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["lender_of_record_legal_entity_id"],
            ["legal_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["credit_providers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "product_code",
            "version_number",
            name="uq_credit_product_provider_code_version",
        ),
    )
    op.create_index(
        "ix_credit_product_versions_provider_status",
        "credit_product_versions",
        ["provider_id", "lifecycle_status"],
        unique=False,
    )
    op.create_index(
        "ix_credit_product_versions_provider_code_effective",
        "credit_product_versions",
        ["provider_id", "product_code", "effective_from"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_legal_authorization_history_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.lifecycle_status IN ('VALID','SUSPENDED','EXPIRED','REVOKED','SUPERSEDED')
               AND (
                    NEW.legal_entity_id IS DISTINCT FROM OLD.legal_entity_id
                    OR NEW.role_code IS DISTINCT FROM OLD.role_code
                    OR NEW.competent_authority IS DISTINCT FROM OLD.competent_authority
                    OR NEW.authorization_type IS DISTINCT FROM OLD.authorization_type
                    OR NEW.authorization_identifier IS DISTINCT FROM OLD.authorization_identifier
                    OR NEW.scope_definition IS DISTINCT FROM OLD.scope_definition
                    OR NEW.permitted_product_scope IS DISTINCT FROM OLD.permitted_product_scope
                    OR NEW.permitted_asset_type_ids IS DISTINCT FROM OLD.permitted_asset_type_ids
                    OR NEW.evidence_reference IS DISTINCT FROM OLD.evidence_reference
                    OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
                    OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
                    OR NEW.last_compliance_review_at IS DISTINCT FROM OLD.last_compliance_review_at
                    OR NEW.created_by IS DISTINCT FROM OLD.created_by
               )
            THEN
                RAISE EXCEPTION 'legal authorization history is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_legal_authorizations_history_immutable
        BEFORE UPDATE ON legal_authorizations
        FOR EACH ROW
        EXECUTE FUNCTION badban_reject_legal_authorization_history_mutation()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_credit_provider_history_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.lifecycle_status IN ('ACTIVE','SUSPENDED','EXPIRED','TERMINATED')
               AND (
                    NEW.legal_entity_id IS DISTINCT FROM OLD.legal_entity_id
                    OR NEW.provider_code IS DISTINCT FROM OLD.provider_code
                    OR NEW.display_name IS DISTINCT FROM OLD.display_name
                    OR NEW.provider_type IS DISTINCT FROM OLD.provider_type
                    OR NEW.integration_mode IS DISTINCT FROM OLD.integration_mode
                    OR NEW.created_by IS DISTINCT FROM OLD.created_by
               )
            THEN
                RAISE EXCEPTION 'credit provider history is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_credit_providers_history_immutable
        BEFORE UPDATE ON credit_providers
        FOR EACH ROW
        EXECUTE FUNCTION badban_reject_credit_provider_history_mutation()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_credit_product_history_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.lifecycle_status IN ('ACTIVE','SUSPENDED','RETIRED')
               AND (
                    NEW.provider_id IS DISTINCT FROM OLD.provider_id
                    OR NEW.lender_of_record_legal_entity_id IS DISTINCT FROM
                       OLD.lender_of_record_legal_entity_id
                    OR NEW.product_code IS DISTINCT FROM OLD.product_code
                    OR NEW.version_number IS DISTINCT FROM OLD.version_number
                    OR NEW.product_name IS DISTINCT FROM OLD.product_name
                    OR NEW.product_type IS DISTINCT FROM OLD.product_type
                    OR NEW.currency IS DISTINCT FROM OLD.currency
                    OR NEW.min_principal IS DISTINCT FROM OLD.min_principal
                    OR NEW.max_principal IS DISTINCT FROM OLD.max_principal
                    OR NEW.tenor_definition IS DISTINCT FROM OLD.tenor_definition
                    OR NEW.repayment_definition IS DISTINCT FROM OLD.repayment_definition
                    OR NEW.pricing_definition IS DISTINCT FROM OLD.pricing_definition
                    OR NEW.guarantee_mode IS DISTINCT FROM OLD.guarantee_mode
                    OR NEW.delinquency_definition IS DISTINCT FROM OLD.delinquency_definition
                    OR NEW.claim_definition IS DISTINCT FROM OLD.claim_definition
                    OR NEW.policy_version_reference IS DISTINCT FROM OLD.policy_version_reference
                    OR NEW.additional_terms IS DISTINCT FROM OLD.additional_terms
                    OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
                    OR NEW.effective_to IS DISTINCT FROM OLD.effective_to
                    OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
                    OR NEW.created_by IS DISTINCT FROM OLD.created_by
               )
            THEN
                RAISE EXCEPTION 'credit product version history is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_credit_product_versions_history_immutable
        BEFORE UPDATE ON credit_product_versions
        FOR EACH ROW
        EXECUTE FUNCTION badban_reject_credit_product_history_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_credit_product_versions_history_immutable "
        "ON credit_product_versions"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_credit_providers_history_immutable ON credit_providers")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_legal_authorizations_history_immutable ON legal_authorizations"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_credit_product_history_mutation")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_credit_provider_history_mutation")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_legal_authorization_history_mutation")
    op.drop_index(
        "ix_credit_product_versions_provider_code_effective",
        table_name="credit_product_versions",
    )
    op.drop_index(
        "ix_credit_product_versions_provider_status",
        table_name="credit_product_versions",
    )
    op.drop_table("credit_product_versions")
    op.drop_index("ix_credit_providers_status", table_name="credit_providers")
    op.drop_index("ix_credit_providers_legal_entity", table_name="credit_providers")
    op.drop_table("credit_providers")
    op.drop_index("ix_legal_authorizations_authority", table_name="legal_authorizations")
    op.drop_index("ix_legal_authorizations_expires_at", table_name="legal_authorizations")
    op.drop_index(
        "ix_legal_authorizations_entity_role_status",
        table_name="legal_authorizations",
    )
    op.drop_table("legal_authorizations")
    op.drop_table("legal_entities")
    op.drop_table("legal_roles")
