"""Sprint 12 audit and evidence trace hardening.

Revision ID: 20261007_0013
Revises: 20261007_0012
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_0013"
down_revision: str | None = "20261007_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_references",
        sa.Column("source_legal_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "evidence_references",
        sa.Column("verified_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "evidence_references",
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_evidence_reference_source_legal_entity",
        "evidence_references",
        "legal_entities",
        ["source_legal_entity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_evidence_references_source_legal_entity",
        "evidence_references",
        ["source_legal_entity_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_evidence_reference_mutation()
        RETURNS trigger AS $evidence$
        BEGIN
            RAISE EXCEPTION 'evidence_references are append-only';
        END;
        $evidence$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evidence_references_append_only
        BEFORE UPDATE OR DELETE ON evidence_references
        FOR EACH ROW EXECUTE FUNCTION badban_reject_evidence_reference_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evidence_references_append_only ON evidence_references")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_evidence_reference_mutation")
    op.drop_index(
        "ix_evidence_references_source_legal_entity",
        table_name="evidence_references",
    )
    op.drop_constraint(
        "fk_evidence_reference_source_legal_entity",
        "evidence_references",
        type_="foreignkey",
    )
    op.drop_column("evidence_references", "captured_at")
    op.drop_column("evidence_references", "verified_status")
    op.drop_column("evidence_references", "source_legal_entity_id")
