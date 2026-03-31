"""Fix phase: conversational bug fixing within a task context.

Provides LLM with full project context (spec, plan, AI_NOTES, source files)
and maintains a conversation log in fix-log.md.

Each fix request sends the full conversation history so LLM can iterate.
"""

from __future__ import annotations

import asyncio
from typing import Any

from skaro_core.phases._fix_base import ConversationalFixBase
from skaro_core.phases.base import PhaseResult

FIX_LOG_FILENAME = "fix-log.md"


class FixPhase(ConversationalFixBase):
    phase_name = "fix"

    _FIX_ROLE = (
        "You are a senior developer fixing bugs and issues in this project.\n"
        "The user will describe a problem they found."
    )

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        """Process a fix request within task context.

        kwargs:
            message: str — user's bug description / follow-up
            conversation: list[dict] — previous conversation turns
                [{"role": "user"|"assistant", "content": "..."}]
        """
        if not task:
            return PhaseResult(success=False, message="Task name is required.")

        user_message: str = kwargs.get("message", "")
        conversation: list[dict] = kwargs.get("conversation", [])
        scope_paths: list[str] = kwargs.get("scope_paths", [])

        if not user_message.strip():
            return PhaseResult(success=False, message="Message is required.")

        # Build smart context: AST index (cacheable) + relevant files (dynamic)
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
        architecture = self.artifacts.read_architecture()
        if architecture.strip():
            cacheable_context["Architecture"] = architecture
        if smart.signatures:
            cacheable_context["Project API Index (all modules)"] = smart.signatures

        # Dynamic context
        extra_context: dict[str, str] = {}
        spec = self.artifacts.find_and_read_task_file(task, "spec.md")
        if spec:
            extra_context["Task Specification"] = spec
        clarif = self.artifacts.find_and_read_task_file(task, "clarifications.md")
        if clarif:
            extra_context["Clarifications"] = clarif
        plan = self.artifacts.find_and_read_task_file(task, "plan.md")
        if plan:
            extra_context["Implementation Plan"] = plan
        # AI_NOTES from completed stages
        completed = self.artifacts.find_completed_stages(task)
        for s in sorted(completed):
            notes_path = self.artifacts.find_stage_dir(task, s) / "AI_NOTES.md"
            if notes_path.exists():
                extra_context[f"Stage {s} AI_NOTES"] = notes_path.read_text(encoding="utf-8")

        # Tier 1 files: user-selected scope (full code)
        if scope_paths:
            scope_code = await asyncio.to_thread(self._read_scope_files, scope_paths)
            if scope_code:
                extra_context["Selected source files (full code)"] = scope_code

        tree = await self._scan_project_tree_async()
        if tree:
            extra_context["Project File Tree"] = tree

        response, proposed, file_diffs, updated_conv = await self._run_fix(
            user_message, conversation, extra_context,
            task=task,
            cacheable_context=cacheable_context,
        )

        # Persist
        self._write_fix_log_entry(
            self._fix_log_path(task),
            f"# Fix Log: {task}",
            user_message,
            response,
            proposed,
        )
        self._save_conversation_to(self._conv_path(task), updated_conv)

        return PhaseResult(
            success=True,
            message=response,
            data={
                "files": file_diffs,
                "conversation": updated_conv,
            },
        )

    # ── Public API (called from web layer) ──

    def load_conversation(self, task: str) -> list[dict]:
        """Load persisted conversation from JSON file."""
        return self._load_conversation_from(self._conv_path(task))

    def clear_conversation(self, task: str) -> None:
        """Clear persisted conversation."""
        self._clear_conversation_at(self._conv_path(task))

    def apply_file(self, task: str, filepath: str, content: str) -> PhaseResult:
        """Apply a single proposed file change to disk."""
        result = self._apply_file_to_disk(filepath, content)
        if result.success:
            self._write_apply_log_entry(self._fix_log_path(task), filepath)
        return result

    # ── Path helpers ──

    def _conv_path(self, task: str):
        return self.artifacts.find_task_dir(task) / "fix-conversation.json"

    def _fix_log_path(self, task: str):
        return self.artifacts.find_task_dir(task) / FIX_LOG_FILENAME

    def _save_conversation(self, task: str, conversation: list[dict]) -> None:
        """Save full conversation as JSON (kept for backward compatibility)."""
        self._save_conversation_to(self._conv_path(task), conversation)

    def _gather_context(self, task: str) -> dict[str, str]:
        """Collect all relevant context (used by API for token estimation)."""
        return self._build_task_context(task, max_files=30, max_file_size=15_000)
