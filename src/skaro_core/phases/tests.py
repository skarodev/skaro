"""Tests phase: structural verification and command execution.

Replaces the old Review phase with concrete, actionable checks:
1. Structural checklist — files from plan exist, test files present.
2. Command execution — task-level commands from verify.yaml + global from config.yaml.

Results are saved to tests.json inside the task directory.
User confirms completion via a separate endpoint.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from skaro_core.phases._command_runner import CommandRunnerMixin
from skaro_core.phases._plan_utils import count_plan_stages
from skaro_core.phases.base import BasePhase, PhaseResult, SKIP_DIRS

# Patterns for detecting test files
_TEST_FILE_PATTERNS = [
    re.compile(r"test[_\-].*\.(py|js|ts|jsx|tsx)$", re.IGNORECASE),
    re.compile(r".*[_\-]test\.(py|js|ts|jsx|tsx)$", re.IGNORECASE),
    re.compile(r".*\.test\.(js|ts|jsx|tsx)$", re.IGNORECASE),
    re.compile(r".*\.spec\.(js|ts|jsx|tsx)$", re.IGNORECASE),
]

class TestsPhase(CommandRunnerMixin, BasePhase):
    phase_name = "tests"

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        if not task:
            return PhaseResult(success=False, message="Task name is required.")

        plan = self.artifacts.find_and_read_task_file(task, "plan.md")
        if not plan:
            return PhaseResult(success=False, message=f"No plan.md for task '{task}'")

        # ── 1. Structural checklist ─────────────────
        checklist = await asyncio.to_thread(self._run_structural_checks, task, plan)

        # ── 2. Collect task-specific commands ────────
        task_commands = self._load_task_commands(task)

        # ── 3. Run task commands ────────────────────
        task_results = await self._run_commands(task_commands)

        # ── 4. Determine overall result ─────────────
        checklist_ok = all(item["passed"] for item in checklist)
        task_cmds_ok = all(cmd["success"] for cmd in task_results)
        passed = checklist_ok and task_cmds_ok

        results = {
            "checklist": checklist,
            "task_commands": task_results,
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
        }

        # ── 5. Save results ─────────────────────────
        self.artifacts.find_and_write_task_file(
            task, "tests.json", json.dumps(results, ensure_ascii=False, indent=2)
        )

        # Remove confirmed marker if re-running tests
        task_dir = self.artifacts.find_task_dir(task)
        confirmed_path = task_dir / "tests-confirmed"
        if confirmed_path.exists():
            confirmed_path.unlink()

        summary_parts = []
        total_checks = len(checklist)
        passed_checks = sum(1 for c in checklist if c["passed"])
        summary_parts.append(f"Checklist: {passed_checks}/{total_checks}")

        if task_results:
            ok = sum(1 for c in task_results if c["success"])
            summary_parts.append(f"Task commands: {ok}/{len(task_results)}")

        return PhaseResult(
            success=True,
            message=" | ".join(summary_parts),
            data=results,
        )

    def confirm(self, task: str) -> PhaseResult:
        """Mark tests as confirmed by the user."""
        task_dir = self.artifacts.find_task_dir(task)
        confirmed_path = task_dir / "tests-confirmed"
        confirmed_path.parent.mkdir(parents=True, exist_ok=True)
        confirmed_path.write_text(
            datetime.now().isoformat(), encoding="utf-8"
        )
        return PhaseResult(success=True, message="Tests confirmed.")

    # ── Verify commands I/O ─────────────────────────

    def _load_task_commands(self, task: str) -> list[dict[str, str]]:
        """Load task-specific verify commands from verify.yaml."""
        task_dir = self.artifacts.find_task_dir(task)
        return self.load_task_commands_static(task_dir)

    @staticmethod
    def load_task_commands_static(task_dir: Path) -> list[dict[str, str]]:
        """Load task verify commands (for API use without full phase init)."""
        verify_path = task_dir / "verify.yaml"
        if not verify_path.exists():
            return []
        try:
            data = yaml.safe_load(verify_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [
                    {"name": str(c.get("name", "")), "command": str(c.get("command", ""))}
                    for c in data
                    if isinstance(c, dict) and c.get("command", "").strip()
                ]
        except (yaml.YAMLError, OSError):
            pass
        return []

    @staticmethod
    def save_task_commands(task_dir: Path, commands: list[dict[str, str]]) -> None:
        """Save task verify commands to verify.yaml."""
        verify_path = task_dir / "verify.yaml"
        verify_path.parent.mkdir(parents=True, exist_ok=True)
        verify_path.write_text(
            yaml.dump(commands, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    # ── Structural checks ───────────────────────────

    def _run_structural_checks(self, task: str, plan: str) -> list[dict]:
        """Run structural verification against the plan."""
        checks: list[dict] = []
        root = self.artifacts.root

        # Scan existing project files (used by test files check)
        existing_files = set()
        for path in root.rglob("*"):
            parts = path.relative_to(root).parts
            # Skip dot-directories (.git, .venv) but NOT dot-files (.env, .eslintrc)
            if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
                continue
            if path.is_file():
                existing_files.add(str(path.relative_to(root)).replace("\\", "/"))

        # Check 1: test files exist in the project
        test_files: list[str] = []
        for fpath in existing_files:
            filename = fpath.split("/")[-1]
            if any(p.match(filename) for p in _TEST_FILE_PATTERNS):
                test_files.append(fpath)

        checks.append({
            "id": "test_files_exist",
            "label": "Test files present",
            "passed": len(test_files) > 0,
            "detail": (
                f"{len(test_files)} test file(s) found"
                if test_files
                else "No test files found"
            ),
        })

        # Check 2: spec.md exists and is non-empty
        spec = self.artifacts.find_and_read_task_file(task, "spec.md")
        spec_filled = bool(spec and len(spec.strip()) > 50)
        checks.append({
            "id": "spec_exists",
            "label": "Specification filled",
            "passed": spec_filled,
            "detail": f"{len(spec)} chars" if spec else "Missing",
        })

        # Check 3: all stages completed
        completed = self.artifacts.find_completed_stages(task)
        plan_stages = count_plan_stages(plan)
        all_stages_done = plan_stages > 0 and len(completed) >= plan_stages
        checks.append({
            "id": "stages_complete",
            "label": "All stages implemented",
            "passed": all_stages_done,
            "detail": f"{len(completed)}/{plan_stages} stages",
        })

        return checks
