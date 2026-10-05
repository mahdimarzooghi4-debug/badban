from __future__ import annotations

from uuid import UUID

from httpx import ASGITransport, AsyncClient

from badban.api.app import create_app
from badban.api.middleware import CORRELATION_HEADER
from badban.config import Settings


async def test_liveness_is_independent_of_external_providers(settings: Settings) -> None:
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    UUID(response.headers[CORRELATION_HEADER])


async def test_valid_correlation_id_is_propagated(settings: Settings) -> None:
    app = create_app(settings)
    correlation_id = "6bba7b2b-c65d-4a93-89b2-7db62179150d"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/health/live",
            headers={CORRELATION_HEADER: correlation_id},
        )

    assert response.headers[CORRELATION_HEADER] == correlation_id
