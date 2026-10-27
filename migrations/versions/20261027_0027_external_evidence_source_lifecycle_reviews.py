"""Sprint 55 maker-checker lifecycle reviews for external evidence sources.

Revision ID: 20261027_0027
Revises: 20261025_0026
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261027_0027"
down_revision: str | None = "20261025_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_evidence_source_lifecycle_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_action", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="REQUESTED",
        ),
        sa.Column("reason_reference", sa.String(length=255), nullable=False),
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
            "requested_action IN ('ACTIVATE','SUSPEND')",
            name="ck_external_evidence_source_review_action",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED','APPROVED','REJECTED')",
            name="ck_external_evidence_source_review_status",
        ),
        sa.CheckConstraint(
            "(status = 'REQUESTED' AND reviewed_by IS NULL AND reviewed_at IS NULL "
            "AND review_reason_reference IS NULL) OR "
            "(status IN ('APPROVED','REJECTED') AND reviewed_by IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND review_reason_reference IS NOT NULL)",
            name="ck_external_evidence_source_review_state",
        ),
        sa.CheckConstraint(
            "reviewed_by IS NULL OR reviewed_by <> requested_by",
            name="ck_external_evidence_source_review_maker_checker",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["external_evidence_sources.id"],
            ondelete="RESTRICT",
            name="fk_external_evidence_source_lifecycle_source",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_external_evidence_source_review_pending",
        "external_evidence_source_lifecycle_reviews",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("status = 'REQUESTED'"),
    )
    op.create_index(
        "ix_external_evidence_source_review_status_created",
        "external_evidence_source_lifecycle_reviews",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_evidence_source_review_status_created",
        table_name="external_evidence_source_lifecycle_reviews",
    )
    op.drop_index(
        "uq_external_evidence_source_review_pending",
        table_name="external_evidence_source_lifecycle_reviews",
    )
    op.drop_table("external_evidence_source_lifecycle_reviews")
