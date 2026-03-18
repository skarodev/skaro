"""Analytics API — upload/analyze technical specifications (ТЗ)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.deps import get_am, get_project_root, get_ws_manager, llm_phase, ConnectionManager

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

TZ_FILENAME = "ts.md"
ANALYTICS_REPORT = "analytics-report.md"


def _tz_path(am: ArtifactManager) -> Path:
    """Path to the stored ТЗ document."""
    return am.skaro / TZ_FILENAME


def _analytics_report_path(am: ArtifactManager) -> Path:
    """Path to the analytics report."""
    return am.skaro / ANALYTICS_REPORT


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
    """Get current ТЗ and analytics report if they exist."""
    tz_path = _tz_path(am)
    report_path = _analytics_report_path(am)

    tz_content = ""
    if tz_path.exists():
        tz_content = tz_path.read_text(encoding="utf-8")

    report_content = ""
    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")

    return {
        "has_tz": tz_path.exists(),
        "tz_content": tz_content,
        "has_report": report_path.exists(),
        "report_content": report_content,
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


@router.delete("")
async def clear_analytics(am: ArtifactManager = Depends(get_am)):
    """Clear ТЗ and analytics report."""
    tz_path = _tz_path(am)
    report_path = _analytics_report_path(am)
    analytics_dir = am.skaro / "analytics"

    for p in [tz_path, report_path]:
        if p.exists():
            p.unlink()

    if analytics_dir.exists():
        import shutil
        shutil.rmtree(analytics_dir)

    return {"success": True, "message": "Analytics data cleared"}
