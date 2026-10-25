"""Sprint 41 versioned service catalogue.

Revision ID: 20261025_0022
Revises: 20261025_0021
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261025_0022"
down_revision: str | None = "20261025_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_catalogue_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_code", sa.String(length=40), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("policy_version_reference", sa.String(length=200), nullable=False),
        sa.Column("policy_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_duration_months", sa.Integer(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False, server_default="DRAFT"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "service_code IN ('LOAN_GUARANTEE','MONTHLY_PENSION','POST_EXIT_SUPPORT')",
            name="ck_service_catalogue_service_code",
        ),
        sa.CheckConstraint("version_number > 0", name="ck_service_catalogue_version_positive"),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','ACTIVE','SUSPENDED','RETIRED')",
            name="ck_service_catalogue_status",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_service_catalogue_effective_window",
        ),
        sa.CheckConstraint(
            "max_duration_months IS NULL OR "
            "(max_duration_months > 0 AND max_duration_months <= 36)",
            name="ck_service_catalogue_duration_bound",
        ),
        sa.CheckConstraint(
            "(service_code = 'POST_EXIT_SUPPORT' AND max_duration_months IS NOT NULL) OR "
            "(service_code <> 'POST_EXIT_SUPPORT' AND max_duration_months IS NULL)",
            name="ck_service_catalogue_duration_service",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_code",
            "version_number",
            name="uq_service_catalogue_code_version",
        ),
    )
    op.create_index(
        "ix_service_catalogue_visibility",
        "service_catalogue_versions",
        ["lifecycle_status", "effective_from", "effective_to"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_catalogue_visibility", table_name="service_catalogue_versions")
    op.drop_table("service_catalogue_versions")
