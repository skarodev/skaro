"""Tasks mixin: task CRUD, files, stages, slug resolution, state."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from skaro_core.artifacts._models import (
    Phase,
    ProjectState,
    Status,
    TaskState,
)


class TasksMixin:
    """Manages tasks within milestones: CRUD, files, stages, state."""

    # ── Task CRUD ───────────────────────────────

    def task_dir(self, milestone: str, task: str) -> Path:
        return self.milestone_dir(milestone) / task

    def task_exists(self, milestone: str, task: str) -> bool:
        return self.task_dir(milestone, task).is_dir()

    def create_task(self, milestone: str, task: str) -> Path:
        """Create task directory with spec.md from template."""
        tdir = self.task_dir(milestone, task)
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "stages").mkdir(exist_ok=True)

        spec_template = self.skaro / "templates" / "spec-template.md"
        spec_path = tdir / "spec.md"
        if spec_template.exists():
            content = spec_template.read_text(encoding="utf-8")
            content = content.replace("<название задачи>", task)
            content = content.replace("<название фичи>", task)
            spec_path.write_text(content, encoding="utf-8")
        else:
            spec_path.write_text(f"# Specification: {task}\n", encoding="utf-8")

        return tdir

    def ensure_task(self, task: str, *, milestone: str) -> Path:
        """Create milestone (if missing) and task (if missing). Idempotent."""
        if not self.milestone_exists(milestone):
            self.create_milestone(milestone)
        if not self.task_exists(milestone, task):
            return self.create_task(milestone, task)
        return self.task_dir(milestone, task)

    def list_tasks(self, milestone: str) -> list[str]:
        """List task slugs within a milestone, respecting order.json."""
        mdir = self.milestone_dir(milestone)
        if not mdir.is_dir():
            return []
        all_tasks = sorted(
            d.name
            for d in mdir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )
        order = self.get_task_order(milestone)
        if not order:
            return all_tasks
        task_set = set(all_tasks)
        ordered = [t for t in order if t in task_set]
        remaining = [t for t in all_tasks if t not in set(order)]
        return ordered + remaining

    def delete_task(self, milestone: str, task: str) -> bool:
        """Delete task directory from disk. Returns True if deleted."""
        tdir = self.task_dir(milestone, task)
        if tdir.is_dir():
            shutil.rmtree(tdir)
            self._remove_from_order(milestone, task)
            return True
        return False

    # ── Task ordering ───────────────────────────

    def get_task_order(self, milestone: str) -> list[str]:
        """Read order.json from milestone dir."""
        order_path = self.milestone_dir(milestone) / "order.json"
        if order_path.exists():
            try:
                return json.loads(order_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def save_task_order(self, milestone: str, names: list[str]) -> None:
        """Save task order to order.json in milestone dir."""
        order_path = self.milestone_dir(milestone) / "order.json"
        order_path.parent.mkdir(parents=True, exist_ok=True)
        order_path.write_text(
            json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _remove_from_order(self, milestone: str, task: str) -> None:
        """Remove a task from order.json if present."""
        order = self.get_task_order(milestone)
        if task in order:
            order.remove(task)
            self.save_task_order(milestone, order)

    def list_all_tasks(self) -> list[tuple[str, str]]:
        """List all (milestone, task) pairs across all milestones."""
        result: list[tuple[str, str]] = []
        for ms in self.list_milestones():
            for task in self.list_tasks(ms):
                result.append((ms, task))
        return result

    # ── Task files ──────────────────────────────

    def read_task_file(self, milestone: str, task: str, filename: str) -> str:
        path = self.task_dir(milestone, task) / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_task_file(
        self, milestone: str, task: str, filename: str, content: str
    ) -> Path:
        path = self.task_dir(milestone, task) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    # ── Stages ──────────────────────────────────

    def stage_dir(self, milestone: str, task: str, stage: int) -> Path:
        return self.task_dir(milestone, task) / "stages" / f"stage-{stage:02d}"

    def create_stage_notes(
        self, milestone: str, task: str, stage: int, content: str
    ) -> Path:
        sdir = self.stage_dir(milestone, task, stage)
        sdir.mkdir(parents=True, exist_ok=True)
        path = sdir / "AI_NOTES.md"
        path.write_text(content, encoding="utf-8")
        return path

    def get_completed_stages(self, milestone: str, task: str) -> list[int]:
        stages_dir = self.task_dir(milestone, task) / "stages"
        if not stages_dir.is_dir():
            return []
        completed = []
        for d in sorted(stages_dir.iterdir()):
            if d.is_dir() and (d / "AI_NOTES.md").exists():
                try:
                    num = int(d.name.split("-")[1])
                    completed.append(num)
                except (IndexError, ValueError):
                    continue
        return completed

    # ── Task state ──────────────────────────────

    def _count_planned_stages(self, milestone: str, task: str) -> int:
        plan = self.read_task_file(milestone, task, "plan.md")
        if not plan:
            return 0
        count = 0
        for line in plan.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith(("#", "##", "###")) and any(
                w in stripped for w in ["этап", "stage"]
            ):
                count += 1
        return max(count, 1)

    def get_task_state(self, milestone: str, task: str) -> TaskState:
        tdir = self.task_dir(milestone, task)
        phases: dict[Phase, Status] = {}

        phases[Phase.CONSTITUTION] = (
            Status.COMPLETE if self.has_constitution else Status.NOT_STARTED
        )

        if self.invariants_path.exists():
            phases[Phase.ARCHITECTURE] = Status.COMPLETE
        else:
            phases[Phase.ARCHITECTURE] = Status.NOT_STARTED

        if (tdir / "clarifications.md").exists():
            # Clarify is complete only when ALL questions have answers
            from skaro_core.phases.clarify import parse_clarifications

            clarify_text = (tdir / "clarifications.md").read_text(encoding="utf-8")
            parsed_qs = parse_clarifications(clarify_text)
            if parsed_qs and all(q.get("answer", "").strip() for q in parsed_qs):
                phases[Phase.CLARIFY] = Status.COMPLETE
            elif parsed_qs:
                phases[Phase.CLARIFY] = Status.IN_PROGRESS
            else:
                # File exists but no parseable questions — treat as complete
                phases[Phase.CLARIFY] = Status.COMPLETE
        else:
            phases[Phase.CLARIFY] = Status.NOT_STARTED

        if (tdir / "plan.md").exists():
            phases[Phase.PLAN] = Status.COMPLETE
        elif (tdir / "tasks.md").exists():
            phases[Phase.PLAN] = Status.IN_PROGRESS
        else:
            phases[Phase.PLAN] = Status.NOT_STARTED

        completed_stages = self.get_completed_stages(milestone, task)
        total_stages = self._count_planned_stages(milestone, task)
        if total_stages > 0 and len(completed_stages) >= total_stages:
            phases[Phase.IMPLEMENT] = Status.COMPLETE
        elif completed_stages:
            phases[Phase.IMPLEMENT] = Status.IN_PROGRESS
        else:
            phases[Phase.IMPLEMENT] = Status.NOT_STARTED

        # Tests phase: confirmed marker file
        tests_confirmed = tdir / "tests-confirmed"
        tests_results = tdir / "tests.json"
        if tests_confirmed.exists():
            phases[Phase.TESTS] = Status.COMPLETE
        elif tests_results.exists():
            phases[Phase.TESTS] = Status.IN_PROGRESS
        else:
            phases[Phase.TESTS] = Status.NOT_STARTED

        return TaskState(
            name=task,
            milestone=milestone,
            phases=phases,
            current_stage=len(completed_stages),
            total_stages=total_stages,
        )

    def get_project_state(self) -> ProjectState:
        all_tasks = [
            self.get_task_state(ms, task) for ms, task in self.list_all_tasks()
        ]
        return ProjectState(
            root=self.root,
            has_constitution=self.has_constitution,
            tasks=all_tasks,
        )

    # ── Slug resolvers ──────────────────────────

    def resolve_task(self, task_slug: str) -> tuple[str, str]:
        """Find (milestone, task) by slug. Raises FileNotFoundError."""
        for ms in self.list_milestones():
            if self.task_exists(ms, task_slug):
                return ms, task_slug
        raise FileNotFoundError(f"Task '{task_slug}' not found in any milestone.")

    def resolve_task_safe(self, task_slug: str) -> tuple[str, str] | None:
        """Like resolve_task but returns None instead of raising."""
        try:
            return self.resolve_task(task_slug)
        except FileNotFoundError:
            return None

    def find_task_dir(self, task_slug: str) -> Path:
        resolved = self.resolve_task_safe(task_slug)
        if resolved:
            return self.task_dir(*resolved)
        milestones = self.list_milestones()
        if milestones:
            return self.milestone_dir(milestones[0]) / task_slug
        return self.milestones_dir / "_unassigned" / task_slug

    def find_task_exists(self, task_slug: str) -> bool:
        return self.resolve_task_safe(task_slug) is not None

    def find_and_read_task_file(self, task_slug: str, filename: str) -> str:
        resolved = self.resolve_task_safe(task_slug)
        if resolved:
            return self.read_task_file(*resolved, filename)
        return ""

    def find_and_write_task_file(
        self, task_slug: str, filename: str, content: str
    ) -> Path:
        resolved = self.resolve_task_safe(task_slug)
        if resolved:
            return self.write_task_file(*resolved, filename, content)
        milestones = self.list_milestones()
        ms = milestones[0] if milestones else "00-unassigned"
        if not self.milestone_exists(ms):
            self.create_milestone(ms, title="Unassigned")
        return self.write_task_file(ms, task_slug, filename, content)

    def find_task_state(self, task_slug: str) -> TaskState:
        resolved = self.resolve_task_safe(task_slug)
        if resolved:
            return self.get_task_state(*resolved)
        return TaskState(
            name=task_slug, milestone="", phases={}, current_stage=0, total_stages=0
        )

    def find_completed_stages(self, task_slug: str) -> list[int]:
        resolved = self.resolve_task_safe(task_slug)
        if resolved:
            return self.get_completed_stages(*resolved)
        return []

    def find_stage_dir(self, task_slug: str, stage: int) -> Path:
        resolved = self.resolve_task_safe(task_slug)
        if resolved:
            return self.stage_dir(*resolved, stage)
        return (
            self.milestones_dir
            / "_unassigned"
            / task_slug
            / "stages"
            / f"stage-{stage:02d}"
        )

    def find_and_create_stage_notes(
        self, task_slug: str, stage: int, content: str
    ) -> Path:
        resolved = self.resolve_task_safe(task_slug)
        if resolved:
            return self.create_stage_notes(*resolved, stage, content)
        raise FileNotFoundError(f"Task '{task_slug}' not found in any milestone.")
