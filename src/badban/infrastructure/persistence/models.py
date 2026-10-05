from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
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
    external_subject: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    identity_type: Mapped[str] = mapped_column(String(40), nullable=False)
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
        Index("ix_role_grants_lookup", "identity_id", "role_code", "scope_type", "scope_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    identity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=True
    )
    reason_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Program(Base, VersionedMixin):
    __tablename__ = "programs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ParticipationEpisode(Base, VersionedMixin):
    __tablename__ = "participation_episodes"
    __table_args__ = (
        Index("ix_participation_program_participant", "program_id", "participant_ref"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    program_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    participant_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AssetType(Base, VersionedMixin):
    __tablename__ = "asset_types"
    __table_args__ = (
        CheckConstraint("precision_scale >= 0 AND precision_scale <= 18", name="ck_asset_type_precision"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    unit: Mapped[str] = mapped_column(String(80), nullable=False)
    precision_scale: Mapped[int] = mapped_column(Integer, nullable=False)
    valuation_source_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    eligibility_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    custody_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="APPROVED")
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AssetPosition(Base, VersionedMixin):
    __tablename__ = "asset_positions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_asset_position_quantity_positive"),
        CheckConstraint(
            "ownership_class IN ('PARTICIPANT_OWNED', 'PROGRAM_ATTRIBUTED')",
            name="ck_asset_position_ownership_class",
        ),
        Index("ix_asset_position_program_episode", "program_id", "participation_episode_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    program_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    participation_episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("participation_episodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    asset_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("asset_types.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    ownership_class: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    custody_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_target", "target_type", "target_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_identity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identities.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
