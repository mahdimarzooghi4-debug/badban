from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from badban.api.sprint02 import router as sprint02_router

from badban.api.health import router as health_router
from badban.api.middleware import CorrelationIdMiddleware
from badban.config import Settings, get_settings
from badban.infrastructure.persistence.database import Database
from badban.observability import configure_logging, configure_tracing
from badban.security.auth import OidcAuthenticator


def create_app(settings: Settings | None = None, authenticator: object | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved)
    database = Database(resolved.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(title="Badban API", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.database = database
    app.state.authenticator = authenticator
    if app.state.authenticator is None and resolved.oidc_issuer and resolved.oidc_audience:
        app.state.authenticator = OidcAuthenticator(resolved.oidc_issuer, resolved.oidc_audience)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health_router)
    app.include_router(sprint02_router)
    configure_tracing(app, resolved)
    return app


app = create_app()
