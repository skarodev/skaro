"""Project Review phase: project-wide structural verification and global commands.

Implements Phase 5 (Review / cross-validation) from methodology.md at the
project level.  Runs:
1. Structural checks -- all tasks complete, devplan milestones closed,
   constitution validated, all task-level tests confirmed.
2. Global verify commands from config.yaml.

Results are saved to .skaro/docs/review-results.json.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from skaro_core.artifacts import Phase, Status
from skaro_core.phases._command_runner import CommandRunnerMixin
from skaro_core.phases.base import BasePhase, PhaseResult

class ProjectReviewPhase(CommandRunnerMixin, BasePhase):
    phase_name = "project_review"

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        checklist = await asyncio.to_thread(self._run_structural_checks)

        # Stream checklist results
        await self._emit("── Structural Checks ──\n")
        for item in checklist:
            mark = "✓" if item["passed"] else "✗"
            await self._emit(f"  {mark} {item['label']}  ({item.get('detail', '')})\n")
        await self._emit("\n")

        global_commands = [
            {"name": vc.name, "command": vc.command}
            for vc in self.config.verify_commands
            if vc.command.strip()
        ]

        if global_commands:
            await self._emit("── Global Verify Commands ──\n")
            global_results = []
            for cmd_def in global_commands:
                if not cmd_def.get("command", "").strip():
                    continue
                await self._emit(f"\n$ {cmd_def['command']}\n")
                result = await self._execute_command(cmd_def["name"], cmd_def["command"])
                global_results.append(result)
                mark = "✓" if result["success"] else "✗"
                await self._emit(f"  {mark} exit code {result['exit_code']}\n")
        else:
            global_results = []

        checklist_ok = all(item["passed"] for item in checklist)
        cmds_ok = all(cmd["success"] for cmd in global_results)
        passed = checklist_ok and cmds_ok

        results = {
            "checklist": checklist,
            "global_commands": global_results,
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
        }

        docs_dir = self.artifacts.skaro / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        results_path = docs_dir / "review-results.json"
        results_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        total_checks = len(checklist)
        passed_checks = sum(1 for c in checklist if c["passed"])
        summary_parts = [f"Checklist: {passed_checks}/{total_checks}"]

        if global_results:
            ok = sum(1 for c in global_results if c["success"])
            summary_parts.append(f"Global commands: {ok}/{len(global_results)}")

        return PhaseResult(
            success=True,
            message=" | ".join(summary_parts),
            data=results,
        )

    def load_results(self) -> dict[str, Any] | None:
        results_path = self.artifacts.skaro / "docs" / "review-results.json"
        if results_path.exists():
            try:
                return json.loads(results_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _run_structural_checks(self) -> list[dict]:
        checks: list[dict] = []
        state = self.artifacts.get_project_state()

        checks.append({
            "id": "constitution_validated",
            "label": "Constitution validated",
            "passed": self.artifacts.is_constitution_validated,
            "detail": "Validated" if self.artifacts.is_constitution_validated else "Not validated",
        })

        checks.append({
            "id": "architecture_reviewed",
            "label": "Architecture reviewed",
            "passed": self.artifacts.is_architecture_reviewed,
            "detail": "Reviewed" if self.artifacts.is_architecture_reviewed else "Not reviewed",
        })

        checks.append({
            "id": "devplan_confirmed",
            "label": "Dev plan confirmed",
            "passed": self.artifacts.is_devplan_confirmed,
            "detail": "Confirmed" if self.artifacts.is_devplan_confirmed else "Not confirmed",
        })

        tasks_total = len(state.tasks)
        tasks_tests_confirmed = sum(
            1 for ts in state.tasks
            if ts.phases.get(Phase.TESTS) == Status.COMPLETE
        )
        all_confirmed = tasks_total > 0 and tasks_tests_confirmed == tasks_total
        checks.append({
            "id": "all_tasks_tests_confirmed",
            "label": "All task tests confirmed",
            "passed": all_confirmed,
            "detail": f"{tasks_tests_confirmed}/{tasks_total} tasks",
        })

        tasks_impl_done = sum(
            1 for ts in state.tasks
            if ts.phases.get(Phase.IMPLEMENT) == Status.COMPLETE
        )
        all_impl = tasks_total > 0 and tasks_impl_done == tasks_total
        checks.append({
            "id": "all_tasks_implemented",
            "label": "All tasks fully implemented",
            "passed": all_impl,
            "detail": f"{tasks_impl_done}/{tasks_total} tasks",
        })

        milestones = self.artifacts.list_milestones()
        milestone_tasks: dict[str, int] = {}
        for ts in state.tasks:
            milestone_tasks[ts.milestone] = milestone_tasks.get(ts.milestone, 0) + 1
        empty_milestones = [m for m in milestones if milestone_tasks.get(m, 0) == 0]
        checks.append({
            "id": "milestones_have_tasks",
            "label": "All milestones have tasks",
            "passed": len(empty_milestones) == 0 and len(milestones) > 0,
            "detail": (
                f"{len(milestones)} milestone(s), all with tasks"
                if not empty_milestones
                else f"Empty: {', '.join(empty_milestones[:5])}"
            ),
        })

        return checks
