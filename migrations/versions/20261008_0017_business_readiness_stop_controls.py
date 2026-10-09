"""Sprint 17 business readiness and stop controls.

Revision ID: 20261008_0017
Revises: 20261008_0016
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261008_0017"
down_revision: str | None = "20261008_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_stop_controls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("control_type", sa.String(length=100), nullable=False),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cleared_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
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
            "control_type IN ("
            "'STOP_NEW_GUARANTEE_RESERVATIONS','STOP_GUARANTEE_ACTIVATION',"
            "'SUSPEND_PROVIDER_FOR_NEW_ACTIONS','SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS',"
            "'STOP_CLAIM_SETTLEMENT','STOP_COLLATERAL_RELEASE'"
            ")",
            name="ck_operational_stop_control_type",
        ),
        sa.CheckConstraint(
            "scope_type IN ('GLOBAL','PROVIDER','ASSET_TYPE')",
            name="ck_operational_stop_control_scope_type",
        ),
        sa.CheckConstraint(
            "("
            "control_type IN ("
            "'STOP_NEW_GUARANTEE_RESERVATIONS','STOP_GUARANTEE_ACTIVATION',"
            "'STOP_CLAIM_SETTLEMENT','STOP_COLLATERAL_RELEASE'"
            ") AND scope_type = 'GLOBAL' AND scope_id IS NULL"
            ") OR ("
            "control_type = 'SUSPEND_PROVIDER_FOR_NEW_ACTIONS' "
            "AND scope_type = 'PROVIDER' AND scope_id IS NOT NULL"
            ") OR ("
            "control_type = 'SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS' "
            "AND scope_type = 'ASSET_TYPE' AND scope_id IS NOT NULL"
            ")",
            name="ck_operational_stop_control_scope_pair",
        ),
        sa.ForeignKeyConstraint(
            ["activated_by"],
            ["identities.id"],
            name="fk_operational_stop_control_activated_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cleared_by"],
            ["identities.id"],
            name="fk_operational_stop_control_cleared_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_stop_controls_active_scope",
        "operational_stop_controls",
        ["active", "control_type", "scope_type", "scope_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_stop_controls_active_scope",
        table_name="operational_stop_controls",
    )
    op.drop_table("operational_stop_controls")
