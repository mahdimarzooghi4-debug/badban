"""Generalize reconciliation target identity without changing published 0015."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0016"
down_revision = "20261007_0015"
branch_labels = None
depends_on = None

TARGET_CHECK = (
    "(reconciliation_type = 'LENDER' AND provider_id IS NOT NULL AND "
    "source_legal_entity_id IS NULL AND program_id IS NULL) OR "
    "(reconciliation_type IN ('GUARANTEE_ISSUER','CUSTODY','SETTLEMENT',"
    "'COLLATERAL_REGISTRY') AND provider_id IS NULL AND "
    "source_legal_entity_id IS NOT NULL AND program_id IS NULL) OR "
    "(reconciliation_type = 'LEDGER' AND provider_id IS NULL AND "
    "source_legal_entity_id IS NULL AND program_id IS NOT NULL)"
)


def upgrade() -> None:
    op.alter_column("reconciliation_runs", "provider_id", nullable=True)
    op.alter_column("reconciliation_runs", "internal_cutoff", nullable=True)
    op.add_column(
        "reconciliation_runs", sa.Column("source_legal_entity_id", sa.UUID(), nullable=True)
    )
    op.add_column("reconciliation_runs", sa.Column("program_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_recon_run_source_legal_entity",
        "reconciliation_runs",
        "legal_entities",
        ["source_legal_entity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_recon_run_program",
        "reconciliation_runs",
        "programs",
        ["program_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint("ck_recon_run_target", "reconciliation_runs", TARGET_CHECK)


def downgrade() -> None:
    incompatible = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM reconciliation_runs WHERE "
                "reconciliation_type <> 'LENDER' OR provider_id IS NULL OR internal_cutoff IS NULL)"
            )
        )
        .scalar()
    )
    if incompatible:
        raise RuntimeError(
            "Cannot downgrade multi-source reconciliation history; use forward correction"
        )
    op.drop_constraint("ck_recon_run_target", "reconciliation_runs", type_="check")
    op.drop_constraint("fk_recon_run_program", "reconciliation_runs", type_="foreignkey")
    op.drop_constraint(
        "fk_recon_run_source_legal_entity", "reconciliation_runs", type_="foreignkey"
    )
    op.drop_column("reconciliation_runs", "program_id")
    op.drop_column("reconciliation_runs", "source_legal_entity_id")
    op.alter_column("reconciliation_runs", "provider_id", nullable=False)
    op.alter_column("reconciliation_runs", "internal_cutoff", nullable=False)
