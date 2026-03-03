"""Development Plan endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.deps import broadcast, get_am, get_project_root, get_ws_manager, llm_phase, ConnectionManager
from skaro_web.api.schemas import (
    ContentBody,
    DevPlanConfirmBody,
    DevPlanConfirmUpdateBody,
    DevPlanUpdateBody,
)

router = APIRouter(prefix="/api/devplan", tags=["devplan"])


@router.get("")
async def get_devplan(am: ArtifactManager = Depends(get_am)):
    return {
        "content": am.read_devplan(),
        "has_devplan": am.has_devplan,
        "devplan_confirmed": am.is_devplan_confirmed,
    }


@router.get("/milestones")
async def get_devplan_milestones(am: ArtifactManager = Depends(get_am)):
    """Parse and return milestones from the current devplan.md.

    Used by the frontend when devplan exists but was not generated in this
    session (e.g. imported from an existing project) and milestones are not
    yet in the client store.
    """
    content = am.read_devplan()
    if not content.strip():
        return {"milestones": []}

    from skaro_core.phases._devplan_parser import parse_milestones
    milestones = parse_milestones(content)
    return {"milestones": milestones}


@router.post("/generate")
async def generate_devplan(
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.devplan import DevPlanPhase

    phase = DevPlanPhase(project_root=project_root)
    async with llm_phase(ws, "devplan", phase):
        result = await phase.run()
    await ws.broadcast({"event": "devplan:generated"})
    return {
        "success": result.success,
        "message": result.message,
        "milestones": result.data.get("milestones", []),
        "devplan": result.data.get("devplan", ""),
        "data": result.data,
    }


@router.post("/confirm")
async def confirm_devplan(
    request: Request,
    payload: DevPlanConfirmBody,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    milestones = [m.model_dump() for m in payload.milestones]

    from skaro_core.phases.devplan import DevPlanPhase

    phase = DevPlanPhase(project_root=project_root)
    result = await phase.confirm_plan(milestones)
    if result.success:
        am.mark_devplan_confirmed()
    await broadcast(request, {"event": "devplan:confirmed", "count": len(milestones)})
    return {
        "success": result.success,
        "message": result.message,
        "tasks_created": result.data.get("tasks_created", []),
    }


@router.post("/update")
async def update_devplan(
    request: Request,
    payload: DevPlanUpdateBody = DevPlanUpdateBody(),
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.devplan import DevPlanPhase

    phase = DevPlanPhase(project_root=project_root)
    async with llm_phase(ws, "devplan", phase):
        result = await phase.update(user_guidance=payload.guidance)
    await ws.broadcast({"event": "devplan:update_proposed"})
    return {
        "success": result.success,
        "message": result.message,
        "updated_devplan": result.data.get("updated_devplan", ""),
        "new_milestones": result.data.get("new_milestones", []),
        "data": result.data,
    }


@router.post("/confirm-update")
async def confirm_devplan_update(
    request: Request,
    payload: DevPlanConfirmUpdateBody,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    updated_devplan = payload.updated_devplan
    new_milestones = [m.model_dump() for m in payload.new_milestones]

    from skaro_core.phases.devplan import DevPlanPhase

    phase = DevPlanPhase(project_root=project_root)
    result = await phase.confirm_update(updated_devplan, new_milestones)
    if result.success:
        am.mark_devplan_confirmed()
    await broadcast(request, {"event": "devplan:updated", "new_milestones": len(new_milestones)})
    return {
        "success": result.success,
        "message": result.message,
        "tasks_created": result.data.get("tasks_created", []),
    }


@router.put("")
async def save_devplan(
    request: Request,
    payload: ContentBody,
    am: ArtifactManager = Depends(get_am),
):
    path = am.write_devplan(payload.content)
    await broadcast(request, {"event": "artifact:updated", "artifact": "devplan"})
    return {"success": True, "path": str(path)}
