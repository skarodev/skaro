"""Analytics API — upload/analyze technical specifications (ТЗ)."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.deps import get_am, get_project_root, get_ws_manager, llm_phase, ConnectionManager

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

TZ_FILENAME = "ts.md"
ANALYTICS_REPORT = "analytics-report.md"
REQUIREMENTS_DIR = "requirements"
REVIEW_FILENAME = "review.md"


def _tz_path(am: ArtifactManager) -> Path:
    """Path to the stored ТЗ document."""
    return am.skaro / TZ_FILENAME


def _analytics_report_path(am: ArtifactManager) -> Path:
    """Path to the analytics report."""
    return am.skaro / ANALYTICS_REPORT


def _requirements_dir(am: ArtifactManager) -> Path:
    """Directory for individual requirement files."""
    d = am.skaro / REQUIREMENTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _review_path(am: ArtifactManager) -> Path:
    """Path to the TS review report."""
    return am.skaro / REVIEW_FILENAME


def _req_review_path(am: ArtifactManager) -> Path:
    """Path to the requirements review report."""
    return am.skaro / "requirements-review.md"


def _list_requirements(am: ArtifactManager, req_type: str | None = None) -> list[dict[str, Any]]:
    """List all requirements as structured objects (like ADRs)."""
    import json
    req_dir = _requirements_dir(am)
    if not req_dir.is_dir():
        return []

    reqs = []
    for f in sorted(req_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        # Extract title from first line (# heading or first line)
        lines = content.strip().split("\n")
        raw_title = lines[0].lstrip("# ").strip() if lines else f.stem
        # Remove ID prefix like "FR-001: " from title for cleaner display
        title = re.sub(r"^[\w]+-\d+:\s*", "", raw_title).strip()
        if not title:
            title = raw_title
        # Extract ID from filename (e.g., "FR-001.md")
        req_id = f.stem
        # Read metadata
        meta_file = req_dir / f"{req_id}.json"
        status = "proposed"
        date = ""
        rtype = "FR"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                status = meta.get("status", "proposed")
                date = meta.get("date", "")
                rtype = meta.get("type", "FR")
            except (json.JSONDecodeError, OSError):
                pass

        # Also try to extract type from content if not in meta
        if rtype == "FR":
            type_match = re.search(r"\*\*Type:\*\*\s*(\w+)", content)
            if type_match:
                rtype = type_match.group(1)

        # Filter by type if requested
        if req_type and rtype.upper() != req_type.upper():
            continue

        reqs.append({
            "id": req_id,
            "title": title,
            "content": content,
            "filename": f.name,
            "status": status,
            "date": date,
            "type": rtype,
        })
    return reqs


def _next_req_id(am: ArtifactManager) -> str:
    """Generate next requirement ID (FR-001, FR-002, ...)."""
    reqs = _list_requirements(am)
    if not reqs:
        return "FR-001"
    max_num = 0
    for r in reqs:
        m = re.match(r"FR-(\d+)", r["id"])
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"FR-{max_num + 1:03d}"


# Requirement type prefixes
REQ_TYPE_PREFIXES = {
    "FR": "FR",   # Functional
    "NFR": "NFR", # Non-Functional
    "IR": "IR",   # Integration
    "DR": "DR",   # Data
    "BR": "BR",   # Business Rule
    "CR": "CR",   # Compliance
    "UR": "UR",   # UI/UX
}


def _next_req_id_for_type(am: ArtifactManager, req_type: str) -> str:
    """Generate next requirement ID for a specific type."""
    prefix = REQ_TYPE_PREFIXES.get(req_type.upper(), "FR")
    reqs = _list_requirements(am)
    max_num = 0
    for r in reqs:
        m = re.match(rf"{prefix}-(\d+)", r["id"])
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{prefix}-{max_num + 1:03d}"


def _get_llm_adapter(project_root: Path, phase: str = "analytics"):
    """Create LLM adapter with token tracking."""
    from skaro_core.llm.base import create_llm_adapter
    from skaro_core.config import load_config
    from skaro_core.phases.base import _TrackingLLMAdapter
    config = load_config(project_root)
    llm_config = config.llm_for_phase(phase)
    inner = create_llm_adapter(llm_config)
    return _TrackingLLMAdapter(inner, project_root, phase=phase)


def _load_prompt(name: str, project_root: Path) -> str:
    """Load prompt template with language instruction."""
    from skaro_core.config import load_config
    from skaro_core.phases.base import BasePhase

    config = load_config(project_root)

    # Try project-level override first
    project_override = project_root / ".skaro" / "prompts" / f"{name}.md"
    if project_override.exists():
        template = project_override.read_text(encoding="utf-8")
    else:
        # Fall back to built-in prompt
        builtin = Path(__file__).parent.parent.parent / "skaro_core" / "prompts" / f"{name}.md"
        if builtin.exists():
            template = builtin.read_text(encoding="utf-8")
        else:
            template = ""

    # Prepend language instruction if not English
    lang = config.lang
    if lang and lang != "en":
        lang_name = BasePhase._LANG_NAMES.get(lang, lang)
        lang_instruction = f"IMPORTANT: You MUST respond entirely in {lang_name}. All headings, descriptions, and text must be in {lang_name}.\n\n"
        template = lang_instruction + template

    return template


def _docx_to_markdown(content: bytes) -> str:
    """Convert docx bytes to clean markdown text."""
    import tempfile, os, re
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        try:
            import mammoth
            with open(tmp_path, "rb") as f:
                result = mammoth.convert_to_markdown(f)
                raw = result.value
        except ImportError:
            # Fallback: try python-docx + basic conversion
            from docx import Document
            doc = Document(tmp_path)
            lines = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    lines.append("")
                    continue
                style = para.style.name if para.style else ""
                if "Heading 1" in style:
                    lines.append(f"# {text}")
                elif "Heading 2" in style:
                    lines.append(f"## {text}")
                elif "Heading 3" in style:
                    lines.append(f"### {text}")
                else:
                    lines.append(text)
            raw = "\n".join(lines)

        return _clean_markdown(raw)
    finally:
        os.unlink(tmp_path)


def _clean_markdown(text: str) -> str:
    """Clean up mammoth markdown output."""
    import re

    # Remove HTML anchor tags: <a id="..."></a>
    text = re.sub(r'<a\s+id="[^"]*"\s*>\s*</a>', '', text)

    # Remove any remaining HTML tags (but keep content)
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up double underscores used as formatting (mammoth artifact)
    # Replace __text__ with **text** for bold
    text = re.sub(r'__(.+?)__', r'**\1**', text)

    # Remove leftover standalone __
    text = text.replace('__', '')

    # Fix multiple consecutive blank lines (max 2)
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    # Fix lines that are just whitespace
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # Strip trailing whitespace but preserve blank lines
        cleaned.append(line.rstrip())

    return '\n'.join(cleaned).strip()


@router.get("")
async def get_analytics(am: ArtifactManager = Depends(get_am)):
    """Get current ТЗ, analytics report, requirements, and review if they exist."""
    tz_path = _tz_path(am)
    report_path = _analytics_report_path(am)
    review_file = _review_path(am)

    tz_content = ""
    if tz_path.exists():
        tz_content = tz_path.read_text(encoding="utf-8")

    report_content = ""
    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")

    review_content = ""
    if review_file.exists():
        review_content = review_file.read_text(encoding="utf-8")

    req_review_file = _req_review_path(am)
    req_review_content = ""
    if req_review_file.exists():
        req_review_content = req_review_file.read_text(encoding="utf-8")

    all_reqs = _list_requirements(am)
    # Count by type
    type_counts = {}
    for r in all_reqs:
        t = r.get("type", "FR")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "has_tz": tz_path.exists(),
        "tz_content": tz_content,
        "has_report": report_path.exists(),
        "report_content": report_content,
        "requirements": all_reqs,
        "type_counts": type_counts,
        "has_review": review_file.exists(),
        "review_content": review_content,
        "has_req_review": req_review_file.exists(),
        "req_review_content": req_review_content,
    }


@router.put("")
async def save_tz(
    body: dict[str, Any],
    am: ArtifactManager = Depends(get_am),
):
    """Save or update the ТЗ (technical specification) as text."""
    content = body.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="ТЗ content cannot be empty")

    tz_path = _tz_path(am)
    tz_path.parent.mkdir(parents=True, exist_ok=True)
    tz_path.write_text(content, encoding="utf-8")

    return {"success": True, "message": "ТЗ saved"}


@router.post("/upload")
async def upload_tz(
    file: UploadFile = File(...),
    am: ArtifactManager = Depends(get_am),
):
    """Upload a ТЗ file (docx or markdown)."""
    content = await file.read()

    if file.filename and file.filename.endswith(".docx"):
        try:
            md_content = _docx_to_markdown(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to convert docx: {e}")
    else:
        # Assume text/markdown
        md_content = content.decode("utf-8", errors="replace")

    tz_path = _tz_path(am)
    tz_path.parent.mkdir(parents=True, exist_ok=True)
    tz_path.write_text(md_content, encoding="utf-8")

    return {
        "success": True,
        "message": f"ТЗ uploaded from {file.filename}",
        "content": md_content,
    }


@router.post("/run")
async def run_analytics(
    ws: ConnectionManager = Depends(get_ws_manager),
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    """Run the Analytics phase on the current ТЗ."""
    from skaro_core.phases.analytics import AnalyticsPhase

    tz_path = _tz_path(am)
    if not tz_path.exists():
        raise HTTPException(status_code=400, detail="No ТЗ found. Upload or paste a technical specification first.")

    tz_content = tz_path.read_text(encoding="utf-8")
    if not tz_content.strip():
        raise HTTPException(status_code=400, detail="ТЗ is empty")

    # Create a temporary task-like directory for analytics
    analytics_task_dir = am.skaro / "analytics"
    analytics_task_dir.mkdir(parents=True, exist_ok=True)
    spec_path = analytics_task_dir / "spec.md"
    spec_path.write_text(tz_content, encoding="utf-8")

    phase = AnalyticsPhase(
        artifacts=am,
        project_root=project_root,
    )

    async with llm_phase(ws, "analytics", phase):
        result = await phase.run(task="analytics")

    if result.success:
        # Move report to expected location
        report_in_task = analytics_task_dir / "analytics-report.md"
        if report_in_task.exists():
            report_in_task.rename(_analytics_report_path(am))

        await ws.broadcast({"event": "phase:completed", "phase": "analytics"})
        return {
            "success": True,
            "message": result.message,
            "report": result.data.get("report", "") if result.data else "",
        }
    else:
        raise HTTPException(status_code=500, detail=result.message)


@router.post("/clean")
async def clean_ts_with_llm(
    ws: ConnectionManager = Depends(get_ws_manager),
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    """Clean up TS document using LLM (fix formatting, remove artifacts)."""
    from skaro_core.llm.base import LLMMessage

    tz_path = _tz_path(am)
    if not tz_path.exists():
        raise HTTPException(status_code=400, detail="No TS found")

    raw_content = tz_path.read_text(encoding="utf-8")
    prompt_template = _load_prompt("ts-clean", project_root)
    prompt = prompt_template + f"\n\n---\n\nOriginal document:\n\n{raw_content}"

    adapter = _get_llm_adapter(project_root)

    async with llm_phase(ws, "analytics", None):
        response = await adapter.complete([
            LLMMessage(role="user", content=prompt),
        ])

    cleaned = response.content.strip()
    # Remove markdown fences if LLM added them
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    tz_path.write_text(cleaned, encoding="utf-8")

    await ws.broadcast({"event": "analytics:cleaned"})

    return {
        "success": True,
        "message": "TS cleaned via LLM",
        "content": cleaned,
    }


@router.post("/generate-requirements")
async def generate_requirements(
    ws: ConnectionManager = Depends(get_ws_manager),
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    """Generate formal requirements from the entire TS document."""
    from skaro_core.llm.base import LLMMessage

    tz_path = _tz_path(am)
    if not tz_path.exists():
        raise HTTPException(status_code=400, detail="No TS found")

    ts_content = tz_path.read_text(encoding="utf-8")
    prompt_template = _load_prompt("requirements-generate", project_root)
    prompt = prompt_template + "\n\n---\n\n## Technical Specification\n\n" + ts_content

    adapter = _get_llm_adapter(project_root)

    async with llm_phase(ws, "requirements", None):
        response = await adapter.complete([
            LLMMessage(role="user", content=prompt),
        ])

    # Parse generated requirements and save as individual files
    raw = response.content.strip()
    # Remove markdown fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    # Split by ### headers to get individual requirements
    sections = re.split(r"^### ", raw, flags=re.MULTILINE)
    created = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split("\n")
        title_line = lines[0].strip() if lines else ""
        content = section

        # Extract type from **Type:** line
        type_match = re.search(r"\*\*Type:\*\*\s*(\w+)", content)
        req_type = type_match.group(1).upper() if type_match else "FR"
        # Validate type
        if req_type not in REQ_TYPE_PREFIXES:
            req_type = "FR"

        # Extract ID from title (e.g., "FR-001: Title")
        id_match = re.match(r"((?:FR|NFR|IR|DR|BR|CR|UR)-\d+)", title_line)
        if id_match:
            req_id = id_match.group(1)
        else:
            req_id = _next_req_id_for_type(am, req_type)

        # Normalize the title to use correct ID
        # Remove any ID prefix like "FR-001:", "BR-001:", "REQ_ID:" from the title
        clean_title = re.sub(r"^[\w]+-\d+:\s*", "", title_line)
        # Also remove "REQ_ID: " prefix if LLM duplicated it
        clean_title = re.sub(r"^REQ_ID:\s*", "", clean_title)
        # Remove leading/trailing whitespace and markdown bold
        clean_title = clean_title.strip().strip("*")
        if not clean_title:
            clean_title = req_id
        final_content = f"# {req_id}: {clean_title}\n" + "\n".join(lines[1:])

        req_file = _requirements_dir(am) / f"{req_id}.md"
        # Don't overwrite existing
        if not req_file.exists():
            req_file.write_text(final_content, encoding="utf-8")
            # Save metadata with type
            import json
            from datetime import datetime, timezone
            meta_file = _requirements_dir(am) / f"{req_id}.json"
            meta_file.write_text(json.dumps({
                "type": req_type,
                "status": "proposed",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }, ensure_ascii=False), encoding="utf-8")
            created.append(req_id)

    await ws.broadcast({"event": "analytics:requirements_generated", "count": len(created)})

    return {
        "success": True,
        "message": f"Generated {len(created)} requirements",
        "requirements": _list_requirements(am),
        "created": created,
    }


@router.post("/generate-requirement")
async def generate_requirement(
    body: dict[str, Any],
    ws: ConnectionManager = Depends(get_ws_manager),
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    """Generate a single formal requirement from selected text."""
    from skaro_core.llm.base import LLMMessage

    selected_text = body.get("text", "")
    if not selected_text.strip():
        raise HTTPException(status_code=400, detail="No text provided")

    req_id = _next_req_id(am)
    prompt_template = _load_prompt("requirement-from-text", project_root)
    prompt = prompt_template.replace("REQ_ID", req_id) + f"\n\n---\n\nSource text:\n\n{selected_text}"

    adapter = _get_llm_adapter(project_root)

    async with llm_phase(ws, "requirements", None):
        response = await adapter.complete([
            LLMMessage(role="user", content=prompt),
        ])

    raw = response.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    req_file = _requirements_dir(am) / f"{req_id}.md"
    req_file.write_text(f"# {raw}", encoding="utf-8")

    await ws.broadcast({"event": "analytics:requirement_added", "id": req_id})

    return {
        "success": True,
        "message": f"Requirement {req_id} created",
        "requirement": {
            "id": req_id,
            "title": raw.split("\n")[0].lstrip("# ").strip() if raw else req_id,
            "content": raw,
        },
        "requirements": _list_requirements(am),
    }


@router.post("/review")
async def review_ts(
    ws: ConnectionManager = Depends(get_ws_manager),
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    """Generate a critical review of the TS document."""
    from skaro_core.llm.base import LLMMessage

    tz_path = _tz_path(am)
    if not tz_path.exists():
        raise HTTPException(status_code=400, detail="No TS found")

    ts_content = tz_path.read_text(encoding="utf-8")
    prompt_template = _load_prompt("ts-review", project_root)
    prompt = prompt_template + f"\n\n---\n\nTechnical Specification:\n\n{ts_content}"

    adapter = _get_llm_adapter(project_root)

    async with llm_phase(ws, "review", None):
        response = await adapter.complete([
            LLMMessage(role="user", content=prompt),
        ])

    review = response.content.strip()
    if review.startswith("```"):
        lines = review.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        review = "\n".join(lines)

    review_file = _review_path(am)
    review_file.write_text(review, encoding="utf-8")

    await ws.broadcast({"event": "analytics:review_done"})

    return {
        "success": True,
        "message": "Review completed",
        "review": review,
    }


@router.post("/review-requirements")
async def review_requirements(
    ws: ConnectionManager = Depends(get_ws_manager),
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    """Review all requirements for duplicates, contradictions, and incompleteness."""
    from skaro_core.llm.base import LLMMessage

    reqs = _list_requirements(am)
    if not reqs:
        raise HTTPException(status_code=400, detail="No requirements to review")

    # Build requirements text
    reqs_text = "\n\n---\n\n".join(
        f"### {r['id']} ({r['type']}): {r['title']}\n\n{r['content']}"
        for r in reqs
    )

    prompt_template = _load_prompt("requirements-review", project_root)
    prompt = prompt_template + f"\n\n---\n\n## Requirements\n\n{reqs_text}"

    adapter = _get_llm_adapter(project_root)

    async with llm_phase(ws, "requirements-review", None):
        response = await adapter.complete([
            LLMMessage(role="user", content=prompt),
        ])

    req_review = response.content.strip()
    if req_review.startswith("```"):
        lines = req_review.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        req_review = "\n".join(lines)

    review_file = _req_review_path(am)
    review_file.write_text(req_review, encoding="utf-8")

    await ws.broadcast({"event": "analytics:req_review_done"})

    return {
        "success": True,
        "message": "Requirements review completed",
        "review": req_review,
    }


@router.get("/requirements")
async def get_requirements(am: ArtifactManager = Depends(get_am)):
    """List all requirements."""
    return {"requirements": _list_requirements(am)}


@router.get("/requirements/{req_id}")
async def get_requirement(req_id: str, am: ArtifactManager = Depends(get_am)):
    """Get a single requirement by ID."""
    req_file = _requirements_dir(am) / f"{req_id}.md"
    if not req_file.exists():
        raise HTTPException(status_code=404, detail=f"Requirement {req_id} not found")
    content = req_file.read_text(encoding="utf-8")

    # Read status from metadata
    import json
    meta_file = _requirements_dir(am) / f"{req_id}.json"
    status = "proposed"
    date = ""
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            status = meta.get("status", "proposed")
            date = meta.get("date", "")
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "id": req_id,
        "title": content.split("\n")[0].lstrip("# ").strip() if content else req_id,
        "content": content,
        "status": status,
        "date": date,
    }


@router.put("/requirements/{req_id}")
async def save_requirement_content(
    req_id: str,
    body: dict[str, Any],
    am: ArtifactManager = Depends(get_am),
):
    """Save/update requirement content."""
    req_file = _requirements_dir(am) / f"{req_id}.md"
    if not req_file.exists():
        raise HTTPException(status_code=404, detail=f"Requirement {req_id} not found")

    content = body.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    req_file.write_text(content, encoding="utf-8")
    return {"success": True, "message": f"Requirement {req_id} saved"}


@router.patch("/requirements/{req_id}/status")
async def update_requirement_status(
    req_id: str,
    body: dict[str, Any],
    am: ArtifactManager = Depends(get_am),
):
    """Update requirement status (proposed/accepted/deprecated/superseded)."""
    import json
    from datetime import datetime, timezone

    req_file = _requirements_dir(am) / f"{req_id}.md"
    if not req_file.exists():
        raise HTTPException(status_code=404, detail=f"Requirement {req_id} not found")

    new_status = body.get("status", "")
    valid_statuses = ["proposed", "accepted", "deprecated", "superseded"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    meta_file = _requirements_dir(am) / f"{req_id}.json"
    meta = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    meta["status"] = new_status
    meta["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "success": True,
        "message": f"Requirement {req_id} status changed to {new_status}",
        "requirements": _list_requirements(am),
    }


@router.delete("/requirements/{req_id}")
async def delete_requirement(req_id: str, am: ArtifactManager = Depends(get_am)):
    """Delete a single requirement."""
    req_dir = _requirements_dir(am)
    req_file = req_dir / f"{req_id}.md"
    meta_file = req_dir / f"{req_id}.json"

    if not req_file.exists():
        raise HTTPException(status_code=404, detail=f"Requirement {req_id} not found")

    req_file.unlink()
    if meta_file.exists():
        meta_file.unlink()

    return {
        "success": True,
        "message": f"Requirement {req_id} deleted",
        "requirements": _list_requirements(am),
    }


@router.delete("/requirements")
async def clear_all_requirements(am: ArtifactManager = Depends(get_am)):
    """Delete all requirements."""
    import shutil
    req_dir = _requirements_dir(am)
    if req_dir.is_dir():
        shutil.rmtree(req_dir)
    return {"success": True, "message": "All requirements cleared"}


@router.get("/review")
async def get_review(am: ArtifactManager = Depends(get_am)):
    """Get the TS review if it exists."""
    review_file = _review_path(am)
    if not review_file.exists():
        return {"has_review": False, "review": ""}
    return {
        "has_review": True,
        "review": review_file.read_text(encoding="utf-8"),
    }


@router.delete("")
async def clear_analytics(am: ArtifactManager = Depends(get_am)):
    """Clear ТЗ, analytics report, requirements, and review."""
    tz_path = _tz_path(am)
    report_path = _analytics_report_path(am)
    review_file = _review_path(am)
    req_dir = _requirements_dir(am)
    analytics_dir = am.skaro / "analytics"

    for p in [tz_path, report_path, review_file]:
        if p.exists():
            p.unlink()

    if req_dir.is_dir():
        import shutil
        shutil.rmtree(req_dir)

    if analytics_dir.exists():
        import shutil
        shutil.rmtree(analytics_dir)

    return {"success": True, "message": "Analytics data cleared"}
