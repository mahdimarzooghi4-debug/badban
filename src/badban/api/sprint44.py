from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_current_principal, get_session
from badban.api.errors import ApiError
from badban.infrastructure.persistence.models import Participant
from badban.security.authorization import Principal

router = APIRouter(prefix="/api/v1/applicant", tags=["applicant"])


class ApplicantParticipantView(BaseModel):
    participant_id: UUID
    lifecycle_status: str


@router.get("/participant", response_model=ApplicantParticipantView)
async def get_linked_participant(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ApplicantParticipantView:
    """Resolve the verified OIDC national ID to its unique Badban participant record."""
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
