"""Sprint 07 GuaranteeCase REQUESTED foundation.

Revision ID: 20261006_0008
Revises: 20261006_0007
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261006_0008"
down_revision: str | None = "20261006_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guarantee_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participation_episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credit_product_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_pack_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("requested_principal", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column(
            "reserved_guarantee_amount",
            sa.Numeric(precision=38, scale=18),
            nullable=True,
        ),
        sa.Column(
            "issued_guarantee_amount",
            sa.Numeric(precision=38, scale=18),
            nullable=True,
        ),
        sa.Column(
            "current_guarantee_exposure",
            sa.Numeric(precision=38, scale=18),
            nullable=False,
        ),
        sa.Column("guarantee_mode", sa.String(length=40), nullable=False),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_guarantee_external_id", sa.String(length=255), nullable=True),
        sa.Column("legal_guarantee_issuer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_loan_mirror_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("risk_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ("
            "'REQUESTED','RESERVED','ISSUED','ACTIVE','DELINQUENT','CLAIM_PENDING',"
            "'CLAIM_APPROVED','CLAIM_REJECTED','ENFORCEMENT','SETTLEMENT','RELEASED',"
            "'CLOSED','CANCELLED','EXPIRED'"
            ")",
            name="ck_guarantee_case_state",
        ),
        sa.CheckConstraint(
            "requested_principal > 0",
            name="ck_guarantee_case_requested_principal_positive",
        ),
        sa.CheckConstraint(
            "reserved_guarantee_amount IS NULL OR reserved_guarantee_amount >= 0",
            name="ck_guarantee_case_reserved_nonnegative",
        ),
        sa.CheckConstraint(
            "issued_guarantee_amount IS NULL OR issued_guarantee_amount >= 0",
            name="ck_guarantee_case_issued_nonnegative",
        ),
        sa.CheckConstraint(
            "current_guarantee_exposure >= 0",
            name="ck_guarantee_case_exposure_nonnegative",
        ),
        sa.CheckConstraint(
            "issued_guarantee_amount IS NULL OR reserved_guarantee_amount IS NULL "
            "OR issued_guarantee_amount <= reserved_guarantee_amount",
            name="ck_guarantee_case_issued_not_above_reserved",
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR state IN ('CLOSED','CANCELLED','EXPIRED')",
            name="ck_guarantee_case_closed_terminal",
        ),
        sa.ForeignKeyConstraint(
            ["participation_episode_id"],
            ["participation_episodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["credit_providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["credit_product_version_id"],
            ["credit_product_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["policy_pack_id"], ["policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["legal_guarantee_issuer_id"],
            ["legal_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "legal_guarantee_issuer_id",
            "legal_guarantee_external_id",
            name="uq_guarantee_case_issuer_external_id",
        ),
    )
    op.create_index(
        "ix_guarantee_cases_episode",
        "guarantee_cases",
        ["participation_episode_id"],
        unique=False,
    )
    op.create_index(
        "ix_guarantee_cases_provider",
        "guarantee_cases",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_guarantee_cases_state",
        "guarantee_cases",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_guarantee_cases_reservation_expiry",
        "guarantee_cases",
        ["reservation_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_guarantee_cases_legal_external_id",
        "guarantee_cases",
        ["legal_guarantee_external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_guarantee_cases_legal_external_id", table_name="guarantee_cases")
    op.drop_index("ix_guarantee_cases_reservation_expiry", table_name="guarantee_cases")
    op.drop_index("ix_guarantee_cases_state", table_name="guarantee_cases")
    op.drop_index("ix_guarantee_cases_provider", table_name="guarantee_cases")
    op.drop_index("ix_guarantee_cases_episode", table_name="guarantee_cases")
    op.drop_table("guarantee_cases")
