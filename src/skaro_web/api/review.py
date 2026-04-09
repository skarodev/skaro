"""Project Review endpoints: project-wide tests and fix chat."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from skaro_core.artifacts import ArtifactManager
from skaro_core.phases.base import BasePhase
from skaro_web.api.deps import broadcast, get_am, get_project_root, get_ws_manager, llm_phase, ConnectionManager
from skaro_web.api.schemas import FileApplyBody, ProjectFixBody

router = APIRouter(prefix="/api/review", tags=["review"])


@router.post("/tests")
async def run_review_tests(
    request: Request,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.project_review import ProjectReviewPhase

    phase = ProjectReviewPhase(project_root=project_root)

    # Wire up streaming: reuse llm:start/chunk/complete events
    # so the BottomPanel shows review test output identically to LLM output.
    await ws.broadcast({"event": "llm:start", "phase": "review"})

    async def _on_chunk(text: str) -> None:
        await ws.broadcast({"event": "llm:chunk", "text": text})

    phase.on_output_chunk = _on_chunk

    try:
        result = await phase.run()
    finally:
        await ws.broadcast({"event": "llm:complete", "phase": "review"})

    await ws.broadcast({"event": "review:completed"})
    return {"success": result.success, "message": result.message, "data": result.data}


@router.get("/results")
async def get_review_results(
    project_root: Path = Depends(get_project_root),
):
    from skaro_core.phases.project_review import ProjectReviewPhase

    phase = ProjectReviewPhase(project_root=project_root)
    results = phase.load_results()
    return {"results": results}


@router.post("/fix")
async def run_project_fix(
    request: Request,
    payload: ProjectFixBody,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.project_fix import ProjectFixPhase
    from skaro_core.phases.base import CancelledByClientError

    phase = ProjectFixPhase(project_root=project_root)
    if payload.provider_override and payload.model_override:
        phase.set_model_override(payload.provider_override, payload.model_override)
    try:
        async with llm_phase(ws, "project_fix", phase, request=request):
            result = await phase.run(
                message=payload.message,
                conversation=payload.conversation,
                scope_tasks=payload.scope_tasks,
                scope_paths=payload.scope_paths,
            )
    except CancelledByClientError:
        return {"success": False, "message": "Cancelled by user", "files": {}, "conversation": []}
    if result.success:
        await ws.broadcast({"event": "review:fix_response"})
    return {
        "success": result.success,
        "message": result.message,
        "files": result.data.get("files", {}),
        "conversation": result.data.get("conversation", []),
        "issue_proposals": result.data.get("issue_proposals", []),
    }


@router.post("/fix/apply")
async def apply_project_fix_file(
    request: Request,
    payload: FileApplyBody,
    project_root: Path = Depends(get_project_root),
):
    try:
        BasePhase._validate_project_path(project_root, payload.filepath)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})

    from skaro_core.phases.project_fix import ProjectFixPhase

    phase = ProjectFixPhase(project_root=project_root)
    result = phase.apply_file(payload.filepath, payload.content)
    await broadcast(request, {"event": "review:fix_applied", "file": payload.filepath})

    from skaro_web.api.git import auto_stage_file

    await auto_stage_file(project_root, payload.filepath)

    return {"success": result.success, "message": result.message}


@router.get("/fix/conversation")
async def get_project_fix_conversation(
    project_root: Path = Depends(get_project_root),
    am: ArtifactManager = Depends(get_am),
):
    from skaro_core.phases.project_fix import ProjectFixPhase

    phase = ProjectFixPhase(project_root=project_root)
    conversation = phase.load_conversation()
    conversation = phase.enrich_conversation(conversation)

    state = am.get_project_state()
    task_names = [ts.name for ts in state.tasks]
    ctx = await asyncio.to_thread(phase._gather_context, task_names)
    ctx_chars = sum(len(v) for v in ctx.values())
    # Auto-scope tokens reported separately so frontend can avoid double-counting
    # when user selects manual scope (which replaces auto-scope)
    auto_scope_chars = await asyncio.to_thread(phase.estimate_auto_scope_chars)
    conv_chars = sum(len(t.get("content", "")) for t in conversation)
    est_tokens = (ctx_chars + conv_chars) // 4
    auto_scope_tokens = auto_scope_chars // 4

    return {
        "conversation": conversation,
        "context_tokens": est_tokens,
        "auto_scope_tokens": auto_scope_tokens,
    }


@router.delete("/fix/conversation")
async def clear_project_fix_conversation(
    project_root: Path = Depends(get_project_root),
):
    from skaro_core.phases.project_fix import ProjectFixPhase

    phase = ProjectFixPhase(project_root=project_root)
    phase.clear_conversation()
    return {"success": True}


@router.get("/scope")
async def get_review_scope(
    am: ArtifactManager = Depends(get_am),
):
    state = am.get_project_state()
    milestones = am.list_milestones()

    tasks_by_milestone: dict[str, list[str]] = {}
    for ts in state.tasks:
        tasks_by_milestone.setdefault(ts.milestone, []).append(ts.name)

    return {
        "milestones": [
            {
                "slug": m,
                "tasks": tasks_by_milestone.get(m, []),
            }
            for m in milestones
        ],
    }
