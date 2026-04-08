"""Autopilot orchestrator — iterate tasks through all phases.

Extracted from the monolithic ``generate()`` closure. The class is
independently testable: all dependencies are injected via the constructor.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, AsyncIterator

from skaro_core.artifacts import ArtifactManager
from skaro_core.phases.base import CancelledByClientError
from skaro_web.api.deps import ConnectionManager

from . import runners
from .session import find_task, is_task_done, sse

logger = logging.getLogger("skaro_web.autopilot")


class AutopilotOrchestrator:
    """Runs all incomplete tasks end-to-end, yielding SSE frames."""

    def __init__(
        self,
        project_root: Path,
        am: ArtifactManager,
        ws: ConnectionManager,
        stop_event: asyncio.Event,
        on_finish: Any = None,
    ) -> None:
        self._root = project_root
        self._am = am
        self._ws = ws
        self._stop = stop_event
        self._on_finish = on_finish  # callable to release session

    # ── public API ───────────────────────────────────

    async def run(self) -> AsyncIterator[str]:
        """Async generator that yields SSE frames."""
        started = time.time()
        try:
            yield sse("started", {"timestamp": started})

            pending = self._collect_pending_tasks()

            yield sse("queue", {
                "total": self._total_task_count,
                "pending": len(pending),
                "tasks": [
                    {"name": t["name"], "milestone": t["milestone"]}
                    for t in pending
                ],
            })

            completed = 0

            for idx, task in enumerate(pending):
                if self._stop.is_set():
                    yield sse("stopped", {"reason": "user", "task": task["name"]})
                    return

                task_name = task["name"]
                yield sse("task:start", {
                    "task": task_name,
                    "index": idx,
                    "total": len(pending),
                    "milestone": task["milestone"],
                })

                async for frame in self._run_task(task_name):
                    yield frame
                    # Check if runner signalled a terminal event
                    if frame.startswith("event: error") or frame.startswith("event: stopped"):
                        return

                completed += 1
                yield sse("task:done", {
                    "task": task_name,
                    "index": idx,
                    "completed": completed,
                    "total": len(pending),
                })

                await runners.try_auto_commit(self._root, task_name)

            elapsed = round(time.time() - started, 1)
            yield sse("completed", {
                "completed": completed,
                "total": len(pending),
                "elapsed": elapsed,
            })
        finally:
            if self._on_finish:
                self._on_finish()

    # ── private helpers ──────────────────────────────

    def _collect_pending_tasks(self) -> list[dict]:
        """Build list of incomplete task dicts from current project state."""
        state = self._am.get_project_state()
        all_tasks = []
        for ts in state.tasks:
            all_tasks.append({
                "name": ts.name,
                "milestone": ts.milestone,
                "current_phase": ts.current_phase.value,
                "current_stage": ts.current_stage,
                "total_stages": ts.total_stages,
                "phases": {p.value: s.value for p, s in ts.phases.items()},
            })
        self._total_task_count = len(all_tasks)
        return [t for t in all_tasks if not is_task_done(t)]

    async def _run_task(self, task_name: str) -> AsyncIterator[str]:
        """Execute all phases for a single task, yielding SSE frames."""
        try:
            fresh = find_task(self._am, task_name)
            if fresh is None:
                yield sse("task:skip", {"task": task_name, "reason": "not found"})
                return

            phases = {p.value: s.value for p, s in fresh.phases.items()}

            # ── CLARIFY ──
            async for frame in self._phase_clarify(task_name, phases):
                yield frame

            # ── PLAN ──
            async for frame in self._phase_plan(task_name, phases):
                yield frame

            # ── IMPLEMENT (all stages) ──
            async for frame in self._phase_implement(task_name):
                yield frame

            # ── TESTS ──
            async for frame in self._phase_tests(task_name):
                yield frame

        except CancelledByClientError:
            yield sse("stopped", {"reason": "cancelled", "task": task_name})

        except Exception as exc:
            logger.exception("Autopilot error on task %s", task_name)
            yield sse("error", {"task": task_name, "message": str(exc)})

    # ── individual phase wrappers ────────────────────

    async def _phase_clarify(
        self, task_name: str, phases: dict,
    ) -> AsyncIterator[str]:
        if phases.get("clarify") == "complete":
            return
        if self._stop.is_set():
            yield sse("stopped", {"reason": "user", "task": task_name})
            return

        yield sse("phase:start", {"task": task_name, "phase": "clarify"})
        result = await runners.run_clarify_auto(
            self._root, self._ws, task_name, self._stop,
        )
        if not result["success"]:
            yield sse("error", {
                "task": task_name, "phase": "clarify",
                "message": result["message"],
            })
            return
        yield sse("phase:done", {"task": task_name, "phase": "clarify"})

    async def _phase_plan(
        self, task_name: str, phases: dict,
    ) -> AsyncIterator[str]:
        if phases.get("plan") == "complete":
            return
        if self._stop.is_set():
            yield sse("stopped", {"reason": "user", "task": task_name})
            return

        yield sse("phase:start", {"task": task_name, "phase": "plan"})
        result = await runners.run_plan(
            self._root, self._ws, task_name, self._stop,
        )
        if not result["success"]:
            yield sse("error", {
                "task": task_name, "phase": "plan",
                "message": result["message"],
            })
            return
        yield sse("phase:done", {
            "task": task_name, "phase": "plan",
            "stages": result.get("stages", 0),
        })

    async def _phase_implement(self, task_name: str) -> AsyncIterator[str]:
        while True:
            if self._stop.is_set():
                yield sse("stopped", {"reason": "user", "task": task_name})
                return

            fresh = find_task(self._am, task_name)
            if fresh is None:
                break

            current_stage = fresh.current_stage
            total_stages = fresh.total_stages
            if current_stage >= total_stages:
                break

            next_stage = current_stage + 1
            yield sse("phase:start", {
                "task": task_name, "phase": "implement",
                "stage": next_stage, "total_stages": total_stages,
            })

            result = await runners.run_implement_and_apply(
                self._root, self._ws, task_name, next_stage, self._stop,
            )
            if not result["success"]:
                yield sse("error", {
                    "task": task_name, "phase": "implement",
                    "stage": next_stage, "message": result["message"],
                })
                return

            yield sse("phase:done", {
                "task": task_name, "phase": "implement",
                "stage": next_stage, "total_stages": total_stages,
                "files_count": result.get("files_count", 0),
            })

    async def _phase_tests(self, task_name: str) -> AsyncIterator[str]:
        if self._stop.is_set():
            yield sse("stopped", {"reason": "user", "task": task_name})
            return

        # Refresh phases after implement
        fresh = find_task(self._am, task_name)
        if fresh:
            phases = {p.value: s.value for p, s in fresh.phases.items()}
        else:
            phases = {}

        if phases.get("tests") == "complete":
            return

        yield sse("phase:start", {"task": task_name, "phase": "tests"})
        result = await runners.run_tests(self._root, self._ws, task_name)
        passed = result.get("passed", False)

        if passed:
            await runners.confirm_tests(self._root, self._am, task_name)

        yield sse("phase:done", {
            "task": task_name, "phase": "tests",
            "passed": passed,
            "confirmed": passed,
            "summary": result.get("message", ""),
        })

        if not passed:
            yield sse("error", {
                "task": task_name, "phase": "tests",
                "message": "Tests failed. Autopilot stopped.",
            })
