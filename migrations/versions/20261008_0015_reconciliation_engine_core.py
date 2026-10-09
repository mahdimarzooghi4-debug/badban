"""Sprint 14 reconciliation engine core.

Revision ID: 20261008_0015
Revises: 20261007_0014
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261008_0015"
down_revision: str | None = "20261007_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_POLICY_TYPES_WITH_RECONCILIATION = (
    "'ASSET_TYPE_POLICY','OWNERSHIP_FUNDING_POLICY',"
    "'PROVIDER_PRODUCT_POLICY','RISK_APPETITE_POLICY',"
    "'RETURN_ALLOCATION_POLICY','LEGAL_AUTHORIZATION_POLICY',"
    "'POSTING_ACCOUNTING_MAPPING_POLICY','RECONCILIATION_POLICY','PILOT_POLICY_PACK'"
)

_POLICY_TYPES_BEFORE_RECONCILIATION = (
    "'ASSET_TYPE_POLICY','OWNERSHIP_FUNDING_POLICY',"
    "'PROVIDER_PRODUCT_POLICY','RISK_APPETITE_POLICY',"
    "'RETURN_ALLOCATION_POLICY','LEGAL_AUTHORIZATION_POLICY',"
    "'POSTING_ACCOUNTING_MAPPING_POLICY','PILOT_POLICY_PACK'"
)

_RECON_TYPES = (
    "'LENDER_EXTERNAL_LOAN','GUARANTEE_ISSUER','CUSTODY_ASSET',"
    "'SETTLEMENT','COLLATERAL_REGISTRY','LEDGER_SUBLEDGER'"
)


def upgrade() -> None:
    op.drop_constraint("ck_policy_version_type", "policy_versions", type_="check")
    op.create_check_constraint(
        "ck_policy_version_type",
        "policy_versions",
        f"policy_type IN ({_POLICY_TYPES_WITH_RECONCILIATION})",
    )

    op.create_table(
        "reconciliation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_type", sa.String(length=80), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "scope_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("policy_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_pack_version", sa.Integer(), nullable=False),
        sa.Column("rule_policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_policy_code", sa.String(length=120), nullable=False),
        sa.Column("rule_policy_version_number", sa.Integer(), nullable=False),
        sa.Column("rule_schema_version", sa.String(length=40), nullable=False),
        sa.Column("internal_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_snapshot_ref", sa.String(length=500), nullable=True),
        sa.Column(
            "source_evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matched_count", sa.Integer(), nullable=False),
        sa.Column("mismatch_count", sa.Integer(), nullable=False),
        sa.Column("stale_count", sa.Integer(), nullable=False),
        sa.Column("critical_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"reconciliation_type IN ({_RECON_TYPES})",
            name="ck_reconciliation_run_type",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING','COMPLETED','FAILED')",
            name="ck_reconciliation_run_status",
        ),
        sa.CheckConstraint(
            "matched_count >= 0 AND mismatch_count >= 0 AND stale_count >= 0 "
            "AND critical_count >= 0",
            name="ck_reconciliation_run_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["credit_providers.id"],
            name="fk_reconciliation_run_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_pack_id"],
            ["policy_versions.id"],
            name="fk_reconciliation_run_policy_pack",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_policy_version_id"],
            ["policy_versions.id"],
            name="fk_reconciliation_run_rule_policy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_fingerprint",
            name="uq_reconciliation_run_source_fingerprint",
        ),
    )
    op.create_index(
        "ix_reconciliation_runs_type_status",
        "reconciliation_runs",
        ["reconciliation_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_runs_provider_status",
        "reconciliation_runs",
        ["provider_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_runs_started",
        "reconciliation_runs",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "reconciliation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_type", sa.String(length=80), nullable=False),
        sa.Column("internal_entity_type", sa.String(length=120), nullable=False),
        sa.Column("internal_entity_id", sa.String(length=160), nullable=True),
        sa.Column("external_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("materiality", sa.String(length=20), nullable=False),
        sa.Column("mismatch_reason_code", sa.String(length=120), nullable=True),
        sa.Column("compared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_reference", sa.String(length=500), nullable=True),
        sa.Column("rule_policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_policy_version_number", sa.Integer(), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"reconciliation_type IN ({_RECON_TYPES})",
            name="ck_reconciliation_case_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','MATCHED','MISMATCH','STALE','DISPUTED','RESOLVED')",
            name="ck_reconciliation_case_status",
        ),
        sa.CheckConstraint(
            "materiality IN ('INFO','WARNING','MATERIAL','CRITICAL')",
            name="ck_reconciliation_case_materiality",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["reconciliation_runs.id"],
            name="fk_reconciliation_case_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["external_provider_id"],
            ["credit_providers.id"],
            name="fk_reconciliation_case_provider",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_policy_version_id"],
            ["policy_versions.id"],
            name="fk_reconciliation_case_rule_policy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reconciliation_cases_type_status",
        "reconciliation_cases",
        ["reconciliation_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_cases_internal",
        "reconciliation_cases",
        ["internal_entity_type", "internal_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_cases_provider_status",
        "reconciliation_cases",
        ["external_provider_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_cases_run",
        "reconciliation_cases",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_cases_compared",
        "reconciliation_cases",
        ["compared_at"],
        unique=False,
    )

    op.create_table(
        "reconciliation_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internal_value_reference", sa.String(length=500), nullable=False),
        sa.Column("external_value_reference", sa.String(length=500), nullable=False),
        sa.Column(
            "difference_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_case_id"],
            ["reconciliation_cases.id"],
            name="fk_reconciliation_observation_case",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reconciliation_observations_case",
        "reconciliation_observations",
        ["reconciliation_case_id"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_observations_observed",
        "reconciliation_observations",
        ["observed_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_reconciliation_observation_mutation()
        RETURNS trigger AS $reconciliation_observation$
        BEGIN
            RAISE EXCEPTION 'reconciliation_observations are append-only';
        END;
        $reconciliation_observation$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_reconciliation_observations_append_only
        BEFORE UPDATE OR DELETE ON reconciliation_observations
        FOR EACH ROW EXECUTE FUNCTION badban_reject_reconciliation_observation_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_reconciliation_observations_append_only "
        "ON reconciliation_observations"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_reconciliation_observation_mutation")
    op.drop_index(
        "ix_reconciliation_observations_observed",
        table_name="reconciliation_observations",
    )
    op.drop_index(
        "ix_reconciliation_observations_case",
        table_name="reconciliation_observations",
    )
    op.drop_table("reconciliation_observations")
    op.drop_index("ix_reconciliation_cases_compared", table_name="reconciliation_cases")
    op.drop_index("ix_reconciliation_cases_run", table_name="reconciliation_cases")
    op.drop_index(
        "ix_reconciliation_cases_provider_status",
        table_name="reconciliation_cases",
    )
    op.drop_index("ix_reconciliation_cases_internal", table_name="reconciliation_cases")
    op.drop_index(
        "ix_reconciliation_cases_type_status",
        table_name="reconciliation_cases",
    )
    op.drop_table("reconciliation_cases")
    op.drop_index("ix_reconciliation_runs_started", table_name="reconciliation_runs")
    op.drop_index(
        "ix_reconciliation_runs_provider_status",
        table_name="reconciliation_runs",
    )
    op.drop_index(
        "ix_reconciliation_runs_type_status",
        table_name="reconciliation_runs",
    )
    op.drop_table("reconciliation_runs")

    op.drop_constraint("ck_policy_version_type", "policy_versions", type_="check")
    op.create_check_constraint(
        "ck_policy_version_type",
        "policy_versions",
        f"policy_type IN ({_POLICY_TYPES_BEFORE_RECONCILIATION})",
    )
