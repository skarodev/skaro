"""Base class for conversational fix phases.

Extracts the shared run-flow, message building, file diffing, conversation
persistence, and fix-log formatting used by both :class:`FixPhase` (task-level)
and :class:`ProjectFixPhase` (project-level).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from skaro_core.llm.base import LLMMessage
from skaro_core.phases.base import BasePhase, PhaseResult, SKIP_DIRS

# ── Shared system-prompt fragment ────────────────────

_OUTPUT_FORMAT = (
    "# OUTPUT FORMAT\n"
    "First, explain the root cause of the issue.\n\n"
    "Then choose ONE of two paths:\n\n"
    "**Path A — No code changes needed** (environment, config, or command issue):\n"
    "Explain the root cause clearly and suggest what should be changed "
    "(e.g. verify commands, environment setup, Docker config). "
    "Do NOT output any source code files. Do NOT rewrite existing files "
    "just to 'improve' them — that causes regressions.\n\n"
    "**Path B — Code changes required** (actual bug in source code):\n"
    "Output EACH changed file wrapped in file markers:\n"
    "--- FILE: path/to/file.ext ---\n"
    "<full file content>\n"
    "--- END FILE ---\n\n"
    "Output the COMPLETE file content, not just the diff. "
    "Include ALL changed files. Use relative paths from project root.\n\n"
    "CRITICAL: Only use Path B if the root cause is genuinely in the source code. "
    "If tests fail because of wrong commands, missing dependencies, wrong environment, "
    "or incorrect paths — that is Path A. Never rewrite source code to work around "
    "an environment problem."
)


class ConversationalFixBase(BasePhase):
    """Shared logic for task-level and project-level fix phases.

    Subclasses must set :attr:`_FIX_ROLE` and implement :meth:`run`.
    """

    # Subclasses override with a short role paragraph, e.g.
    # "You are a senior developer fixing bugs and issues …"
    _FIX_ROLE: str = ""

    # ── Core conversational flow ──────────────────────

    async def _run_fix(
        self,
        user_message: str,
        conversation: list[dict],
        extra_context: dict[str, str],
        *,
        task: str = "",
        cacheable_context: dict[str, str] | None = None,
    ) -> tuple[str, dict[str, str], dict[str, dict], list[dict]]:
        """Execute the shared fix-conversation flow.

        Returns:
            response_content: raw LLM response text.
            proposed_files:   ``{filepath: new_content}`` parsed from response.
            file_diffs:       ``{filepath: {old, new, is_new}}`` for UI.
            updated_conversation: conversation + this exchange appended.
        """
        # ── System prompt ──
        system = self._build_system_message()
        system += (
            "\n\n# YOUR ROLE\n"
            f"{self._FIX_ROLE}\n"
            "You must:\n"
            "1. Analyze the issue and identify the ROOT CAUSE\n"
            "2. Determine whether the fix is in code, environment, or configuration\n"
            "3. Respond accordingly (see OUTPUT FORMAT)\n\n"
            f"{_OUTPUT_FORMAT}"
        )

        # ── Messages ──
        messages: list[LLMMessage] = [LLMMessage(role="system", content=system, cache=True)]

        # Inject cacheable context (AST index, architecture) — prompt caching
        if cacheable_context:
            ctx_parts = [
                f"## {label}\n\n{content}"
                for label, content in cacheable_context.items()
                if content.strip()
            ]
            if ctx_parts:
                messages.append(
                    LLMMessage(
                        role="user",
                        content="\n\n---\n\n".join(ctx_parts),
                        cache=True,
                    )
                )
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content="I've reviewed the project API index. Ready to help fix issues.",
                    )
                )

        # Inject dynamic context
        if extra_context:
            ctx_parts = [
                f"## {label}\n\n{content}"
                for label, content in extra_context.items()
                if content.strip()
            ]
            if ctx_parts:
                messages.append(
                    LLMMessage(role="user", content="\n\n---\n\n".join(ctx_parts))
                )
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content="I've reviewed the full project context. Ready to help fix issues.",
                    )
                )

        # Replay conversation history
        for turn in conversation:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content.strip():
                messages.append(LLMMessage(role=role, content=content))

        # Current user message (+ language reminder)
        final_message = user_message
        if self.config.lang != "en":
            final_message += f"\n\n---\nReminder: {self._lang_instruction()}"
        messages.append(LLMMessage(role="user", content=final_message))

        # ── LLM call ──
        response_content = await self._stream_collect(
            messages, min_tokens=16384, task=task,
        )

        # ── Parse response ──
        proposed_files = self._parse_file_blocks(response_content)

        file_diffs: dict[str, dict] = {}
        for fpath, new_content in proposed_files.items():
            old_content = self._read_project_file(fpath)
            file_diffs[fpath] = {
                "old": old_content,
                "new": new_content,
                "is_new": old_content is None,
            }

        updated_conversation = list(conversation) + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response_content},
        ]

        return response_content, proposed_files, file_diffs, updated_conversation

    # ── Conversation enrichment ────────────────────────

    def enrich_conversation(self, conversation: list[dict]) -> list[dict]:
        """Re-parse file blocks from assistant messages and attach diffs.

        When a conversation is loaded from JSON, the ``files`` field is not
        persisted.  This method walks each assistant turn, extracts proposed
        file blocks via :meth:`_parse_file_blocks`, computes diffs against
        the current state on disk, and returns a new list with ``files``
        and ``turnIndex`` attached to every assistant turn.
        """
        enriched: list[dict] = []
        for i, turn in enumerate(conversation):
            turn_copy = dict(turn)
            if turn_copy.get("role") == "assistant":
                content = turn_copy.get("content", "")
                proposed = self._parse_file_blocks(content)
                if proposed:
                    file_diffs: dict[str, dict] = {}
                    for fpath, new_content in proposed.items():
                        old_content = self._read_project_file(fpath)
                        file_diffs[fpath] = {
                            "old": old_content,
                            "new": new_content,
                            "is_new": old_content is None,
                        }
                    turn_copy["files"] = file_diffs
                turn_copy["turnIndex"] = i
            enriched.append(turn_copy)
        return enriched

    # ── File I/O helpers ──────────────────────────────

    def _read_project_file(self, filepath: str) -> str | None:
        """Read a file from the project root. Returns *None* if not found."""
        target = self.artifacts.root / filepath
        if target.is_file():
            try:
                return target.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                return None
        return None

    def _read_scope_files(
        self,
        scope_paths: list[str],
    ) -> str:
        """Read full code for user-selected scope paths.

        Paths can be files or directories. Directories are expanded
        recursively to include all text files within.

        No limits applied — user explicitly chose these files, so all of
        them are sent in full. Token budget management is the caller's
        responsibility (UI shows estimated token count).

        Returns formatted markdown blocks ready for LLM context.
        """
        root = self.artifacts.root
        collected: dict[str, str] = {}

        for sp in scope_paths:
            target = root / sp
            if target.is_file():
                self._read_into(target, root, collected)
            elif target.is_dir():
                for child in sorted(target.rglob("*")):
                    parts = child.relative_to(root).parts
                    if any(d in SKIP_DIRS or d.startswith(".") for d in parts[:-1]):
                        continue
                    if child.is_file():
                        self._read_into(child, root, collected)

        if not collected:
            return ""
        parts = []
        for fpath, content in collected.items():
            parts.append(f"### {fpath}\n```\n{content}\n```")
        return "\n\n".join(parts)

    @staticmethod
    def _read_into(
        path: Path, root: Path,
        target: dict[str, str],
    ) -> None:
        """Read a single file into the target dict."""
        rel = str(path.relative_to(root)).replace("\\", "/")
        if rel in target:
            return
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            return
        target[rel] = content

    def _apply_file_to_disk(self, filepath: str, content: str) -> PhaseResult:
        """Validate path, write file, return result (no logging)."""
        try:
            target = self._validate_project_path(self.artifacts.root, filepath)
        except ValueError as e:
            return PhaseResult(success=False, message=str(e))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return PhaseResult(
            success=True,
            message=f"Applied: {filepath}",
            artifacts_updated=[filepath],
        )

    # ── Conversation persistence helpers ──────────────

    @staticmethod
    def _load_conversation_from(path: Path) -> list[dict]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    @staticmethod
    def _save_conversation_to(path: Path, conversation: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(conversation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _clear_conversation_at(path: Path) -> None:
        if path.exists():
            path.unlink()

    # ── Fix-log helpers ───────────────────────────────

    @staticmethod
    def _write_fix_log_entry(
        path: Path,
        title: str,
        user_msg: str,
        llm_msg: str,
        files: dict[str, str],
    ) -> None:
        """Append a fix exchange entry to a markdown log file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8")
        if not existing.strip():
            existing = f"{title}\n"

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        file_list = (
            ", ".join(f"`{f}`" for f in files.keys()) if files else "(no files)"
        )

        entry = (
            f"\n---\n\n"
            f"## {ts}\n\n"
            f"**User:** {user_msg}\n\n"
            f"**LLM:** {llm_msg[:500]}{'...' if len(llm_msg) > 500 else ''}\n\n"
            f"**Proposed files:** {file_list}\n"
        )

        path.write_text(existing + entry, encoding="utf-8")

    @staticmethod
    def _write_apply_log_entry(path: Path, filepath: str) -> None:
        """Append an 'applied' note to a markdown log file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8")

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        existing += f"\n**Applied:** `{filepath}` ✓ ({ts})\n"
        path.write_text(existing, encoding="utf-8")
