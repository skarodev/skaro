"""Base phase class with common logic for all Skaro phases."""

from __future__ import annotations

import asyncio
import platform
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any, AsyncIterator, Callable

from skaro_core.artifacts import ArtifactManager
from skaro_core.config import SkaroConfig, add_token_usage, load_config
from skaro_core.llm.base import BaseLLMAdapter, LLMMessage, LLMResponse, create_llm_adapter


class CancelledByClientError(Exception):
    """Raised when an LLM streaming operation is cancelled by the client."""


# ── Shared constants ──────────────────────────────────────────
SKIP_DIRS: set[str] = {
    ".skaro", ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs",
    ".ruff_cache", "htmlcov", ".coverage", "coverage", "lcov-report",
}

SOURCE_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
    ".java", ".rb", ".html", ".css", ".vue", ".svelte",
}

SKIP_BINARY_EXTENSIONS: set[str] = {".pyc", ".pyo", ".so", ".dylib"}


def _has_inner_close_ahead(lines: list[str], start: int) -> bool:
    """Check whether a bare ````` has a matching close ````` ahead.

    Scans forward from *start*, skipping over any labeled fence pairs
    (e.g. ``\u0060\u0060\u0060python`` … ``\u0060\u0060\u0060``) encountered
    on the way.  Returns ``True`` if a bare ````` is found that would
    close the inner block — meaning the ````` that triggered this check
    is an inner opener, not the outer block closer.

    Labeled fences that look like file paths (contain ``/`` or ``.``)
    are treated as NEW outer file blocks, not inner fences — their
    presence means the bare ````` was the outer closer.
    """
    depth = 0
    for k in range(start, len(lines)):
        stripped = lines[k].strip()
        if stripped.startswith("```") and len(stripped) > 3:
            label = stripped[3:].strip()
            # A filepath fence signals a new outer file block — stop here.
            # The bare ``` that triggered this check was the outer closer.
            if "/" in label or ("." in label and not label.split()[0].isalpha()):
                return False
            # Language label (```python, ```yaml …) — track as inner fence
            depth += 1
        elif stripped == "```":
            if depth > 0:
                depth -= 1  # closes a labeled inner fence
            else:
                return True  # matching close for the bare inner block
    return False


# ── Regex for markdown outer‐fence detection ──────────────────
_OUTER_FENCE_OPEN_RE = re.compile(r"^```(?:markdown|md)?\s*$")


def strip_outer_md_fence(text: str) -> str:
    """Remove an outer markdown fence that LLMs sometimes wrap around MD output.

    Only strips when the **very first** non-blank line is an opening fence
    (````` ``, ````markdown``, or ````md``) **and** the **very last**
    non-blank line is a bare closing ````` ``.  This guarantees that inner
    code blocks (including bare ````` `` fences) are never touched.
    """
    text = text.strip()
    if not text:
        return text

    lines = text.splitlines()

    # First non-blank line must be the opening fence
    first_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip():
            first_idx = i
            break

    if first_idx is None:
        return text

    if not _OUTER_FENCE_OPEN_RE.match(lines[first_idx].strip()):
        return text  # not wrapped

    # Last non-blank line must be the closing fence
    last_idx: int | None = None
    for i in range(len(lines) - 1, first_idx, -1):
        if lines[i].strip():
            last_idx = i
            break

    if last_idx is None or last_idx <= first_idx:
        return text

    if lines[last_idx].strip() != "```":
        return text  # no closing fence

    return "\n".join(lines[first_idx + 1 : last_idx]).strip()


_MD_FENCE_RE = re.compile(r"^(`{3,})\s*(markdown|md)\s*$")


def unwrap_markdown_fences(text: str) -> str:
    """Unwrap top-level ```markdown / ```md fences inline.

    LLMs sometimes place plan content inside a ````markdown`` fence alongside
    other blocks (e.g. a ````yaml`` verify section).  The content of these
    fences **is** markdown and must be rendered normally, not as ``<pre>``.

    This scans top-level fences only (no nesting awareness needed because
    a ````markdown`` fence never legitimately appears inside another fence).
    """
    if not text:
        return text

    trailing_nl = text.endswith("\n")
    lines = text.split("\n")
    # split("\n") on "a\n" gives ["a", ""] — drop the sentinel empty string
    if trailing_nl and lines and lines[-1] == "":
        lines.pop()
    result: list[str] = []
    i = 0
    while i < len(lines):
        m = _MD_FENCE_RE.match(lines[i].strip())
        if m:
            backticks = m.group(1)
            close_re = re.compile(rf"^{re.escape(backticks)}\s*$")
            # Find closing fence
            j = i + 1
            while j < len(lines):
                if close_re.match(lines[j].strip()):
                    break
                j += 1
            if j < len(lines):
                # Unwrap: emit inner lines without the fence delimiters
                result.extend(lines[i + 1 : j])
                i = j + 1
                continue
        result.append(lines[i])
        i += 1

    return "\n".join(result) + ("\n" if trailing_nl else "")


class _TrackingLLMAdapter(BaseLLMAdapter):
    """Wrapper that tracks token usage from every complete()/stream() call."""

    def __init__(self, inner: BaseLLMAdapter, project_root: Path | None,
                 phase: str = "", task: str = ""):
        self._inner = inner
        self._project_root = project_root
        self._phase = phase
        self._task = task
        # expose config for compatibility
        self.config = inner.config

    def _track(self, usage: dict[str, int] | None) -> None:
        if usage:
            from skaro_core.config import ROLE_PHASES
            role = ""
            for r, phases in ROLE_PHASES.items():
                if self._phase in phases:
                    role = r
                    break
            add_token_usage(
                usage, self._project_root,
                phase=self._phase,
                task=self._task,
                model=self.config.model,
                provider=self.config.provider,
                role=role,
            )

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        response = await self._inner.complete(messages)
        self._track(response.usage)
        return response

    async def stream(self, messages: list[LLMMessage]):
        self._inner.last_usage = None
        async for chunk in self._inner.stream(messages):
            yield chunk
        self._track(self._inner.last_usage)


@dataclass
class PhaseResult:
    success: bool
    message: str
    artifacts_created: list[str] = field(default_factory=list)
    artifacts_updated: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


class BasePhase(ABC):
    """Base class for all Skaro phases."""

    phase_name: str = "base"

    def __init__(
        self,
        project_root: Path | None = None,
        config: SkaroConfig | None = None,
    ):
        self.project_root = project_root
        self.config = config or load_config(project_root)
        self.artifacts = ArtifactManager(project_root)
        self._llm: BaseLLMAdapter | None = None
        self._current_task: str = ""
        self.on_stream_chunk: Callable[[str], Any] | None = None
        self._cancel_event: asyncio.Event | None = None

    def _get_llm(self, task: str = "") -> BaseLLMAdapter:
        """Get or create LLM adapter, updating task context."""
        if self._llm is None or self._current_task != task:
            self._current_task = task
            llm_config = self.config.llm_for_phase(self.phase_name)
            inner = create_llm_adapter(llm_config)
            self._llm = _TrackingLLMAdapter(
                inner, self.project_root,
                phase=self.phase_name, task=task,
            )
        return self._llm

    @property
    def llm(self) -> BaseLLMAdapter:
        return self._get_llm(self._current_task)

    def _track_usage(self, response: LLMResponse) -> None:
        """Track token usage from an LLM response (manual fallback)."""
        if response.usage:
            add_token_usage(response.usage, self.project_root)

    def _load_prompt_template(self, name: str) -> str:
        """Load a prompt template, preferring project-level overrides.

        Lookup order:
        1. ``{project_root}/.skaro/prompts/{name}.md`` — user override
        2. Built-in ``skaro_core/prompts/{name}.md`` — default

        This allows users to customise any phase prompt without forking
        the project.  Place a file in ``.skaro/prompts/`` with the same
        base name to override the built-in template.
        """
        # 1. Project-level override
        if self.project_root is not None:
            override = self.project_root / ".skaro" / "prompts" / f"{name}.md"
            if override.exists():
                return override.read_text(encoding="utf-8")

        # 2. Built-in default
        builtin = Path(__file__).parent.parent / "prompts" / f"{name}.md"
        if builtin.exists():
            return builtin.read_text(encoding="utf-8")

        return ""

    # Language code → human-readable name for LLM instruction
    _LANG_NAMES: dict[str, str] = {
        "en": "English",
        "ru": "Russian",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
    }

    def _lang_instruction(self) -> str:
        """Return language instruction string."""
        lang = self.config.lang
        lang_name = self._LANG_NAMES.get(lang, lang)
        return f"IMPORTANT: You MUST respond entirely in {lang_name}. All explanations, comments in code, AI_NOTES, headings, and descriptions must be in {lang_name}."

    @staticmethod
    def _os_info() -> str:
        """Return OS/shell information for LLM context.

        Ensures that generated shell commands (verify, scripts, etc.)
        are compatible with the user's operating system.
        """
        os_name = platform.system()  # "Windows", "Linux", "Darwin"
        if os_name == "Windows":
            shell = "PowerShell"
            note = (
                "Use PowerShell-compatible syntax for all shell commands. "
                "Do NOT use Unix-specific commands (grep, sed, awk, chmod, etc.) or bash syntax. "
                "Use PowerShell equivalents: Select-String, ForEach-Object, Get-ChildItem, etc. "
                "Use semicolons or backticks for line continuation, not backslashes."
            )
        elif os_name == "Darwin":
            shell = "zsh"
            note = "Use macOS-compatible commands. Prefer POSIX-compliant syntax."
        else:
            shell = "bash"
            note = "Use standard Linux/bash commands."

        return (
            f"OS: {os_name} ({platform.machine()})\n"
            f"Default shell: {shell}\n"
            f"{note}"
        )

    def _build_system_message(self) -> str:
        """Build system message with language, constitution, skills, and invariants."""
        parts = []

        # Language instruction — always first, unconditional
        parts.append(f"# LANGUAGE\n\n{self._lang_instruction()}")

        # OS environment — so LLM generates compatible commands
        env_info = self._os_info()
        exec_env_desc = self.config.execution_env.describe_for_llm()
        if exec_env_desc:
            env_info += f"\n\n## Execution environment\n{exec_env_desc}"
        parts.append(f"# ENVIRONMENT\n\n{env_info}")

        constitution = self.artifacts.read_constitution()
        if constitution:
            parts.append(f"# PROJECT CONSTITUTION\n\n{constitution}")

        # Skills — additional LLM instructions from active skill packs
        skills_text = self._build_skills_section()
        if skills_text:
            parts.append(f"# SKILLS\n\n{skills_text}")

        invariants = self.artifacts.read_invariants()
        if invariants:
            parts.append(f"# ARCHITECTURAL INVARIANTS\n\n{invariants}")

        adr_index = self.artifacts.read_adr_index()
        if adr_index:
            parts.append(adr_index)

        completed_work_path = self.artifacts.skaro / "docs" / "completed-work.md"
        if completed_work_path.exists():
            content = completed_work_path.read_text(encoding="utf-8")
            if content.strip():
                parts.append(f"# COMPLETED WORK (pre-existing)\n\n{content}")

        return "\n\n---\n\n".join(parts)

    def _build_skills_section(self) -> str:
        """Load and format active skills for the current phase and role."""
        from skaro_core.skills import load_skills_for_phase

        role = self.config.role_for_phase(self.phase_name)
        skills = load_skills_for_phase(
            config_skills=self.config.skills,
            phase=self.phase_name,
            role=role,
            project_root=self.project_root,
        )
        if not skills:
            return ""

        parts = []
        for skill in skills:
            text = skill.get_instructions(self.phase_name)
            if text.strip():
                parts.append(f"## Skill: {skill.name}\n\n{text.strip()}")

        return "\n\n".join(parts)

    def _build_messages(
        self,
        user_content: str,
        extra_context: dict[str, str] | None = None,
        cacheable_context: dict[str, str] | None = None,
    ) -> list[LLMMessage]:
        """Build message list with system context and user prompt.

        Args:
            user_content: The main user prompt text.
            extra_context: Dynamic context (stage-specific files, plan, etc.).
            cacheable_context: Stable context that benefits from prompt caching
                (e.g. AST index).  Sent before *extra_context* and marked with
                ``cache=True`` so providers that support prompt caching can
                reuse the prefix across calls.
        """
        messages = []

        system = self._build_system_message()
        if system:
            # System message is stable across stages → cacheable
            messages.append(LLMMessage(role="system", content=system, cache=True))

        # ── Cacheable context (AST index, architecture) — sent first ──
        if cacheable_context:
            context_parts = []
            for label, content in cacheable_context.items():
                if content.strip():
                    context_parts.append(f"## {label}\n\n{content}")
            if context_parts:
                messages.append(
                    LLMMessage(
                        role="user",
                        content="\n\n---\n\n".join(context_parts),
                        cache=True,
                    )
                )
                messages.append(
                    LLMMessage(role="assistant", content="I've reviewed the project context. Ready for your request.")
                )

        # ── Dynamic context (stage-specific, changes each call) ──
        if extra_context:
            context_parts = []
            for label, content in extra_context.items():
                if content.strip():
                    context_parts.append(f"## {label}\n\n{content}")
            if context_parts:
                messages.append(
                    LLMMessage(role="user", content="\n\n---\n\n".join(context_parts))
                )
                messages.append(
                    LLMMessage(role="assistant", content="I've reviewed the context. Ready for your request.")
                )

        # Append language reminder to the actual user prompt if not English
        lang = self.config.lang
        if lang != "en":
            user_content += f"\n\n---\nReminder: {self._lang_instruction()}"

        messages.append(LLMMessage(role="user", content=user_content))

        return messages

    def _scan_project_tree(self) -> str:
        """Scan project directory and return file tree as text.

        Skips .sgd, .git, __pycache__, node_modules, and other common junk dirs.
        Useful for giving LLM context about existing project structure.
        """
        root = self.artifacts.root
        lines: list[str] = []

        for path in sorted(root.rglob("*")):
            parts = path.relative_to(root).parts
            # Skip dot-directories (.git, .venv) but NOT dot-files (.env, .eslintrc)
            if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
                continue
            if path.is_file() and path.suffix in SKIP_BINARY_EXTENSIONS:
                continue
            if path.is_file():
                lines.append(str(path.relative_to(root)))
            if len(lines) >= 200:
                lines.append("... (truncated)")
                break

        return "\n".join(lines) if lines else ""

    def _collect_project_sources(
        self,
        *,
        max_files: int = 30,
        max_file_size: int = 10_000,
        extra_extensions: set[str] | None = None,
    ) -> dict[str, str]:
        """Read existing source files from the project for LLM context.

        Args:
            max_files: Maximum number of files to collect.
            max_file_size: Truncate files larger than this (chars).
            extra_extensions: Additional extensions beyond SOURCE_EXTENSIONS.
        """
        files: dict[str, str] = {}
        root = self.artifacts.root
        extensions = SOURCE_EXTENSIONS | (extra_extensions or set())

        for path in sorted(root.rglob("*")):
            parts = path.relative_to(root).parts
            # Skip dot-directories (.git, .venv) but NOT dot-files (.env, .eslintrc)
            if any(p in SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
                continue
            if path.is_file() and path.suffix in extensions:
                rel = str(path.relative_to(root))
                try:
                    content = path.read_text(encoding="utf-8")
                    if len(content) > max_file_size:
                        files[rel] = content[:max_file_size] + "\n... (truncated)"
                    else:
                        files[rel] = content
                except (UnicodeDecodeError, PermissionError):
                    continue
                if len(files) >= max_files:
                    break

        return files

    def _format_source_files(self, source_files: dict[str, str]) -> str:
        """Format collected source files into markdown blocks."""
        parts = []
        for fpath, content in source_files.items():
            parts.append(f"### {fpath}\n```\n{content}\n```")
        return "\n\n".join(parts)

    def _append_source_context(
        self,
        ctx: dict[str, str],
        *,
        max_files: int = 30,
        max_file_size: int = 15_000,
    ) -> None:
        """Append project source files and file tree to a context dict."""
        source_files = self._collect_project_sources(
            max_files=max_files, max_file_size=max_file_size,
        )
        if source_files:
            ctx["Current Project Source Files"] = self._format_source_files(source_files)

        tree = self._scan_project_tree()
        if tree:
            ctx["Project File Tree"] = tree

    def _build_task_context(
        self,
        task: str,
        *,
        include_clarifications: bool = True,
        max_files: int = 30,
        max_file_size: int = 15_000,
    ) -> dict[str, str]:
        """Gather standard context for a single task.

        Collects architecture, spec, clarifications, plan, AI_NOTES from
        completed stages, project source files, and project tree.
        """
        ctx: dict[str, str] = {}

        # Architecture
        arch = self.artifacts.read_architecture()
        if arch.strip():
            ctx["Architecture"] = arch

        # Task spec
        spec = self.artifacts.find_and_read_task_file(task, "spec.md")
        if spec:
            ctx["Task Specification"] = spec

        # Clarifications
        if include_clarifications:
            clarif = self.artifacts.find_and_read_task_file(task, "clarifications.md")
            if clarif:
                ctx["Clarifications"] = clarif

        # Plan
        plan = self.artifacts.find_and_read_task_file(task, "plan.md")
        if plan:
            ctx["Implementation Plan"] = plan

        # AI_NOTES from completed stages
        completed = self.artifacts.find_completed_stages(task)
        for s in sorted(completed):
            notes_path = self.artifacts.find_stage_dir(task, s) / "AI_NOTES.md"
            if notes_path.exists():
                ctx[f"Stage {s} AI_NOTES"] = notes_path.read_text(encoding="utf-8")

        # Source files + project tree
        self._append_source_context(ctx, max_files=max_files, max_file_size=max_file_size)

        return ctx

    @staticmethod
    def _parse_file_blocks(content: str) -> dict[str, str]:
        """Parse LLM output into {filepath: content} dict.

        Primary format (preferred)::

            --- FILE: path/to/file.ext ---
            content here — any content is safe, no escaping needed
            --- END FILE ---

        Legacy format (backward compatibility with old conversations)::

            ```path/to/file.ext
            content
            ```

        Both formats can coexist in a single response.
        """
        files: dict[str, str] = {}
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()

            # ── Primary format: --- FILE: path --- ──
            if stripped.startswith("--- FILE:") and stripped.endswith("---"):
                filepath = stripped[9:-3].strip()
                if filepath:
                    file_lines: list[str] = []
                    i += 1
                    while i < len(lines):
                        if lines[i].strip() == "--- END FILE ---":
                            break
                        file_lines.append(lines[i])
                        i += 1
                    files[filepath] = "\n".join(file_lines)

            # ── Legacy format: ```path/to/file.ext ──
            elif stripped.startswith("```") and stripped != "```":
                fence = stripped[3:].strip()
                if "/" in fence or "." in fence:
                    filepath = fence
                    file_lines = []
                    i += 1
                    inner_fence = False
                    while i < len(lines):
                        s = lines[i].strip()
                        if inner_fence:
                            file_lines.append(lines[i])
                            if s == "```":
                                inner_fence = False
                        elif s.startswith("```") and len(s) > 3:
                            label = s[3:].strip()
                            if "/" in label or ("." in label and not label.split()[0].isalpha()):
                                i -= 1
                                break
                            inner_fence = True
                            file_lines.append(lines[i])
                        elif s == "```":
                            break
                        else:
                            file_lines.append(lines[i])
                        i += 1
                    files[filepath] = "\n".join(file_lines)

            i += 1
        return files

    @staticmethod
    def _validate_project_path(project_root: Path, filepath: str) -> Path:
        """Validate that filepath resolves inside project_root.

        Raises ValueError on path traversal attempts.
        """
        resolved = (project_root / filepath).resolve()
        if not resolved.is_relative_to(project_root.resolve()):
            raise ValueError(
                f"Path traversal detected: '{filepath}' resolves outside project root."
            )
        return resolved

    # ── Async wrappers (offload sync I/O to thread pool) ──

    async def _scan_project_tree_async(self) -> str:
        """Async version of :meth:`_scan_project_tree`."""
        return await asyncio.to_thread(self._scan_project_tree)

    async def _collect_project_sources_async(
        self,
        *,
        max_files: int = 30,
        max_file_size: int = 10_000,
        extra_extensions: set[str] | None = None,
    ) -> dict[str, str]:
        """Async version of :meth:`_collect_project_sources`."""
        return await asyncio.to_thread(
            self._collect_project_sources,
            max_files=max_files,
            max_file_size=max_file_size,
            extra_extensions=extra_extensions,
        )

    @abstractmethod
    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        """Execute this phase."""
        ...

    async def _stream_collect(
        self, messages: list[LLMMessage], min_tokens: int = 16384,
        task: str = "",
    ) -> str:
        """Stream LLM response and collect into a single string.

        Uses streaming to avoid Anthropic's 10-minute timeout on large context.
        Temporarily raises max_tokens if below min_tokens.
        Calls self.on_stream_chunk(text) periodically if set.
        """
        if task:
            self._current_task = task
        llm = self._get_llm(self._current_task)
        original = llm.config.max_tokens
        if llm.config.max_tokens < min_tokens:
            llm.config.max_tokens = min_tokens
        try:
            chunks: list[str] = []
            buf: list[str] = []
            buf_len = 0
            last_flush = monotonic()

            async for chunk in llm.stream(messages):
                if self._cancel_event and self._cancel_event.is_set():
                    raise CancelledByClientError("LLM request cancelled by client")
                chunks.append(chunk)
                if self.on_stream_chunk:
                    buf.append(chunk)
                    buf_len += len(chunk)
                    now = monotonic()
                    if buf_len >= 80 or (now - last_flush) > 0.3:
                        try:
                            await self.on_stream_chunk("".join(buf))
                        except Exception:
                            pass
                        buf.clear()
                        buf_len = 0
                        last_flush = now

            if buf and self.on_stream_chunk:
                try:
                    await self.on_stream_chunk("".join(buf))
                except Exception:
                    pass

            return "".join(chunks)
        finally:
            llm.config.max_tokens = original

    async def stream_run(
        self, feature: str | None = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        """Execute this phase with streaming output. Default: non-streaming fallback."""
        result = await self.run(task=feature, **kwargs)
        yield result.message
