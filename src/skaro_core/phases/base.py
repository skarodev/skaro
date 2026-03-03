"""Base phase class with common logic for all Skaro phases."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any, AsyncIterator, Callable

from skaro_core.artifacts import ArtifactManager
from skaro_core.config import SkaroConfig, add_token_usage, load_config
from skaro_core.llm.base import BaseLLMAdapter, LLMMessage, LLMResponse, create_llm_adapter

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
        """Load a prompt template from the prompts directory."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        path = prompts_dir / f"{name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
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

    def _build_system_message(self) -> str:
        """Build system message with language, constitution, and invariants."""
        parts = []

        # Language instruction — always first, unconditional
        parts.append(f"# LANGUAGE\n\n{self._lang_instruction()}")

        constitution = self.artifacts.read_constitution()
        if constitution:
            parts.append(f"# PROJECT CONSTITUTION\n\n{constitution}")

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

    def _build_messages(
        self, user_content: str, extra_context: dict[str, str] | None = None
    ) -> list[LLMMessage]:
        """Build message list with system context and user prompt."""
        messages = []

        system = self._build_system_message()
        if system:
            messages.append(LLMMessage(role="system", content=system))

        # Add extra context files
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
            if any(p in SKIP_DIRS or p.startswith(".") for p in parts):
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
            if any(p in SKIP_DIRS or p.startswith(".") for p in parts):
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

    @staticmethod
    def _parse_file_blocks(content: str) -> dict[str, str]:
        """Parse LLM output into {filepath: content} dict.

        Expects format:
        ```path/to/file.ext
        content here
        ```
        """
        files: dict[str, str] = {}
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("```") and not line.strip() == "```":
                fence = line.strip()[3:].strip()
                # Ignore language-only fences like ```python, ```typescript
                if "/" in fence or "." in fence:
                    filepath = fence
                    file_lines = []
                    i += 1
                    while i < len(lines) and not lines[i].strip() == "```":
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
