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
from badban.api.sprint08 import router as sprint08_router
from badban.api.sprint09 import router as sprint09_router
from badban.api.sprint13 import router as sprint13_router
from badban.api.sprint14 import router as sprint14_router
from badban.api.sprint17 import router as sprint17_router
from badban.api.sprint18 import router as sprint18_router
from badban.api.sprint21 import router as sprint21_router
from badban.api.sprint26 import router as sprint26_router
from badban.api.sprint28 import router as sprint28_router
from badban.api.sprint29 import router as sprint29_router
from badban.api.sprint31 import router as sprint31_router
from badban.api.sprint32 import router as sprint32_router
from badban.api.sprint40 import router as sprint40_router
from badban.api.sprint41 import router as sprint41_router
from badban.api.sprint42 import router as sprint42_router
from badban.api.sprint43 import router as sprint43_router
from badban.api.sprint44 import router as sprint44_router
from badban.api.sprint45 import router as sprint45_router
from badban.api.sprint46 import router as sprint46_router
from badban.api.sprint48 import admin_router as sprint48_admin_router
from badban.api.sprint48 import institution_router as sprint48_institution_router
from badban.api.sprint49 import admin_router as sprint49_admin_router
from badban.api.sprint49 import lender_router as sprint49_lender_router
from badban.api.sprint50 import router as sprint50_router
from badban.api.sprint53 import router as sprint53_router
from badban.api.sprint56 import router as sprint56_router
from badban.api.v1 import router as v1_router
from badban.application.external_evidence import EvidenceAdapterRegistry
from badban.application.lender_adapter import LenderAdapterRegistry
from badban.config import Settings, get_settings
from badban.infrastructure.persistence.database import Database
from badban.observability import configure_logging, configure_tracing
from badban.security.oidc import OidcTokenVerifier


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved)
    database = Database(resolved.database_url)
    token_verifier = OidcTokenVerifier(resolved)
    lender_adapter_registry = LenderAdapterRegistry()
    evidence_adapter_registry = EvidenceAdapterRegistry()

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
    app.state.lender_adapter_registry = lender_adapter_registry
    app.state.evidence_adapter_registry = evidence_adapter_registry
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health_router)
    app.include_router(v1_router)
    app.include_router(sprint03_router)
    app.include_router(sprint04_router)
    app.include_router(sprint06_router)
    app.include_router(sprint07_router)
    app.include_router(sprint08_router)
    app.include_router(sprint09_router)
    app.include_router(sprint13_router)
    app.include_router(sprint14_router)
    app.include_router(sprint17_router)
    app.include_router(sprint18_router)
    app.include_router(sprint21_router)
    app.include_router(sprint26_router)
    app.include_router(sprint28_router)
    app.include_router(sprint29_router)
    app.include_router(sprint31_router)
    app.include_router(sprint32_router)
    app.include_router(sprint40_router)
    app.include_router(sprint41_router)
    app.include_router(sprint42_router)
    app.include_router(sprint43_router)
    app.include_router(sprint44_router)
    app.include_router(sprint45_router)
    app.include_router(sprint46_router)
    app.include_router(sprint48_admin_router)
    app.include_router(sprint48_institution_router)
    app.include_router(sprint49_admin_router)
    app.include_router(sprint49_lender_router)
    app.include_router(sprint50_router)
    app.include_router(sprint53_router)
    app.include_router(sprint56_router)
    configure_tracing(app, resolved)
    return app


app = create_app()
