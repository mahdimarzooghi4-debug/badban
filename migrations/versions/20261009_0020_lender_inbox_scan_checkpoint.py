"""Sprint 33 durable multi-replica lender inbox scan cursor.

Revision ID: 20261009_0020
Revises: 20261009_0019
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261009_0020"
down_revision: str | None = "20261009_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lender_inbox_scan_checkpoints",
        sa.Column("stream_key", sa.String(length=80), nullable=False),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "(last_received_at IS NULL) = (last_message_id IS NULL)",
            name="ck_lender_inbox_checkpoint_pair",
        ),
        sa.PrimaryKeyConstraint("stream_key"),
    )
    op.create_index(
        "ix_inbox_processing_scan",
        "inbox_messages",
        ["processed_at", "received_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_processing_scan", table_name="inbox_messages")
    op.drop_table("lender_inbox_scan_checkpoints")
