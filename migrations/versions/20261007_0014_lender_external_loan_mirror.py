"""Sprint 13 lender adapter and external loan mirror.

Revision ID: 20261007_0014
Revises: 20261007_0013
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_0014"
down_revision: str | None = "20261007_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_loan_mirrors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guarantee_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_loan_id", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("original_principal", sa.Numeric(38, 18), nullable=False),
        sa.Column("outstanding_principal", sa.Numeric(38, 18), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("disbursed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delinquency_state", sa.String(length=80), nullable=True),
        sa.Column("last_provider_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_provider_event_sequence", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciliation_status", sa.String(length=40), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
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
            "state IN ('PENDING','ACTIVE','DELINQUENT','SETTLED','REPLACED')",
            name="ck_external_loan_state",
        ),
        sa.CheckConstraint(
            "original_principal > 0",
            name="ck_external_loan_original_principal_positive",
        ),
        sa.CheckConstraint(
            "outstanding_principal >= 0",
            name="ck_external_loan_outstanding_nonnegative",
        ),
        sa.CheckConstraint(
            "outstanding_principal <= original_principal",
            name="ck_external_loan_outstanding_not_above_original",
        ),
        sa.CheckConstraint(
            "last_provider_event_sequence IS NULL OR last_provider_event_sequence >= 0",
            name="ck_external_loan_sequence_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["guarantee_case_id"],
            ["guarantee_cases.id"],
            name="fk_external_loan_guarantee_case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["credit_providers.id"],
            name="fk_external_loan_provider",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "external_loan_id",
            name="uq_external_loan_provider_external_id",
        ),
        sa.UniqueConstraint(
            "guarantee_case_id",
            name="uq_external_loan_guarantee_case",
        ),
    )
    op.alter_column("external_loan_mirrors", "version", server_default=None)
    op.create_index(
        "ix_external_loan_provider",
        "external_loan_mirrors",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_external_loan_state",
        "external_loan_mirrors",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_external_loan_last_provider_event",
        "external_loan_mirrors",
        ["last_provider_event_at"],
        unique=False,
    )

    op.create_table(
        "external_loan_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_loan_mirror_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_event_id", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("principal_delta", sa.Numeric(38, 18), nullable=True),
        sa.Column("outstanding_principal_reported", sa.Numeric(38, 18), nullable=True),
        sa.Column("provider_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("processed_status", sa.String(length=40), nullable=False),
        sa.Column("provider_contract_version", sa.String(length=80), nullable=False),
        sa.Column("adapter_mapping_version", sa.String(length=80), nullable=False),
        sa.Column("inbound_normalization_version", sa.String(length=80), nullable=False),
        sa.Column("provider_event_sequence", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'LOAN_APPROVED','LOAN_DISBURSED','REPAYMENT_RECEIVED',"
            "'LOAN_DELINQUENT','LOAN_SETTLED','LOAN_CORRECTED'"
            ")",
            name="ck_external_loan_event_type",
        ),
        sa.CheckConstraint(
            "outstanding_principal_reported IS NULL OR outstanding_principal_reported >= 0",
            name="ck_external_loan_event_outstanding_nonnegative",
        ),
        sa.CheckConstraint(
            "provider_event_sequence IS NULL OR provider_event_sequence >= 0",
            name="ck_external_loan_event_sequence_nonnegative",
        ),
        sa.CheckConstraint(
            "processed_status IN ('APPLIED','STALE','HISTORY_ONLY','CORRECTED')",
            name="ck_external_loan_event_processed_status",
        ),
        sa.ForeignKeyConstraint(
            ["external_loan_mirror_id"],
            ["external_loan_mirrors.id"],
            name="fk_external_loan_event_mirror",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_loan_mirror_id",
            "provider_event_id",
            name="uq_external_loan_event_provider_event",
        ),
    )
    op.create_index(
        "ix_external_loan_events_mirror_time",
        "external_loan_events",
        ["external_loan_mirror_id", "provider_event_at"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_guarantee_case_external_loan_mirror",
        "guarantee_cases",
        "external_loan_mirrors",
        ["external_loan_mirror_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_external_loan_event_mutation()
        RETURNS trigger AS $external_loan_event$
        BEGIN
            RAISE EXCEPTION 'external_loan_events are append-only';
        END;
        $external_loan_event$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_external_loan_events_append_only
        BEFORE UPDATE OR DELETE ON external_loan_events
        FOR EACH ROW EXECUTE FUNCTION badban_reject_external_loan_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_external_loan_events_append_only ON external_loan_events"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_external_loan_event_mutation")
    op.drop_constraint(
        "fk_guarantee_case_external_loan_mirror",
        "guarantee_cases",
        type_="foreignkey",
    )
    op.drop_index("ix_external_loan_events_mirror_time", table_name="external_loan_events")
    op.drop_table("external_loan_events")
    op.drop_index("ix_external_loan_last_provider_event", table_name="external_loan_mirrors")
    op.drop_index("ix_external_loan_state", table_name="external_loan_mirrors")
    op.drop_index("ix_external_loan_provider", table_name="external_loan_mirrors")
    op.drop_table("external_loan_mirrors")
