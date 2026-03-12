"""Task CRUD and phase execution endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from skaro_core.artifacts import ArtifactManager
from skaro_core.phases.base import BasePhase
from skaro_web.api.deps import broadcast, get_am, get_project_root, get_ws_manager, llm_phase, ConnectionManager
from skaro_web.api.schemas import (
    ClarifyAnswerBody,
    ClarifyDraftBody,
    ContentBody,
    FileApplyBody,
    FixBody,
    ImplementBody,
    TaskCreateBody,
    TaskFileSaveBody,
    TaskReorderBody,
    VerifyCommandsBody,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── CRUD ────────────────────────────────────────

@router.get("")
async def get_tasks(am: ArtifactManager = Depends(get_am)):
    state = am.get_project_state()
    return {
        "tasks": [
            {"name": ts.name, "milestone": ts.milestone}
            for ts in state.tasks
        ],
        "milestones": am.list_milestones(),
    }


@router.post("")
async def create_task(
    request: Request,
    payload: TaskCreateBody,
    am: ArtifactManager = Depends(get_am),
):
    name = payload.name.strip()
    milestone_slug = payload.milestone.strip()
    if not milestone_slug:
        return {"success": False, "message": "Milestone is required."}
    am.ensure_task(name, milestone=milestone_slug)
    await broadcast(request, {"event": "task:created", "task": name, "milestone": milestone_slug})
    return {"success": True, "name": name, "milestone": milestone_slug}


@router.put("/reorder")
async def reorder_tasks(
    request: Request,
    payload: TaskReorderBody,
    am: ArtifactManager = Depends(get_am),
):
    """Save custom task order within a milestone."""
    if not am.milestone_exists(payload.milestone):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Milestone '{payload.milestone}' not found."},
        )
    am.save_task_order(payload.milestone, payload.tasks)
    await broadcast(request, {"event": "tasks:reordered", "milestone": payload.milestone})
    return {"success": True}


@router.delete("/{name}")
async def delete_task(
    name: str,
    request: Request,
    am: ArtifactManager = Depends(get_am),
):
    """Delete a task and its directory from disk."""
    resolved = am.resolve_task_safe(name)
    if not resolved:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Task '{name}' not found."},
        )
    milestone, task_slug = resolved
    am.delete_task(milestone, task_slug)
    await broadcast(request, {"event": "task:deleted", "task": name, "milestone": milestone})
    return {"success": True, "name": name, "milestone": milestone}


@router.get("/{name}")
async def get_task_detail(name: str, am: ArtifactManager = Depends(get_am)):
    state = am.get_project_state()
    ts = None
    for t in state.tasks:
        if t.name == name:
            ts = t
            break
    if ts is None:
        return {"success": False, "message": f"Task '{name}' not found."}

    files: dict[str, str] = {}
    for filename in ("spec.md", "clarifications.md", "plan.md", "tasks.md"):
        content = am.find_and_read_task_file(name, filename) or ""
        if content:
            files[filename] = content

    # Include tests.json if exists
    tests_json = am.find_and_read_task_file(name, "tests.json")
    if tests_json:
        files["tests.json"] = tests_json

    stages: dict[int, str] = {}
    for stage_num in am.find_completed_stages(name):
        stage_dir = am.find_stage_dir(name, stage_num)
        notes_path = stage_dir / "AI_NOTES.md"
        if notes_path.exists():
            stages[stage_num] = notes_path.read_text(encoding="utf-8")

    return {
        "name": ts.name,
        "milestone": ts.milestone,
        "files": files,
        "stages": stages,
        "state": {
            "current_phase": ts.current_phase.value,
            "current_stage": ts.current_stage,
            "total_stages": ts.total_stages,
            "progress_percent": ts.progress_percent,
            "phases": {p.value: s.value for p, s in ts.phases.items()},
        },
    }


# ── Task file editing ──────────────────────────────

@router.put("/{name}/file")
async def save_task_file(
    name: str,
    request: Request,
    payload: TaskFileSaveBody,
    am: ArtifactManager = Depends(get_am),
):
    """Save a task file (spec.md, plan.md, etc.)."""
    if not am.find_task_exists(name):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Task '{name}' not found."},
        )
    am.find_and_write_task_file(name, payload.filename, payload.content)
    await broadcast(request, {"event": "task:file_saved", "task": name, "file": payload.filename})
    return {"success": True, "file": payload.filename}


@router.put("/{name}/stage/{stage_num}/notes")
async def save_stage_notes(
    name: str,
    stage_num: int,
    request: Request,
    payload: ContentBody,
    am: ArtifactManager = Depends(get_am),
):
    """Save stage AI_NOTES.md content."""
    resolved = am.resolve_task_safe(name)
    if not resolved:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Task '{name}' not found."},
        )
    am.create_stage_notes(*resolved, stage_num, payload.content)
    await broadcast(request, {"event": "task:stage_saved", "task": name, "stage": stage_num})
    return {"success": True, "stage": stage_num}


# ── Clarify ─────────────────────────────────────

@router.post("/{name}/clarify")
async def run_clarify(
    name: str,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.clarify import ClarifyPhase

    phase = ClarifyPhase(project_root=project_root)
    async with llm_phase(ws, "clarify", phase):
        result = await phase.run(task=name)
    await ws.broadcast({"event": "phase:completed", "task": name, "phase": "clarify"})
    return {"success": result.success, "message": result.message, "data": result.data}


@router.post("/{name}/clarify/answer")
async def answer_clarify(
    name: str,
    payload: ClarifyAnswerBody,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.clarify import ClarifyPhase

    phase = ClarifyPhase(project_root=project_root)
    async with llm_phase(ws, "clarify", phase):
        result = await phase.process_answers(name, payload.questions, payload.parsed_answers())
    await ws.broadcast({"event": "phase:completed", "task": name, "phase": "clarify"})
    return {"success": result.success, "message": result.message}


@router.put("/{name}/clarify/draft")
async def save_clarify_draft(
    name: str,
    payload: ClarifyDraftBody,
    project_root: Path = Depends(get_project_root),
):
    from skaro_core.phases.clarify import ClarifyPhase

    phase = ClarifyPhase(project_root=project_root)
    result = phase.save_draft(name, payload.to_dicts())
    return {"success": result.success, "message": result.message}


# ── Plan ────────────────────────────────────────

@router.post("/{name}/plan")
async def run_plan(
    name: str,
    project_root: Path = Depends(get_project_root),
    am: ArtifactManager = Depends(get_am),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    # Guard: clarification questions must be answered before generating plan
    clarify_content = am.find_and_read_task_file(name, "clarifications.md")
    if clarify_content:
        from skaro_core.phases.clarify import parse_clarifications

        parsed = parse_clarifications(clarify_content)
        unanswered = [q for q in parsed if not q.get("answer", "").strip()]
        if unanswered:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Cannot generate plan: {len(unanswered)} clarification question(s) still unanswered.",
                },
            )
    else:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Cannot generate plan: clarification phase has not been run yet.",
            },
        )

    from skaro_core.phases.plan import PlanPhase

    phase = PlanPhase(project_root=project_root)
    async with llm_phase(ws, "plan", phase):
        result = await phase.run(task=name)
    await ws.broadcast({"event": "phase:completed", "task": name, "phase": "plan"})
    return {"success": result.success, "message": result.message, "data": result.data}


# ── Implement ───────────────────────────────────

@router.post("/{name}/implement")
async def run_implement(
    name: str,
    payload: ImplementBody = ImplementBody(),
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.implement import ImplementPhase

    phase = ImplementPhase(project_root=project_root)
    async with llm_phase(ws, "implement", phase):
        result = await phase.run(task=name, stage=payload.stage, source_files=payload.source_files)
    await ws.broadcast({
        "event": "phase:completed" if result.success else "phase:error",
        "task": name, "phase": "implement", "stage": payload.stage,
    })
    return {"success": result.success, "message": result.message, "data": result.data}


@router.post("/{name}/apply-file")
async def apply_implement_file(
    name: str,
    request: Request,
    payload: FileApplyBody,
    project_root: Path = Depends(get_project_root),
):
    """Apply a single generated file to disk (used by implement review)."""
    try:
        target = BasePhase._validate_project_path(project_root, payload.filepath)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})

    target.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(target.write_text, payload.content, "utf-8")
    await broadcast(request, {"event": "implement:applied", "task": name, "file": payload.filepath})

    # Auto-stage the applied file in git
    from skaro_web.api.git import auto_stage_file

    await auto_stage_file(project_root, payload.filepath)

    return {"success": True, "message": f"Applied: {payload.filepath}"}


# ── Tests ───────────────────────────────────────

@router.post("/{name}/tests")
async def run_tests(
    name: str,
    request: Request,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Run structural checks and verify commands for a task."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)
    result = await phase.run(task=name)
    await ws.broadcast({
        "event": "phase:completed" if result.success else "phase:error",
        "task": name, "phase": "tests",
    })
    return {"success": result.success, "message": result.message, "data": result.data}


@router.post("/{name}/tests/confirm")
async def confirm_tests(
    name: str,
    request: Request,
    project_root: Path = Depends(get_project_root),
):
    """Mark tests as confirmed by the user."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)
    result = phase.confirm(name)
    await broadcast(request, {"event": "tests:confirmed", "task": name})
    return {"success": result.success, "message": result.message}


@router.get("/{name}/tests/commands")
async def get_verify_commands(
    name: str,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    """Return task-level verify commands from verify.yaml."""
    from skaro_core.phases.tests import TestsPhase

    task_dir = am.find_task_dir(name)
    commands = TestsPhase.load_task_commands_static(task_dir)
    return {"commands": commands}


@router.put("/{name}/tests/commands")
async def save_verify_commands(
    name: str,
    payload: VerifyCommandsBody,
    am: ArtifactManager = Depends(get_am),
):
    """Save task-level verify commands to verify.yaml."""
    from skaro_core.phases.tests import TestsPhase

    task_dir = am.find_task_dir(name)
    commands = [c.model_dump() for c in payload.commands]
    TestsPhase.save_task_commands(task_dir, commands)
    return {"success": True, "count": len(commands)}


@router.post("/{name}/stage/{stage_num}/complete")
async def complete_stage(
    name: str,
    stage_num: int,
    request: Request,
    am: ArtifactManager = Depends(get_am),
):
    resolved = am.resolve_task_safe(name)
    if resolved:
        stage_d = am.stage_dir(*resolved, stage_num)
        if not (stage_d / "AI_NOTES.md").exists():
            am.create_stage_notes(
                *resolved, stage_num, f"# AI_NOTES — Stage {stage_num}\n\nManually completed."
            )
    await broadcast(request, {"event": "stage:completed", "task": name, "stage": stage_num})
    return {"success": True}


# ── Fix ─────────────────────────────────────────

@router.post("/{name}/fix")
async def run_fix(
    name: str,
    request: Request,
    payload: FixBody,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    from skaro_core.phases.fix import FixPhase
    from skaro_core.phases.base import CancelledByClientError

    phase = FixPhase(project_root=project_root)
    try:
        async with llm_phase(ws, "fix", phase, request=request):
            result = await phase.run(task=name, message=payload.message, conversation=payload.conversation, scope_paths=payload.scope_paths)
    except CancelledByClientError:
        return {"success": False, "message": "Cancelled by user", "files": {}, "conversation": []}
    if result.success:
        await ws.broadcast({"event": "fix:response", "task": name})
    return {
        "success": result.success,
        "message": result.message,
        "files": result.data.get("files", {}),
        "conversation": result.data.get("conversation", []),
    }


@router.post("/{name}/fix/apply")
async def apply_fix_file(
    name: str,
    request: Request,
    payload: FileApplyBody,
    project_root: Path = Depends(get_project_root),
):
    try:
        BasePhase._validate_project_path(project_root, payload.filepath)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})

    from skaro_core.phases.fix import FixPhase

    phase = FixPhase(project_root=project_root)
    result = phase.apply_file(name, payload.filepath, payload.content)
    await broadcast(request, {"event": "fix:applied", "task": name, "file": payload.filepath})

    # Auto-stage the applied file in git
    from skaro_web.api.git import auto_stage_file

    await auto_stage_file(project_root, payload.filepath)

    return {"success": result.success, "message": result.message}


@router.get("/{name}/fix/log")
async def get_fix_log(name: str, am: ArtifactManager = Depends(get_am)):
    content = am.find_and_read_task_file(name, "fix-log.md")
    return {"content": content or ""}


@router.get("/{name}/fix/conversation")
async def get_fix_conversation(
    name: str,
    project_root: Path = Depends(get_project_root),
):
    from skaro_core.phases.fix import FixPhase

    phase = FixPhase(project_root=project_root)
    conversation = phase.load_conversation(name)
    ctx = await asyncio.to_thread(phase._gather_context, name)
    ctx_chars = sum(len(v) for v in ctx.values())
    conv_chars = sum(len(t.get("content", "")) for t in conversation)
    est_tokens = (ctx_chars + conv_chars) // 4
    return {
        "conversation": conversation,
        "context_tokens": est_tokens,
    }


@router.delete("/{name}/fix/conversation")
async def clear_fix_conversation(
    name: str,
    project_root: Path = Depends(get_project_root),
):
    from skaro_core.phases.fix import FixPhase

    phase = FixPhase(project_root=project_root)
    phase.clear_conversation(name)
    return {"success": True}
