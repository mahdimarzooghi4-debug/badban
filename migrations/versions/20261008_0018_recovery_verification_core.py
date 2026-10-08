"""Sprint 18 recovery verification core.

Revision ID: 20261008_0018
Revises: 20261008_0017
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261008_0018"
down_revision: str | None = "20261008_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recovery_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restore_reference", sa.String(length=255), nullable=False),
        sa.Column("source_backup_reference", sa.String(length=500), nullable=True),
        sa.Column("source_integrity_reference", sa.String(length=500), nullable=True),
        sa.Column("environment_reference", sa.String(length=120), nullable=False),
        sa.Column("verification_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("check_count", sa.Integer(), nullable=False),
        sa.Column("failed_check_count", sa.Integer(), nullable=False),
        sa.Column("not_verified_check_count", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('PASSED','FAILED')",
            name="ck_recovery_verification_status",
        ),
        sa.CheckConstraint(
            "check_count >= 0 AND failed_check_count >= 0 AND not_verified_check_count >= 0",
            name="ck_recovery_verification_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["identities.id"],
            name="fk_recovery_verification_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recovery_verifications_restore",
        "recovery_verifications",
        ["restore_reference", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_recovery_verifications_status",
        "recovery_verifications",
        ["status", "completed_at"],
        unique=False,
    )

    op.create_table(
        "recovery_verification_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "recovery_verification_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("check_code", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('PASS','FAIL','NOT_VERIFIED')",
            name="ck_recovery_verification_check_status",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_verification_id"],
            ["recovery_verifications.id"],
            name="fk_recovery_verification_check_parent",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recovery_verification_id",
            "check_code",
            name="uq_recovery_verification_check_code",
        ),
    )
    op.create_index(
        "ix_recovery_verification_checks_verification",
        "recovery_verification_checks",
        ["recovery_verification_id", "status"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_recovery_verification_mutation()
        RETURNS trigger AS $recovery$
        BEGIN
            RAISE EXCEPTION 'recovery verification evidence is append-only';
        END;
        $recovery$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_recovery_verifications_append_only
        BEFORE UPDATE OR DELETE ON recovery_verifications
        FOR EACH ROW EXECUTE FUNCTION badban_reject_recovery_verification_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_recovery_verification_checks_append_only
        BEFORE UPDATE OR DELETE ON recovery_verification_checks
        FOR EACH ROW EXECUTE FUNCTION badban_reject_recovery_verification_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_recovery_verification_checks_append_only "
        "ON recovery_verification_checks"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_recovery_verifications_append_only ON recovery_verifications"
    )
    op.execute("DROP FUNCTION IF EXISTS badban_reject_recovery_verification_mutation")
    op.drop_index(
        "ix_recovery_verification_checks_verification",
        table_name="recovery_verification_checks",
    )
    op.drop_table("recovery_verification_checks")
    op.drop_index(
        "ix_recovery_verifications_status",
        table_name="recovery_verifications",
    )
    op.drop_index(
        "ix_recovery_verifications_restore",
        table_name="recovery_verifications",
    )
    op.drop_table("recovery_verifications")
