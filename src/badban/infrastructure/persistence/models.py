from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class VersionedMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    __table_args__ = (
        CheckConstraint("publish_attempts >= 0", name="ck_outbox_publish_attempts_nonnegative"),
        CheckConstraint("replay_count >= 0", name="ck_outbox_replay_count_nonnegative"),
        CheckConstraint(
            "NOT (published_at IS NOT NULL AND dead_lettered_at IS NOT NULL)",
            name="ck_outbox_not_published_and_dead_lettered",
        ),
        Index("ix_outbox_unpublished_created", "published_at", "created_at"),
        Index(
            "ix_outbox_delivery_due",
            "published_at",
            "dead_lettered_at",
            "next_attempt_at",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(160), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dead_letter_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    replay_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InboxMessage(Base):
    __tablename__ = "inbox_messages"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "event_type",
            "external_event_id",
            name="uq_inbox_source_event_external",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome_status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Identity(Base):
    __tablename__ = "identities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    identity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    external_subject: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RoleGrant(VersionedMixin, Base):
    __tablename__ = "role_grants"
    __table_args__ = (
        Index("ix_role_grants_identity_status", "identity_id", "status"),
        Index("ix_role_grants_scope", "scope_type", "scope_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    identity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    granted_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reason_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Program(VersionedMixin, Base):
    __tablename__ = "programs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    legal_entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ParticipationEpisode(VersionedMixin, Base):
    __tablename__ = "participation_episodes"
    __table_args__ = (
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_participation_episode_end_after_start",
        ),
        Index("ix_participation_episodes_participant", "participant_id"),
        Index("ix_participation_episodes_program", "program_id"),
        Index(
            "ix_participation_episodes_participant_program_status",
            "participant_id",
            "program_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False
    )
    program_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    eligibility_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_state: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AssetType(VersionedMixin, Base):
    __tablename__ = "asset_types"
    __table_args__ = (
        CheckConstraint("quantity_scale >= 0 AND quantity_scale <= 18", name="ck_asset_type_scale"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    unit_code: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_scale: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_or_valuation_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    valuation_source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eligibility_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    custody_restriction_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AssetPosition(VersionedMixin, Base):
    __tablename__ = "asset_positions"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_asset_position_quantity_nonnegative"),
        CheckConstraint(
            "ownership_funding_type IN ('PARTICIPANT_OWNED', 'PROGRAM_ATTRIBUTED')",
            name="ck_asset_position_ownership_type",
        ),
        CheckConstraint(
            "("
            "ownership_funding_type = 'PARTICIPANT_OWNED' "
            "AND legal_owner_participant_id IS NOT NULL "
            "AND legal_owner_entity_id IS NULL"
            ") OR ("
            "ownership_funding_type = 'PROGRAM_ATTRIBUTED' "
            "AND legal_owner_entity_id IS NOT NULL "
            "AND legal_owner_participant_id IS NULL"
            ")",
            name="ck_asset_position_owner_pattern",
        ),
        Index("ix_asset_positions_episode", "participation_episode_id"),
        Index("ix_asset_positions_program", "program_id"),
        Index("ix_asset_positions_asset_type", "asset_type_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    participation_episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("participation_episodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    program_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    asset_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("asset_types.id", ondelete="RESTRICT"), nullable=False
    )
    ownership_funding_type: Mapped[str] = mapped_column(String(40), nullable=False)
    legal_owner_entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    legal_owner_participant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=True
    )
    custodian_legal_entity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(40), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index(
            "ix_audit_events_aggregate",
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
        ),
        Index("ix_audit_events_actor", "actor_id"),
        Index("ix_audit_events_correlation", "correlation_id"),
        Index("ix_audit_events_occurred_at", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(160), nullable=False)
    aggregate_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    policy_pack_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    scope: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceReference(Base):
    __tablename__ = "evidence_references"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_legal_entity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("legal_entities.id", ondelete="RESTRICT"),
        nullable=True,
    )
    verified_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApprovalRequest(VersionedMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "checker_identity_id IS NULL OR checker_identity_id <> maker_identity_id",
            name="ck_approval_request_distinct_checker",
        ),
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','CANCELLED','EXPIRED')",
            name="ck_approval_request_status",
        ),
        Index("ix_approval_requests_status_expires", "status", "expires_at"),
        Index("ix_approval_requests_scope", "scope_type", "scope_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    action_type: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False)
    target_aggregate_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maker_identity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    checker_identity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=True
    )
    required_checker_role: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ValuationObservation(Base):
    __tablename__ = "valuation_observations"
    __table_args__ = (
        CheckConstraint("valued_quantity >= 0", name="ck_valuation_quantity_nonnegative"),
        CheckConstraint("unit_price >= 0", name="ck_valuation_unit_price_nonnegative"),
        CheckConstraint("fx_rate IS NULL OR fx_rate > 0", name="ck_valuation_fx_positive"),
        CheckConstraint("gross_market_value >= 0", name="ck_valuation_gross_nonnegative"),
        Index(
            "ix_valuation_observations_position_observed",
            "asset_position_id",
            "observed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_position_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("asset_positions.id", ondelete="RESTRICT"), nullable=False
    )
    valued_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    valuation_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    gross_market_value: Mapped[Decimal] = mapped_column(Numeric(114, 54), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    source_version_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JournalAccountTaxonomy(Base):
    __tablename__ = "journal_account_taxonomy"
    __table_args__ = (
        CheckConstraint(
            "account_class IN ("
            "'CONTROLLED_ASSET','OWNER_OR_ENTITLEMENT_BALANCE',"
            "'RETURN_OR_INCOME_CLEARING','LOSS_OR_COST_CONTROL','MEMORANDUM_CONTROL'"
            ")",
            name="ck_journal_account_taxonomy_class",
        ),
        CheckConstraint(
            "normal_balance IN ('DEBIT','CREDIT','MEMO')",
            name="ck_journal_account_taxonomy_normal_balance",
        ),
        CheckConstraint(
            "ledger_layer IN ('MONETARY','MEMORANDUM_CONTROL','EXTERNAL_MIRROR')",
            name="ck_journal_account_taxonomy_layer",
        ),
    )

    account_code: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_class: Mapped[str] = mapped_column(String(80), nullable=False)
    normal_balance: Mapped[str] = mapped_column(String(16), nullable=False)
    ledger_layer: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LegalEntityAccountMapping(Base):
    __tablename__ = "legal_entity_account_mappings"
    __table_args__ = (
        UniqueConstraint(
            "legal_entity_id",
            "product_account_code",
            "mapping_version",
            name="uq_legal_entity_account_mapping_version",
        ),
        CheckConstraint(
            "mapping_version > 0",
            name="ck_legal_entity_account_mapping_version_positive",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_legal_entity_account_mapping_window",
        ),
        Index(
            "ix_legal_entity_account_mapping_lookup",
            "legal_entity_id",
            "product_account_code",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    legal_entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("legal_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_account_code: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("journal_account_taxonomy.account_code", ondelete="RESTRICT"),
        nullable=False,
    )
    external_chart_account_code: Mapped[str] = mapped_column(String(160), nullable=False)
    mapping_version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        CheckConstraint("state IN ('PREPARED','POSTED')", name="ck_journal_entry_state"),
        UniqueConstraint("idempotency_key", name="uq_journal_entry_idempotency_key"),
        UniqueConstraint("reversal_of_entry_id", name="uq_journal_entry_reversal"),
        Index("ix_journal_entries_business_event", "business_event_type", "business_event_id"),
        Index("ix_journal_entries_posted_at", "posted_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    business_event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    business_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    legal_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="PREPARED")
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_of_entry_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_reference: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    policy_version_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    posting_template_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_mapping_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settlement_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JournalPosting(Base):
    __tablename__ = "journal_postings"
    __table_args__ = (
        CheckConstraint("debit_amount >= 0", name="ck_journal_posting_debit_nonnegative"),
        CheckConstraint("credit_amount >= 0", name="ck_journal_posting_credit_nonnegative"),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="ck_journal_posting_one_sided_positive",
        ),
        Index("ix_journal_postings_entry", "journal_entry_id"),
        Index("ix_journal_postings_account_currency", "account_code", "currency"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    journal_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False
    )
    account_code: Mapped[str] = mapped_column(String(80), nullable=False)
    legal_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    economic_owner_type: Mapped[str] = mapped_column(String(80), nullable=False)
    economic_owner_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    participant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=True
    )
    program_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=True
    )
    provider_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    asset_position_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("asset_positions.id", ondelete="RESTRICT"), nullable=True
    )
    guarantee_case_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    claim_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reserve_account_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LegalRole(Base):
    __tablename__ = "legal_roles"

    code: Mapped[str] = mapped_column(String(120), primary_key=True)


class LegalEntity(VersionedMixin, Base):
    __tablename__ = "legal_entities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_identifier: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LegalAuthorization(VersionedMixin, Base):
    __tablename__ = "legal_authorizations"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN "
            "('PENDING_VERIFICATION','VALID','SUSPENDED','EXPIRED','REVOKED','SUPERSEDED')",
            name="ck_legal_authorization_status",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > effective_from",
            name="ck_legal_authorization_effective_window",
        ),
        Index(
            "ix_legal_authorizations_entity_role_status",
            "legal_entity_id",
            "role_code",
            "lifecycle_status",
        ),
        Index("ix_legal_authorizations_expires_at", "expires_at"),
        Index("ix_legal_authorizations_authority", "competent_authority"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    legal_entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("legal_entities.id", ondelete="RESTRICT"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(
        String(120), ForeignKey("legal_roles.code", ondelete="RESTRICT"), nullable=False
    )
    competent_authority: Mapped[str] = mapped_column(String(255), nullable=False)
    authorization_type: Mapped[str] = mapped_column(String(160), nullable=False)
    authorization_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    scope_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    permitted_product_scope: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    permitted_asset_type_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_compliance_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="PENDING_VERIFICATION"
    )
    verified_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CreditProvider(VersionedMixin, Base):
    __tablename__ = "credit_providers"
    __table_args__ = (
        CheckConstraint(
            "provider_type = 'EXTERNAL_LENDER'",
            name="ck_credit_provider_bounded_pilot_type",
        ),
        CheckConstraint(
            "integration_mode IN "
            "('API','WEBHOOK_CALLBACK','POLLING','SECURE_BATCH_FILE','CONTROLLED_MANUAL')",
            name="ck_credit_provider_integration_mode",
        ),
        CheckConstraint(
            "lifecycle_status IN ('DRAFT','APPROVED','ACTIVE','SUSPENDED','EXPIRED','TERMINATED')",
            name="ck_credit_provider_status",
        ),
        Index("ix_credit_providers_legal_entity", "legal_entity_id"),
        Index("ix_credit_providers_status", "lifecycle_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    legal_entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("legal_entities.id", ondelete="RESTRICT"), nullable=False
    )
    provider_code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String(80), nullable=False, default="EXTERNAL_LENDER"
    )
    integration_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    authorization_review_state: Mapped[str] = mapped_column(String(80), nullable=False)
    suspension_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CreditProductVersion(VersionedMixin, Base):
    __tablename__ = "credit_product_versions"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "product_code",
            "version_number",
            name="uq_credit_product_provider_code_version",
        ),
        CheckConstraint("version_number > 0", name="ck_credit_product_version_positive"),
        CheckConstraint("min_principal >= 0", name="ck_credit_product_min_nonnegative"),
        CheckConstraint(
            "max_principal >= min_principal",
            name="ck_credit_product_max_not_below_min",
        ),
        CheckConstraint(
            "guarantee_mode IN ('FIXED','DECLINING')",
            name="ck_credit_product_guarantee_mode",
        ),
        CheckConstraint(
            "lifecycle_status IN ('DRAFT','ACTIVE','SUSPENDED','RETIRED')",
            name="ck_credit_product_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_credit_product_effective_window",
        ),
        Index(
            "ix_credit_product_versions_provider_status",
            "provider_id",
            "lifecycle_status",
        ),
        Index(
            "ix_credit_product_versions_provider_code_effective",
            "provider_id",
            "product_code",
            "effective_from",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("credit_providers.id", ondelete="RESTRICT"), nullable=False
    )
    lender_of_record_legal_entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("legal_entities.id", ondelete="RESTRICT"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(String(120), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[str] = mapped_column(String(120), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    min_principal: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    max_principal: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    tenor_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    repayment_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pricing_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    guarantee_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    delinquency_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    claim_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_version_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    additional_terms: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GuaranteeCase(VersionedMixin, Base):
    __tablename__ = "guarantee_cases"
    __table_args__ = (
        CheckConstraint(
            "state IN ("
            "'REQUESTED','RESERVED','ISSUED','ACTIVE','DELINQUENT','CLAIM_PENDING',"
            "'CLAIM_APPROVED','CLAIM_REJECTED','ENFORCEMENT','SETTLEMENT','RELEASED',"
            "'CLOSED','CANCELLED','EXPIRED'"
            ")",
            name="ck_guarantee_case_state",
        ),
        CheckConstraint(
            "requested_principal > 0",
            name="ck_guarantee_case_requested_principal_positive",
        ),
        CheckConstraint(
            "reserved_guarantee_amount IS NULL OR reserved_guarantee_amount >= 0",
            name="ck_guarantee_case_reserved_nonnegative",
        ),
        CheckConstraint(
            "issued_guarantee_amount IS NULL OR issued_guarantee_amount >= 0",
            name="ck_guarantee_case_issued_nonnegative",
        ),
        CheckConstraint(
            "current_guarantee_exposure >= 0",
            name="ck_guarantee_case_exposure_nonnegative",
        ),
        CheckConstraint(
            "issued_guarantee_amount IS NULL OR reserved_guarantee_amount IS NULL "
            "OR issued_guarantee_amount <= reserved_guarantee_amount",
            name="ck_guarantee_case_issued_not_above_reserved",
        ),
        CheckConstraint(
            "closed_at IS NULL OR state IN ('CLOSED','CANCELLED','EXPIRED')",
            name="ck_guarantee_case_closed_terminal",
        ),
        UniqueConstraint(
            "legal_guarantee_issuer_id",
            "legal_guarantee_external_id",
            name="uq_guarantee_case_issuer_external_id",
        ),
        Index("ix_guarantee_cases_episode", "participation_episode_id"),
        Index("ix_guarantee_cases_provider", "provider_id"),
        Index("ix_guarantee_cases_state", "state"),
        Index("ix_guarantee_cases_reservation_expiry", "reservation_expires_at"),
        Index("ix_guarantee_cases_legal_external_id", "legal_guarantee_external_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    participation_episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("participation_episodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("credit_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    credit_product_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("credit_product_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_pack_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("policy_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="REQUESTED")
    requested_principal: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    reserved_guarantee_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18), nullable=True
    )
    issued_guarantee_amount: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    current_guarantee_exposure: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False, default=Decimal("0")
    )
    guarantee_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    legal_guarantee_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_guarantee_issuer_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("legal_entities.id", ondelete="RESTRICT"),
        nullable=True,
    )
    external_loan_mirror_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    risk_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("portfolio_risk_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PolicyVersion(VersionedMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "policy_type",
            "policy_code",
            "version_number",
            name="uq_policy_version_identity",
        ),
        CheckConstraint(
            "policy_type IN "
            "('ASSET_TYPE_POLICY','OWNERSHIP_FUNDING_POLICY',"
            "'PROVIDER_PRODUCT_POLICY','RISK_APPETITE_POLICY',"
            "'RETURN_ALLOCATION_POLICY','LEGAL_AUTHORIZATION_POLICY',"
            "'POSTING_ACCOUNTING_MAPPING_POLICY','PILOT_POLICY_PACK')",
            name="ck_policy_version_type",
        ),
        CheckConstraint(
            "version_number > 0",
            name="ck_policy_version_number_positive",
        ),
        CheckConstraint(
            "lifecycle_status IN ('DRAFT','REVIEWED','APPROVED','ACTIVE','SUPERSEDED','RETIRED')",
            name="ck_policy_version_lifecycle_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name="ck_policy_version_effective_window",
        ),
        Index(
            "ix_policy_versions_lookup",
            "policy_type",
            "policy_code",
            "lifecycle_status",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_type: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_code: Mapped[str] = mapped_column(String(120), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    scope_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PortfolioRiskSnapshot(Base):
    __tablename__ = "portfolio_risk_snapshots"
    __table_args__ = (
        CheckConstraint(
            "risk_state IN ('GREEN','AMBER','RED')",
            name="ck_portfolio_risk_snapshot_state",
        ),
        CheckConstraint(
            "total_active_exposure >= 0 "
            "AND total_reserved_exposure >= 0 "
            "AND committed_exposure >= 0 "
            "AND approved_portfolio_limit >= 0 "
            "AND reserve_requirement >= 0 "
            "AND reserve_available >= 0",
            name="ck_portfolio_risk_snapshot_metrics_nonnegative",
        ),
        CheckConstraint(
            "policy_pack_version > 0 AND risk_policy_version_number > 0",
            name="ck_portfolio_risk_snapshot_versions_positive",
        ),
        Index("ix_portfolio_risk_snapshots_evaluated", "evaluated_at", "created_at"),
        Index("ix_portfolio_risk_snapshots_policy_pack", "policy_pack_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_pack_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_pack_version: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_policy_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    risk_policy_code: Mapped[str] = mapped_column(String(120), nullable=False)
    risk_policy_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_state: Mapped[str] = mapped_column(String(20), nullable=False)
    total_active_exposure: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    total_reserved_exposure: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    committed_exposure: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    approved_portfolio_limit: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    reserve_requirement: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    reserve_available: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    reserve_metrics_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    concentration_metrics_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    stress_result_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evaluated_inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_code: Mapped[str] = mapped_column(String(120), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DecisionSnapshot(Base):
    __tablename__ = "decision_snapshots"
    __table_args__ = (
        CheckConstraint(
            "policy_pack_version > 0",
            name="ck_decision_snapshot_policy_pack_version_positive",
        ),
        Index(
            "ix_decision_snapshots_entity",
            "business_entity_type",
            "business_entity_id",
        ),
        Index("ix_decision_snapshots_policy_pack", "policy_pack_id"),
        Index("ix_decision_snapshots_effective_at", "effective_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    business_entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    business_entity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_pack_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_pack_version: Mapped[int] = mapped_column(Integer, nullable=False)
    component_version_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    algorithm_code: Mapped[str] = mapped_column(String(120), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)
    material_input_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    material_output_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    valuation_observation_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    authoritative_external_references: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    risk_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("portfolio_risk_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
