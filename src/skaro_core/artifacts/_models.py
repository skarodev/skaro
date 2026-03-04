"""Domain models: Phase, Status, TaskState, ProjectState."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Phase(str, Enum):
    CONSTITUTION = "constitution"
    ARCHITECTURE = "architecture"
    CLARIFY = "clarify"
    PLAN = "plan"
    IMPLEMENT = "implement"
    TESTS = "tests"


class Status(str, Enum):
    NOT_STARTED = "not_started"
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    AWAITING_REVIEW = "awaiting_review"


PHASE_ORDER = list(Phase)


@dataclass
class TaskState:
    """State of a single task within a milestone."""

    name: str
    milestone: str
    phases: dict[Phase, Status]
    current_stage: int
    total_stages: int

    @property
    def current_phase(self) -> Phase:
        for phase in PHASE_ORDER:
            status = self.phases.get(phase, Status.NOT_STARTED)
            if status not in (Status.COMPLETE,):
                return phase
        return Phase.TESTS

    @property
    def progress_percent(self) -> int:
        completed = sum(1 for s in self.phases.values() if s == Status.COMPLETE)
        return int(completed / len(Phase) * 100)


@dataclass
class ProjectState:
    root: Path
    has_constitution: bool
    tasks: list[TaskState]

    @property
    def features(self) -> list[TaskState]:
        """Backward-compatible alias."""
        return self.tasks
