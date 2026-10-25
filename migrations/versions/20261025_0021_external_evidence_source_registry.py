"""Sprint 40 external evidence source registry.

Revision ID: 20261025_0021
Revises: 20261009_0020
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261025_0021"
down_revision: str | None = "20261009_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_evidence_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_purpose", sa.String(length=40), nullable=False),
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("adapter_key", sa.String(length=100), nullable=False),
        sa.Column("contract_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("configuration_reference", sa.String(length=255), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "evidence_purpose IN ('VALUATION','RESTRICTION','ENCUMBRANCE')",
            name="ck_external_evidence_source_purpose",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','ACTIVE','SUSPENDED')",
            name="ck_external_evidence_source_status",
        ),
        sa.ForeignKeyConstraint(["asset_type_id"], ["asset_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_type_id",
            "evidence_purpose",
            "source_key",
            "version",
            name="uq_external_evidence_source_version",
        ),
    )
    op.create_index(
        "ix_external_evidence_sources_lookup",
        "external_evidence_sources",
        ["asset_type_id", "evidence_purpose", "lifecycle_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_evidence_sources_lookup",
        table_name="external_evidence_sources",
    )
    op.drop_table("external_evidence_sources")
