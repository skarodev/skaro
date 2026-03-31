"""DevPlan phase: generate and update development plan with milestones and tasks."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from skaro_core.phases._devplan_parser import make_slug, parse_milestones, parse_update_response
from skaro_core.phases._devplan_prompts import (
    DEFAULT_PROMPT,
    DEFAULT_UPDATE_PROMPT,
    build_devplan_markdown,
)
from skaro_core.phases.base import BasePhase, PhaseResult

# Provider-specific max_tokens for devplan (long output).
_DEVPLAN_TOKEN_LIMITS = {
    "anthropic": 128000,
    "openai": 65536,
    "groq": 65536,
    "ollama": 131072,
}


class DevPlanPhase(BasePhase):
    phase_name = "devplan"

    async def run(self, feature: str | None = None, **kwargs: Any) -> PhaseResult:
        """Generate a development plan: milestones with tasks and pre-filled specs."""
        constitution = self.artifacts.read_constitution()
        architecture = self.artifacts.read_architecture()
        invariants = self.artifacts.read_invariants()

        if not constitution.strip() or len(constitution) < 100:
            return PhaseResult(success=False, message="Constitution is not filled in.")
        if not architecture.strip() or len(architecture) < 100:
            return PhaseResult(success=False, message="Architecture is not filled in.")
        if not self.artifacts.is_architecture_reviewed:
            return PhaseResult(
                success=False,
                message="Architecture is not approved. Review and approve it first.",
            )

        # ── Choose prompt based on whether this is an imported project ────
        is_imported = self.artifacts.import_mode is not None

        if is_imported:
            prompt = self._load_prompt_template("devplan-imported") or DEFAULT_PROMPT
        else:
            prompt = self._load_prompt_template("devplan") or DEFAULT_PROMPT

        prompt = prompt.replace("{spec_template}", self._read_template("spec-template.md"))
        prompt = prompt.replace("{devplan_template}", self._read_template("devplan-template.md"))

        extra_context: dict[str, str] = {"Architecture": architecture}
        cacheable_context: dict[str, str] = {}

        if invariants.strip():
            extra_context["Invariants"] = invariants
        self._add_adr_context(extra_context)

        # ── Add codebase context so LLM knows what already exists ─────────
        # Project file tree — shows what files are already on disk
        project_tree = await self._scan_project_tree_async()
        if project_tree:
            extra_context["Project File Tree"] = project_tree

        # AST index — compact view of existing classes/functions/types
        from skaro_core.context import SmartContextBuilder

        builder = SmartContextBuilder(
            self.artifacts.root,
            always_include=self.config.context_always_include,
        )
        smart = await asyncio.to_thread(
            builder.build,
            stage_section=architecture,
            max_full_files=0,  # DevPlan only needs signatures, not full code
        )
        if smart.signatures:
            cacheable_context["Project API Index (existing code)"] = smart.signatures

        messages = self._build_messages(prompt, extra_context, cacheable_context=cacheable_context)
        response_content = await self._llm_collect_with_high_limit(messages)

        milestones = parse_milestones(response_content)
        devplan_md = build_devplan_markdown(milestones)
        self.artifacts.write_devplan(devplan_md)

        return PhaseResult(
            success=True,
            message=response_content,
            artifacts_created=[str(self.artifacts.devplan_path)],
            data={
                "milestones": milestones,
                "devplan": devplan_md,
                "raw_response": response_content,
            },
        )

    async def update(self, user_guidance: str = "", **kwargs: Any) -> PhaseResult:
        """Update existing devplan based on current project state and optional user guidance."""
        current_devplan = self.artifacts.read_devplan()
        if not current_devplan.strip():
            return PhaseResult(success=False, message="No devplan found. Generate one first.")

        architecture = self.artifacts.read_architecture()
        invariants = self.artifacts.read_invariants()

        prompt = self._load_prompt_template("devplan-update") or DEFAULT_UPDATE_PROMPT
        prompt = prompt.replace("{user_guidance}", user_guidance or "(no specific guidance)")

        extra_context = {
            "Architecture": architecture,
            "Current Development Plan": current_devplan,
            "Current Tasks State": self._gather_tasks_state(),
        }
        if invariants.strip():
            extra_context["Invariants"] = invariants
        self._add_adr_context(extra_context)

        messages = self._build_messages(prompt, extra_context)
        response_content = await self._llm_collect_with_high_limit(messages)

        updated_devplan, new_milestones = parse_update_response(response_content)

        return PhaseResult(
            success=True,
            message=response_content,
            data={
                "updated_devplan": updated_devplan,
                "new_milestones": new_milestones,
                "raw_response": response_content,
            },
        )

    async def confirm_update(
        self, updated_devplan: str, new_milestones: list[dict[str, Any]]
    ) -> PhaseResult:
        """Apply confirmed devplan update: save devplan.md and create new milestones/tasks."""
        if updated_devplan.strip():
            self.artifacts.write_devplan(updated_devplan)

        created = self._materialize_milestones(new_milestones)

        return PhaseResult(
            success=True,
            message=f"DevPlan updated. Created {len(created)} new tasks.",
            artifacts_created=[str(self.artifacts.devplan_path)] + created,
            data={"tasks_created": created},
        )

    async def confirm_plan(self, milestones: list[dict[str, Any]]) -> PhaseResult:
        """Create milestone and task directories with pre-filled specs from confirmed plan."""
        created = self._materialize_milestones(milestones, with_description=True)

        # Append to devplan.md changelog
        if self.artifacts.has_devplan:
            devplan = self.artifacts.read_devplan()
            changelog = (
                f"\n- {date.today().isoformat()}: "
                f"Confirmed {len(created)} tasks: {', '.join(created)}"
            )
            if "## Change Log" in devplan:
                devplan = devplan.replace(
                    "## Change Log",
                    f"## Change Log\n{changelog}",
                    1,
                )
            else:
                devplan += f"\n\n## Change Log\n{changelog}\n"
            self.artifacts.write_devplan(devplan)

        return PhaseResult(
            success=True,
            message=f"Plan confirmed. Created {len(created)} tasks.",
            artifacts_created=[str(self.artifacts.devplan_path)]
            + [f"milestones/{t}/spec.md" for t in created],
            data={"tasks_created": created},
        )

    # ── Private helpers ─────────────────────────

    def _materialize_milestones(
        self,
        milestones: list[dict[str, Any]],
        *,
        with_description: bool = False,
    ) -> list[str]:
        """Create milestone dirs and tasks on disk. Returns list of created paths."""
        created: list[str] = []
        for ms_data in milestones:
            ms_slug = ms_data.get("milestone_slug", "").strip()
            ms_title = ms_data.get("milestone_title", "").strip()
            ms_desc = ms_data.get("description", "").strip() if with_description else ""
            tasks = ms_data.get("tasks", [])
            if not ms_slug:
                continue

            if not self.artifacts.milestone_exists(ms_slug):
                self.artifacts.create_milestone(ms_slug, title=ms_title, description=ms_desc)

            task_slugs: list[str] = []
            for task_data in tasks:
                name = task_data.get("name", "").strip()
                spec = task_data.get("spec", "").strip()
                if not name:
                    continue

                slug = make_slug(name)
                if not self.artifacts.task_exists(ms_slug, slug):
                    self.artifacts.create_task(ms_slug, slug)
                if spec:
                    self.artifacts.write_task_file(ms_slug, slug, "spec.md", spec)

                task_slugs.append(slug)
                created.append(f"{ms_slug}/{slug}")

            # Persist LLM-defined task order so list_tasks() respects it
            if task_slugs:
                existing_order = self.artifacts.get_task_order(ms_slug)
                merged = existing_order + [s for s in task_slugs if s not in set(existing_order)]
                self.artifacts.save_task_order(ms_slug, merged)

        return created

    def _read_template(self, name: str) -> str:
        """Read a template file from .skaro/templates/."""
        path = self.artifacts.skaro / "templates" / name
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _add_adr_context(self, extra_context: dict[str, str]) -> None:
        """Append ADR content to extra_context if any ADRs exist."""
        parts = []
        for adr_path in self.artifacts.list_adrs():
            content = adr_path.read_text(encoding="utf-8")
            if content.strip():
                parts.append(content)
        if parts:
            extra_context["Architecture Decision Records (ADR)"] = "\n\n---\n\n".join(parts)

    def _gather_tasks_state(self) -> str:
        """Build a summary of current task states for LLM context."""
        lines: list[str] = []
        for ms in self.artifacts.list_milestones():
            lines.append(f"### Milestone: {ms}")
            for task in self.artifacts.list_tasks(ms):
                state = self.artifacts.get_task_state(ms, task)
                phase = state.current_phase.value
                progress = state.progress_percent
                stages = (
                    f"stage {state.current_stage}/{state.total_stages}"
                    if state.total_stages
                    else "no stages"
                )
                lines.append(
                    f"  - {task}: phase={phase}, progress={progress}%, {stages}"
                )
        return "\n".join(lines) if lines else "(no tasks yet)"

    async def _llm_collect_with_high_limit(self, messages: list) -> str:
        """Stream-collect LLM response with temporarily raised max_tokens."""
        original_max = self.llm.config.max_tokens
        provider = self.llm.config.provider.lower()
        self.llm.config.max_tokens = max(
            original_max, _DEVPLAN_TOKEN_LIMITS.get(provider, 16384)
        )
        try:
            return await self._stream_collect(messages)
        finally:
            self.llm.config.max_tokens = original_max
