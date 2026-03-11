"""Determine which project files are relevant for a given plan stage.

Extracts file paths mentioned in the plan or stage section, then expands
the set by tracing local import/require statements.  The result is the set
of files that should be sent to the LLM as full source code (Tier 1).
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Path extraction from text
# ---------------------------------------------------------------------------

_BACKTICK_PATH_RE = re.compile(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z]{1,10})`")
_BARE_PATH_RE = re.compile(
    r"(?:^|\s)([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+\.[a-zA-Z]{1,10})(?=\s|$|,|;|\))",
    re.MULTILINE,
)
_SKIP_PREFIXES = ("http://", "https://", "//", "ftp://")


def extract_paths_from_text(text: str) -> list[str]:
    """Extract candidate file paths from markdown/plan text.

    Returns de-duplicated list preserving first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []

    for pattern in (_BACKTICK_PATH_RE, _BARE_PATH_RE):
        for match in pattern.finditer(text):
            fp = match.group(1).strip()
            if any(fp.startswith(p) for p in _SKIP_PREFIXES):
                continue
            if fp not in seen:
                seen.add(fp)
                result.append(fp)

    return result


# ---------------------------------------------------------------------------
# Import resolution
# ---------------------------------------------------------------------------

_PY_FROM_RE = re.compile(r"^\s*from\s+([\w.]+)\s+import", re.MULTILINE)
_PY_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+)", re.MULTILINE)
_JS_IMPORT_RE = re.compile(
    r"""(?:from|require\()\s*['"]([./][\w./-]+)['"]""",
)
_GO_IMPORT_RE = re.compile(r'"([^"]+)"')


def _resolve_python_imports(content: str, root: Path) -> set[str]:
    """Resolve Python import statements to project-local file paths."""
    found: set[str] = set()

    for pattern in (_PY_FROM_RE, _PY_IMPORT_RE):
        for match in pattern.finditer(content):
            module = match.group(1)
            parts = module.replace(".", "/")
            for candidate in (f"{parts}.py", f"{parts}/__init__.py"):
                if (root / candidate).is_file():
                    found.add(candidate.replace("\\", "/"))
                    break

    return found


def _resolve_js_imports(content: str, file_path: Path, root: Path) -> set[str]:
    """Resolve JS/TS import/require to project-local file paths."""
    found: set[str] = set()
    base_dir = file_path.parent

    for match in _JS_IMPORT_RE.finditer(content):
        rel_import = match.group(1)
        # Try various extensions
        for ext in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js", "/index.tsx"):
            candidate = (base_dir / (rel_import + ext)).resolve()
            try:
                rel_to_root = candidate.relative_to(root.resolve())
                if candidate.is_file():
                    found.add(str(rel_to_root).replace("\\", "/"))
                    break
            except ValueError:
                continue

    return found


def _resolve_go_imports(content: str, file_path: Path, root: Path) -> set[str]:
    """Resolve Go imports — only local packages within the project."""
    found: set[str] = set()

    # Look for import blocks
    for match in _GO_IMPORT_RE.finditer(content):
        import_path = match.group(1)
        # Check if path corresponds to a local directory
        candidate_dir = root / import_path
        if candidate_dir.is_dir():
            for go_file in candidate_dir.glob("*.go"):
                rel = str(go_file.relative_to(root)).replace("\\", "/")
                found.add(rel)

    return found


def find_imports(file_path: Path, root: Path) -> set[str]:
    """Find project-local imports from a source file.

    Returns a set of relative paths (from project root).
    """
    try:
        content = file_path.read_text("utf-8", errors="replace")
    except (OSError, PermissionError):
        return set()

    ext = file_path.suffix.lower()

    if ext == ".py":
        return _resolve_python_imports(content, root)
    if ext in (".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"):
        return _resolve_js_imports(content, file_path, root)
    if ext == ".go":
        return _resolve_go_imports(content, file_path, root)

    # Rust, Java, Ruby — import resolution is more complex;
    # skip for now (their files will still appear in AST index).
    return set()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_relevant_paths(
    text: str,
    root: Path,
    *,
    expand_imports: bool = True,
    max_depth: int = 1,
) -> set[str]:
    """Determine which project files are relevant for a given text context.

    1. Extract file paths mentioned directly in *text*.
    2. Validate they exist on disk (or fuzzy-match by filename).
    3. Optionally expand the set by resolving local import statements.

    Args:
        text: Plan stage section or other context text.
        root: Project root directory.
        expand_imports: Whether to trace imports from discovered files.
        max_depth: How many import levels to follow (1 = direct imports only).

    Returns:
        Set of relative file paths (from project root).
    """
    raw_paths = extract_paths_from_text(text)

    # Build set of existing project files for fuzzy matching
    existing: set[str] | None = None

    relevant: set[str] = set()
    for fp in raw_paths:
        normalized = fp.replace("\\", "/")
        if (root / normalized).is_file():
            relevant.add(normalized)
            continue
        # Fuzzy: check if the filename exists somewhere in the project
        if existing is None:
            from skaro_core.phases.base import SKIP_DIRS
            existing = set()
            for p in root.rglob("*"):
                parts = p.relative_to(root).parts
                # Skip dot-directories but NOT dot-files (.env, .eslintrc)
                if any(d in SKIP_DIRS or d.startswith(".") for d in parts[:-1]):
                    continue
                if p.is_file():
                    existing.add(str(p.relative_to(root)).replace("\\", "/"))

        # Try suffix match: plan says "auth.py" → actual "src/auth/auth.py"
        for ep in existing:
            if ep.endswith("/" + normalized) or ep == normalized:
                relevant.add(ep)
                break

    # Expand with imports
    if expand_imports and relevant:
        current_level = set(relevant)
        for _ in range(max_depth):
            next_level: set[str] = set()
            for fp in current_level:
                abs_path = root / fp
                if abs_path.is_file():
                    imports = find_imports(abs_path, root)
                    new_imports = imports - relevant
                    next_level |= new_imports
            if not next_level:
                break
            relevant |= next_level
            current_level = next_level

    return relevant
