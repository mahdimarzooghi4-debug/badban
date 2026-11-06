from __future__ import annotations

from pathlib import Path

from badban.api.app import app

ROOT = Path(__file__).resolve().parents[1]

SCOPED_API = {
    "/api/v1/applicant/financial-case": {"get"},
    "/api/v1/applicant/service-requests": {"get", "post"},
    "/api/v1/support-institution/programs": {"get"},
    "/api/v1/support-institution/programs/{program_id}/beneficiaries": {"get"},
    "/api/v1/lender/providers": {"get"},
    "/api/v1/lender/providers/{provider_id}/guarantees": {"get"},
    "/api/v1/admin/workspace": {"get"},
}


def test_figma_web_client_targets_actual_backend_contracts() -> None:
    """Web endpoints must remain present and bearer protected after refactors."""
    schema = app.openapi()
    source = (ROOT / "web" / "src" / "api.ts").read_text(encoding="utf-8")
    for path, methods in SCOPED_API.items():
        assert path in schema["paths"], path
        # Dynamic segments are encoded by the browser and bound by the router.
        fragment = path.split("/{")[0]
        assert fragment in source, fragment
        for method in methods:
            route = schema["paths"][path][method]
            assert route.get("security"), f"Unauthenticated: {method.upper()} {path}"


def test_brand_assets_are_versioned_not_undocumented_remote_urls() -> None:
    assets = ROOT / "web" / "public" / "assets"
    for name in ("badban-logo.png", "badban-hero.jpg", "badban-building.jpg"):
        path = assets / name
        assert path.exists() and path.stat().st_size > 0, name

    source = (ROOT / "web" / "src" / "main.tsx").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "src" / "styles.css").read_text(encoding="utf-8")
    assert "/assets/badban-logo.png" in source
    assert "/assets/badban-hero.jpg" in styles
    assert "/assets/badban-building.jpg" in styles
    assert "figma.com/api/mcp/asset/" not in source + styles
