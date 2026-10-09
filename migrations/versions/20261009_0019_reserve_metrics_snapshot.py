"""Sprint 21 reserve metrics snapshot.

Revision ID: 20261009_0019
Revises: 20261008_0018
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261009_0019"
down_revision: str | None = "20261008_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guarantee_reserve_metrics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("cash_control_balance", sa.Numeric(38, 18), nullable=False),
        sa.Column("designated_balance", sa.Numeric(38, 18), nullable=False),
        sa.Column("source_journal_count", sa.Integer(), nullable=False),
        sa.Column("source_posting_count", sa.Integer(), nullable=False),
        sa.Column("source_journal_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_posting_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("algorithm_code", sa.String(length=120), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "source_journal_count >= 0 AND source_posting_count >= 0",
            name="ck_reserve_metrics_source_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["identities.id"],
            name="fk_reserve_metrics_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legal_entity_id"],
            ["legal_entities.id"],
            name="fk_reserve_metrics_legal_entity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "legal_entity_id",
            "currency",
            "source_fingerprint",
            name="uq_reserve_metrics_scope_fingerprint",
        ),
    )
    op.create_index(
        "ix_reserve_metrics_scope_evaluated",
        "guarantee_reserve_metrics_snapshots",
        ["legal_entity_id", "currency", "evaluated_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_reserve_metrics_snapshot_mutation()
        RETURNS trigger AS $reserve_metrics$
        BEGIN
            RAISE EXCEPTION 'reserve metrics snapshots are append-only';
        END;
        $reserve_metrics$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_reserve_metrics_snapshot_append_only
        BEFORE UPDATE OR DELETE ON guarantee_reserve_metrics_snapshots
        FOR EACH ROW EXECUTE FUNCTION badban_reject_reserve_metrics_snapshot_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_reserve_metrics_snapshot_append_only "
        "ON guarantee_reserve_metrics_snapshots"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_reserve_metrics_snapshot_mutation")
    op.drop_index(
        "ix_reserve_metrics_scope_evaluated",
        table_name="guarantee_reserve_metrics_snapshots",
    )
    op.drop_table("guarantee_reserve_metrics_snapshots")
