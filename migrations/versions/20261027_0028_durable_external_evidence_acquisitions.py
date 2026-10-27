"""Sprint 56 durable external evidence acquisition history.

Revision ID: 20261027_0028
Revises: 20261027_0027
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261027_0028"
down_revision: str | None = "20261027_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_evidence_acquisitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_position_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_purpose", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "evidence_purpose IN ('VALUATION','RESTRICTION','ENCUMBRANCE')",
            name="ck_external_evidence_acquisition_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED')",
            name="ck_external_evidence_acquisition_status",
        ),
        sa.CheckConstraint(
            "source_count >= 0",
            name="ck_external_evidence_acquisition_source_count",
        ),
        sa.CheckConstraint(
            "completed_at >= requested_at",
            name="ck_external_evidence_acquisition_time_order",
        ),
        sa.ForeignKeyConstraint(
            ["asset_position_id"],
            ["asset_positions.id"],
            ondelete="RESTRICT",
            name="fk_external_evidence_acquisition_position",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["identities.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_evidence_acquisitions_position_time",
        "external_evidence_acquisitions",
        ["asset_position_id", "requested_at"],
    )

    op.create_table(
        "external_evidence_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acquisition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("contract_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("source_value", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("restriction_state", sa.String(length=20), nullable=True),
        sa.Column("encumbrance_state", sa.String(length=20), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "acquisition_id",
            "source_id",
            name="uq_external_evidence_observation_acquisition_source",
        ),
        sa.CheckConstraint(
            "status IN ('VALID','UNAVAILABLE','INVALID')",
            name="ck_external_evidence_observation_status",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code IN "
            "('SOURCE_UNAVAILABLE','SOURCE_TIMEOUT','SOURCE_TRANSPORT_ERROR',"
            "'SOURCE_CONTRACT_INVALID')",
            name="ck_external_evidence_observation_error",
        ),
        sa.CheckConstraint(
            "(status = 'VALID' AND error_code IS NULL) OR "
            "(status IN ('UNAVAILABLE','INVALID') AND error_code IS NOT NULL)",
            name="ck_external_evidence_observation_status_error",
        ),
        sa.CheckConstraint(
            "source_value IS NULL OR source_value > 0",
            name="ck_external_evidence_observation_positive_value",
        ),
        sa.CheckConstraint(
            "restriction_state IS NULL OR restriction_state IN ('CLEAR','BLOCKED','UNKNOWN')",
            name="ck_external_evidence_observation_restriction",
        ),
        sa.CheckConstraint(
            "encumbrance_state IS NULL OR encumbrance_state IN ('CLEAR','BLOCKED','UNKNOWN')",
            name="ck_external_evidence_observation_encumbrance",
        ),
        sa.CheckConstraint(
            "received_at >= observed_at",
            name="ck_external_evidence_observation_time_order",
        ),
        sa.CheckConstraint(
            "status = 'VALID' OR "
            "(evidence_reference IS NULL AND source_value IS NULL AND currency IS NULL "
            "AND restriction_state IS NULL AND encumbrance_state IS NULL)",
            name="ck_external_evidence_observation_failure_has_no_facts",
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_id"],
            ["external_evidence_acquisitions.id"],
            ondelete="RESTRICT",
            name="fk_external_evidence_observation_acquisition",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["external_evidence_sources.id"],
            ondelete="RESTRICT",
            name="fk_external_evidence_observation_source",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_evidence_observations_source_time",
        "external_evidence_observations",
        ["source_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_evidence_observations_source_time",
        table_name="external_evidence_observations",
    )
    op.drop_table("external_evidence_observations")
    op.drop_index(
        "ix_external_evidence_acquisitions_position_time",
        table_name="external_evidence_acquisitions",
    )
    op.drop_table("external_evidence_acquisitions")
