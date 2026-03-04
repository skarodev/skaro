"""Skaro Web Dashboard — FastAPI application.

This module wires together the API routers, error handlers, WebSocket
endpoint and SPA static file serving. All endpoint logic lives in
``skaro_web.api.*`` sub-modules.
"""

from __future__ import annotations

import json
import logging
import traceback as tb
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from skaro_core.llm.base import LLMError
from skaro_web.api import all_routers
from skaro_web.api.deps import ConnectionManager

logger = logging.getLogger("skaro_web")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

STATIC_DIR = Path(__file__).parent / "static"
DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"


def create_app(project_root: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        project_root: Path to the project being managed. Defaults to cwd.
    """
    resolved_root = project_root or Path.cwd()

    app = FastAPI(title="Skaro Dashboard", version="0.1.0")

    # ── Shared state (replaces module-level globals) ────────
    app.state.project_root = resolved_root
    app.state.ws_manager = ConnectionManager()

    # ── Error handlers ──────────────────────────────────────

    @app.exception_handler(LLMError)
    async def llm_error_handler(request, exc: LLMError):  # noqa: ARG001
        if exc.status_code:
            status_code = exc.status_code
        elif exc.retriable:
            status_code = 503
        else:
            status_code = 502
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "message": str(exc),
                "error_type": "llm_error",
                "provider": exc.provider,
                "retriable": exc.retriable,
            },
        )

    @app.exception_handler(Exception)
    async def general_error_handler(request, exc: Exception):
        logger.error("Unhandled error on %s: %s\n%s", request.url, exc, tb.format_exc())
        if "/ws" in str(request.url):
            raise exc
        if "/api/" in str(request.url):
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"Server error: {exc}",
                    "error_type": "server_error",
                },
            )
        return HTMLResponse(
            f"<h1>500 — Skaro Dashboard Error</h1><pre>{tb.format_exc()}</pre>",
            status_code=500,
        )

    # ── Mount API routers ───────────────────────────────────

    for router in all_routers:
        app.include_router(router)

    # ── WebSocket ───────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        manager: ConnectionManager = app.state.ws_manager
        await manager.connect(ws)
        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
        except WebSocketDisconnect:
            await manager.disconnect(ws)

    # ── Static / SPA ────────────────────────────────────────

    if STATIC_DIR.is_dir() and (STATIC_DIR / "_app").is_dir():
        app.mount("/_app", StaticFiles(directory=STATIC_DIR / "_app"), name="svelte-app")
        logger.info("Mounted Svelte _app from %s", STATIC_DIR / "_app")
    else:
        logger.warning("No _app dir in %s — Svelte build missing?", STATIC_DIR)

    @app.get("/{path:path}")
    async def serve_dashboard(path: str):
        try:
            if path and STATIC_DIR.is_dir():
                file_path = STATIC_DIR / path
                if file_path.is_file():
                    return FileResponse(file_path)
                # Static assets (JS/CSS/etc.) must exist — never fall back to index.html
                if path.startswith("_app/"):
                    return JSONResponse(
                        status_code=404,
                        content={"detail": f"Static asset not found: {path}"},
                    )
            svelte_index = STATIC_DIR / "index.html"
            if svelte_index.is_file():
                return FileResponse(svelte_index)
            if DASHBOARD_FILE.exists():
                logger.info("Falling back to legacy dashboard.html")
                return FileResponse(DASHBOARD_FILE)
            return HTMLResponse(
                "<h1>Skaro Dashboard</h1>"
                "<p>No frontend build found.</p>"
                "<p>Run: <code>cd frontend && npm install && npm run build</code></p>"
                f"<p>Looked in: {STATIC_DIR}</p>"
            )
        except Exception as e:
            logger.error("serve_dashboard error: %s", e, exc_info=True)
            return HTMLResponse(f"<h1>Error</h1><pre>{e}</pre>", status_code=500)

    return app
