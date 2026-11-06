from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from badban.config import Settings


def mount_same_origin_web(app: FastAPI, settings: Settings) -> None:
    """Opt-in Stage web/API integration, preserving the API's existing authorization."""
    if settings.web_dist_dir is None:
        return

    # An explicit build artifact is required. Never substitute a demo UI or dev proxy.
    root = Path(settings.web_dist_dir).resolve(strict=True)
    index = root / "index.html"
    assets = root / "assets"
    if not root.is_dir() or not index.is_file() or not assets.is_dir():
        raise RuntimeError("Badban web build is incomplete; refusing to serve partial UI")
    if not settings.web_oidc_client_id:
        raise RuntimeError("Public OIDC client ID is required to serve Badban web")

    parsed = urlsplit(settings.oidc_issuer)
    issuer_origin = f"{parsed.scheme}://{parsed.netloc}"
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
    }
    csp = (
        "default-src 'none'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' " + issuer_origin + "; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'none'"
    )
    app.mount(
        "/assets", StaticFiles(directory=str(assets), follow_symlink=False), name="web-assets"
    )

    @app.get("/runtime-config.js", include_in_schema=False)
    async def public_oidc_config() -> Response:
        # Only public OIDC metadata. No bearer token, cookie or backend secret in the UI.
        public = {
            "authority": settings.oidc_issuer,
            "clientId": settings.web_oidc_client_id,
        }
        source = (
            "window.__BADBAN_PUBLIC_OIDC_CONFIG__ = Object.freeze("
            + json.dumps(public, ensure_ascii=True, separators=(",", ":"))
            + ");"
        )
        return Response(
            content=source,
            media_type="application/javascript",
            headers=headers,
        )

    @app.get("/", include_in_schema=False)
    @app.get("/app", include_in_schema=False)
    @app.get("/auth/callback", include_in_schema=False)
    async def web_entrypoint() -> FileResponse:
        return FileResponse(
            path=index,
            media_type="text/html",
            headers={**headers, "Content-Security-Policy": csp},
        )
