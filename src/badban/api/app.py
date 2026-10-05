from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from badban.api.health import router as health_router
from badban.api.middleware import CorrelationIdMiddleware
from badban.config import Settings, get_settings
from badban.infrastructure.persistence.database import Database
from badban.observability import configure_logging, configure_tracing


def create_app(settings: Settings | None = None) -> FastAPI:
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
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health_router)
    configure_tracing(app, resolved)
    return app


app = create_app()
