"""Autopilot session state and shared utilities."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from skaro_core.artifacts import ArtifactManager


@dataclass
class AutopilotSession:
    """Encapsulated autopilot state — one session at a time."""

    running: bool = False
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    def acquire(self) -> asyncio.Event:
        """Mark session as running and return a fresh stop event.

        Raises ``RuntimeError`` if already running.
        """
        if self.running:
            raise RuntimeError("Autopilot is already running.")
        self.running = True
        self.stop_event = asyncio.Event()
        return self.stop_event

    def release(self) -> None:
        """Mark session as no longer running."""
        self.running = False

    def request_stop(self) -> bool:
        """Signal a running session to stop. Returns True if was running."""
        if self.running:
            self.stop_event.set()
            return True
        return False


# Module-level singleton
session = AutopilotSession()


# ── SSE helpers ──────────────────────────────────────


def sse(event: str, data: dict[str, Any]) -> str:
    """Format a single Server-Sent Event frame."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


# ── Task utilities ───────────────────────────────────


def is_task_done(task: dict) -> bool:
    """Check if all four task phases are complete."""
    phases = task.get("phases", {})
    return all(
        phases.get(p) == "complete"
        for p in ("clarify", "plan", "implement", "tests")
    )


def find_task(am: ArtifactManager, task_name: str):
    """Find a TaskState by name, or ``None``."""
    for ts in am.get_project_state().tasks:
        if ts.name == task_name:
            return ts
    return None


def make_cancel_bridge(stop_event: asyncio.Event, phase) -> None:
    """Wire the autopilot stop_event into the phase's ``_cancel_event``.

    When the user presses Stop, the LLM stream is cancelled immediately
    instead of waiting for the current phase to finish.
    """
    phase._cancel_event = stop_event
