"""Phase runners — each function executes one autopilot phase.

All runners share a common signature pattern:
  - ``project_root``, ``ws``, ``task_name`` are always required
  - ``stop_event`` is passed to cancellable phases
  - Return ``dict[str, Any]`` with at least ``success`` and ``message`` keys
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from skaro_core.artifacts import ArtifactManager
from skaro_core.phases.base import BasePhase
from skaro_web.api.deps import ConnectionManager, llm_phase

from .session import make_cancel_bridge

logger = logging.getLogger("skaro_web.autopilot")


# ── Clarify ──────────────────────────────────────────


async def run_clarify_auto(
    project_root: Path,
    ws: ConnectionManager,
    task_name: str,
    stop_event: asyncio.Event,
) -> dict[str, Any]:
    """Run clarify phase and auto-answer generated questions."""
    from skaro_core.phases.clarify import ClarifyPhase, parse_clarifications

    phase = ClarifyPhase(project_root=project_root)
    make_cancel_bridge(stop_event, phase)

    # Step 1: generate questions
    async with llm_phase(ws, "clarify", phase):
        result = await phase.run(task=task_name)
    if not result.success:
        return {"success": False, "message": result.message}

    # Step 2: auto-answer
    clarify_content = phase.artifacts.find_and_read_task_file(
        task_name, "clarifications.md",
    )
    if not clarify_content:
        return {"success": True, "message": "No clarifications needed."}

    parsed = parse_clarifications(clarify_content)
    if not parsed or not any(not q["answer"].strip() for q in parsed):
        return {"success": True, "message": "All questions already answered."}

    # Ask LLM to pick best answers (with streaming to dashboard)
    auto_answers = await _auto_answer_clarifications(
        phase, ws, task_name, parsed,
    )

    # Step 3: submit answers
    async with llm_phase(ws, "clarify", phase):
        submit_result = await phase.process_answers(
            task_name, clarify_content, auto_answers,
        )

    await ws.broadcast({
        "event": "phase:completed", "task": task_name, "phase": "clarify",
    })
    return {"success": submit_result.success, "message": submit_result.message}


async def _auto_answer_clarifications(
    phase,
    ws: ConnectionManager,
    task_name: str,
    parsed_questions: list[dict],
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

    extra: dict[str, str] = {}
    if spec:
        extra["Specification"] = spec
    if architecture:
        extra["Architecture"] = architecture

    messages = phase._build_messages(prompt, extra)

    async with llm_phase(ws, "clarify-auto-answer", phase):
        response = await phase._stream_collect(messages, task=task_name)

    # Parse answers
    answers: dict[int, str] = {}
    for match in re.finditer(
        r"A(\d+):\s*(.+?)(?=\nA\d+:|\Z)", response, re.DOTALL,
    ):
        num = int(match.group(1))
        ans = match.group(2).strip()
        answers[num] = ans

    # Fill any missing with first option
    for q in parsed_questions:
        if q["num"] not in answers and q.get("options"):
            answers[q["num"]] = "A"

    return answers


# ── Plan ─────────────────────────────────────────────


async def run_plan(
    project_root: Path,
    ws: ConnectionManager,
    task_name: str,
    stop_event: asyncio.Event,
) -> dict[str, Any]:
    """Run plan phase."""
    from skaro_core.phases.plan import PlanPhase

    phase = PlanPhase(project_root=project_root)
    make_cancel_bridge(stop_event, phase)

    async with llm_phase(ws, "plan", phase):
        result = await phase.run(task=task_name)

    await ws.broadcast({
        "event": "phase:completed", "task": task_name, "phase": "plan",
    })
    return {
        "success": result.success,
        "message": result.message,
        "stages": result.data.get("stage_count", 0),
    }


# ── Implement ────────────────────────────────────────


async def run_implement_and_apply(
    project_root: Path,
    ws: ConnectionManager,
    task_name: str,
    stage: int,
    stop_event: asyncio.Event,
) -> dict[str, Any]:
    """Run implement for a single stage and auto-apply all files.

    Skips truncated files to prevent writing incomplete content to disk.
    """
    from skaro_core.phases.implement import ImplementPhase

    phase = ImplementPhase(project_root=project_root)
    make_cancel_bridge(stop_event, phase)

    async with llm_phase(ws, "implement", phase):
        result = await phase.run(task=task_name, stage=stage)

    if not result.success:
        return {"success": False, "message": result.message}

    # Auto-apply generated files (skip truncated)
    files_map = result.data.get("files", {})
    applied = 0
    skipped_truncated: list[str] = []

    for fpath, fdata in files_map.items():
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

            # Auto-stage in git (non-critical)
            try:
                from skaro_web.api.git import auto_stage_file
                await auto_stage_file(project_root, fpath)
            except Exception:
                pass
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


# ── Tests ────────────────────────────────────────────


async def run_tests(
    project_root: Path,
    ws: ConnectionManager,
    task_name: str,
) -> dict[str, Any]:
    """Run tests with streaming output to dashboard."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)

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


async def confirm_tests(
    project_root: Path,
    am: ArtifactManager,
    task_name: str,
) -> None:
    """Confirm tests only when they passed."""
    from skaro_core.phases.tests import TestsPhase

    phase = TestsPhase(project_root=project_root)
    phase.confirm(task_name)

    await try_auto_commit(project_root, task_name)


# ── Git ──────────────────────────────────────────────


async def try_auto_commit(project_root: Path, task_name: str) -> None:
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
