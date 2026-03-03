"""Repository scanner for the existing-project import flow.

Collects source files respecting .gitignore and .skaroignore patterns.
Applies smart sampling when the estimated token count exceeds the configured limit.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

from skaro_core.phases.base import SKIP_DIRS

# Extensions considered as project manifests — always included when present.
# Extensions and filenames used only by the smart sampler for priority scoring.
# The collector itself is extension-agnostic.
_MANIFEST_NAMES: frozenset[str] = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "pubspec.yaml",
        "composer.json",
        "Gemfile",
        "mix.exs",
        "README.md",
        "CHANGELOG.md",
        "Dockerfile",
        ".env.example",
    }
)

# Chars-per-token approximation (conservative).
_CHARS_PER_TOKEN = 4

# Patterns always excluded regardless of .skaroignore.
_ALWAYS_SKIP_PATTERNS: tuple[str, ...] = (
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.bin",
    "*.whl",
    "*.egg-info",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.ico",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.pdf",
    "*.zip",
    "*.tar.gz",
    "*.tgz",
)


# ── Ignore file parsing ──────────────────────────────────────────────────────


def _load_ignore_patterns(path: Path) -> list[str]:
    """Read ignore patterns from a .gitignore/.skaroignore file.

    Blank lines and comment lines starting with '#' are skipped.
    Negation patterns (!) are not supported and are silently ignored.
    """
    if not path.exists():
        return []
    patterns: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        patterns.append(line)
    return patterns


def _matches_any(rel: str, patterns: list[str]) -> bool:
    """Return True if *rel* (forward-slash path) matches any pattern."""
    name = rel.split("/")[-1]
    for pat in patterns:
        # Directory-only pattern (trailing /)
        if pat.endswith("/"):
            dir_pat = pat.rstrip("/")
            if any(fnmatch.fnmatch(part, dir_pat) for part in rel.split("/")):
                return True
            continue
        # Pattern with path separator — match against full relative path
        if "/" in pat.lstrip("/"):
            if fnmatch.fnmatch(rel, pat.lstrip("/")):
                return True
        else:
            # No separator — match against each path component and the filename
            if fnmatch.fnmatch(name, pat):
                return True
            if any(fnmatch.fnmatch(part, pat) for part in rel.split("/")):
                return True
    return False


# ── Token estimation ─────────────────────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """Estimate token count using character-based heuristic (~4 chars/token)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ── Main scan result ─────────────────────────────────────────────────────────


@dataclass
class ScanResult:
    """Outcome of a repository scan."""

    # Files included in full: {relative_path: content}
    files: dict[str, str] = field(default_factory=dict)

    # Files present but excluded due to size / sampling: relative paths only
    skipped_paths: list[str] = field(default_factory=list)

    # Paths excluded by .skaroignore (for CLI display)
    skaroignored_paths: list[str] = field(default_factory=list)

    # Flat directory tree (all non-ignored paths, no content)
    tree: list[str] = field(default_factory=list)

    # Whether smart sampling was applied
    sampled: bool = False

    # Estimated token count of included file contents
    estimated_tokens: int = 0

    def format_tree(self) -> str:
        return "\n".join(self.tree)

    def format_files(self) -> str:
        """Format all included files as fenced code blocks for LLM context."""
        parts: list[str] = []
        for path, content in self.files.items():
            parts.append(f"```{path}\n{content}\n```")
        return "\n\n".join(parts)


# ── Scanner ──────────────────────────────────────────────────────────────────


class RepoScanner:
    """Scans a project repository and collects files for LLM analysis.

    Args:
        project_root: Root directory of the project.
        token_limit: Maximum estimated tokens before smart sampling kicks in.
        max_file_size: Files larger than this (bytes) are excluded.
    """

    def __init__(
        self,
        project_root: Path,
        token_limit: int = 200_000,
        max_file_size: int = 100_000,
    ) -> None:
        self.root = project_root
        self.token_limit = token_limit
        self.max_file_size = max_file_size

        self._gitignore_patterns = _load_ignore_patterns(project_root / ".gitignore")
        self._skaroignore_patterns = _load_ignore_patterns(project_root / ".skaroignore")

    # ── Public API ───────────────────────────────────────────────────────────

    def scan(self) -> ScanResult:
        """Run the scan and return a ScanResult."""
        result = ScanResult()

        all_files = self._collect_all_files(result)
        self._build_tree(result)

        total_tokens = sum(
            estimate_tokens(content) for _, content in all_files
        )
        result.estimated_tokens = total_tokens

        if total_tokens <= self.token_limit:
            result.files = dict(all_files)
        else:
            result.sampled = True
            result.files, result.skipped_paths = self._smart_sample(
                all_files, result
            )
            result.estimated_tokens = sum(
                estimate_tokens(c) for c in result.files.values()
            )

        return result

    def skaroignored_files(self) -> list[str]:
        """Return relative paths of files excluded exclusively by .skaroignore."""
        excluded: list[str] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            if self._is_skaro_dir_skip(rel):
                continue
            if self._matches_gitignore(rel):
                continue
            if self._matches_skaroignore(rel):
                excluded.append(rel)
        return excluded

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _is_always_skip(self, rel: str) -> bool:
        name = rel.split("/")[-1]
        return _matches_any(name, list(_ALWAYS_SKIP_PATTERNS))

    def _is_skaro_dir_skip(self, rel: str) -> bool:
        """Skip dirs listed in SKIP_DIRS. Hidden dirs are allowed (e.g. .github)."""
        parts = rel.split("/")
        for part in parts[:-1]:  # directory components only
            if part in SKIP_DIRS:
                return True
        return False

    def _matches_gitignore(self, rel: str) -> bool:
        return _matches_any(rel, self._gitignore_patterns)

    def _matches_skaroignore(self, rel: str) -> bool:
        return _matches_any(rel, self._skaroignore_patterns)

    def _should_skip(self, rel: str) -> bool:
        return (
            self._is_skaro_dir_skip(rel)
            or self._is_always_skip(rel)
            or self._matches_gitignore(rel)
            or self._matches_skaroignore(rel)
        )

    def _read_file(self, path: Path) -> str | None:
        """Read a file if it's within size limits and decodable."""
        if path.stat().st_size > self.max_file_size:
            return None
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except (PermissionError, OSError):
            return None

    def _collect_all_files(self, result: ScanResult) -> list[tuple[str, str]]:
        """Collect all readable text files, populating skaroignored_paths on result.

        Strategy: include everything that is not explicitly excluded or binary.
        This is safer than a whitelist — arbitrary projects may use any extension.
        """
        files: list[tuple[str, str]] = []

        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()

            if self._is_skaro_dir_skip(rel) or self._is_always_skip(rel):
                continue
            if self._matches_gitignore(rel):
                continue
            if self._matches_skaroignore(rel):
                result.skaroignored_paths.append(rel)
                continue

            content = self._read_file(path)
            if content is not None:
                files.append((rel, content))

        return files

    def _build_tree(self, result: ScanResult) -> None:
        """Populate result.tree with ALL non-ignored paths (dirs + files).

        Walks the filesystem independently of which files were collected,
        so the tree is always complete even when sampling is applied.
        """
        seen_dirs: set[str] = set()
        entries: list[str] = []

        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root).as_posix()

            if self._is_skaro_dir_skip(rel) or self._is_always_skip(rel):
                continue
            if self._matches_gitignore(rel):
                continue
            if self._matches_skaroignore(rel):
                continue

            if path.is_dir():
                entries.append(rel + "/")
            else:
                entries.append(rel)

        result.tree = entries

    def _smart_sample(
        self,
        all_files: list[tuple[str, str]],
        result: ScanResult,
    ) -> tuple[dict[str, str], list[str]]:
        """Select the most informative files when total tokens exceed the limit.

        Priority order:
          1. Manifests (package.json, pyproject.toml, README, etc.)
          2. Entry points (main, index, app, server, cli, __main__)
          3. Hub files (most import/require statements)
          4. API layer files (routes, controllers, handlers, views)
          5. Data models (models, schemas, entities, types)
          6. Everything else — included until token budget exhausted
        """
        file_map = dict(all_files)
        selected: dict[str, str] = {}
        skipped: list[str] = []
        budget = self.token_limit

        def add(rel: str) -> bool:
            nonlocal budget
            if rel in selected or rel not in file_map:
                return False
            tokens = estimate_tokens(file_map[rel])
            if tokens > budget:
                skipped.append(rel)
                return False
            selected[rel] = file_map[rel]
            budget -= tokens
            return True

        def score_file(rel: str, content: str) -> int:
            """Compute a priority score (higher = more important)."""
            name = rel.split("/")[-1]
            stem = name.rsplit(".", 1)[0].lower()
            score = 0
            if name in _MANIFEST_NAMES:
                score += 1000
            _entry = {"main", "index", "app", "server", "cli", "__main__", "manage", "start"}
            if stem in _entry:
                score += 800
            _api = {"route", "routes", "controller", "controllers", "handler", "handlers",
                    "router", "routers", "view", "views", "endpoint", "endpoints", "api"}
            if any(k in stem for k in _api) or any(k in rel for k in _api):
                score += 600
            _model = {"model", "models", "schema", "schemas", "entity", "entities",
                      "type", "types", "dto", "dtos"}
            if any(k in stem for k in _model) or any(k in rel for k in _model):
                score += 500
            # Hub: count import statements
            import_count = len(re.findall(r"^(?:import|from|require|use)\b", content, re.MULTILINE))
            score += min(import_count * 10, 300)
            return score

        # Sort by priority
        scored = sorted(
            file_map.items(),
            key=lambda kv: score_file(kv[0], kv[1]),
            reverse=True,
        )

        for rel, _ in scored:
            if budget <= 0:
                skipped.append(rel)
            else:
                add(rel)

        return selected, skipped
