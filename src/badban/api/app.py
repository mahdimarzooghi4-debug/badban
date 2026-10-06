from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from badban.api.errors import ApiError, api_error_handler
from badban.api.health import router as health_router
from badban.api.middleware import CorrelationIdMiddleware
from badban.api.sprint03 import router as sprint03_router
from badban.api.sprint04 import router as sprint04_router
from badban.api.sprint06 import router as sprint06_router
from badban.api.sprint07 import router as sprint07_router
from badban.api.v1 import router as v1_router
from badban.config import Settings, get_settings
from badban.infrastructure.persistence.database import Database
from badban.observability import configure_logging, configure_tracing
from badban.security.oidc import OidcTokenVerifier


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved)
    database = Database(resolved.database_url)
    token_verifier = OidcTokenVerifier(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(title="Badban API", version="0.2.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.database = database
    app.state.token_verifier = token_verifier
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health_router)
    app.include_router(v1_router)
    app.include_router(sprint03_router)
    app.include_router(sprint04_router)
    app.include_router(sprint06_router)
    app.include_router(sprint07_router)
    configure_tracing(app, resolved)
    return app


app = create_app()
