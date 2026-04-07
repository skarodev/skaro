"""Autopilot — run all incomplete tasks end-to-end via SSE.

The endpoint streams Server-Sent Events so the frontend can display
real-time progress in a Mission Control overlay.

Flow per task:
  1. Clarify  — auto-answer via LLM
  2. Plan     — generate implementation plan
  3. Implement — stages 1..N with auto-apply
  4. Tests    — run & auto-confirm if passed

On any error the autopilot stops and reports the failure.
A stop signal (asyncio.Event) lets the user abort mid-flight.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from skaro_core.artifacts import ArtifactManager
from skaro_core.phases.base import BasePhase
from skaro_web.api.deps import (
    ConnectionManager,
    get_am,
    get_project_root,
    get_ws_manager,
    llm_phase,
)

logger = logging.getLogger("skaro_web.autopilot")

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])

# ── Global stop event (one autopilot session at a time) ──────────
_stop_event: asyncio.Event | None = None
_running: bool = False


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE frame."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _is_task_done(task: dict) -> bool:
    """Check if all four task phases are complete."""
    phases = task.get("phases", {})
    return all(
        phases.get(p) == "complete"
        for p in ("clarify", "plan", "implement", "tests")
    )


# ── SSE endpoint ─────────────────────────────────────────────────

@router.post("/start")
async def start_autopilot(
    request: Request,
    project_root: Path = Depends(get_project_root),
    am: ArtifactManager = Depends(get_am),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Start autopilot and stream progress via SSE."""
    global _stop_event, _running

    if _running:
        return StreamingResponse(
            iter([_sse("error", {"message": "Autopilot is already running."})]),
            media_type="text/event-stream",
        )

    _stop_event = asyncio.Event()
    _running = True

    # Capture in local var for closure (avoids Python 3.13 global scoping issue)
    stop_event = _stop_event

    async def generate():
        global _running, _stop_event
        started = time.time()
        try:
            yield _sse("started", {"timestamp": started})

            # Gather incomplete tasks in milestone/order
            state = am.get_project_state()
            all_tasks = []
            for ts in state.tasks:
                task_dict = {
                    "name": ts.name,
                    "milestone": ts.milestone,
                    "current_phase": ts.current_phase.value,
                    "current_stage": ts.current_stage,
                    "total_stages": ts.total_stages,
                    "phases": {p.value: s.value for p, s in ts.phases.items()},
                }
                all_tasks.append(task_dict)

            pending = [t for t in all_tasks if not _is_task_done(t)]

            yield _sse("queue", {
                "total": len(all_tasks),
                "pending": len(pending),
                "tasks": [{"name": t["name"], "milestone": t["milestone"]} for t in pending],
            })

            completed_count = 0

            for idx, task in enumerate(pending):
                if stop_event.is_set():
                    yield _sse("stopped", {"reason": "user", "task": task["name"]})
                    return

                task_name = task["name"]
                yield _sse("task:start", {
                    "task": task_name,
                    "index": idx,
                    "total": len(pending),
                    "milestone": task["milestone"],
                })

                try:
                    # ── Refresh task state from disk ──
                    fresh_state = am.get_project_state()
                    fresh_ts = None
                    for ts in fresh_state.tasks:
                        if ts.name == task_name:
                            fresh_ts = ts
                            break
                    if fresh_ts is None:
                        yield _sse("task:skip", {"task": task_name, "reason": "not found"})
                        continue

                    phases = {p.value: s.value for p, s in fresh_ts.phases.items()}
                    current_stage = fresh_ts.current_stage
                    total_stages = fresh_ts.total_stages

                    # ── CLARIFY ──────────────────────────
                    if phases.get("clarify") != "complete":
                        if stop_event.is_set():
                            yield _sse("stopped", {"reason": "user", "task": task_name})
                            return

                        yield _sse("phase:start", {"task": task_name, "phase": "clarify"})
                        result = await _run_clarify_auto(project_root, ws, task_name)
                        if not result["success"]:
                            yield _sse("error", {
                                "task": task_name, "phase": "clarify",
                                "message": result["message"],
                            })
                            return
                        yield _sse("phase:done", {"task": task_name, "phase": "clarify"})

                    # ── PLAN ─────────────────────────────
                    if phases.get("plan") != "complete":
                        if stop_event.is_set():
                            yield _sse("stopped", {"reason": "user", "task": task_name})
                            return

                        yield _sse("phase:start", {"task": task_name, "phase": "plan"})
                        result = await _run_plan(project_root, ws, task_name)
                        if not result["success"]:
                            yield _sse("error", {
                                "task": task_name, "phase": "plan",
                                "message": result["message"],
                            })
                            return
                        yield _sse("phase:done", {
                            "task": task_name, "phase": "plan",
                            "stages": result.get("stages", 0),
                        })

                        # Refresh stages count after plan
                        fresh_state = am.get_project_state()
                        for ts in fresh_state.tasks:
                            if ts.name == task_name:
                                total_stages = ts.total_stages
                                current_stage = ts.current_stage
                                break

                    # ── IMPLEMENT (all stages) ───────────
                    if stop_event.is_set():
                        yield _sse("stopped", {"reason": "user", "task": task_name})
                        return

                    # Refresh current state
                    fresh_state = am.get_project_state()
                    for ts in fresh_state.tasks:
                        if ts.name == task_name:
                            current_stage = ts.current_stage
                            total_stages = ts.total_stages
                            break

                    while current_stage < total_stages:
                        if stop_event.is_set():
                            yield _sse("stopped", {"reason": "user", "task": task_name})
                            return

                        next_stage = current_stage + 1
                        yield _sse("phase:start", {
                            "task": task_name, "phase": "implement",
                            "stage": next_stage, "total_stages": total_stages,
                        })

                        result = await _run_implement_and_apply(
                            project_root, ws, task_name, next_stage,
                        )
                        if not result["success"]:
                            yield _sse("error", {
                                "task": task_name, "phase": "implement",
                                "stage": next_stage,
                                "message": result["message"],
                            })
                            return

                        yield _sse("phase:done", {
                            "task": task_name, "phase": "implement",
                            "stage": next_stage, "total_stages": total_stages,
                            "files_count": result.get("files_count", 0),
                        })
                        current_stage = next_stage

                    # ── TESTS ────────────────────────────
                    if stop_event.is_set():
                        yield _sse("stopped", {"reason": "user", "task": task_name})
                        return

                    # Refresh phases after implement
                    fresh_state = am.get_project_state()
                    for ts in fresh_state.tasks:
                        if ts.name == task_name:
                            phases = {p.value: s.value for p, s in ts.phases.items()}
                            break

                    if phases.get("tests") != "complete":
                        yield _sse("phase:start", {"task": task_name, "phase": "tests"})
                        result = await _run_tests_and_confirm(project_root, task_name)
                        yield _sse("phase:done", {
                            "task": task_name, "phase": "tests",
                            "passed": result.get("passed", False),
                            "summary": result.get("message", ""),
                        })

                    completed_count += 1
                    yield _sse("task:done", {
                        "task": task_name,
                        "index": idx,
                        "completed": completed_count,
                        "total": len(pending),
                    })

                    # Auto-commit if configured
                    try:
                        from skaro_core.config import load_config as _load_cfg
                        from skaro_core.git_ops import auto_commit_task

                        _cfg = _load_cfg(project_root)
                        if _cfg.git.auto_commit:
                            committed = await asyncio.to_thread(
                                auto_commit_task,
                                project_root,
                                task_name,
                                push=_cfg.git.auto_push,
                            )
                            if committed:
                                yield _sse("git:committed", {"task": task_name})
                    except Exception as git_exc:
                        logger.warning("Autopilot auto-commit failed for %s: %s", task_name, git_exc)

                except Exception as exc:
                    logger.exception("Autopilot error on task %s", task_name)
                    yield _sse("error", {
                        "task": task_name,
                        "message": str(exc),
                    })
                    return

            elapsed = round(time.time() - started, 1)
            yield _sse("completed", {
                "completed": completed_count,
                "total": len(pending),
                "elapsed": elapsed,
            })
        finally:
            _running = False
            _stop_event = None

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop")
async def stop_autopilot():
    """Signal the running autopilot to stop after the current step."""
    global _stop_event
    if _stop_event is not None:
        _stop_event.set()
        return {"success": True, "message": "Stop signal sent."}
    return {"success": False, "message": "Autopilot is not running."}


@router.get("/state")
async def get_autopilot_state():
    """Return whether autopilot is currently running."""
    return {"running": _running}


# ═══════════════════════════════════════════════════
# Phase runners (reuse existing phase classes)
# ═══════════════════════════════════════════════════

async def _run_clarify_auto(
    project_root: Path, ws: ConnectionManager, task_name: str,
) -> dict[str, Any]:
    """Run clarify + auto-answer in one go."""
    from skaro_core.phases.clarify import ClarifyPhase, parse_clarifications

    phase = ClarifyPhase(project_root=project_root)

    # Step 1: generate questions
    async with llm_phase(ws, "clarify", phase):
        result = await phase.run(task=task_name)
    if not result.success:
        return {"success": False, "message": result.message}

    # Step 2: auto-answer
    clarify_content = phase.artifacts.find_and_read_task_file(task_name, "clarifications.md")
    if not clarify_content:
        return {"success": True, "message": "No clarifications needed."}

    parsed = parse_clarifications(clarify_content)
    if not parsed or not any(not q["answer"].strip() for q in parsed):
        return {"success": True, "message": "All questions already answered."}

    # Ask LLM to pick best answers
    auto_answers = await _auto_answer_clarifications(phase, task_name, parsed)

    # Step 3: submit answers
    async with llm_phase(ws, "clarify", phase):
        submit_result = await phase.process_answers(
            task_name, clarify_content, auto_answers,
        )

    await ws.broadcast({"event": "phase:completed", "task": task_name, "phase": "clarify"})
    return {"success": submit_result.success, "message": submit_result.message}


async def _auto_answer_clarifications(
    phase, task_name: str, parsed_questions: list[dict],
) -> dict[int, str]:
    """Use LLM to auto-answer clarification questions."""
    spec = phase.artifacts.find_and_read_task_file(task_name, "spec.md") or ""
    architecture = phase.artifacts.read_architecture()

    questions_text = []
    for q in parsed_questions:
        entry = f"Q{q['num']}: {q['question']}"
        if q.get("context"):
            entry += f"\nContext: {q['context']}"
        if q.get("options"):
            for i, opt in enumerate(q["options"]):
                letter = chr(65 + i)  # A, B, C...
                entry += f"\n  {letter}) {opt}"
        questions_text.append(entry)

    prompt = (
        "You are an expert software architect acting as autopilot.\n"
        "Based on the specification and architecture, choose the BEST answer "
        "for each clarification question.\n\n"
        "Rules:\n"
        "- For questions with options, respond with the option letter (A, B, C, etc.)\n"
        "- For open questions, give a concise, practical answer\n"
        "- Choose the option that best aligns with the architecture and spec\n"
        "- Prefer simpler, more maintainable approaches when options are equally viable\n\n"
        "Format your response as:\n"
        "A1: <answer>\n"
        "A2: <answer>\n"
        "...\n\n"
        "Questions:\n" + "\n\n".join(questions_text)
    )

    extra = {}
    if spec:
        extra["Specification"] = spec
    if architecture:
        extra["Architecture"] = architecture

    messages = phase._build_messages(prompt, extra)
    response = await phase._stream_collect(messages, task=task_name)

    # Parse answers
    answers: dict[int, str] = {}
    import re
    for match in re.finditer(r"A(\d+):\s*(.+?)(?=\nA\d+:|\Z)", response, re.DOTALL):
        num = int(match.group(1))
        ans = match.group(2).strip()
        answers[num] = ans

    # Fill any missing with first option
    for q in parsed_questions:
        if q["num"] not in answers and q.get("options"):
            answers[q["num"]] = "A"

    return answers


async def _run_plan(
    project_root: Path, ws: ConnectionManager, task_name: str,
) -> dict[str, Any]:
    """Run plan phase."""
    from skaro_core.phases.plan import PlanPhase

    phase = PlanPhase(project_root=project_root)
    async with llm_phase(ws, "plan", phase):
        result = await phase.run(task=task_name)

    await ws.broadcast({"event": "phase:completed", "task": task_name, "phase": "plan"})
    return {
        "success": result.success,
        "message": result.message,
        "stages": result.data.get("stage_count", 0),
    }


async def _run_implement_and_apply(
    project_root: Path, ws: ConnectionManager,
    task_name: str, stage: int,
) -> dict[str, Any]:
    """Run implement for a single stage and auto-apply all files."""
    from skaro_core.phases.implement import ImplementPhase

    phase = ImplementPhase(project_root=project_root)
    async with llm_phase(ws, "implement", phase):
        result = await phase.run(task=task_name, stage=stage)

    if not result.success:
        return {"success": False, "message": result.message}

    # Auto-apply all generated files
    files_map = result.data.get("files", {})
    applied = 0
    for fpath, fdata in files_map.items():
        content = fdata.get("new", "")
        if not content:
            continue
        try:
            target = BasePhase._validate_project_path(Path(project_root), fpath)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            applied += 1

            # Auto-stage in git
            try:
                from skaro_web.api.git import auto_stage_file
                await auto_stage_file(project_root, fpath)
            except Exception:
                pass  # Git staging is non-critical
        except (ValueError, OSError) as exc:
            logger.warning("Failed to apply %s: %s", fpath, exc)

    await ws.broadcast({
        "event": "phase:completed", "task": task_name,
        "phase": "implement", "stage": stage,
    })
    return {"success": True, "message": f"Applied {applied} files", "files_count": applied}


async def _run_tests_and_confirm(
    project_root: Path, task_name: str,
) -> dict[str, Any]:
    """Run tests and auto-confirm."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)
    result = await phase.run(task=task_name)

    passed = result.data.get("passed", False) if result.success else False

    # Auto-confirm regardless (autopilot mode)
    phase.confirm(task_name)

    return {
        "success": result.success,
        "message": result.message,
        "passed": passed,
    }
