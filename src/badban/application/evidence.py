from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from badban.infrastructure.persistence.models import EvidenceReference, LegalEntity


class EvidenceReferenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _required_text(value: str, *, code: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise EvidenceReferenceError(code, f"{field} must not be empty")
    return cleaned


def _validate_storage_reference(value: str) -> str:
    cleaned = _required_text(
        value,
        code="EVIDENCE_STORAGE_REFERENCE_REQUIRED",
        field="storage_reference",
    )
    scheme = urlsplit(cleaned).scheme.lower()
    if scheme in {"http", "https"}:
        raise EvidenceReferenceError(
            "EVIDENCE_PUBLIC_STORAGE_URL_FORBIDDEN",
            "Evidence storage_reference must not be a permanent public HTTP(S) URL",
        )
    return cleaned


async def register_evidence_reference(
    session: AsyncSession,
    *,
    evidence_type: str,
    storage_provider: str,
    storage_reference: str,
    captured_at: datetime,
    external_reference: str | None = None,
    content_hash: str | None = None,
    media_type: str | None = None,
    source_legal_entity_id: UUID | None = None,
    verified_status: str | None = None,
) -> EvidenceReference:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise EvidenceReferenceError(
            "EVIDENCE_CAPTURED_AT_TIMEZONE_REQUIRED",
            "captured_at must be timezone-aware",
        )

    clean_evidence_type = _required_text(
        evidence_type,
        code="EVIDENCE_TYPE_REQUIRED",
        field="evidence_type",
    )
    clean_storage_provider = _required_text(
        storage_provider,
        code="EVIDENCE_STORAGE_PROVIDER_REQUIRED",
        field="storage_provider",
    )
    clean_storage_reference = _validate_storage_reference(storage_reference)

    if source_legal_entity_id is not None:
        entity = await session.get(LegalEntity, source_legal_entity_id)
        if entity is None:
            raise EvidenceReferenceError(
                "EVIDENCE_SOURCE_LEGAL_ENTITY_NOT_FOUND",
                "source_legal_entity_id does not reference an existing legal entity",
            )

    evidence = EvidenceReference(
        evidence_type=clean_evidence_type,
        storage_provider=clean_storage_provider,
        storage_reference=clean_storage_reference,
        external_reference=external_reference.strip() if external_reference else None,
        content_hash=content_hash.strip() if content_hash else None,
        media_type=media_type.strip() if media_type else None,
        source_legal_entity_id=source_legal_entity_id,
        verified_status=verified_status.strip() if verified_status else None,
        captured_at=captured_at,
    )
    session.add(evidence)
    await session.flush()
    return evidence
