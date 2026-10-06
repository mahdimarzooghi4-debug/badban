"""Sprint 04 policy version persistence foundation.

Revision ID: 20261006_0004
Revises: 20261005_0003
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261006_0004"
down_revision: str | None = "20261005_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_type", sa.String(length=80), nullable=False),
        sa.Column("policy_code", sa.String(length=120), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column(
            "scope_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            "policy_type IN "
            "('ASSET_TYPE_POLICY','OWNERSHIP_FUNDING_POLICY',"
            "'PROVIDER_PRODUCT_POLICY','RISK_APPETITE_POLICY',"
            "'RETURN_ALLOCATION_POLICY','LEGAL_AUTHORIZATION_POLICY',"
            "'POSTING_ACCOUNTING_MAPPING_POLICY','PILOT_POLICY_PACK')",
            name="ck_policy_version_type",
        ),
        sa.CheckConstraint(
            "version_number > 0",
            name="ck_policy_version_number_positive",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN "
            "('DRAFT','REVIEWED','APPROVED','ACTIVE','SUPERSEDED','RETIRED')",
            name="ck_policy_version_lifecycle_status",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL "
            "OR effective_to > effective_from",
            name="ck_policy_version_effective_window",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_type",
            "policy_code",
            "version_number",
            name="uq_policy_version_identity",
        ),
    )
    op.create_index(
        "ix_policy_versions_lookup",
        "policy_versions",
        [
            "policy_type",
            "policy_code",
            "lifecycle_status",
            "effective_from",
            "effective_to",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_policy_versions_lookup", table_name="policy_versions")
    op.drop_table("policy_versions")
