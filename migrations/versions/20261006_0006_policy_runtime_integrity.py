"""Sprint 04 policy runtime integrity hardening.

Revision ID: 20261006_0006
Revises: 20261006_0005
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261006_0006"
down_revision: str | None = "20261006_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_immutable_policy_content_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.lifecycle_status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED')
               AND (
                    NEW.policy_type IS DISTINCT FROM OLD.policy_type
                    OR NEW.policy_code IS DISTINCT FROM OLD.policy_code
                    OR NEW.version_number IS DISTINCT FROM OLD.version_number
                    OR NEW.scope_definition IS DISTINCT FROM OLD.scope_definition
                    OR NEW.payload IS DISTINCT FROM OLD.payload
                    OR NEW.payload_hash IS DISTINCT FROM OLD.payload_hash
                    OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
                    OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
                    OR NEW.effective_to IS DISTINCT FROM OLD.effective_to
                    OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
                    OR NEW.activated_at IS DISTINCT FROM OLD.activated_at
                    OR NEW.created_by IS DISTINCT FROM OLD.created_by
                    OR NEW.approved_by IS DISTINCT FROM OLD.approved_by
               )
            THEN
                RAISE EXCEPTION 'activated policy content is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_versions_immutable_content
        BEFORE UPDATE ON policy_versions
        FOR EACH ROW EXECUTE FUNCTION badban_reject_immutable_policy_content_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_policy_versions_immutable_content ON policy_versions")
    op.execute("DROP FUNCTION IF EXISTS badban_reject_immutable_policy_content_mutation")
