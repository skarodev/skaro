"""DevPlan parsers: extract milestones from LLM response (JSON / Markdown fallback)."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_milestones(content: str) -> list[dict[str, Any]]:
    """Parse LLM response into list of milestones with tasks.

    Tries fenced JSON first, then unbalanced JSON, then markdown fallback.
    """
    # Try fenced JSON blocks (longest first — most likely the full response)
    fenced = re.findall(r"```json\s*([\s\S]*?)\s*```", content)
    for block in sorted(fenced, key=len, reverse=True):
        block = block.strip()
        if block.startswith("["):
            result = _try_parse_json_milestones(block)
            if result is not None:
                return result

    # Try unbalanced JSON (model forgot closing fence)
    for m in re.finditer(r"\[", content):
        candidate = _extract_balanced_json(content, m.start())
        if candidate:
            result = _try_parse_json_milestones(candidate)
            if result is not None:
                return result

    # Fallback: parse markdown structure
    return parse_milestones_markdown(content)


def parse_update_response(content: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse update response into (updated_devplan_markdown, new_milestones_list)."""
    devplan_md = ""
    new_milestones: list[dict[str, Any]] = []

    devplan_match = re.search(
        r"```(?:markdown)?\s*\n(# Development Plan[\s\S]*?)```",
        content,
    )
    if devplan_match:
        devplan_md = devplan_match.group(1).strip()

    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
    if json_match:
        block = json_match.group(1).strip()
        if block.startswith("["):
            try:
                data = json.loads(block)
                if isinstance(data, list) and all(isinstance(d, dict) for d in data):
                    new_milestones = data
            except json.JSONDecodeError:
                pass

    return devplan_md, new_milestones


def parse_milestones_markdown(content: str) -> list[dict[str, Any]]:
    """Fallback: parse markdown sections into milestones with tasks.

    Supports two task formats:
      - ``### Task Name`` heading style
      - ``| # | name | status | deps | description |`` table style
        (produced by ``build_devplan_markdown``)
    """
    milestones: list[dict[str, Any]] = []
    current_ms: dict[str, Any] | None = None
    current_task: dict[str, Any] | None = None
    spec_lines: list[str] = []
    in_spec = False
    in_table = False

    for line in content.splitlines():
        # Milestone header (## level)
        ms_match = re.match(r"^##\s+(?:Milestone\s+\d+[.:]\s*)?(.+)", line)
        if ms_match and not in_spec:
            # Skip known non-milestone ## headings
            heading_text = ms_match.group(1).strip()
            if heading_text.lower() in ("status legend", "change log"):
                _flush_task(current_task, spec_lines, current_ms)
                current_task = None
                spec_lines = []
                if current_ms is not None:
                    milestones.append(current_ms)
                    current_ms = None
                in_table = False
                continue

            _flush_task(current_task, spec_lines, current_ms)
            current_task = None
            spec_lines = []
            in_table = False

            if current_ms is not None:
                milestones.append(current_ms)

            title = heading_text
            slug = make_slug(title)
            idx = len(milestones) + 1
            current_ms = {
                "milestone_slug": f"{idx:02d}-{slug}" if slug else f"{idx:02d}-milestone",
                "milestone_title": title,
                "tasks": [],
            }
            continue

        # _Directory: `milestones/<slug>/`_ — extract original slug
        dir_match = re.match(
            r"^_Directory:\s*`milestones/([^/`]+)/?`_", line
        )
        if dir_match and current_ms is not None:
            current_ms["milestone_slug"] = dir_match.group(1)
            continue

        # Table header/separator — skip but mark we're in a table
        if current_ms is not None and re.match(
            r"^\|\s*#?\s*\|\s*Task\s*\|", line, re.IGNORECASE
        ):
            in_table = True
            continue
        if current_ms is not None and re.match(r"^\|[-|:\s]+\|$", line):
            in_table = True
            continue

        # Table data row: | idx | name | status | deps | description |
        table_row = re.match(
            r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
            line,
        )
        if table_row and current_ms is not None:
            in_table = True
            _flush_task(current_task, spec_lines, current_ms)
            spec_lines = []

            name = table_row.group(1).strip()
            status = table_row.group(2).strip() or "planned"
            deps_raw = table_row.group(3).strip()
            desc = table_row.group(4).strip()

            deps: list[str] = []
            if deps_raw and deps_raw not in ("—", "-", "none", ""):
                deps = [d.strip() for d in deps_raw.split(",") if d.strip()]

            current_task = {
                "name": name,
                "description": desc,
                "status": status,
                "dependencies": deps,
            }
            # Table tasks are self-contained — flush immediately
            _flush_task(current_task, [], current_ms)
            current_task = None
            continue

        # Task header (### level) — heading style
        task_match = re.match(r"^###\s*\d*\.?\s*(.+)", line)
        if task_match and not in_spec and not in_table:
            _flush_task(current_task, spec_lines, current_ms)
            spec_lines = []

            name = task_match.group(1).strip().strip("*").strip()
            current_task = {"name": name, "description": ""}
            continue

        if line.strip().startswith("```") and (
            "spec" in line.lower() or "md" in line.lower()
        ):
            in_spec = True
            continue
        if in_spec and line.strip() == "```":
            in_spec = False
            continue
        if in_spec:
            spec_lines.append(line)
            continue

        if current_task and current_task.get("name") and not spec_lines:
            if line.strip() and not line.startswith("#"):
                desc = line.strip().lstrip("- ").lstrip("> ")
                if current_task["description"]:
                    current_task["description"] += " " + desc
                else:
                    current_task["description"] = desc

    # Flush remaining
    _flush_task(current_task, spec_lines, current_ms)
    if current_ms is not None:
        milestones.append(current_ms)

    return milestones


# ── Internal helpers ────────────────────────────


def make_slug(name: str) -> str:
    """Convert a human-readable name into a directory-safe slug."""
    slug = re.sub(r"[^a-z0-9_-]", "-", name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def wrap_legacy_features(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert flat feature list (old format) into milestone structure."""
    foundation: list[dict[str, Any]] = []
    mvp: list[dict[str, Any]] = []

    for f in features:
        priority = f.get("priority", 99)
        if priority <= 2:
            foundation.append(f)
        else:
            mvp.append(f)

    milestones: list[dict[str, Any]] = []
    if foundation:
        milestones.append({
            "milestone_slug": "01-foundation",
            "milestone_title": "Foundation",
            "description": "Project structure and core components",
            "tasks": foundation,
        })
    if mvp:
        milestones.append({
            "milestone_slug": "02-mvp",
            "milestone_title": "MVP",
            "description": "Minimum viable product features",
            "tasks": mvp,
        })
    if not milestones:
        milestones.append({
            "milestone_slug": "01-mvp",
            "milestone_title": "MVP",
            "description": "",
            "tasks": features,
        })

    return milestones


def _try_parse_json_milestones(text: str) -> list[dict[str, Any]] | None:
    """Try parsing JSON text as milestones. Returns None on failure."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
        return None
    if not data:
        return None

    if "milestone_slug" in data[0]:
        return data
    if "name" in data[0]:
        return wrap_legacy_features(data)

    return None


def _extract_balanced_json(text: str, start: int) -> str | None:
    """Extract a balanced JSON array starting at `start` index."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _flush_task(
    task: dict[str, Any] | None,
    spec_lines: list[str],
    milestone: dict[str, Any] | None,
) -> None:
    """Append current task to milestone if valid."""
    if task and task.get("name"):
        task["spec"] = "\n".join(spec_lines).strip()
        if milestone is not None:
            milestone.setdefault("tasks", []).append(task)
