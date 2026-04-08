"""Autopilot HTTP endpoints — thin routing layer.

All business logic lives in :mod:`.orchestrator` and :mod:`.runners`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.deps import (
    ConnectionManager,
    get_am,
    get_project_root,
    get_ws_manager,
)

from .orchestrator import AutopilotOrchestrator
from .session import session, sse

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


@router.post("/start")
async def start_autopilot(
    request: Request,
    project_root: Path = Depends(get_project_root),
    am: ArtifactManager = Depends(get_am),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Start autopilot and stream progress via SSE."""
    if session.running:
        return StreamingResponse(
            iter([sse("error", {"message": "Autopilot is already running."})]),
            media_type="text/event-stream",
        )

    stop_event = session.acquire()

    orchestrator = AutopilotOrchestrator(
        project_root=project_root,
        am=am,
        ws=ws,
        stop_event=stop_event,
        on_finish=session.release,
    )

    return StreamingResponse(
        orchestrator.run(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop")
async def stop_autopilot():
    """Signal the running autopilot to stop after the current step."""
    if session.request_stop():
        return {"success": True, "message": "Stop signal sent."}
    return {"success": False, "message": "Autopilot is not running."}


@router.get("/state")
async def get_autopilot_state():
    """Return whether autopilot is currently running."""
    return {"running": session.running}
