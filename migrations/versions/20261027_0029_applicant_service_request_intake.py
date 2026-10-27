"""Sprint 57 applicant service request intake.

Revision ID: 20261027_0029
Revises: 20261027_0028
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261027_0029"
down_revision: str | None = "20261027_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applicant_service_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_code", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "service_code IN ('LOAN_GUARANTEE','MONTHLY_PENSION','POST_EXIT_SUPPORT')",
            name="ck_applicant_service_request_service",
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED')",
            name="ck_applicant_service_request_status",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            ondelete="RESTRICT",
            name="fk_applicant_service_request_participant",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["identities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_applicant_service_requests_participant_time",
        "applicant_service_requests",
        ["participant_id", "submitted_at"],
    )
    op.create_index(
        "ix_applicant_service_requests_service_time",
        "applicant_service_requests",
        ["service_code", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_applicant_service_requests_service_time",
        table_name="applicant_service_requests",
    )
    op.drop_index(
        "ix_applicant_service_requests_participant_time",
        table_name="applicant_service_requests",
    )
    op.drop_table("applicant_service_requests")
