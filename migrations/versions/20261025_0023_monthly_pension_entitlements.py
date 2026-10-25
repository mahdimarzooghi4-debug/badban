"""Sprint 42 monthly pension entitlement lifecycle.

Revision ID: 20261025_0023
Revises: 20261025_0022
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261025_0023"
down_revision: str | None = "20261025_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monthly_pension_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_catalogue_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_reference", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(38, 18), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("policy_version_reference", sa.String(length=200), nullable=False),
        sa.Column("calculation_reference", sa.String(length=500), nullable=False),
        sa.Column("eligibility_evidence_reference", sa.String(length=500), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_monthly_pension_amount_positive"),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','APPROVED','CANCELLED')", name="ck_monthly_pension_status"
        ),
        sa.CheckConstraint(
            "approved_by IS NULL OR approved_by <> created_by",
            name="ck_monthly_pension_maker_checker",
        ),
        sa.ForeignKeyConstraint(
            ["service_catalogue_version_id"], ["service_catalogue_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "participant_id", "period_reference", name="uq_monthly_pension_participant_period"
        ),
    )
    op.create_index(
        "ix_monthly_pension_participant_status",
        "monthly_pension_entitlements",
        ["participant_id", "lifecycle_status"],
    )

    op.create_table(
        "monthly_pension_funding_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_journal_posting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(38, 18), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_monthly_pension_allocation_amount_positive"),
        sa.ForeignKeyConstraint(
            ["entitlement_id"], ["monthly_pension_entitlements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_journal_posting_id"], ["journal_postings.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entitlement_id",
            "source_journal_posting_id",
            name="uq_monthly_pension_entitlement_source",
        ),
    )
    op.create_index(
        "ix_monthly_pension_funding_source",
        "monthly_pension_funding_allocations",
        ["source_journal_posting_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monthly_pension_funding_source", table_name="monthly_pension_funding_allocations"
    )
    op.drop_table("monthly_pension_funding_allocations")
    op.drop_index(
        "ix_monthly_pension_participant_status", table_name="monthly_pension_entitlements"
    )
    op.drop_table("monthly_pension_entitlements")
