"""Dependency injection for Skaro Web API.

All shared state lives on ``app.state`` and is injected via FastAPI ``Depends()``.

Usage in routers::

    from skaro_web.api.deps import get_am, get_project_root, broadcast, llm_phase

    @router.get("/example")
    async def example(am: ArtifactManager = Depends(get_am)):
        ...
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Request, WebSocket

from skaro_core.artifacts import ArtifactManager

logger = logging.getLogger("skaro_web")


# ═══════════════════════════════════════════════════
# Connection manager (replaces global list)
# ═══════════════════════════════════════════════════

class ConnectionManager:
    """Thread-safe WebSocket connection manager."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        message = json.dumps(data)
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._connections.remove(ws)


# ═══════════════════════════════════════════════════
# FastAPI Depends() providers
# ═══════════════════════════════════════════════════

def get_project_root(request: Request) -> Path:
    """Inject project root path."""
    return request.app.state.project_root


def get_am(request: Request) -> ArtifactManager:
    """Inject ArtifactManager (created per-request, lightweight)."""
    return ArtifactManager(request.app.state.project_root)


def get_ws_manager(request: Request) -> ConnectionManager:
    """Inject WebSocket ConnectionManager."""
    return request.app.state.ws_manager


# ═══════════════════════════════════════════════════
# Broadcast shortcut (for use inside routers)
# ═══════════════════════════════════════════════════

async def broadcast(request: Request, data: dict[str, Any]) -> None:
    """Broadcast a message to all connected WebSocket clients."""
    manager: ConnectionManager = request.app.state.ws_manager
    await manager.broadcast(data)


# ═══════════════════════════════════════════════════
# LLM phase context manager
# ═══════════════════════════════════════════════════

@asynccontextmanager
async def llm_phase(
    ws_manager: ConnectionManager,
    phase_name: str,
    phase_obj: Any = None,
    request: Request | None = None,
) -> AsyncIterator[None]:
    """Wrap LLM phase execution: broadcast start/chunk/complete over WS.

    When *request* is provided, monitors the HTTP connection and cancels
    the running LLM stream when the client disconnects (e.g. stop button).
    """
    await ws_manager.broadcast({"event": "llm:start", "phase": phase_name})

    cancel_event: asyncio.Event | None = None
    monitor_task: asyncio.Task | None = None

    if request is not None and phase_obj is not None:
        cancel_event = asyncio.Event()
        phase_obj._cancel_event = cancel_event

        async def _monitor_disconnect() -> None:
            """Poll request connection; set cancel event on disconnect."""
            try:
                while not cancel_event.is_set():
                    if await request.is_disconnected():
                        logger.info("Client disconnected during %s — cancelling", phase_name)
                        cancel_event.set()
                        return
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                pass

        monitor_task = asyncio.create_task(_monitor_disconnect())

    if phase_obj is not None:
        async def _on_chunk(text: str) -> None:
            await ws_manager.broadcast({"event": "llm:chunk", "text": text})
        phase_obj.on_stream_chunk = _on_chunk

    try:
        yield
    finally:
        if cancel_event is not None:
            cancel_event.set()
        if monitor_task is not None:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        await ws_manager.broadcast({"event": "llm:complete", "phase": phase_name})
