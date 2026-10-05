from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    database = request.app.state.database
    database_ok = await database.ping()
    payload = {
        "status": "ready" if database_ok else "not_ready",
        "components": {"database": "ready" if database_ok else "unavailable"},
    }
    return JSONResponse(
        payload,
        status_code=status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
