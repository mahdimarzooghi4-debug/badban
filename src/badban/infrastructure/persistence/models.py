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
    __table_args__ = (Index("ix_outbox_unpublished_created", "published_at", "created_at"),)

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


class RoleGrant(Base, VersionedMixin):
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


class Program(Base, VersionedMixin):
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


class ParticipationEpisode(Base, VersionedMixin):
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


class AssetType(Base, VersionedMixin):
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
    eligibility_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
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


class AssetPosition(Base, VersionedMixin):
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
    custodian_legal_entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
