"""Sprint 11 transactional outbox/inbox hardening.

Revision ID: 20261007_0012
Revises: 20261007_0011
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0012"
down_revision: str | None = "20261007_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outbox_messages", sa.Column("last_error", sa.String(length=1000), nullable=True))
    op.add_column(
        "outbox_messages",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_messages",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_messages",
        sa.Column("dead_letter_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "outbox_messages",
        sa.Column(
            "replay_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.alter_column("outbox_messages", "replay_count", server_default=None)

    op.create_check_constraint(
        "ck_outbox_publish_attempts_nonnegative",
        "outbox_messages",
        "publish_attempts >= 0",
    )
    op.create_check_constraint(
        "ck_outbox_replay_count_nonnegative",
        "outbox_messages",
        "replay_count >= 0",
    )
    op.create_check_constraint(
        "ck_outbox_not_published_and_dead_lettered",
        "outbox_messages",
        "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
    )
    op.create_index(
        "ix_outbox_delivery_due",
        "outbox_messages",
        ["published_at", "dead_lettered_at", "next_attempt_at", "created_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_protect_outbox_event_facts()
        RETURNS trigger AS $outbox$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'outbox event facts are append-only';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.event_type IS DISTINCT FROM OLD.event_type
                OR NEW.event_version IS DISTINCT FROM OLD.event_version
                OR NEW.aggregate_type IS DISTINCT FROM OLD.aggregate_type
                OR NEW.aggregate_id IS DISTINCT FROM OLD.aggregate_id
                OR NEW.aggregate_version IS DISTINCT FROM OLD.aggregate_version
                OR NEW.payload IS DISTINCT FROM OLD.payload
                OR NEW.correlation_id IS DISTINCT FROM OLD.correlation_id
                OR NEW.causation_id IS DISTINCT FROM OLD.causation_id
                OR NEW.occurred_at IS DISTINCT FROM OLD.occurred_at
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
            THEN
                RAISE EXCEPTION 'outbox event facts are immutable';
            END IF;
            RETURN NEW;
        END;
        $outbox$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_outbox_event_facts_immutable
        BEFORE UPDATE OR DELETE ON outbox_messages
        FOR EACH ROW EXECUTE FUNCTION badban_protect_outbox_event_facts()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_protect_inbox_event_facts()
        RETURNS trigger AS $inbox$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'inbox event facts are append-only';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.source_id IS DISTINCT FROM OLD.source_id
                OR NEW.event_type IS DISTINCT FROM OLD.event_type
                OR NEW.external_event_id IS DISTINCT FROM OLD.external_event_id
                OR NEW.payload_hash IS DISTINCT FROM OLD.payload_hash
                OR NEW.payload IS DISTINCT FROM OLD.payload
                OR NEW.received_at IS DISTINCT FROM OLD.received_at
            THEN
                RAISE EXCEPTION 'inbox event facts are immutable';
            END IF;
            RETURN NEW;
        END;
        $inbox$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_inbox_event_facts_immutable
        BEFORE UPDATE OR DELETE ON inbox_messages
        FOR EACH ROW EXECUTE FUNCTION badban_protect_inbox_event_facts()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_inbox_event_facts_immutable ON inbox_messages")
    op.execute("DROP FUNCTION IF EXISTS badban_protect_inbox_event_facts")
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_event_facts_immutable ON outbox_messages")
    op.execute("DROP FUNCTION IF EXISTS badban_protect_outbox_event_facts")

    op.drop_index("ix_outbox_delivery_due", table_name="outbox_messages")
    op.drop_constraint(
        "ck_outbox_not_published_and_dead_lettered",
        "outbox_messages",
        type_="check",
    )
    op.drop_constraint(
        "ck_outbox_replay_count_nonnegative",
        "outbox_messages",
        type_="check",
    )
    op.drop_constraint(
        "ck_outbox_publish_attempts_nonnegative",
        "outbox_messages",
        type_="check",
    )

    op.drop_column("outbox_messages", "replay_count")
    op.drop_column("outbox_messages", "dead_letter_reason")
    op.drop_column("outbox_messages", "dead_lettered_at")
    op.drop_column("outbox_messages", "next_attempt_at")
    op.drop_column("outbox_messages", "last_error")
