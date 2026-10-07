"""Sprint 09 portfolio risk snapshot and gate.

Revision ID: 20261007_0010
Revises: 20261007_0009
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_0010"
down_revision: str | None = "20261007_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_risk_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_pack_version", sa.Integer(), nullable=False),
        sa.Column("risk_policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("risk_policy_code", sa.String(length=120), nullable=False),
        sa.Column("risk_policy_version_number", sa.Integer(), nullable=False),
        sa.Column("risk_state", sa.String(length=20), nullable=False),
        sa.Column("total_active_exposure", sa.Numeric(38, 18), nullable=False),
        sa.Column("total_reserved_exposure", sa.Numeric(38, 18), nullable=False),
        sa.Column("committed_exposure", sa.Numeric(38, 18), nullable=False),
        sa.Column("approved_portfolio_limit", sa.Numeric(38, 18), nullable=False),
        sa.Column("reserve_requirement", sa.Numeric(38, 18), nullable=False),
        sa.Column("reserve_available", sa.Numeric(38, 18), nullable=False),
        sa.Column("reserve_metrics_reference", sa.String(length=500), nullable=False),
        sa.Column("concentration_metrics_reference", sa.String(length=500), nullable=False),
        sa.Column("stress_result_reference", sa.String(length=500), nullable=True),
        sa.Column("evaluated_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("algorithm_code", sa.String(length=120), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "risk_state IN ('GREEN','AMBER','RED')",
            name="ck_portfolio_risk_snapshot_state",
        ),
        sa.CheckConstraint(
            "total_active_exposure >= 0 "
            "AND total_reserved_exposure >= 0 "
            "AND committed_exposure >= 0 "
            "AND approved_portfolio_limit >= 0 "
            "AND reserve_requirement >= 0 "
            "AND reserve_available >= 0",
            name="ck_portfolio_risk_snapshot_metrics_nonnegative",
        ),
        sa.CheckConstraint(
            "policy_pack_version > 0 AND risk_policy_version_number > 0",
            name="ck_portfolio_risk_snapshot_versions_positive",
        ),
        sa.ForeignKeyConstraint(
            ["policy_pack_id"],
            ["policy_versions.id"],
            name="fk_portfolio_risk_snapshot_policy_pack",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["risk_policy_version_id"],
            ["policy_versions.id"],
            name="fk_portfolio_risk_snapshot_risk_policy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_risk_snapshots_evaluated",
        "portfolio_risk_snapshots",
        ["evaluated_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_risk_snapshots_policy_pack",
        "portfolio_risk_snapshots",
        ["policy_pack_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_guarantee_cases_risk_snapshot",
        "guarantee_cases",
        "portfolio_risk_snapshots",
        ["risk_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_decision_snapshots_risk_snapshot",
        "decision_snapshots",
        "portfolio_risk_snapshots",
        ["risk_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_portfolio_risk_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'portfolio_risk_snapshots are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_risk_snapshots_append_only
        BEFORE UPDATE OR DELETE ON portfolio_risk_snapshots
        FOR EACH ROW EXECUTE FUNCTION badban_reject_portfolio_risk_snapshot_mutation()
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_decision_snapshots_risk_snapshot",
        "decision_snapshots",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_guarantee_cases_risk_snapshot",
        "guarantee_cases",
        type_="foreignkey",
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_risk_snapshots_append_only "
        "ON portfolio_risk_snapshots"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_portfolio_risk_snapshot_mutation()")
    op.drop_index(
        "ix_portfolio_risk_snapshots_policy_pack",
        table_name="portfolio_risk_snapshots",
    )
    op.drop_index(
        "ix_portfolio_risk_snapshots_evaluated",
        table_name="portfolio_risk_snapshots",
    )
    op.drop_table("portfolio_risk_snapshots")
