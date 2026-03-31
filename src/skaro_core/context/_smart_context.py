"""Smart context builder — tiered project context for LLM prompts.

Produces three tiers of context:

- **Tier 1 — full code**: files that the current stage creates, modifies, or
  directly depends on.  Sent as complete source.
- **Tier 2 — signatures**: all other project source files.  Sent as a compact
  AST index (class/function/type signatures only).
- **Tier 3 — paths**: the project file tree (already handled separately by
  ``_scan_project_tree``).

Usage::

    builder = SmartContextBuilder(project_root)
    result = builder.build(stage_section=section, plan=plan)
    # result.signatures   — compact AST index string
    # result.full_files   — formatted full source of relevant files
    # result.relevant     — set of relevant file paths
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from skaro_core.context._ast_index import build_project_index
from skaro_core.context._relevance import find_relevant_paths
from skaro_core.phases.base import SKIP_DIRS, is_text_file

log = logging.getLogger(__name__)


@dataclass
class SmartContext:
    """Result of a smart context build."""

    signatures: str = ""
    """Compact AST index of all project source files."""

    full_files: str = ""
    """Formatted full source code of relevant (Tier 1) files."""

    relevant_paths: set[str] = field(default_factory=set)
    """Set of file paths selected as Tier 1 (relevant)."""

    stats: dict[str, int] = field(default_factory=dict)
    """Statistics: total_files, signatures_files, full_files, etc."""


class SmartContextBuilder:
    """Build tiered project context for LLM phases.

    Designed to be instantiated once per phase invocation and reused
    if the same phase needs to build context multiple times (e.g. fix
    conversation that re-reads files on each turn).
    """

    def __init__(
        self,
        project_root: Path,
        *,
        skip_dirs: set[str] | None = None,
        always_include: list[str] | None = None,
    ):
        self.root = project_root
        self._skip_dirs = skip_dirs or SKIP_DIRS
        self._always_include_patterns = always_include or []

    def _resolve_always_include(self) -> set[str]:
        """Resolve ``always_include`` glob patterns to relative file paths."""
        resolved: set[str] = set()
        for pattern in self._always_include_patterns:
            for path in self.root.glob(pattern):
                if not path.is_file() or not is_text_file(path):
                    continue
                parts = path.relative_to(self.root).parts
                if any(p in self._skip_dirs or p.startswith(".") for p in parts[:-1]):
                    continue
                resolved.add(str(path.relative_to(self.root)).replace("\\", "/"))
        return resolved

    def build(
        self,
        *,
        stage_section: str = "",
        plan: str = "",
        extra_relevant: set[str] | None = None,
        max_full_files: int = 15,
        max_full_file_size: int = 15_000,
        max_index_files: int = 200,
    ) -> SmartContext:
        """Build tiered context.

        Args:
            stage_section: Current stage description (highest priority for
                relevance extraction).
            plan: Full plan text (used as fallback for relevance).
            extra_relevant: Additional file paths to always include as full code.
            max_full_files: Maximum number of Tier 1 (full code) files.
                Does NOT apply to ``always_include`` files from config — those
                are always sent regardless of this limit.
            max_full_file_size: Truncate individual files above this size (chars).
            max_index_files: Maximum files in the AST index.

        Returns:
            :class:`SmartContext` with signatures, full_files, and stats.
        """
        # ── 0. Resolve always_include patterns ───────────────────
        always_paths = self._resolve_always_include()

        # ── 1. Determine relevant files ─────────────────────────
        context_text = stage_section or plan
        relevant = find_relevant_paths(
            context_text, self.root,
            expand_imports=True,
            max_depth=1,
        )

        if extra_relevant:
            relevant |= extra_relevant

        # ── 2. Build AST index (source code files only) ────────
        signatures = build_project_index(
            self.root,
            skip_dirs=self._skip_dirs,
            max_files=max_index_files,
        )

        # ── 3. Read always_include files (no limit) ────────────
        full_files_dict: dict[str, str] = {}
        for fp in sorted(always_paths):
            abs_path = self.root / fp
            if not abs_path.is_file():
                continue
            try:
                content = abs_path.read_text("utf-8", errors="replace")
            except (OSError, PermissionError):
                continue
            if len(content) > max_full_file_size:
                content = content[:max_full_file_size] + "\n... (truncated)"
            full_files_dict[fp] = content

        # ── 4. Read Tier 1 relevant files (subject to limit) ───
        sorted_relevant = sorted(relevant)
        for fp in sorted_relevant:
            if fp in full_files_dict:
                continue  # already included via always_include
            if len(full_files_dict) - len(always_paths & set(full_files_dict)) >= max_full_files:
                break
            abs_path = self.root / fp
            if not abs_path.is_file():
                continue
            if not is_text_file(abs_path):
                continue
            parts = abs_path.relative_to(self.root).parts
            if any(p in self._skip_dirs or p.startswith(".") for p in parts[:-1]):
                continue
            try:
                content = abs_path.read_text("utf-8", errors="replace")
            except (OSError, PermissionError):
                continue
            if len(content) > max_full_file_size:
                content = content[:max_full_file_size] + "\n... (truncated)"
            full_files_dict[fp] = content

        full_files_text = _format_full_files(full_files_dict)

        stats = {
            "total_relevant": len(relevant),
            "always_include_sent": len(always_paths & set(full_files_dict)),
            "full_files_sent": len(full_files_dict),
            "index_length_chars": len(signatures),
            "full_files_length_chars": len(full_files_text),
        }

        return SmartContext(
            signatures=signatures,
            full_files=full_files_text,
            relevant_paths=relevant | always_paths,
            stats=stats,
        )


def _format_full_files(files: dict[str, str]) -> str:
    """Format a dict of {path: content} for LLM context."""
    if not files:
        return ""
    parts = []
    for fpath, content in files.items():
        parts.append(f"--- FILE: {fpath} ---\n{content}\n--- END FILE ---")
    return "\n\n".join(parts)
