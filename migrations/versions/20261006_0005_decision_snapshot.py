"""Sprint 04 append-only DecisionSnapshot persistence.

Revision ID: 20261006_0005
Revises: 20261006_0004
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261006_0005"
down_revision: str | None = "20261006_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_entity_type", sa.String(length=120), nullable=False),
        sa.Column("business_entity_id", sa.String(length=160), nullable=False),
        sa.Column("decision_type", sa.String(length=120), nullable=False),
        sa.Column("policy_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_pack_version", sa.Integer(), nullable=False),
        sa.Column(
            "component_version_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("algorithm_code", sa.String(length=120), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=False),
        sa.Column(
            "material_input_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "material_output_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "valuation_observation_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "authoritative_external_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("risk_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "policy_pack_version > 0",
            name="ck_decision_snapshot_policy_pack_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["policy_pack_id"],
            ["policy_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_decision_snapshots_entity",
        "decision_snapshots",
        ["business_entity_type", "business_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_decision_snapshots_policy_pack",
        "decision_snapshots",
        ["policy_pack_id"],
        unique=False,
    )
    op.create_index(
        "ix_decision_snapshots_effective_at",
        "decision_snapshots",
        ["effective_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_decision_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'decision_snapshots are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_snapshots_append_only
        BEFORE UPDATE OR DELETE ON decision_snapshots
        FOR EACH ROW EXECUTE FUNCTION badban_reject_decision_snapshot_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_decision_snapshots_append_only ON decision_snapshots")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_decision_snapshot_mutation")
    op.drop_index("ix_decision_snapshots_effective_at", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_policy_pack", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_entity", table_name="decision_snapshots")
    op.drop_table("decision_snapshots")
