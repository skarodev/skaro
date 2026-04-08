"""Autopilot — run all incomplete tasks end-to-end via SSE.

The endpoint streams Server-Sent Events so the frontend can display
real-time progress in a Mission Control overlay.

Flow per task:
  1. Clarify  — auto-answer via LLM
  2. Plan     — generate implementation plan
  3. Implement — stages 1..N with auto-apply (truncation-safe)
  4. Tests    — run & confirm only if passed

On any error the autopilot stops and reports the failure.
A stop signal (asyncio.Event) lets the user abort mid-flight,
including cancellation of in-progress LLM streams.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from skaro_core.artifacts import ArtifactManager
from skaro_core.phases.base import BasePhase, CancelledByClientError
from skaro_web.api.deps import (
    ConnectionManager,
    get_am,
    get_project_root,
    get_ws_manager,
    llm_phase,
)

logger = logging.getLogger("skaro_web.autopilot")

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


# ═══════════════════════════════════════════════════
# Session state (replaces module-level globals)
# ═══════════════════════════════════════════════════

@dataclass
class _AutopilotSession:
    """Encapsulated autopilot state — one session at a time."""
    running: bool = False
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)

_session = _AutopilotSession()


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


# ═══════════════════════════════════════════════════
# SSE endpoint
# ═══════════════════════════════════════════════════

@router.post("/start")
async def start_autopilot(
    request: Request,
    project_root: Path = Depends(get_project_root),
    am: ArtifactManager = Depends(get_am),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Start autopilot and stream progress via SSE."""
    if _session.running:
        return StreamingResponse(
            iter([_sse("error", {"message": "Autopilot is already running."})]),
            media_type="text/event-stream",
        )

    _session.running = True
    _session.stop_event = asyncio.Event()
    stop_event = _session.stop_event

    async def generate():
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
                    fresh_ts = _find_task(am, task_name)
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
                        result = await _run_clarify_auto(
                            project_root, ws, task_name, stop_event,
                        )
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
                        result = await _run_plan(project_root, ws, task_name, stop_event)
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

                    # ── IMPLEMENT (all stages) ───────────
                    while True:
                        if stop_event.is_set():
                            yield _sse("stopped", {"reason": "user", "task": task_name})
                            return

                        # Refresh from disk on every iteration
                        fresh_ts = _find_task(am, task_name)
                        if fresh_ts is None:
                            break
                        current_stage = fresh_ts.current_stage
                        total_stages = fresh_ts.total_stages

                        if current_stage >= total_stages:
                            break

                        next_stage = current_stage + 1
                        yield _sse("phase:start", {
                            "task": task_name, "phase": "implement",
                            "stage": next_stage, "total_stages": total_stages,
                        })

                        result = await _run_implement_and_apply(
                            project_root, ws, task_name, next_stage, stop_event,
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

                    # ── TESTS ────────────────────────────
                    if stop_event.is_set():
                        yield _sse("stopped", {"reason": "user", "task": task_name})
                        return

                    # Refresh phases after implement
                    fresh_ts = _find_task(am, task_name)
                    if fresh_ts:
                        phases = {p.value: s.value for p, s in fresh_ts.phases.items()}

                    if phases.get("tests") != "complete":
                        yield _sse("phase:start", {"task": task_name, "phase": "tests"})
                        result = await _run_tests(project_root, ws, task_name)
                        passed = result.get("passed", False)

                        if passed:
                            await _confirm_tests(project_root, am, task_name)

                        yield _sse("phase:done", {
                            "task": task_name, "phase": "tests",
                            "passed": passed,
                            "confirmed": passed,
                            "summary": result.get("message", ""),
                        })

                        if not passed:
                            yield _sse("error", {
                                "task": task_name, "phase": "tests",
                                "message": "Tests failed. Autopilot stopped.",
                            })
                            return

                    completed_count += 1
                    yield _sse("task:done", {
                        "task": task_name,
                        "index": idx,
                        "completed": completed_count,
                        "total": len(pending),
                    })

                    # Auto-commit if configured
                    await _try_auto_commit(project_root, task_name)

                except CancelledByClientError:
                    yield _sse("stopped", {"reason": "cancelled", "task": task_name})
                    return

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
            _session.running = False

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
    if _session.running:
        _session.stop_event.set()
        return {"success": True, "message": "Stop signal sent."}
    return {"success": False, "message": "Autopilot is not running."}


@router.get("/state")
async def get_autopilot_state():
    """Return whether autopilot is currently running."""
    return {"running": _session.running}


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _find_task(am: ArtifactManager, task_name: str):
    """Find a TaskState by name, or None."""
    for ts in am.get_project_state().tasks:
        if ts.name == task_name:
            return ts
    return None


def _make_cancel_bridge(stop_event: asyncio.Event, phase) -> None:
    """Wire the autopilot stop_event into the phase's _cancel_event.

    When the user presses Stop, the LLM stream is cancelled immediately
    instead of waiting for the current phase to finish.
    """
    phase._cancel_event = stop_event


# ═══════════════════════════════════════════════════
# Phase runners
# ═══════════════════════════════════════════════════

async def _run_clarify_auto(
    project_root: Path, ws: ConnectionManager,
    task_name: str, stop_event: asyncio.Event,
) -> dict[str, Any]:
    """Run clarify + auto-answer in one go."""
    from skaro_core.phases.clarify import ClarifyPhase, parse_clarifications

    phase = ClarifyPhase(project_root=project_root)
    _make_cancel_bridge(stop_event, phase)

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

    # Ask LLM to pick best answers (with streaming to dashboard)
    auto_answers = await _auto_answer_clarifications(phase, ws, task_name, parsed)

    # Step 3: submit answers
    async with llm_phase(ws, "clarify", phase):
        submit_result = await phase.process_answers(
            task_name, clarify_content, auto_answers,
        )

    await ws.broadcast({"event": "phase:completed", "task": task_name, "phase": "clarify"})
    return {"success": submit_result.success, "message": submit_result.message}


async def _auto_answer_clarifications(
    phase, ws: ConnectionManager,
    task_name: str, parsed_questions: list[dict],
) -> dict[int, str]:
    """Use LLM to auto-answer clarification questions."""
    import re

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

    # Stream through llm_phase so dashboard shows progress and tokens are tracked
    async with llm_phase(ws, "clarify-auto-answer", phase):
        response = await phase._stream_collect(messages, task=task_name)

    # Parse answers
    answers: dict[int, str] = {}
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
    project_root: Path, ws: ConnectionManager,
    task_name: str, stop_event: asyncio.Event,
) -> dict[str, Any]:
    """Run plan phase."""
    from skaro_core.phases.plan import PlanPhase

    phase = PlanPhase(project_root=project_root)
    _make_cancel_bridge(stop_event, phase)

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
    task_name: str, stage: int, stop_event: asyncio.Event,
) -> dict[str, Any]:
    """Run implement for a single stage and auto-apply all files.

    Skips truncated files to prevent writing incomplete content to disk.
    """
    from skaro_core.phases.implement import ImplementPhase

    phase = ImplementPhase(project_root=project_root)
    _make_cancel_bridge(stop_event, phase)

    async with llm_phase(ws, "implement", phase):
        result = await phase.run(task=task_name, stage=stage)

    if not result.success:
        return {"success": False, "message": result.message}

    # Auto-apply generated files (skip truncated)
    files_map = result.data.get("files", {})
    applied = 0
    skipped_truncated: list[str] = []

    for fpath, fdata in files_map.items():
        # Skip truncated files (detected by _find_truncated_file_blocks in implement)
        if fdata.get("truncated"):
            skipped_truncated.append(fpath)
            continue

        content = fdata.get("new", "")
        if not content:
            continue
        try:
            target = BasePhase._validate_project_path(Path(project_root), fpath)
            target.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(target.write_text, content, "utf-8")
            applied += 1

            # Auto-stage in git
            try:
                from skaro_web.api.git import auto_stage_file
                await auto_stage_file(project_root, fpath)
            except Exception:
                pass  # Git staging is non-critical
        except (ValueError, OSError) as exc:
            logger.warning("Failed to apply %s: %s", fpath, exc)

    if skipped_truncated:
        logger.warning(
            "Autopilot skipped %d truncated file(s) in stage %d: %s",
            len(skipped_truncated), stage, ", ".join(skipped_truncated),
        )

    await ws.broadcast({
        "event": "phase:completed", "task": task_name,
        "phase": "implement", "stage": stage,
    })

    msg = f"Applied {applied} files"
    if skipped_truncated:
        msg += f" (skipped {len(skipped_truncated)} truncated)"

    return {"success": True, "message": msg, "files_count": applied}


async def _run_tests(
    project_root: Path, ws: ConnectionManager, task_name: str,
) -> dict[str, Any]:
    """Run tests with streaming output to dashboard."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)

    # Wire up streaming so test output appears in real-time (same as manual flow)
    await ws.broadcast({"event": "llm:start", "phase": "tests"})

    async def _on_chunk(text: str) -> None:
        await ws.broadcast({"event": "llm:chunk", "text": text})

    phase.on_output_chunk = _on_chunk

    try:
        result = await phase.run(task=task_name)
    finally:
        await ws.broadcast({"event": "llm:complete", "phase": "tests"})

    passed = result.data.get("passed", False) if result.success else False

    return {
        "success": result.success,
        "message": result.message,
        "passed": passed,
    }


async def _confirm_tests(
    project_root: Path, am: ArtifactManager, task_name: str,
) -> None:
    """Confirm tests only when they passed."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)
    phase.confirm(task_name)

    # Auto-commit if configured
    await _try_auto_commit(project_root, task_name)


async def _try_auto_commit(project_root: Path, task_name: str) -> None:
    """Auto-commit if configured. Non-critical — errors are logged only."""
    try:
        from skaro_core.config import load_config as _load_cfg
        from skaro_core.git_ops import auto_commit_task

        cfg = _load_cfg(project_root)
        if cfg.git.auto_commit:
            await asyncio.to_thread(
                auto_commit_task,
                project_root,
                task_name,
                push=cfg.git.auto_push,
            )
    except Exception as exc:
        logger.warning("Auto-commit failed for %s: %s", task_name, exc)
