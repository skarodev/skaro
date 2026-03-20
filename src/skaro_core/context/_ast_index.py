"""AST-based signature extraction using tree-sitter.

Extracts public API signatures (classes, functions, methods, types, exports)
from source files.  Produces a compact text index that gives an LLM full
visibility into the project's API surface at a fraction of the token cost
of sending complete source files.

Tree-sitter grammars are optional: if a grammar is not installed the file
is silently skipped (listed in the tree but without signatures).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language, Node

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language registry
# ---------------------------------------------------------------------------

# Maps file extension → (grammar_package, language_getter_name)
# `language_getter_name` is the function name inside the grammar package
# that returns the raw Language pointer.
_GRAMMAR_MAP: dict[str, tuple[str, str]] = {
    ".py": ("tree_sitter_python", "language"),
    ".js": ("tree_sitter_javascript", "language"),
    ".jsx": ("tree_sitter_javascript", "language"),
    ".ts": ("tree_sitter_typescript", "language_typescript"),
    ".tsx": ("tree_sitter_typescript", "language_tsx"),
    ".go": ("tree_sitter_go", "language"),
    ".rs": ("tree_sitter_rust", "language"),
    ".java": ("tree_sitter_java", "language"),
    ".rb": ("tree_sitter_ruby", "language"),
    ".html": ("tree_sitter_html", "language"),
    ".css": ("tree_sitter_css", "language"),
    ".vue": ("tree_sitter_html", "language"),  # Vue parsed as HTML (fallback)
    ".svelte": ("tree_sitter_html", "language"),  # Svelte parsed as HTML (fallback)
}

# Node types that represent "definition" constructs per language family.
# The extractor walks top-level children and looks for these types.
_DEFINITION_TYPES: dict[str, set[str]] = {
    "python": {
        "function_definition", "class_definition", "decorated_definition",
    },
    "javascript": {
        "function_declaration", "class_declaration", "export_statement",
        "lexical_declaration", "variable_declaration",
    },
    "typescript": {
        "function_declaration", "class_declaration", "export_statement",
        "lexical_declaration", "variable_declaration",
        "interface_declaration", "type_alias_declaration", "enum_declaration",
    },
    "tsx": {
        "function_declaration", "class_declaration", "export_statement",
        "lexical_declaration", "variable_declaration",
        "interface_declaration", "type_alias_declaration", "enum_declaration",
    },
    "go": {
        "function_declaration", "method_declaration", "type_declaration",
    },
    "rust": {
        "function_item", "struct_item", "impl_item", "trait_item",
        "enum_item", "type_item", "mod_item",
    },
    "java": {
        "class_declaration", "interface_declaration", "enum_declaration",
        "record_declaration",
    },
    "ruby": {
        "class", "module", "method", "singleton_method",
    },
}

# Node types that represent the "body" of a definition.
_BODY_TYPES: frozenset[str] = frozenset({
    "block",                    # Python, Go, Rust
    "statement_block",          # JS/TS
    "class_body",               # JS/TS/Java
    "interface_body",           # TS/Java
    "enum_body",                # TS/Java/Rust
    "body_statement",           # Ruby
    "field_declaration_list",   # Go struct, Rust struct
    "declaration_list",         # Rust impl/trait
    "body",                     # Ruby class/module
})


# ---------------------------------------------------------------------------
# Tree-sitter helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _load_language(ext: str) -> "Language | None":
    """Load a tree-sitter Language for the given file extension.

    Returns ``None`` when the grammar package is not installed.
    """
    entry = _GRAMMAR_MAP.get(ext)
    if entry is None:
        return None

    pkg_name, getter_name = entry
    try:
        import importlib
        from tree_sitter import Language

        mod = importlib.import_module(pkg_name)
        getter = getattr(mod, getter_name)
        return Language(getter())
    except Exception:  # noqa: BLE001
        log.debug("tree-sitter grammar not available for %s (%s)", ext, pkg_name)
        return None


def _get_parser(ext: str):
    """Create a Parser for the given extension.  Returns ``None`` if unavailable."""
    lang = _load_language(ext)
    if lang is None:
        return None
    try:
        from tree_sitter import Parser

        return Parser(lang)
    except TypeError:
        # Older tree-sitter API: Parser() then set .language
        from tree_sitter import Parser

        p = Parser()
        p.language = lang  # type: ignore[attr-defined]
        return p


def _lang_family(ext: str) -> str:
    """Map extension to language family name."""
    mapping = {
        ".py": "python",
        ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "tsx",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".html": "html", ".css": "css",
        ".vue": "html", ".svelte": "html",
    }
    return mapping.get(ext, "")


# ---------------------------------------------------------------------------
# Signature extraction
# ---------------------------------------------------------------------------

def _extract_header(node: "Node", source: bytes) -> str:
    """Extract the declaration header (everything before the body)."""
    for child in node.children:
        if child.type in _BODY_TYPES:
            raw = source[node.start_byte:child.start_byte].decode("utf-8", errors="replace")
            raw = raw.rstrip()
            # Remove trailing opening chars
            raw = raw.rstrip("{").rstrip(":").rstrip()
            return raw
    # No body child — take first line
    full = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    return full.split("\n")[0].rstrip()


def _extract_short_body(node: "Node", source: bytes, max_chars: int = 200) -> str:
    """Extract full node text when it's compact (types, interfaces, enums)."""
    text = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    if len(text) <= max_chars:
        return text.rstrip()
    return _extract_header(node, source)


def _is_exported(node: "Node") -> bool:
    """Check if a Rust/Go/Java node has a public visibility modifier."""
    for child in node.children:
        if child.type in ("visibility_modifier", "modifiers"):
            text = child.text
            if text and b"pub" in text:
                return True
    # Go: exported if first letter is uppercase
    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            name = child.text.decode("utf-8", errors="replace") if child.text else ""
            if name and name[0].isupper():
                return True
    return True  # default to include


def _walk_children(node: "Node"):
    """Yield direct children of a node."""
    for child in node.children:
        yield child


def _extract_class_methods(node: "Node", source: bytes, lang: str, indent: str = "    ") -> list[str]:
    """Extract method signatures from within a class/impl/trait body."""
    results = []
    method_types = {
        "python": {"function_definition", "decorated_definition"},
        "javascript": {"method_definition", "public_field_definition"},
        "typescript": {"method_definition", "public_field_definition", "method_signature"},
        "tsx": {"method_definition", "public_field_definition", "method_signature"},
        "java": {"method_declaration", "constructor_declaration", "field_declaration"},
        "ruby": {"method", "singleton_method"},
        "rust": {"function_item"},
        "go": set(),  # Go methods are at module level
    }
    target_types = method_types.get(lang, set())

    for child in _deep_walk_body(node):
        if child.type in target_types:
            inner = child
            # Unwrap decorated_definition for Python
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in ("function_definition", "class_definition"):
                        inner = sub
                        break
            header = _extract_header(inner, source)
            if header:
                results.append(indent + header)
    return results


def _deep_walk_body(node: "Node"):
    """Walk into the body of a definition, yielding direct members."""
    for child in node.children:
        if child.type in _BODY_TYPES:
            yield from child.children
            return
    # Some languages have the body as direct children
    yield from node.children


# ---------------------------------------------------------------------------
# Main extraction per file
# ---------------------------------------------------------------------------

def extract_signatures(filepath: Path) -> list[str]:
    """Extract API signatures from a single source file.

    Returns a list of signature lines.  Empty list if the file cannot be
    parsed (unsupported language, syntax error, etc.).
    """
    ext = filepath.suffix.lower()
    parser = _get_parser(ext)
    if parser is None:
        return []

    try:
        source = filepath.read_bytes()
    except (OSError, PermissionError):
        return []

    try:
        tree = parser.parse(source)
    except Exception:  # noqa: BLE001
        return []

    lang = _lang_family(ext)
    definition_types = _DEFINITION_TYPES.get(lang, set())
    if not definition_types:
        return []

    lines: list[str] = []
    root = tree.root_node

    for node in root.children:
        if node.type not in definition_types:
            continue

        # Handle Python decorated definitions
        if node.type == "decorated_definition":
            inner = None
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    inner = child
                    break
            if inner is None:
                continue
            # Include decorator text
            header = _extract_header(inner, source)
            for child in node.children:
                if child.type == "decorator":
                    dec_text = source[child.start_byte:child.end_byte].decode("utf-8", errors="replace").rstrip()
                    lines.append(dec_text)
            if header:
                lines.append(header)
                if inner.type == "class_definition":
                    lines.extend(_extract_class_methods(inner, source, lang))
            continue

        # Handle export statements (JS/TS)
        if node.type == "export_statement":
            for child in node.children:
                if child.type in definition_types and child.type != "export_statement":
                    header = _extract_header(child, source)
                    if header:
                        lines.append("export " + header if not header.startswith("export") else header)
                        if child.type in ("class_declaration", "interface_declaration"):
                            lines.extend(_extract_class_methods(child, source, lang))
                    break
            else:
                # Simple re-export or default export
                header = _extract_header(node, source)
                if header:
                    lines.append(header)
            continue

        # Compact types: interface, type alias, enum — include full body if short
        if node.type in ("interface_declaration", "type_alias_declaration", "enum_declaration", "enum_item"):
            text = _extract_short_body(node, source, max_chars=300)
            if text:
                lines.append(text)
            continue

        # Class definitions
        if node.type in ("class_definition", "class_declaration", "class",
                          "struct_item", "impl_item", "trait_item", "module"):
            header = _extract_header(node, source)
            if header:
                lines.append(header)
                lines.extend(_extract_class_methods(node, source, lang))
            continue

        # Go type declarations (may contain struct/interface)
        if node.type == "type_declaration":
            text = _extract_short_body(node, source, max_chars=500)
            if text:
                lines.append(text)
            continue

        # Regular function / method declarations
        header = _extract_header(node, source)
        if header:
            lines.append(header)

    return lines


# ---------------------------------------------------------------------------
# Project-wide index
# ---------------------------------------------------------------------------

def build_project_index(
    root: Path,
    *,
    skip_dirs: set[str] | None = None,
    source_extensions: set[str] | None = None,
    max_files: int = 200,
) -> str:
    """Build a compact signature index for an entire project.

    Args:
        root: Project root directory.
        skip_dirs: Directory names to skip.
        source_extensions: File extensions to include.  Defaults to the
            set of extensions that have a tree-sitter grammar registered
            in ``_GRAMMAR_MAP``.
        max_files: Maximum number of files to process.

    Returns:
        Formatted text ready to embed in an LLM prompt.
        Empty string if no signatures were extracted.
    """
    from skaro_core.phases.base import SKIP_DIRS

    if skip_dirs is None:
        skip_dirs = SKIP_DIRS
    if source_extensions is None:
        source_extensions = set(_GRAMMAR_MAP.keys())

    sections: list[str] = []
    file_count = 0

    for path in sorted(root.rglob("*")):
        if file_count >= max_files:
            break
        if not path.is_file():
            continue
        if path.suffix.lower() not in source_extensions:
            continue
        parts = path.relative_to(root).parts
        # Skip dot-directories but NOT dot-files (.env, .eslintrc)
        if any(p in skip_dirs or p.startswith(".") for p in parts[:-1]):
            continue

        file_count += 1
        rel = str(path.relative_to(root)).replace("\\", "/")
        sigs = extract_signatures(path)

        if sigs:
            sections.append(f"## {rel}\n" + "\n".join(sigs))
        else:
            # File listed without signatures (grammar unavailable or no definitions)
            sections.append(f"## {rel}\n(signatures not available)")

    if not sections:
        return ""

    return "\n\n".join(sections)
