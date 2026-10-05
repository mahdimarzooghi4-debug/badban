"""Sprint 03 control, valuation, and journal foundations.

Revision ID: 20261005_0003
Revises: 20261005_0002
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261005_0003"
down_revision: str | None = "20261005_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=160), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False),
        sa.Column("target_id", sa.String(length=160), nullable=False),
        sa.Column("target_aggregate_version", sa.Integer(), nullable=True),
        sa.Column("maker_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checker_identity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("required_checker_role", sa.String(length=80), nullable=False),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            "checker_identity_id IS NULL OR checker_identity_id <> maker_identity_id",
            name="ck_approval_request_distinct_checker",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','CANCELLED','EXPIRED')",
            name="ck_approval_request_status",
        ),
        sa.ForeignKeyConstraint(["maker_identity_id"], ["identities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["checker_identity_id"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_requests_status_expires",
        "approval_requests",
        ["status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_scope",
        "approval_requests",
        ["scope_type", "scope_id"],
        unique=False,
    )

    op.create_table(
        "valuation_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_position_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valued_quantity", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("valuation_currency", sa.String(length=16), nullable=False),
        sa.Column("fx_rate", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("gross_market_value", sa.Numeric(precision=114, scale=54), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("source_version_reference", sa.String(length=255), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness_status", sa.String(length=40), nullable=False),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "valued_quantity >= 0",
            name="ck_valuation_quantity_nonnegative",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_valuation_unit_price_nonnegative",
        ),
        sa.CheckConstraint(
            "fx_rate IS NULL OR fx_rate > 0",
            name="ck_valuation_fx_positive",
        ),
        sa.CheckConstraint(
            "gross_market_value >= 0",
            name="ck_valuation_gross_nonnegative",
        ),
        sa.ForeignKeyConstraint(["asset_position_id"], ["asset_positions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_valuation_observations_position_observed",
        "valuation_observations",
        ["asset_position_id", "observed_at"],
        unique=False,
    )

    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_event_type", sa.String(length=120), nullable=False),
        sa.Column("business_event_id", sa.String(length=160), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_of_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_reference", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('PREPARED','POSTED')",
            name="ck_journal_entry_state",
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_journal_entry_idempotency_key",
        ),
        sa.UniqueConstraint(
            "reversal_of_entry_id",
            name="uq_journal_entry_reversal",
        ),
    )
    op.create_index(
        "ix_journal_entries_business_event",
        "journal_entries",
        ["business_event_type", "business_event_id"],
        unique=False,
    )
    op.create_index(
        "ix_journal_entries_posted_at",
        "journal_entries",
        ["posted_at"],
        unique=False,
    )

    op.create_table(
        "journal_postings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(length=80), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("economic_owner_type", sa.String(length=80), nullable=False),
        sa.Column("economic_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("guarantee_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reserve_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("debit_amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("credit_amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "debit_amount >= 0",
            name="ck_journal_posting_debit_nonnegative",
        ),
        sa.CheckConstraint(
            "credit_amount >= 0",
            name="ck_journal_posting_credit_nonnegative",
        ),
        sa.CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="ck_journal_posting_one_sided_positive",
        ),
        sa.ForeignKeyConstraint(["asset_position_id"], ["asset_positions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_journal_postings_entry",
        "journal_postings",
        ["journal_entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_journal_postings_account_currency",
        "journal_postings",
        ["account_code", "currency"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_valuation_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'valuation_observations are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_valuation_observations_append_only
        BEFORE UPDATE OR DELETE ON valuation_observations
        FOR EACH ROW EXECUTE FUNCTION badban_reject_valuation_mutation()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_posted_journal_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.state = 'POSTED' THEN
                RAISE EXCEPTION 'posted journal_entries are append-only';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_posted_append_only
        BEFORE UPDATE OR DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION badban_reject_posted_journal_mutation()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_journal_posting_mutation()
        RETURNS trigger AS $
        DECLARE
            parent_state text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT state INTO parent_state
                FROM journal_entries
                WHERE id = NEW.journal_entry_id;
                IF parent_state = 'POSTED' THEN
                    RAISE EXCEPTION 'cannot add posting to a POSTED journal';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'journal_postings are append-only';
        END;
        $ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_postings_append_only
        BEFORE INSERT OR UPDATE OR DELETE ON journal_postings
        FOR EACH ROW EXECUTE FUNCTION badban_reject_journal_posting_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_journal_postings_append_only ON journal_postings")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_journal_posting_mutation")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_posted_append_only ON journal_entries")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_posted_journal_mutation")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_valuation_observations_append_only ON valuation_observations"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_valuation_mutation")
    op.drop_index(
        "ix_journal_postings_account_currency",
        table_name="journal_postings",
    )
    op.drop_index("ix_journal_postings_entry", table_name="journal_postings")
    op.drop_table("journal_postings")
    op.drop_index("ix_journal_entries_posted_at", table_name="journal_entries")
    op.drop_index("ix_journal_entries_business_event", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_index(
        "ix_valuation_observations_position_observed",
        table_name="valuation_observations",
    )
    op.drop_table("valuation_observations")
    op.drop_index("ix_approval_requests_scope", table_name="approval_requests")
    op.drop_index(
        "ix_approval_requests_status_expires",
        table_name="approval_requests",
    )
    op.drop_table("approval_requests")
