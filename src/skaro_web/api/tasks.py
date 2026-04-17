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
    FixFromIssuesBody,
    ImplementBody,
    TaskBatchCreateBody,
    TaskCreateBody,
    TaskFileSaveBody,
    TaskReorderBody,
    VerifyCommandsBody,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Helpers ────────────────────────────────────

def _task_matches(ts, task_name: str) -> bool:
    """Match either a stable task ref or a legacy bare slug."""
    return getattr(ts, "ref", "") == task_name or ts.name == task_name


async def _auto_commit_if_done(
    am: ArtifactManager,
    project_root: Path,
    task_name: str,
) -> bool:
    """Auto-commit if all 4 task phases are complete and config allows it."""
    import logging
    from skaro_core.config import load_config

    logger = logging.getLogger("skaro_web")

    cfg = load_config(project_root)
    if not cfg.git.auto_commit:
        return False

    state = am.get_project_state()
    commit_name = task_name
    for ts in state.tasks:
        if _task_matches(ts, task_name):
            from skaro_core.artifacts._models import Status
            all_done = all(s == Status.COMPLETE for s in ts.phases.values())
            if not all_done:
                return False
            commit_name = ts.name
            break
    else:
        return False

    from skaro_core.git_ops import auto_commit_task

    result = await asyncio.to_thread(
        auto_commit_task, project_root, commit_name, push=cfg.git.auto_push,
    )
    if result:
        logger.info("Auto-committed task completion: %s", task_name)
    return result


# ── CRUD ────────────────────────────────────────

@router.get("")
async def get_tasks(am: ArtifactManager = Depends(get_am)):
    state = am.get_project_state()
    return {
        "tasks": [
            {"name": ts.name, "ref": ts.ref, "milestone": ts.milestone}
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


@router.post("/batch")
async def batch_create_tasks(
    request: Request,
    payload: TaskBatchCreateBody,
    am: ArtifactManager = Depends(get_am),
):
    """Create multiple tasks at once, optionally writing spec.md for each."""
    created: list[dict] = []
    errors: list[str] = []

    for item in payload.tasks:
        name = item.name.strip()
        milestone_slug = item.milestone.strip()

        if not milestone_slug:
            errors.append(f"Task '{name}': milestone is required.")
            continue

        if am.find_task_exists(name):
            errors.append(f"Task '{name}': already exists, skipped.")
            continue

        try:
            am.ensure_task(name, milestone=milestone_slug)
            # Write spec if provided.
            if item.spec.strip():
                am.find_and_write_task_file(name, "spec.md", item.spec)
            created.append({"name": name, "milestone": milestone_slug})
        except Exception as e:
            errors.append(f"Task '{name}': {e}")

    if created:
        await broadcast(request, {
            "event": "tasks:batch_created",
            "count": len(created),
            "tasks": [t["name"] for t in created],
        })

    return {
        "success": len(created) > 0,
        "created": created,
        "errors": errors,
    }


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
        if _task_matches(t, name):
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
        "ref": ts.ref,
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

    # Wire up streaming: reuse the same llm:start/chunk/complete events
    # so the BottomPanel shows test output identically to LLM output.
    await ws.broadcast({"event": "llm:start", "phase": "tests"})

    async def _on_chunk(text: str) -> None:
        await ws.broadcast({"event": "llm:chunk", "text": text})

    phase.on_output_chunk = _on_chunk

    try:
        result = await phase.run(task=name)
    finally:
        await ws.broadcast({"event": "llm:complete", "phase": "tests"})

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
    am: ArtifactManager = Depends(get_am),
):
    """Mark tests as confirmed by the user."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)
    result = phase.confirm(name)
    await broadcast(request, {"event": "tests:confirmed", "task": name})

    # Auto-commit if the task is now fully complete
    await _auto_commit_if_done(am, project_root, name)

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

@router.get("/{name}/tests/issues")
async def get_test_issues(
    name: str,
    am: ArtifactManager = Depends(get_am),
):
    """Extract structured issues from the latest test results."""
    from skaro_core.phases.tests import TestsPhase

    raw = am.find_and_read_task_file(name, "tests.json")
    if not raw:
        return {"issues": [], "has_results": False}

    import json
    try:
        results = json.loads(raw)
    except json.JSONDecodeError:
        return {"issues": [], "has_results": False}

    issues = TestsPhase.extract_issues(results)
    return {"issues": issues, "has_results": True}


@router.post("/{name}/fix/from-issues")
async def fix_from_issues(
    name: str,
    request: Request,
    payload: FixFromIssuesBody,
    project_root: Path = Depends(get_project_root),
    am: ArtifactManager = Depends(get_am),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Start a Fix session from selected test issues.

    Loads the latest test results, filters to selected issue IDs,
    builds a structured prompt with environment context, auto-extracts
    file paths from error output for scope, and sends through Fix flow.
    """
    from skaro_core.phases.fix import FixPhase
    from skaro_core.phases.tests import TestsPhase
    from skaro_core.phases.base import CancelledByClientError

    # Load and parse test results
    raw = am.find_and_read_task_file(name, "tests.json")
    if not raw:
        return {"success": False, "message": "No test results found. Run tests first."}

    import json
    try:
        results = json.loads(raw)
    except json.JSONDecodeError:
        return {"success": False, "message": "Cannot parse tests.json."}

    all_issues = TestsPhase.extract_issues(results)

    # Filter to selected issues (or use all if none specified)
    if payload.issue_ids:
        selected_ids = set(payload.issue_ids)
        selected = [i for i in all_issues if i["id"] in selected_ids]
    else:
        selected = all_issues

    if not selected:
        return {"success": False, "message": "No matching issues found."}

    # Load verify commands for context
    task_dir = am.find_task_dir(name)
    verify_commands = TestsPhase.load_task_commands_static(task_dir)

    # Load execution environment config
    from skaro_core.config import load_config
    config = load_config(project_root)
    exec_env = config.execution_env

    # Detect environment hint from config / project structure
    import platform
    env_parts = [f"OS: {platform.system()} {platform.release()}"]
    if exec_env.mode == "docker" and exec_env.docker_service:
        env_parts.append(
            f"Docker mode: commands run inside container "
            f"(service: {exec_env.docker_service})"
        )
    else:
        docker_compose = project_root / "docker-compose.yml"
        dockerfile = project_root / "Dockerfile"
        if docker_compose.exists() or dockerfile.exists():
            env_parts.append("Docker project detected (Dockerfile/docker-compose.yml present)")
    env_parts.append(f"Project root: {project_root}")
    environment_hint = "; ".join(env_parts)

    # Path mapping hint for LLM
    path_mapping = ""
    docker_workdir = ""
    if exec_env.mode == "docker" and exec_env.workdir:
        docker_workdir = exec_env.workdir
        path_mapping = (
            f"Container path `{exec_env.workdir}/` "
            f"maps to project files on host. "
            f"Paths in error output starting with `{exec_env.workdir}/` "
            f"correspond to files shown in the source context."
        )

    # Build prompt with full context
    message = TestsPhase.build_fix_prompt(
        selected,
        verify_commands=verify_commands,
        environment_hint=environment_hint,
        path_mapping=path_mapping,
    )

    # Auto-scope: extract file paths from error output
    auto_paths = await asyncio.to_thread(
        TestsPhase.extract_file_paths, selected, project_root,
        docker_workdir=docker_workdir,
    )
    # Merge with user-provided scope (user paths take priority)
    all_scope = list(dict.fromkeys(list(payload.scope_paths) + auto_paths))

    phase = FixPhase(project_root=project_root)
    if payload.provider_override and payload.model_override:
        phase.set_model_override(payload.provider_override, payload.model_override)
    try:
        async with llm_phase(ws, "fix", phase, request=request):
            result = await phase.run(
                task=name,
                message=message,
                conversation=payload.conversation,
                scope_paths=all_scope,
            )
    except CancelledByClientError:
        return {"success": False, "message": "Cancelled by user", "files": {}, "conversation": []}

    if result.success:
        await ws.broadcast({"event": "fix:response", "task": name})

    return {
        "success": result.success,
        "message": result.message,
        "files": result.data.get("files", {}),
        "conversation": result.data.get("conversation", []),
        "issues_count": len(selected),
    }


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
    if payload.provider_override and payload.model_override:
        phase.set_model_override(payload.provider_override, payload.model_override)
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
    conversation = phase.enrich_conversation(conversation)
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
