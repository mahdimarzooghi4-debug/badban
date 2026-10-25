from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import Participant
from badban.security.audit import append_audit
from badban.security.authorization import Principal

router = APIRouter(prefix="/api/v1/applicant", tags=["applicant"])


class ApplicantParticipantView(BaseModel):
    participant_id: UUID
    lifecycle_status: str


@router.post("/participant", response_model=ApplicantParticipantView)
async def ensure_individual_profile(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> ApplicantParticipantView:
    """Create or resolve an individual profile from a verified OIDC national ID."""
    if principal.identity_type != "PARTICIPANT" or not principal.national_id:
        raise ApiError(
            403,
            "PARTICIPANT_LINK_UNAVAILABLE",
            "The authenticated account has no trusted participant reference",
        )

    participant = await session.scalar(
        select(Participant).where(Participant.external_reference == principal.national_id)
    )
    if participant is None:
        participant = await session.scalar(
            insert(Participant)
            .values(external_reference=principal.national_id, lifecycle_status="ACTIVE")
            .on_conflict_do_nothing(index_elements=[Participant.external_reference])
            .returning(Participant)
        )
        if participant is None:
            participant = await session.scalar(
                select(Participant).where(Participant.external_reference == principal.national_id)
            )
        if participant is None:
            raise ApiError(
                503,
                "PARTICIPANT_PROFILE_UNAVAILABLE",
                "Individual profile could not be resolved",
            )
        append_audit(
            session,
            aggregate_type="Participant",
            aggregate_id=str(participant.id),
            aggregate_version=None,
            action="INDIVIDUAL_PROFILE_CREATE",
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
            outcome="SUCCESS",
            scope={"creation_source": "VERIFIED_OIDC_NATIONAL_ID"},
        )
        await session.commit()
    return ApplicantParticipantView(
        participant_id=participant.id,
        lifecycle_status=participant.lifecycle_status,
    )


@router.get("/participant", response_model=ApplicantParticipantView)
async def get_linked_participant(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ApplicantParticipantView:
    """Read the caller's existing profile without creating or changing state."""
    if principal.identity_type != "PARTICIPANT" or not principal.national_id:
        raise ApiError(
            403,
            "PARTICIPANT_LINK_UNAVAILABLE",
            "The authenticated account has no trusted participant reference",
        )
    participant = await session.scalar(
        select(Participant).where(Participant.external_reference == principal.national_id)
    )
    if participant is None:
        raise ApiError(
            404,
            "PARTICIPANT_RECORD_NOT_FOUND",
            "No Badban participant record matches the authenticated account",
        )
    return ApplicantParticipantView(
        participant_id=participant.id,
        lifecycle_status=participant.lifecycle_status,
    )
