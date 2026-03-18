"""Plan phase: decompose task into stages with dependencies."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import yaml

from skaro_core.phases._plan_utils import count_plan_stages
from skaro_core.phases.base import BasePhase, PhaseResult, strip_outer_md_fence, unwrap_markdown_fences


class PlanPhase(BasePhase):
    phase_name = "plan"

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        if not task:
            return PhaseResult(success=False, message="Task name is required.")

        spec = self.artifacts.find_and_read_task_file(task, "spec.md")
        if not spec:
            return PhaseResult(success=False, message=f"No spec.md for task '{task}'")

        clarifications = self.artifacts.find_and_read_task_file(task, "clarifications.md")

        prompt_template = self._load_prompt_template("plan")
        prompt = prompt_template or (
            "Create an implementation plan for this task.\n\n"
            "CRITICAL: Each stage will be implemented by an LLM in a single pass.\n"
            "An LLM generates 500-1500 lines per pass without quality loss.\n"
            "DO NOT create tiny stages of 50-100 lines — this wastes context.\n"
            "Group by logical cohesion: one stage = one module/layer/vertical slice.\n"
            "Typical task: 2-5 stages, not 8-15.\n\n"
            "Rules:\n"
            "1. Break into stages by logical cohesion, not by size.\n"
            "2. For each stage: goal, inputs, outputs, artifacts, risks, DoD.\n"
            "3. Specify dependencies between stages.\n"
            "4. Mark stages that can run in parallel.\n"
            "5. Verify the plan doesn't violate invariants.\n"
            "6. Verify the plan complies with constitution.\n\n"
            "Do NOT add stages not in the specification. Do NOT over-engineer.\n\n"
            "IMPORTANT: At the end of plan.md, add a section '## Verify' with specific\n"
            "shell commands to verify this task's implementation. These commands will be\n"
            "run automatically after implementation to check correctness.\n"
            "Format each command as a YAML list item:\n"
            "```\n"
            "## Verify\n"
            "- name: Unit tests\n"
            "  command: pytest tests/test_auth.py -v\n"
            "- name: Type check\n"
            "  command: mypy src/auth/\n"
            "```\n"
            "Choose commands specific to THIS task's files and modules.\n"
            "If the task has no testable output, you may omit this section.\n\n"
            "Output TWO documents separated by '---TASKS---':\n"
            "1. plan.md — stages with dependencies, DoD, and ## Verify section\n"
            "2. tasks.md — flat task list with file paths and checkboxes"
        )

        extra_context: dict[str, str] = {}
        cacheable_context: dict[str, str] = {}

        # Architecture — tells LLM what project structure to use (cacheable)
        architecture = self.artifacts.read_architecture()
        if architecture.strip():
            cacheable_context["Architecture"] = architecture

        # AST index — gives LLM visibility into existing codebase (cacheable)
        from skaro_core.context import SmartContextBuilder

        builder = SmartContextBuilder(self.artifacts.root)
        smart = await asyncio.to_thread(
            builder.build,
            stage_section=spec,
            max_full_files=0,  # Plan only needs signatures, not full code
        )
        if smart.signatures:
            cacheable_context["Project API Index (existing code)"] = smart.signatures

        extra_context["Specification (final)"] = spec

        if clarifications:
            extra_context["Clarifications"] = clarifications

        # Current project file tree — so LLM knows what already exists
        project_tree = await self._scan_project_tree_async()
        if project_tree:
            extra_context["Current project file tree"] = project_tree

        messages = self._build_messages(prompt, extra_context, cacheable_context=cacheable_context)
        response_content = await self._stream_collect(messages, task=task or "")

        # Split response into plan and tasks
        content = response_content
        if "---TASKS---" in content:
            parts = content.split("---TASKS---", 1)
            plan_content = parts[0].strip()
            tasks_content = parts[1].strip()
        else:
            plan_content = content
            tasks_content = ""

        # Remove outer code fences if LLM wrapped the response
        plan_content = strip_outer_md_fence(plan_content)
        tasks_content = strip_outer_md_fence(tasks_content)

        # Unwrap inline ```markdown fences (LLM sometimes wraps plan
        # stages in a ```markdown block alongside a ```yaml verify block)
        plan_content = unwrap_markdown_fences(plan_content)
        tasks_content = unwrap_markdown_fences(tasks_content)

        # Save
        created = []
        plan_path = self.artifacts.find_and_write_task_file(task, "plan.md", plan_content)
        created.append(str(plan_path))

        if tasks_content:
            tasks_path = self.artifacts.find_and_write_task_file(task, "tasks.md", tasks_content)
            created.append(str(tasks_path))

        # Parse and save verify commands from plan
        verify_commands = self._parse_verify_section(plan_content)
        verify_count = 0
        if verify_commands:
            verify_path = self.artifacts.find_task_dir(task) / "verify.yaml"
            verify_path.parent.mkdir(parents=True, exist_ok=True)
            verify_path.write_text(
                yaml.dump(verify_commands, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )
            verify_count = len(verify_commands)
            created.append(str(verify_path))

        # Count stages
        stage_count = max(count_plan_stages(plan_content), 1)

        return PhaseResult(
            success=True,
            message=f"Plan created: {stage_count} stages, {verify_count} verify commands",
            artifacts_created=created,
            data={
                "stage_count": stage_count,
                "plan": plan_content,
                "tasks": tasks_content,
                "verify_commands": verify_commands,
            },
        )

    @staticmethod
    def _parse_verify_section(plan: str) -> list[dict[str, str]]:
        """Extract verify commands from the ## Verify section of the plan.

        Supports two formats:
        1. YAML-style:  - name: X\\n  command: Y
        2. Simple list:  - `command here`  or  - command here
        """
        # Find the ## Verify section
        lines = plan.splitlines()
        start = None
        end = None

        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if stripped in ("## verify", "## верификация", "## проверка"):
                start = i + 1
            elif start is not None and line.strip().startswith("## "):
                end = i
                break

        if start is None:
            return []

        section_lines = lines[start:end]

        # Strip code fences that LLM may wrap around the YAML block
        # e.g. ```yaml ... ``` or bare ``` ... ```
        cleaned = []
        for line in section_lines:
            s = line.strip()
            if re.match(r"^```(?:yaml|yml)?\s*$", s):
                continue
            cleaned.append(line)

        section = "\n".join(cleaned).strip()
        if not section:
            return []

        # Try YAML parse first
        commands = _try_yaml_parse(section)
        if commands:
            return commands

        # Fallback: parse simple list items
        commands = []
        for line in section.splitlines():
            line = line.strip()
            if line.startswith("- "):
                cmd = line[2:].strip().strip("`")
                if cmd:
                    commands.append({"name": cmd.split()[0], "command": cmd})
        return commands

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Deprecated: use :func:`strip_outer_md_fence` directly."""
        return strip_outer_md_fence(text)


def _try_yaml_parse(section: str) -> list[dict[str, str]]:
    """Attempt to parse section as a YAML list of {name, command} dicts."""
    try:
        data = yaml.safe_load(section)
    except yaml.YAMLError:
        return []

    if not isinstance(data, list):
        return []

    result = []
    for item in data:
        if isinstance(item, dict) and "command" in item:
            result.append({
                "name": str(item.get("name", item["command"].split()[0])),
                "command": str(item["command"]),
            })
    return result
