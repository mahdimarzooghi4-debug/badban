"""Sprint 08 journal lineage completion.

Revision ID: 20261007_0009
Revises: 20261006_0008
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0009"
down_revision: str | None = "20261006_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column("policy_version_reference", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "journal_entries",
        sa.Column("posting_template_code", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "journal_entries",
        sa.Column("posting_template_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "journal_entries",
        sa.Column("account_mapping_reference", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "journal_entries",
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("journal_entries", "evidence_reference")
    op.drop_column("journal_entries", "account_mapping_reference")
    op.drop_column("journal_entries", "posting_template_version")
    op.drop_column("journal_entries", "posting_template_code")
    op.drop_column("journal_entries", "policy_version_reference")
