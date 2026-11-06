from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from badban.api.app import create_app
from badban.config import Settings


def _settings(web_dist_dir: str | None = None, web_oidc_client_id: str | None = None) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+asyncpg://badban@localhost:5432/badban",
        oidc_issuer="https://issuer.example/realms/badban",
        oidc_audience="badban-api",
        web_dist_dir=web_dist_dir,
        web_oidc_client_id=web_oidc_client_id,
    )


def _bundle(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "assets" / "app.js").write_text("console.log('badban');", encoding="utf-8")
    (root / "index.html").write_text(
        "<!doctype html><html><body>Badban Stage candidate</body></html>",
        encoding="utf-8",
    )
    return root


def test_web_bundle_is_opt_in_and_does_not_change_api_routes() -> None:
    with TestClient(create_app(_settings())) as client:
        assert client.get("/app").status_code == 404
        assert client.get("/runtime-config.js").status_code == 404
        assert client.get("/health/live").json() == {"status": "alive"}


def test_same_origin_responds_with_app_and_public_oidc_metadata(tmp_path: Path) -> None:
    web_root = _bundle(tmp_path / "dist")
    with TestClient(create_app(_settings(str(web_root), "badban-web"))) as client:
        for route in ("/", "/app", "/auth/callback"):
            page = client.get(route)
            assert page.status_code == 200
            assert "Badban Stage candidate" in page.text
            assert page.headers["cache-control"] == "no-store"
            assert "script-src 'self'" in page.headers["content-security-policy"]
            assert "https://issuer.example" in page.headers["content-security-policy"]
            assert page.headers["x-frame-options"] == "DENY"

        config = client.get("/runtime-config.js")
        assert config.status_code == 200
        assert "application/javascript" in config.headers["content-type"]
        assert '"clientId":"badban-web"' in config.text
        assert '"authority":"https://issuer.example/realms/badban"' in config.text
        assert config.headers["cache-control"] == "no-store"
        assert "token" not in config.text.lower()
        assert "database" not in config.text.lower()
        assert "secret" not in config.text.lower()

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text
        assert client.get("/api/v1/nonexistent").status_code == 404
        assert client.get("/api/v1/me").status_code == 401
        assert client.get("/does-not-exist").status_code == 404
        assert client.get("/assets/does-not-exist.js").status_code == 404


def test_web_startup_fails_closed_without_real_build_or_oidc_configuration(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        _settings(str(tmp_path / "missing"), "")
    with pytest.raises(FileNotFoundError):
        create_app(_settings(str(tmp_path / "missing"), "badban-web"))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="build is incomplete"):
        create_app(_settings(str(empty), "badban-web"))


def test_stage_env_secret_fallback_stays_forbidden_with_web_enabled(tmp_path: Path) -> None:
    dist = _bundle(tmp_path / "dist")
    with pytest.raises(ValidationError, match="requires BADBAN_SECRET_PROVIDER=vault"):
        Settings(
            app_env="stage",
            secret_provider="environment",
            database_url="postgresql+asyncpg://badban@localhost:5432/badban",
            oidc_issuer="https://issuer.example/realms/badban",
            oidc_audience="badban-api",
            web_dist_dir=str(dist),
            web_oidc_client_id="badban-web",
        )
