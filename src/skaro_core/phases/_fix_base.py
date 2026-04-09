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
    "⚠️ You MUST use the --- FILE: / --- END FILE --- markers shown above. "
    "Do NOT wrap code in ```python, ```javascript or any other markdown "
    "code fences — those will NOT be parsed. Only the --- FILE: --- format works.\n\n"
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

        # Replay conversation history (file blocks stripped, tail cached).
        self._replay_conversation(messages, conversation)

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

        # ── Detect truncation ──
        truncated_paths = set(self._find_truncated_file_blocks(response_content))
        is_truncated = (
            self._last_stop_reason in ("max_tokens", "length")
            or bool(truncated_paths)
        )

        # Remove truncated files from proposed_files to prevent applying
        # incomplete content to disk.
        for tp in truncated_paths:
            proposed_files.pop(tp, None)

        file_diffs: dict[str, dict] = {}
        for fpath, new_content in proposed_files.items():
            old_content = self._read_project_file(fpath)
            file_diffs[fpath] = {
                "old": old_content,
                "new": new_content,
                "is_new": old_content is None,
            }

        # Add truncated files as non-applicable diffs with warning flag
        for tp in truncated_paths:
            old_content = self._read_project_file(tp)
            file_diffs[tp] = {
                "old": old_content,
                "new": None,
                "is_new": old_content is None,
                "truncated": True,
            }

        # Append truncation warning so it is visible in the conversation
        if is_truncated and truncated_paths:
            warning = (
                "\n\n---\n"
                "⚠️ **Response truncated by token limit.** "
                "The following files were cut short and cannot be applied:\n"
                + "".join(f"- `{p}`\n" for p in sorted(truncated_paths))
                + "\nPlease re-run the fix or increase `max_tokens` in LLM settings."
            )
            response_content += warning

        updated_conversation = list(conversation) + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response_content},
        ]

        return response_content, proposed_files, file_diffs, updated_conversation

    # ── Conversation enrichment ────────────────────────

    def enrich_conversation(self, conversation: list[dict]) -> list[dict]:
        """Re-parse file blocks and task proposals from assistant messages.

        When a conversation is loaded from JSON, the ``files`` and
        ``taskProposals`` fields are not persisted.  This method walks each
        assistant turn, extracts proposed file blocks and task proposals,
        computes diffs against the current state on disk, and returns a new
        list with ``files``, ``taskProposals``, and ``turnIndex`` attached
        to every assistant turn.
        """
        enriched: list[dict] = []
        for i, turn in enumerate(conversation):
            turn_copy = dict(turn)
            if turn_copy.get("role") == "assistant":
                content = turn_copy.get("content", "")
                proposed = self._parse_file_blocks(content)
                truncated_paths = set(self._find_truncated_file_blocks(content))
                # Remove truncated from proposed — incomplete content
                for tp in truncated_paths:
                    proposed.pop(tp, None)
                if proposed or truncated_paths:
                    file_diffs: dict[str, dict] = {}
                    for fpath, new_content in proposed.items():
                        old_content = self._read_project_file(fpath)
                        file_diffs[fpath] = {
                            "old": old_content,
                            "new": new_content,
                            "is_new": old_content is None,
                        }
                    for tp in truncated_paths:
                        old_content = self._read_project_file(tp)
                        file_diffs[tp] = {
                            "old": old_content,
                            "new": None,
                            "is_new": old_content is None,
                            "truncated": True,
                        }
                    turn_copy["files"] = file_diffs
                # Task proposals
                task_proposals = self._parse_task_proposals(content)
                if task_proposals:
                    turn_copy["taskProposals"] = task_proposals
                # Review issue proposals
                issue_proposals = self._parse_issue_blocks(content)
                if issue_proposals:
                    turn_copy["issueProposals"] = issue_proposals
                turn_copy["turnIndex"] = i
            enriched.append(turn_copy)
        return enriched

    # ── Conversation replay helpers ────────────────────

    @staticmethod
    def _strip_all_file_blocks(text: str) -> str:
        """Remove every ``--- FILE: … --- END FILE ---`` block from *text*.

        Keeps the surrounding prose so the LLM still sees the explanation
        that accompanied the code, but not the (potentially huge) inline
        file content that is already available via scope context.
        """
        lines = text.splitlines(True)
        result: list[str] = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith("--- FILE:") and stripped.endswith("---"):
                # Skip until the closing marker or end of text.
                i += 1
                while i < len(lines):
                    if lines[i].strip() == "--- END FILE ---":
                        i += 1
                        break
                    i += 1
            else:
                result.append(lines[i])
                i += 1
        return "".join(result)

    @staticmethod
    def _parse_task_proposals(text: str) -> list[dict]:
        """Parse ``--- TASKS --- ... --- END TASKS ---`` blocks from LLM output.

        Returns a list of task dicts with ``name``, ``milestone``, ``spec``.
        """
        lines = text.splitlines()
        i = 0
        proposals: list[dict] = []
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == "--- TASKS ---":
                block_lines: list[str] = []
                i += 1
                while i < len(lines):
                    if lines[i].strip() == "--- END TASKS ---":
                        break
                    block_lines.append(lines[i])
                    i += 1
                raw = "\n".join(block_lines).strip()
                if raw:
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict) and item.get("name"):
                                    proposals.append({
                                        "name": item["name"],
                                        "milestone": item.get("milestone", ""),
                                        "spec": item.get("spec", ""),
                                    })
                    except (json.JSONDecodeError, KeyError):
                        pass
            i += 1
        return proposals

    @staticmethod
    def _strip_task_proposals(text: str) -> str:
        """Remove ``--- TASKS ---`` blocks from visible text."""
        lines = text.splitlines(True)
        result: list[str] = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == "--- TASKS ---":
                i += 1
                while i < len(lines):
                    if lines[i].strip() == "--- END TASKS ---":
                        i += 1
                        break
                    i += 1
            else:
                result.append(lines[i])
                i += 1
        return "".join(result)

    @staticmethod
    def _parse_issue_blocks(text: str) -> list[dict]:
        """Parse ``<skaro-issue>`` blocks from LLM output.

        Each block contains simple key: value lines (title, severity, file,
        description).  Returns a list of issue dicts.
        """
        import re

        issues: list[dict] = []
        for match in re.finditer(
            r"<skaro-issue>\s*\n(.*?)\n\s*</skaro-issue>",
            text,
            re.DOTALL,
        ):
            body = match.group(1).strip()
            issue: dict[str, str] = {}
            current_key: str | None = None
            current_lines: list[str] = []

            for line in body.splitlines():
                kv = line.split(":", 1)
                if len(kv) == 2 and kv[0].strip().lower() in (
                    "title", "severity", "file", "description",
                ):
                    # Flush previous key
                    if current_key is not None:
                        issue[current_key] = "\n".join(current_lines).strip()
                    current_key = kv[0].strip().lower()
                    current_lines = [kv[1].strip()]
                elif current_key is not None:
                    current_lines.append(line)

            # Flush last key
            if current_key is not None:
                issue[current_key] = "\n".join(current_lines).strip()

            if issue.get("title"):
                issues.append({
                    "title": issue.get("title", ""),
                    "severity": issue.get("severity", "should_improve"),
                    "file": issue.get("file", ""),
                    "description": issue.get("description", ""),
                })
        return issues

    @staticmethod
    def _strip_issue_blocks(text: str) -> str:
        """Remove ``<skaro-issue>`` blocks from visible text."""
        import re

        return re.sub(
            r"<skaro-issue>\s*\n.*?\n\s*</skaro-issue>\s*\n?",
            "",
            text,
            flags=re.DOTALL,
        )

    def _replay_conversation(
        self,
        messages: list[LLMMessage],
        conversation: list[dict],
    ) -> None:
        """Replay prior conversation turns into *messages*.

        Two optimisations applied:

        1. **Strip file blocks** — assistant turns often contain full file
           contents inside ``--- FILE: … --- END FILE ---`` markers.  These
           are removed because the LLM already receives the current file
           state through scope / extra context.  This alone saves 50-80 %
           of history tokens in a typical fix session.

        2. **Prompt-cache the old prefix** — the last replayed turn is
           marked ``cache=True`` so providers that support prompt caching
           (Anthropic) can reuse the ever-growing conversation prefix
           across successive calls (90 % read discount).
        """
        turns: list[LLMMessage] = []
        for turn in conversation:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role not in ("user", "assistant") or not content.strip():
                continue
            if role == "assistant":
                content = self._strip_all_file_blocks(content)
                content = self._strip_task_proposals(content)
                content = self._strip_issue_blocks(content)
            if not content.strip():
                continue
            turns.append(LLMMessage(role=role, content=content))

        # Mark the last replayed turn as a cache breakpoint so that
        # the entire conversation prefix is prompt-cached on the next call.
        if turns:
            turns[-1] = LLMMessage(
                role=turns[-1].role,
                content=turns[-1].content,
                cache=True,
            )

        messages.extend(turns)

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
            parts.append(f"--- FILE: {fpath} ---\n{content}\n--- END FILE ---")
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
