"""Sprint 16 reconciliation blocks and resolution workflow.

Revision ID: 20261008_0016
Revises: 20261008_0015
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261008_0016"
down_revision: str | None = "20261008_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_RESOLUTION_TYPES = (
    "'INTERNAL_CORRECTION','EXTERNAL_CORRECTION','LATE_EVENT_APPLIED',"
    "'MAPPING_CORRECTION','ACCEPTED_DIFFERENCE','DISPUTE_OUTCOME'"
)


def upgrade() -> None:
    op.add_column(
        "reconciliation_runs",
        sa.Column("scope_reference", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "reconciliation_cases",
        sa.Column("resolution_type", sa.String(length=80), nullable=True),
    )
    op.create_check_constraint(
        "ck_reconciliation_case_resolution_type",
        "reconciliation_cases",
        f"resolution_type IS NULL OR resolution_type IN ({_RESOLUTION_TYPES})",
    )

    op.create_table(
        "reconciliation_resolution_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_case_version", sa.Integer(), nullable=False),
        sa.Column("resolution_type", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "correction_command_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("proposed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
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
            f"resolution_type IN ({_RESOLUTION_TYPES})",
            name="ck_reconciliation_resolution_type",
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED','APPROVED','REJECTED','APPLIED')",
            name="ck_reconciliation_resolution_status",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_case_id"],
            ["reconciliation_cases.id"],
            name="fk_reconciliation_resolution_case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approval_request_id"],
            ["approval_requests.id"],
            name="fk_reconciliation_resolution_approval",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reconciliation_resolution_case_status",
        "reconciliation_resolution_proposals",
        ["reconciliation_case_id", "status"],
        unique=False,
    )

    op.create_table(
        "reconciliation_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blocked_command_type", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=False),
        sa.Column("resource_id", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_number", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_case_id"],
            ["reconciliation_cases.id"],
            name="fk_reconciliation_block_case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_versions.id"],
            name="fk_reconciliation_block_policy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_case_id",
            "blocked_command_type",
            "resource_type",
            "resource_id",
            name="uq_reconciliation_block_case_command_resource",
        ),
    )
    op.create_index(
        "ix_reconciliation_blocks_active_command",
        "reconciliation_blocks",
        ["active", "blocked_command_type"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_blocks_resource",
        "reconciliation_blocks",
        ["resource_type", "resource_id", "active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reconciliation_blocks_resource", table_name="reconciliation_blocks")
    op.drop_index(
        "ix_reconciliation_blocks_active_command",
        table_name="reconciliation_blocks",
    )
    op.drop_table("reconciliation_blocks")
    op.drop_index(
        "ix_reconciliation_resolution_case_status",
        table_name="reconciliation_resolution_proposals",
    )
    op.drop_table("reconciliation_resolution_proposals")
    op.drop_constraint(
        "ck_reconciliation_case_resolution_type",
        "reconciliation_cases",
        type_="check",
    )
    op.drop_column("reconciliation_cases", "resolution_type")
    op.drop_column("reconciliation_runs", "scope_reference")
