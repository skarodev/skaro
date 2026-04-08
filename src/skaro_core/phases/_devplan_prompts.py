"""DevPlan prompts and markdown formatting."""

from __future__ import annotations

from datetime import date
from typing import Any


def build_devplan_markdown(milestones: list[dict[str, Any]]) -> str:
    """Build devplan.md content from parsed milestones."""
    lines = [
        "# Development Plan",
        "",
        f"_Generated: {date.today().isoformat()}_",
        "",
    ]

    for ms_data in milestones:
        ms_slug = ms_data.get("milestone_slug", "")
        ms_title = ms_data.get("milestone_title", ms_slug)
        tasks = ms_data.get("tasks", [])

        lines.extend([
            f"## {ms_title}",
            f"_Directory: `milestones/{ms_slug}/`_",
            "",
            "| # | Task | Status | Dependencies | Description |",
            "|---|------|--------|--------------|-------------|",
        ])

        for i, t in enumerate(tasks, 1):
            name = t.get("name", f"task-{i}")
            desc = t.get("description", "")
            deps = (
                ", ".join(t.get("dependencies", [])) if t.get("dependencies") else "—"
            )
            lines.append(f"| {i} | {name} | planned | {deps} | {desc} |")

        lines.append("")

    lines.extend([
        "---",
        "",
        "## Status Legend",
        "- **idea** — not yet scoped",
        "- **planned** — scoped, assigned to milestone",
        "- **in-progress** — actively being developed",
        "- **done** — completed and reviewed",
        "- **cut** — removed from scope (with reason)",
        "",
        "## Change Log",
        f"- {date.today().isoformat()}: Initial plan created with "
        f"{sum(len(m.get('tasks', [])) for m in milestones)} tasks "
        f"across {len(milestones)} milestones",
    ])

    return "\n".join(lines)


DEFAULT_PROMPT = (
    "Based on the project constitution and architecture, "
    "create a development plan.\n\n"
    "Organize the work into MILESTONES. Each milestone groups related tasks "
    "that together achieve a coherent project goal.\n\n"
    "For EACH milestone provide:\n"
    "1. **milestone_slug** — directory name with numeric prefix (e.g. '01-foundation', '02-mvp')\n"
    "2. **milestone_title** — human-readable title\n"
    "3. **description** — what this milestone achieves\n"
    "4. **tasks** — array of tasks within this milestone\n\n"
    "For EACH task provide:\n"
    "1. **name** — slug for directory (lowercase, hyphens, e.g. 'project-setup')\n"
    "2. **description** — 1-2 sentences explaining what this task does\n"
    "3. **priority** — order of implementation within the milestone (1 = first)\n"
    "4. **dependencies** — names of tasks this depends on (or empty)\n"
    "5. **spec** — a FULL pre-filled specification following the spec template\n\n"
    "Spec template for reference:\n{spec_template}\n\n"
    "Rules:\n"
    "- Tasks can be anything: project setup, feature, infrastructure, refactoring\n"
    "- First milestone should include foundational work (structure, configs, base models)\n"
    "- Order tasks so dependencies come first\n"
    "- Specs should be detailed enough for the Clarify phase\n"
    "- Include functional requirements, scenarios, acceptance criteria\n"
    "- Mark open questions that need clarification\n"
    "- Do NOT over-engineer: keep tasks focused and scoped\n\n"
    "Return the result as a SINGLE JSON array of milestone objects wrapped in ```json fences.\n"
    "IMPORTANT: Return exactly ONE ```json ... ``` block containing ONE array. "
    "Do NOT split the response into multiple JSON blocks."
)

DEFAULT_UPDATE_PROMPT = (
    "You are updating an existing development plan.\n\n"
    "Review the current devplan, the state of all tasks, and the user guidance.\n\n"
    "User guidance: {user_guidance}\n\n"
    "Tasks:\n"
    "1. Update task statuses based on actual progress\n"
    "2. Re-prioritize if needed based on what's been learned\n"
    "3. Add new tasks/milestones if the user requested or if gaps are found\n"
    "4. Move tasks between milestones if appropriate\n"
    "5. Mark tasks as 'cut' if they should be removed\n\n"
    "Return TWO things:\n\n"
    "1. The FULL updated devplan.md inside ```markdown ... ``` fences\n"
    "2. If there are NEW tasks (not yet in .skaro/milestones/), return them as a JSON array "
    "inside ```json ... ``` fences with keys: milestone_slug, milestone_title, tasks "
    "(each task with name, description, spec)\n"
    "   If no new tasks, omit the JSON block.\n\n"
    "IMPORTANT: The updated devplan must be a complete document, not a diff."
)
