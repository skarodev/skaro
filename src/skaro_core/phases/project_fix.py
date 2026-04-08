"""Project Fix phase: conversational bug fixing at the project level.

Provides LLM with project-wide context (constitution, architecture, specs,
AI_NOTES, source files) filtered by user-selected scope (milestones/tasks).
Maintains conversation log in .skaro/docs/project-fix-conversation.json
and appends to .skaro/docs/project-fix-log.md.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from skaro_core.phases._fix_base import ConversationalFixBase
from skaro_core.phases.base import PhaseResult

_FIX_LOG_FILENAME = "project-fix-log.md"
_CONVERSATION_FILENAME = "project-fix-conversation.json"


class ProjectFixPhase(ConversationalFixBase):
    phase_name = "project_fix"

    _FIX_ROLE = (
        "You are a senior developer performing project-wide review and fixes.\n"
        "The user will describe a cross-cutting problem found during project review."
    )

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        user_message: str = kwargs.get("message", "")
        conversation: list[dict] = kwargs.get("conversation", [])
        scope_tasks: list[str] = kwargs.get("scope_tasks", [])
        scope_paths: list[str] = kwargs.get("scope_paths", [])

        if not user_message.strip():
            return PhaseResult(success=False, message="Message is required.")

        # Build smart context
        from skaro_core.context import SmartContextBuilder

        builder = SmartContextBuilder(
            self.artifacts.root,
            always_include=self.config.context_always_include,
        )
        smart = await asyncio.to_thread(
            builder.build,
            stage_section=user_message,
            max_full_files=0,  # Tier 1 is handled by scope_paths
            max_full_file_size=15_000,
        )

        # Cacheable: architecture + AST index
        cacheable_context: dict[str, str] = {}
        arch = self.artifacts.read_architecture()
        if arch.strip():
            cacheable_context["Architecture"] = arch
        if smart.signatures:
            cacheable_context["Project API Index (all modules)"] = smart.signatures

        extra_context = await asyncio.to_thread(self._gather_dynamic_context, scope_tasks)

        # Tier 1 files: user-selected scope (full code)
        if scope_paths:
            scope_code = await asyncio.to_thread(self._read_scope_files, scope_paths)
            if scope_code:
                extra_context["Selected source files (full code)"] = scope_code

        response, proposed, file_diffs, updated_conv = await self._run_fix(
            user_message, conversation, extra_context,
            cacheable_context=cacheable_context,
        )

        # Persist
        self._write_fix_log_entry(
            self._fix_log_path,
            "# Project Fix Log",
            user_message,
            response,
            proposed,
        )
        self._save_conversation_to(self._conv_path, updated_conv)

        return PhaseResult(
            success=True,
            message=response,
            data={
                "files": file_diffs,
                "conversation": updated_conv,
            },
        )

    # ── Public API (called from web layer) ──

    def load_conversation(self) -> list[dict]:
        return self._load_conversation_from(self._conv_path)

    def clear_conversation(self) -> None:
        self._clear_conversation_at(self._conv_path)

    def apply_file(self, filepath: str, content: str) -> PhaseResult:
        result = self._apply_file_to_disk(filepath, content)
        if result.success:
            self._write_apply_log_entry(self._fix_log_path, filepath)
        return result

    # ── Context (project-wide, multi-task) ──

    def _gather_dynamic_context(self, scope_tasks: list[str]) -> dict[str, str]:
        """Gather task-specific context (specs, plans, AI_NOTES)."""
        ctx: dict[str, str] = {}

        state = self.artifacts.get_project_state()
        tasks_to_include = scope_tasks if scope_tasks else [ts.name for ts in state.tasks]

        for task_name in tasks_to_include:
            spec = self.artifacts.find_and_read_task_file(task_name, "spec.md")
            if spec:
                ctx[f"Task '{task_name}' Specification"] = spec

            plan = self.artifacts.find_and_read_task_file(task_name, "plan.md")
            if plan:
                ctx[f"Task '{task_name}' Plan"] = plan

            completed = self.artifacts.find_completed_stages(task_name)
            for s in sorted(completed):
                notes_path = self.artifacts.find_stage_dir(task_name, s) / "AI_NOTES.md"
                if notes_path.exists():
                    notes = notes_path.read_text(encoding="utf-8")
                    if len(notes) > 3000:
                        notes = notes[:3000] + "\n... (truncated)"
                    ctx[f"Task '{task_name}' Stage {s} AI_NOTES"] = notes

        tree = self._scan_project_tree()
        if tree:
            ctx["Project File Tree"] = tree

        return ctx

    def _gather_context(self, scope_tasks: list[str]) -> dict[str, str]:
        """Backward-compatible context gathering (used by API for token estimation)."""
        ctx = self._gather_dynamic_context(scope_tasks)
        arch = self.artifacts.read_architecture()
        if arch.strip():
            ctx["Architecture"] = arch
        return ctx

    # ── Path helpers ──

    @property
    def _conv_path(self) -> Path:
        return self.artifacts.skaro / "docs" / _CONVERSATION_FILENAME

    @property
    def _fix_log_path(self) -> Path:
        return self.artifacts.skaro / "docs" / _FIX_LOG_FILENAME
