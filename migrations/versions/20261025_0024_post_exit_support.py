"""Sprint 43 post-exit support lifecycle.

Revision ID: 20261025_0024
Revises: 20261025_0023
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261025_0024"
down_revision: str | None = "20261025_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "post_exit_support_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_catalogue_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exit_event_reference", sa.String(length=255), nullable=False),
        sa.Column("exit_evidence_reference", sa.String(length=500), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("support_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("policy_version_reference", sa.String(length=200), nullable=False),
        sa.Column("eligibility_decision_reference", sa.String(length=500), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "duration_months > 0 AND duration_months <= 36", name="ck_post_exit_duration_months"
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','ACTIVE','SUSPENDED','COMPLETED','CANCELLED')",
            name="ck_post_exit_case_status",
        ),
        sa.CheckConstraint(
            "activated_by IS NULL OR activated_by <> created_by",
            name="ck_post_exit_case_maker_checker",
        ),
        sa.ForeignKeyConstraint(
            ["service_catalogue_version_id"], ["service_catalogue_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["activated_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "participant_id", "exit_event_reference", name="uq_post_exit_participant_exit_event"
        ),
    )
    op.create_index(
        "ix_post_exit_case_participant_status",
        "post_exit_support_cases",
        ["participant_id", "lifecycle_status"],
    )

    op.create_table(
        "post_exit_support_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("support_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_sequence", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "period_sequence > 0 AND period_sequence <= 36", name="ck_post_exit_period_sequence"
        ),
        sa.CheckConstraint("amount > 0", name="ck_post_exit_entitlement_amount_positive"),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','APPROVED','CANCELLED')",
            name="ck_post_exit_entitlement_status",
        ),
        sa.CheckConstraint(
            "approved_by IS NULL OR approved_by <> created_by",
            name="ck_post_exit_entitlement_maker_checker",
        ),
        sa.ForeignKeyConstraint(
            ["support_case_id"], ["post_exit_support_cases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "support_case_id", "period_sequence", name="uq_post_exit_case_period_sequence"
        ),
    )
    op.create_index(
        "ix_post_exit_entitlement_case_status",
        "post_exit_support_entitlements",
        ["support_case_id", "lifecycle_status"],
    )

    op.create_table(
        "post_exit_support_funding_allocations",
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
        sa.CheckConstraint("amount > 0", name="ck_post_exit_allocation_amount_positive"),
        sa.ForeignKeyConstraint(
            ["entitlement_id"], ["post_exit_support_entitlements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_journal_posting_id"], ["journal_postings.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entitlement_id", "source_journal_posting_id", name="uq_post_exit_entitlement_source"
        ),
    )
    op.create_index(
        "ix_post_exit_funding_source",
        "post_exit_support_funding_allocations",
        ["source_journal_posting_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_post_exit_funding_source", table_name="post_exit_support_funding_allocations")
    op.drop_table("post_exit_support_funding_allocations")
    op.drop_index(
        "ix_post_exit_entitlement_case_status", table_name="post_exit_support_entitlements"
    )
    op.drop_table("post_exit_support_entitlements")
    op.drop_index("ix_post_exit_case_participant_status", table_name="post_exit_support_cases")
    op.drop_table("post_exit_support_cases")
