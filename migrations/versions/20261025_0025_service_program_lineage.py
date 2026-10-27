"""Sprint 52 adds explicit program and participation-episode lineage to benefits.

Revision ID: 20261025_0025
Revises: 20261025_0024
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261025_0025"
down_revision: str | None = "20261025_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_participation_episode_identity_program",
        "participation_episodes",
        ["id", "participant_id", "program_id"],
    )

    op.drop_constraint(
        "uq_monthly_pension_participant_period",
        "monthly_pension_entitlements",
        type_="unique",
    )
    op.add_column(
        "monthly_pension_entitlements",
        sa.Column("participation_episode_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "monthly_pension_entitlements",
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_monthly_pension_program_episode_pair",
        "monthly_pension_entitlements",
        "(participation_episode_id IS NULL AND program_id IS NULL) OR "
        "(participation_episode_id IS NOT NULL AND program_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_monthly_pension_episode_program",
        "monthly_pension_entitlements",
        "participation_episodes",
        ["participation_episode_id", "participant_id", "program_id"],
        ["id", "participant_id", "program_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_monthly_pension_episode_period",
        "monthly_pension_entitlements",
        ["participation_episode_id", "period_reference"],
    )
    op.create_index(
        "ix_monthly_pension_program_episode_status",
        "monthly_pension_entitlements",
        ["program_id", "participation_episode_id", "lifecycle_status"],
    )

    op.drop_constraint(
        "uq_post_exit_participant_exit_event",
        "post_exit_support_cases",
        type_="unique",
    )
    op.add_column(
        "post_exit_support_cases",
        sa.Column("participation_episode_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "post_exit_support_cases",
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_post_exit_program_episode_pair",
        "post_exit_support_cases",
        "(participation_episode_id IS NULL AND program_id IS NULL) OR "
        "(participation_episode_id IS NOT NULL AND program_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_post_exit_episode_program",
        "post_exit_support_cases",
        "participation_episodes",
        ["participation_episode_id", "participant_id", "program_id"],
        ["id", "participant_id", "program_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_post_exit_episode_exit_event",
        "post_exit_support_cases",
        ["participation_episode_id", "exit_event_reference"],
    )
    op.create_index(
        "ix_post_exit_case_program_episode_status",
        "post_exit_support_cases",
        ["program_id", "participation_episode_id", "lifecycle_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_post_exit_case_program_episode_status",
        table_name="post_exit_support_cases",
    )
    op.drop_constraint(
        "uq_post_exit_episode_exit_event",
        "post_exit_support_cases",
        type_="unique",
    )
    op.drop_constraint(
        "fk_post_exit_episode_program",
        "post_exit_support_cases",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_post_exit_program_episode_pair",
        "post_exit_support_cases",
        type_="check",
    )
    op.drop_column("post_exit_support_cases", "program_id")
    op.drop_column("post_exit_support_cases", "participation_episode_id")
    op.create_unique_constraint(
        "uq_post_exit_participant_exit_event",
        "post_exit_support_cases",
        ["participant_id", "exit_event_reference"],
    )

    op.drop_index(
        "ix_monthly_pension_program_episode_status",
        table_name="monthly_pension_entitlements",
    )
    op.drop_constraint(
        "uq_monthly_pension_episode_period",
        "monthly_pension_entitlements",
        type_="unique",
    )
    op.drop_constraint(
        "fk_monthly_pension_episode_program",
        "monthly_pension_entitlements",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_monthly_pension_program_episode_pair",
        "monthly_pension_entitlements",
        type_="check",
    )
    op.drop_column("monthly_pension_entitlements", "program_id")
    op.drop_column("monthly_pension_entitlements", "participation_episode_id")
    op.create_unique_constraint(
        "uq_monthly_pension_participant_period",
        "monthly_pension_entitlements",
        ["participant_id", "period_reference"],
    )
    op.drop_constraint(
        "uq_participation_episode_identity_program",
        "participation_episodes",
        type_="unique",
    )
