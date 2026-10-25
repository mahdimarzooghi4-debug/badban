"""Sprint 53 audited maker-checker review for legacy benefit lineage.

Revision ID: 20261025_0026
Revises: 20261025_0025
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261025_0026"
down_revision: str | None = "20261025_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legacy_benefit_lineage_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benefit_type", sa.String(length=40), nullable=False),
        sa.Column("benefit_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participation_episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=False),
        sa.Column("reason_reference", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="REQUESTED"),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "benefit_type IN ('MONTHLY_PENSION','POST_EXIT_SUPPORT')",
            name="ck_legacy_benefit_lineage_type",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED','APPROVED','REJECTED')",
            name="ck_legacy_benefit_lineage_status",
        ),
        sa.CheckConstraint(
            "(status = 'REQUESTED' AND reviewed_by IS NULL AND reviewed_at IS NULL) OR "
            "(status IN ('APPROVED','REJECTED') AND reviewed_by IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND review_reason_reference IS NOT NULL)",
            name="ck_legacy_benefit_lineage_review_state",
        ),
        sa.CheckConstraint(
            "reviewed_by IS NULL OR reviewed_by <> requested_by",
            name="ck_legacy_benefit_lineage_maker_checker",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"], ["participants.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["participation_episode_id", "participant_id", "program_id"],
            [
                "participation_episodes.id",
                "participation_episodes.participant_id",
                "participation_episodes.program_id",
            ],
            ondelete="RESTRICT",
            name="fk_legacy_benefit_lineage_episode_program",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["identities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["identities.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_legacy_benefit_lineage_pending_subject",
        "legacy_benefit_lineage_reviews",
        ["benefit_type", "benefit_record_id"],
        unique=True,
        postgresql_where=sa.text("status = 'REQUESTED'"),
    )
    op.create_index(
        "ix_legacy_benefit_lineage_status_created",
        "legacy_benefit_lineage_reviews",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legacy_benefit_lineage_status_created",
        table_name="legacy_benefit_lineage_reviews",
    )
    op.drop_index(
        "uq_legacy_benefit_lineage_pending_subject",
        table_name="legacy_benefit_lineage_reviews",
    )
    op.drop_table("legacy_benefit_lineage_reviews")
