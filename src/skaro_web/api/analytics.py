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


def _list_requirements(am: ArtifactManager) -> list[dict[str, Any]]:
    """List all requirements as structured objects (like ADRs)."""
    req_dir = _requirements_dir(am)
    if not req_dir.is_dir():
        return []

    reqs = []
    for f in sorted(req_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        # Extract title from first line (# heading or first line)
        lines = content.strip().split("\n")
        title = lines[0].lstrip("# ").strip() if lines else f.stem
        # Extract ID from filename (e.g., "FR-001.md")
        req_id = f.stem
        # Read status from metadata file
        meta_file = req_dir / f"{req_id}.json"
        status = "proposed"
        date = ""
        if meta_file.exists():
            import json
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                status = meta.get("status", "proposed")
                date = meta.get("date", "")
            except (json.JSONDecodeError, OSError):
                pass

        reqs.append({
            "id": req_id,
            "title": title,
            "content": content,
            "filename": f.name,
            "status": status,
            "date": date,
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


def _get_llm_adapter(project_root: Path):
    """Create LLM adapter from project config."""
    from skaro_core.llm.base import create_llm_adapter
    from skaro_core.config import load_config
    config = load_config(project_root)
    llm_config = config.llm_for_phase("analytics")
    return create_llm_adapter(llm_config)


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

    return {
        "has_tz": tz_path.exists(),
        "tz_content": tz_content,
        "has_report": report_path.exists(),
        "report_content": report_content,
        "requirements": _list_requirements(am),
        "has_review": review_file.exists(),
        "review_content": review_content,
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
    from skaro_core.llm.base import LLMMessage, create_llm_adapter
    from skaro_core.config import load_config

    tz_path = _tz_path(am)
    if not tz_path.exists():
        raise HTTPException(status_code=400, detail="No TS found")

    raw_content = tz_path.read_text(encoding="utf-8")

    prompt = """Clean up this technical specification document. Fix formatting issues:
- Remove HTML artifacts (anchors, tags)
- Fix broken markdown formatting
- Normalize headings (# structure)
- Fix bullet points and numbering
- Remove duplicate/empty lines
- Keep ALL original content and meaning
- Output clean, well-formatted markdown

Original document:

""" + raw_content

    config = load_config(project_root)
    llm_config = config.llm_for_phase("analytics")
    adapter = create_llm_adapter(llm_config)

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


REQUIREMENTS_PROMPT = """Analyze this technical specification and extract ALL formal requirements.

For each requirement, output EXACTLY in this format:

### {REQ_ID}: {Short Title}

{Detailed description of the requirement in 1-3 sentences}

**Acceptance Criteria:**
- {criterion 1}
- {criterion 2}
- {criterion 3}

---

Generate requirements for:
- Functional requirements (what the system must do)
- Non-functional requirements (performance, security, availability)
- Integration requirements (external systems, APIs)
- Data requirements (storage, migration, validation)

Be thorough. Each requirement should be testable and unambiguous.
Use sequential IDs starting from FR-001.

Return ONLY the requirements list. No preamble."""


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
    prompt = REQUIREMENTS_PROMPT + "\n\n---\n\n## Technical Specification\n\n" + ts_content

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

        # Extract ID from title (e.g., "FR-001: Title")
        id_match = re.match(r"(FR-\d+)", title_line)
        req_id = id_match.group(1) if id_match else _next_req_id(am)

        req_file = _requirements_dir(am) / f"{req_id}.md"
        # Don't overwrite existing
        if not req_file.exists():
            req_file.write_text(f"# {content}", encoding="utf-8")
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

    prompt = f"""Convert this text from a technical specification into a single formal requirement.

Format EXACTLY as:

### {req_id}: {{Short Title}}

{{Detailed description of the requirement in 1-3 sentences}}

**Acceptance Criteria:**
- {{criterion 1}}
- {{criterion 2}}
- {{criterion 3}}

---

Source text:

{selected_text}

Return ONLY the requirement. No preamble."""

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

    prompt = f"""Conduct a thorough critical review of this technical specification.

Your review MUST include these sections:

## 1. Completeness Assessment
- Missing sections or unclear areas
- Undefined requirements or vague statements
- Gaps in acceptance criteria

## 2. Technical Feasibility
- Are the stated requirements technically achievable?
- Are there contradictions between requirements?
- Technology stack compatibility issues

## 3. Risks & Concerns
- List each risk with severity (HIGH/MEDIUM/LOW)
- Security implications
- Performance bottlenecks
- Scalability concerns

## 4. Questions for Clarification
- List specific questions that need answers before development
- Ambiguous terms or requirements

## 5. Recommendations
- Suggested improvements
- Missing best practices
- Standards compliance issues

## 6. Overall Verdict
- Overall quality: EXCELLENT / GOOD / NEEDS_WORK / POOR
- Ready for development: YES / NO / WITH_CONDITIONS
- Summary (2-3 sentences)

Be critical and thorough. Flag ALL issues, even minor ones.

Technical Specification:

{ts_content}

Return ONLY the review report. No preamble."""

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
