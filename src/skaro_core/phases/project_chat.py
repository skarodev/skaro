"""Universal project chat phase: context-aware advisory and editing chat.

Provides a single chat phase that adapts to different page contexts
(constitution, ADR, devplan, features list, tasks list).  Each context
type loads its own prompt template, builds relevant project context,
and supports context-specific actions (file edits, JSON proposals).

Conversation is persisted per context type in ``.skaro/chat/{context_type}.json``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from skaro_core.llm.base import LLMMessage
from skaro_core.phases._fix_base import ConversationalFixBase
from skaro_core.phases.base import PhaseResult


# Valid context types and their LLM role names (for model selection).
_CONTEXT_ROLES: dict[str, str] = {
    "constitution": "architect",
    "adr": "architect",
    "adr-detail": "architect",
    "devplan": "architect",
    "features": "architect",
    "tasks": "coder",
}


class ProjectChatPhase(ConversationalFixBase):
    """Universal advisory chat with context-specific prompts and actions."""

    phase_name = "project-chat"
    _FIX_ROLE = ""  # Not used directly — each context has its own prompt.

    # ── Public API ──────────────────────────────────

    async def chat(
        self,
        *,
        context_type: str,
        context_id: str = "",
        message: str,
        conversation: list[dict[str, str]],
        scope_paths: list[str] | None = None,
    ) -> PhaseResult:
        """Send a message in the project chat.

        Args:
            context_type: One of ``constitution``, ``adr``, ``adr-detail``,
                ``devplan``, ``features``, ``tasks``.
            context_id: Optional identifier (e.g. ADR number for ``adr-detail``).
            message: User message text.
            conversation: Previous conversation turns.
            scope_paths: Optional file paths for scope context.
        """
        if context_type not in _CONTEXT_ROLES:
            return PhaseResult(
                success=False,
                message=f"Unknown context type: {context_type}",
            )
        if not message.strip():
            return PhaseResult(success=False, message="Message is required.")

        # Override phase_name for correct LLM role selection.
        role_name = _CONTEXT_ROLES[context_type]
        self.phase_name = role_name

        # ── Build system prompt ──
        prompt_template = self._load_prompt_template(f"chat-{context_type}")
        system = self._build_system_message()
        if prompt_template:
            system += "\n\n---\n\n" + prompt_template

        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system, cache=True),
        ]

        # ── Build context ──
        cacheable_ctx, extra_ctx = await self._build_page_context(
            context_type, context_id,
        )

        if cacheable_ctx:
            ctx_parts = [
                f"## {label}\n\n{content}"
                for label, content in cacheable_ctx.items()
                if content.strip()
            ]
            if ctx_parts:
                messages.append(LLMMessage(
                    role="user",
                    content="\n\n---\n\n".join(ctx_parts),
                    cache=True,
                ))
                messages.append(LLMMessage(
                    role="assistant",
                    content="I've reviewed the project context. Ready to help.",
                ))

        if extra_ctx:
            ctx_parts = [
                f"## {label}\n\n{content}"
                for label, content in extra_ctx.items()
                if content.strip()
            ]
            if ctx_parts:
                messages.append(LLMMessage(
                    role="user",
                    content="\n\n---\n\n".join(ctx_parts),
                ))
                messages.append(LLMMessage(
                    role="assistant",
                    content="I've reviewed the additional context. Ready to discuss.",
                ))

        # Scope files (full code).
        if scope_paths:
            scope_code = await asyncio.to_thread(self._read_scope_files, scope_paths)
            if scope_code:
                messages.append(LLMMessage(
                    role="user",
                    content=f"## Selected source files (full code)\n\n{scope_code}",
                ))
                messages.append(LLMMessage(
                    role="assistant",
                    content="I've reviewed the selected source files.",
                ))

        # Replay conversation history (file blocks stripped, tail cached).
        self._replay_conversation(messages, conversation)

        # Current user message (+ language reminder).
        final_message = message
        if self.config.lang != "en":
            final_message += f"\n\n---\nReminder: {self._lang_instruction()}"
        messages.append(LLMMessage(role="user", content=final_message))

        # ── LLM call ──
        response_content = await self._stream_collect(messages, min_tokens=16384)

        # ── Parse response for file blocks ──
        proposed_files = self._parse_file_blocks(response_content)
        file_diffs: dict[str, dict] = {}
        display_message = response_content

        for fpath, new_content in proposed_files.items():
            old_content = self._read_project_file(fpath)
            file_diffs[fpath] = {
                "old": old_content or "",
                "new": new_content,
                "is_new": old_content is None,
            }
            # Strip file blocks from visible message.
            display_message = self._strip_file_block(display_message, fpath)

        # ── Parse response for task proposals ──
        task_proposals = self._parse_task_proposals(response_content)
        if task_proposals:
            display_message = self._strip_task_proposals(display_message)

        display_message = display_message.strip()

        # ── Persist conversation ──
        updated_conversation = list(conversation) + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response_content},
        ]
        conv_path = self._conv_path(context_type, context_id)
        self._save_conversation_to(conv_path, updated_conversation)

        return PhaseResult(
            success=True,
            message=display_message,
            data={
                "files": file_diffs,
                "task_proposals": task_proposals,
                "conversation": updated_conversation,
            },
        )

    def load_conversation(
        self, context_type: str, context_id: str = "",
    ) -> list[dict]:
        return self._load_conversation_from(
            self._conv_path(context_type, context_id),
        )

    def clear_conversation(
        self, context_type: str, context_id: str = "",
    ) -> None:
        self._clear_conversation_at(
            self._conv_path(context_type, context_id),
        )

    def apply_file(self, filepath: str, content: str) -> PhaseResult:
        return self._apply_file_to_disk(filepath, content)

    # ── run() stub (required by BasePhase ABC) ──

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        return await self.chat(**kwargs)

    # ── Context builders per page type ──────────────

    async def _build_page_context(
        self,
        context_type: str,
        context_id: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Build cacheable and dynamic context for the given page type.

        Returns:
            (cacheable_context, extra_context)
        """
        builders = {
            "constitution": self._ctx_constitution,
            "adr": self._ctx_adr_list,
            "adr-detail": self._ctx_adr_detail,
            "devplan": self._ctx_devplan,
            "features": self._ctx_features,
            "tasks": self._ctx_tasks,
        }
        builder = builders.get(context_type, self._ctx_default)
        return await builder(context_id)

    async def _ctx_constitution(self, _id: str) -> tuple[dict, dict]:
        cacheable: dict[str, str] = {}
        extra: dict[str, str] = {}

        constitution = self.artifacts.read_constitution()
        if constitution.strip():
            extra["Current Constitution"] = constitution

        arch = self.artifacts.read_architecture()
        if arch.strip():
            cacheable["Architecture"] = arch

        return cacheable, extra

    async def _ctx_adr_list(self, _id: str) -> tuple[dict, dict]:
        cacheable: dict[str, str] = {}
        extra: dict[str, str] = {}

        arch = self.artifacts.read_architecture()
        if arch.strip():
            cacheable["Architecture"] = arch

        invariants = self.artifacts.read_invariants()
        if invariants.strip():
            cacheable["Architectural Invariants"] = invariants

        adr_index = self.artifacts.read_adr_index()
        if adr_index:
            extra["Existing ADRs"] = adr_index

        # Full ADR contents for context.
        adrs_text = self._read_all_adrs()
        if adrs_text:
            extra["ADR Full Contents"] = adrs_text

        return cacheable, extra

    async def _ctx_adr_detail(self, context_id: str) -> tuple[dict, dict]:
        cacheable: dict[str, str] = {}
        extra: dict[str, str] = {}

        arch = self.artifacts.read_architecture()
        if arch.strip():
            cacheable["Architecture"] = arch

        invariants = self.artifacts.read_invariants()
        if invariants.strip():
            cacheable["Architectural Invariants"] = invariants

        # Load specific ADR content.
        if context_id:
            try:
                adr_num = int(context_id)
                for adr_path in self.artifacts.list_adrs():
                    meta = self.artifacts.parse_adr_metadata(
                        adr_path.read_text(encoding="utf-8"), adr_path.name,
                    )
                    if meta.get("number") == adr_num:
                        extra[f"ADR-{adr_num:03d}"] = adr_path.read_text(
                            encoding="utf-8",
                        )
                        break
            except (ValueError, OSError):
                pass

        return cacheable, extra

    async def _ctx_devplan(self, _id: str) -> tuple[dict, dict]:
        cacheable: dict[str, str] = {}
        extra: dict[str, str] = {}

        arch = self.artifacts.read_architecture()
        if arch.strip():
            cacheable["Architecture"] = arch

        devplan = self.artifacts.read_devplan()
        if devplan.strip():
            extra["Current Development Plan"] = devplan

        tasks_state = self._gather_tasks_overview()
        if tasks_state:
            extra["Current Tasks State"] = tasks_state

        return cacheable, extra

    async def _ctx_features(self, _id: str) -> tuple[dict, dict]:
        cacheable: dict[str, str] = {}
        extra: dict[str, str] = {}

        arch = self.artifacts.read_architecture()
        if arch.strip():
            cacheable["Architecture"] = arch

        invariants = self.artifacts.read_invariants()
        if invariants.strip():
            cacheable["Architectural Invariants"] = invariants

        devplan = self.artifacts.read_devplan()
        if devplan.strip():
            extra["Current Development Plan"] = devplan

        tasks_state = self._gather_tasks_overview()
        if tasks_state:
            extra["Current Tasks State"] = tasks_state

        features_state = self._gather_features_overview()
        if features_state:
            extra["Existing Features"] = features_state

        tree = await self._scan_project_tree_async()
        if tree:
            extra["Project File Tree"] = tree

        return cacheable, extra

    async def _ctx_tasks(self, _id: str) -> tuple[dict, dict]:
        cacheable: dict[str, str] = {}
        extra: dict[str, str] = {}

        arch = self.artifacts.read_architecture()
        if arch.strip():
            cacheable["Architecture"] = arch

        devplan = self.artifacts.read_devplan()
        if devplan.strip():
            extra["Current Development Plan"] = devplan

        tasks_state = self._gather_tasks_overview()
        if tasks_state:
            extra["Current Tasks State"] = tasks_state

        tree = await self._scan_project_tree_async()
        if tree:
            extra["Project File Tree"] = tree

        return cacheable, extra

    async def _ctx_default(self, _id: str) -> tuple[dict, dict]:
        return {}, {}

    # ── Helpers ──────────────────────────────────────

    def _conv_path(self, context_type: str, context_id: str = "") -> Path:
        safe_type = context_type.replace("/", "-").replace("\\", "-")
        if context_id:
            safe_id = str(context_id).replace("/", "-").replace("\\", "-")
            filename = f"{safe_type}-{safe_id}.json"
        else:
            filename = f"{safe_type}.json"
        return self.artifacts.skaro / "chat" / filename

    def _gather_tasks_overview(self) -> str:
        """Build a summary of all milestones and tasks."""
        lines: list[str] = []
        for ms in self.artifacts.list_milestones():
            lines.append(f"### Milestone: {ms}")
            for task in self.artifacts.list_tasks(ms):
                state = self.artifacts.get_task_state(ms, task)
                phase = state.current_phase.value
                progress = state.progress_percent
                lines.append(f"  - {task}: phase={phase}, progress={progress}%")
        return "\n".join(lines) if lines else ""

    def _gather_features_overview(self) -> str:
        """Build a summary of all features."""
        lines: list[str] = []
        features_dir = self.artifacts.skaro / "features"
        if not features_dir.exists():
            return ""
        for meta_path in sorted(features_dir.glob("*/meta.json")):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                slug = meta_path.parent.name
                title = meta.get("title", slug)
                status = meta.get("status", "draft")
                desc = meta.get("description", "")
                lines.append(f"- **{slug}** ({status}): {title}")
                if desc:
                    lines.append(f"  {desc}")
            except (json.JSONDecodeError, OSError):
                continue
        return "\n".join(lines) if lines else ""

    def _read_all_adrs(self) -> str:
        """Read all ADR contents for full context."""
        parts: list[str] = []
        for adr_path in self.artifacts.list_adrs():
            try:
                content = adr_path.read_text(encoding="utf-8")
                parts.append(f"### {adr_path.name}\n\n{content}")
            except (UnicodeDecodeError, OSError):
                continue
        return "\n\n---\n\n".join(parts) if parts else ""

    @staticmethod
    def _strip_file_block(text: str, filepath: str) -> str:
        """Remove a ``--- FILE: <filepath> ---`` block from text."""
        lines = text.splitlines(True)
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith("--- FILE:") and stripped.endswith("---"):
                block_filepath = stripped[9:-3].strip()
                if block_filepath == filepath:
                    block_start = i
                    i += 1
                    while i < len(lines):
                        if lines[i].strip() == "--- END FILE ---":
                            return "".join(lines[:block_start] + lines[i + 1:])
                        i += 1
                    return "".join(lines[:block_start])
            i += 1
        return text
