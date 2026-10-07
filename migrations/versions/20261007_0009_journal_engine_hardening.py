"""Sprint 08 append-only journal engine hardening.

Revision ID: 20261007_0009
Revises: 20261006_0008
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261007_0009"
down_revision: str | None = "20261006_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_journal_entries_posted_append_only ON journal_entries
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_posted_journal_mutation()
        RETURNS trigger AS $$
        DECLARE
            posting_count bigint;
            debit_total numeric;
            credit_total numeric;
            contexts_match boolean;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'PREPARED' OR NEW.posted_at IS NOT NULL THEN
                    RAISE EXCEPTION 'journal_entries must be inserted as PREPARED';
                END IF;
                RETURN NEW;
            END IF;

            IF OLD.state = 'POSTED' THEN
                RAISE EXCEPTION 'posted journal_entries are append-only';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;

            IF NEW.state = 'PREPARED' THEN
                IF NEW.posted_at IS NOT NULL THEN
                    RAISE EXCEPTION 'PREPARED journal cannot have posted_at';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.state = 'POSTED' THEN
                IF NEW.posted_at IS NULL THEN
                    RAISE EXCEPTION 'POSTED journal requires posted_at';
                END IF;

                SELECT
                    count(*),
                    COALESCE(sum(debit_amount), 0),
                    COALESCE(sum(credit_amount), 0),
                    COALESCE(
                        bool_and(
                            legal_entity_id = NEW.legal_entity_id
                            AND currency = NEW.currency
                        ),
                        false
                    )
                INTO posting_count, debit_total, credit_total, contexts_match
                FROM journal_postings
                WHERE journal_entry_id = OLD.id;

                IF posting_count < 2 THEN
                    RAISE EXCEPTION 'POSTED journal requires at least two postings';
                END IF;
                IF debit_total <= 0 OR debit_total <> credit_total THEN
                    RAISE EXCEPTION 'POSTED journal must balance exactly';
                END IF;
                IF NOT contexts_match THEN
                    RAISE EXCEPTION 'journal posting context must match journal entry';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_posted_append_only
        BEFORE INSERT OR UPDATE OR DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION badban_reject_posted_journal_mutation()
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_journal_postings_append_only ON journal_postings
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_journal_posting_mutation()
        RETURNS trigger AS $$
        DECLARE
            parent_state text;
            parent_legal_entity_id uuid;
            parent_currency text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT state, legal_entity_id, currency
                INTO parent_state, parent_legal_entity_id, parent_currency
                FROM journal_entries
                WHERE id = NEW.journal_entry_id;

                IF parent_state IS NULL THEN
                    RAISE EXCEPTION 'journal parent does not exist';
                END IF;
                IF parent_state <> 'PREPARED' THEN
                    RAISE EXCEPTION 'cannot add posting to a non-PREPARED journal';
                END IF;
                IF NEW.legal_entity_id <> parent_legal_entity_id
                   OR NEW.currency <> parent_currency THEN
                    RAISE EXCEPTION 'journal posting context must match journal entry';
                END IF;
                RETURN NEW;
            END IF;

            RAISE EXCEPTION 'journal_postings are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_postings_append_only
        BEFORE INSERT OR UPDATE OR DELETE ON journal_postings
        FOR EACH ROW EXECUTE FUNCTION badban_reject_journal_posting_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_journal_entries_posted_append_only ON journal_entries
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_posted_journal_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.state = 'POSTED' THEN
                RAISE EXCEPTION 'posted journal_entries are append-only';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_posted_append_only
        BEFORE UPDATE OR DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION badban_reject_posted_journal_mutation()
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_journal_postings_append_only ON journal_postings
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION badban_reject_journal_posting_mutation()
        RETURNS trigger AS $$
        DECLARE
            parent_state text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT state INTO parent_state
                FROM journal_entries
                WHERE id = NEW.journal_entry_id;
                IF parent_state = 'POSTED' THEN
                    RAISE EXCEPTION 'cannot add posting to a POSTED journal';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'journal_postings are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_postings_append_only
        BEFORE INSERT OR UPDATE OR DELETE ON journal_postings
        FOR EACH ROW EXECUTE FUNCTION badban_reject_journal_posting_mutation()
        """
    )
