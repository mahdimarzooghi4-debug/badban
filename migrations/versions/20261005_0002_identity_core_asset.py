"""Sprint 02 identity, program, asset, and audit state.

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261005_0002"
down_revision: str | None = "20261005_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_type", sa.String(length=40), nullable=False),
        sa.Column("external_subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_subject"),
    )

    op.create_table(
        "participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_reference"),
    )

    op.create_table(
        "programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "asset_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("unit_code", sa.String(length=40), nullable=False),
        sa.Column("quantity_scale", sa.Integer(), nullable=False),
        sa.Column("currency_or_valuation_currency", sa.String(length=16), nullable=True),
        sa.Column("valuation_source_reference", sa.String(length=255), nullable=True),
        sa.Column("eligibility_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "custody_restriction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity_scale >= 0 AND quantity_scale <= 18",
            name="ck_asset_type_scale",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_code"),
    )

    op.create_table(
        "role_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_code", sa.String(length=80), nullable=False),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason_ref", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["identity_id"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_role_grants_identity_status",
        "role_grants",
        ["identity_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_role_grants_scope",
        "role_grants",
        ["scope_type", "scope_id"],
        unique=False,
    )

    op.create_table(
        "participation_episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("eligibility_reference", sa.String(length=255), nullable=True),
        sa.Column("consent_state", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_participation_episode_end_after_start",
        ),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_participation_episodes_participant",
        "participation_episodes",
        ["participant_id"],
        unique=False,
    )
    op.create_index(
        "ix_participation_episodes_program",
        "participation_episodes",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_participation_episodes_participant_program_status",
        "participation_episodes",
        ["participant_id", "program_id", "status"],
        unique=False,
    )

    op.create_table(
        "asset_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participation_episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ownership_funding_type", sa.String(length=40), nullable=False),
        sa.Column("legal_owner_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("legal_owner_participant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("custodian_legal_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("unit_code", sa.String(length=40), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_asset_position_quantity_nonnegative"),
        sa.CheckConstraint(
            "ownership_funding_type IN ('PARTICIPANT_OWNED', 'PROGRAM_ATTRIBUTED')",
            name="ck_asset_position_ownership_type",
        ),
        sa.CheckConstraint(
            "("
            "ownership_funding_type = 'PARTICIPANT_OWNED' "
            "AND legal_owner_participant_id IS NOT NULL "
            "AND legal_owner_entity_id IS NULL"
            ") OR ("
            "ownership_funding_type = 'PROGRAM_ATTRIBUTED' "
            "AND legal_owner_entity_id IS NOT NULL "
            "AND legal_owner_participant_id IS NULL"
            ")",
            name="ck_asset_position_owner_pattern",
        ),
        sa.ForeignKeyConstraint(["asset_type_id"], ["asset_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["legal_owner_participant_id"], ["participants.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["participation_episode_id"],
            ["participation_episodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_asset_positions_episode",
        "asset_positions",
        ["participation_episode_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_positions_program",
        "asset_positions",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_positions_asset_type",
        "asset_positions",
        ["asset_type_id"],
        unique=False,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_id", sa.String(length=160), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason_code", sa.String(length=120), nullable=True),
        sa.Column("policy_pack_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_aggregate",
        "audit_events",
        ["aggregate_type", "aggregate_id", "aggregate_version"],
        unique=False,
    )
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_correlation", "audit_events", ["correlation_id"], unique=False)
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"], unique=False)

    op.create_table(
        "evidence_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("storage_provider", sa.String(length=80), nullable=False),
        sa.Column("storage_reference", sa.String(length=500), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("media_type", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION badban_reject_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_audit_mutation")
    op.drop_table("evidence_references")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_correlation", table_name="audit_events")
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_index("ix_audit_events_aggregate", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_asset_positions_asset_type", table_name="asset_positions")
    op.drop_index("ix_asset_positions_program", table_name="asset_positions")
    op.drop_index("ix_asset_positions_episode", table_name="asset_positions")
    op.drop_table("asset_positions")
    op.drop_index(
        "ix_participation_episodes_participant_program_status",
        table_name="participation_episodes",
    )
    op.drop_index(
        "ix_participation_episodes_program",
        table_name="participation_episodes",
    )
    op.drop_index(
        "ix_participation_episodes_participant",
        table_name="participation_episodes",
    )
    op.drop_table("participation_episodes")
    op.drop_index("ix_role_grants_scope", table_name="role_grants")
    op.drop_index("ix_role_grants_identity_status", table_name="role_grants")
    op.drop_table("role_grants")
    op.drop_table("asset_types")
    op.drop_table("programs")
    op.drop_table("participants")
    op.drop_table("identities")
