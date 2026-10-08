from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from badban.api.dependencies import get_correlation_id, get_current_principal, get_session
from badban.api.errors import ApiError
from badban.application.recovery_verification import (
    RecoveryVerificationError,
    execute_recovery_verification,
)
from badban.infrastructure.persistence.models import (
    RecoveryVerification,
    RecoveryVerificationCheck,
)
from badban.security.authorization import (
    ROLE_AUDITOR,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_LEGAL_COMPLIANCE,
    ROLE_OPERATIONS,
    ROLE_RISK,
    ROLE_SYSTEM_OPERATOR,
    SCOPE_GLOBAL,
    AuthorizationDenied,
    Principal,
    authorize,
)

router = APIRouter(prefix="/api/v1", tags=["recovery-verification"])

_EXECUTE_ROLES = {ROLE_OPERATIONS, ROLE_GOVERNANCE_APPROVER, ROLE_SYSTEM_OPERATOR}
_READ_ROLES = {
    ROLE_OPERATIONS,
    ROLE_GOVERNANCE_APPROVER,
    ROLE_SYSTEM_OPERATOR,
    ROLE_AUDITOR,
    ROLE_RISK,
    ROLE_FINANCE_RECONCILIATION,
    ROLE_LEGAL_COMPLIANCE,
}


class RecoveryVerificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restore_reference: str = Field(min_length=1, max_length=255)
    environment_reference: str = Field(min_length=1, max_length=120)
    source_backup_reference: str | None = Field(default=None, min_length=1, max_length=500)
    source_integrity_reference: str | None = Field(default=None, min_length=1, max_length=500)


class RecoveryVerificationCheckView(BaseModel):
    id: UUID
    check_code: str
    status: Literal["PASS", "FAIL", "NOT_VERIFIED"]
    details: dict[str, Any]
    evidence_reference: str | None
    created_at: datetime


class RecoveryVerificationView(BaseModel):
    id: UUID
    restore_reference: str
    source_backup_reference: str | None
    source_integrity_reference: str | None
    environment_reference: str
    verification_version: str
    status: Literal["PASSED", "FAILED"]
    check_count: int
    failed_check_count: int
    not_verified_check_count: int
    actor_type: str
    actor_id: UUID
    correlation_id: UUID
    started_at: datetime
    completed_at: datetime
    created_at: datetime
    checks: list[RecoveryVerificationCheckView]


def _raise_recovery_error(exc: RecoveryVerificationError) -> NoReturn:
    raise ApiError(422, exc.code, str(exc)) from exc


async def _authorize_global(
    session: AsyncSession,
    *,
    principal: Principal,
    roles: set[str],
    action: str,
    target_id: str,
    correlation_id: UUID,
) -> None:
    try:
        await authorize(
            session,
            principal=principal,
            roles=roles,
            scope_type=SCOPE_GLOBAL,
            scope_id=None,
            allow_global=False,
            action=action,
            target_type="RecoveryVerification",
            target_id=target_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as exc:
        raise ApiError(403, exc.code, "Authorization denied for recovery verification") from exc


async def _view(
    session: AsyncSession,
    verification: RecoveryVerification,
) -> RecoveryVerificationView:
    checks = (
        await session.scalars(
            select(RecoveryVerificationCheck)
            .where(RecoveryVerificationCheck.recovery_verification_id == verification.id)
            .order_by(
                RecoveryVerificationCheck.check_code,
                RecoveryVerificationCheck.id,
            )
        )
    ).all()
    return RecoveryVerificationView(
        id=verification.id,
        restore_reference=verification.restore_reference,
        source_backup_reference=verification.source_backup_reference,
        source_integrity_reference=verification.source_integrity_reference,
        environment_reference=verification.environment_reference,
        verification_version=verification.verification_version,
        status=cast(Literal["PASSED", "FAILED"], verification.status),
        check_count=verification.check_count,
        failed_check_count=verification.failed_check_count,
        not_verified_check_count=verification.not_verified_check_count,
        actor_type=verification.actor_type,
        actor_id=verification.actor_id,
        correlation_id=verification.correlation_id,
        started_at=verification.started_at,
        completed_at=verification.completed_at,
        created_at=verification.created_at,
        checks=[
            RecoveryVerificationCheckView(
                id=check.id,
                check_code=check.check_code,
                status=cast(Literal["PASS", "FAIL", "NOT_VERIFIED"], check.status),
                details=check.details,
                evidence_reference=check.evidence_reference,
                created_at=check.created_at,
            )
            for check in checks
        ],
    )


@router.post(
    "/recovery-verifications",
    response_model=RecoveryVerificationView,
    status_code=status.HTTP_201_CREATED,
)
async def create_recovery_verification(
    body: RecoveryVerificationCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> RecoveryVerificationView:
    await _authorize_global(
        session,
        principal=principal,
        roles=_EXECUTE_ROLES,
        action="RECOVERY_VERIFICATION_EXECUTE",
        target_id=body.restore_reference,
        correlation_id=correlation_id,
    )
    try:
        verification = await execute_recovery_verification(
            session,
            restore_reference=body.restore_reference,
            environment_reference=body.environment_reference,
            source_backup_reference=body.source_backup_reference,
            source_integrity_reference=body.source_integrity_reference,
            actor_type=principal.identity_type,
            actor_id=principal.identity_id,
            correlation_id=correlation_id,
        )
    except RecoveryVerificationError as exc:
        _raise_recovery_error(exc)
    await session.commit()
    return await _view(session, verification)


@router.get(
    "/recovery-verifications/{verification_id}",
    response_model=RecoveryVerificationView,
)
async def get_recovery_verification(
    verification_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
    correlation_id: UUID = Depends(get_correlation_id),
) -> RecoveryVerificationView:
    await _authorize_global(
        session,
        principal=principal,
        roles=_READ_ROLES,
        action="RECOVERY_VERIFICATION_READ",
        target_id=str(verification_id),
        correlation_id=correlation_id,
    )
    verification = await session.get(RecoveryVerification, verification_id)
    if verification is None:
        raise ApiError(
            404, "RECOVERY_VERIFICATION_NOT_FOUND", "Recovery verification was not found"
        )
    return await _view(session, verification)
