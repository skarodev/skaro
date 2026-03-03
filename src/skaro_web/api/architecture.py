"""Architecture endpoints (review, ADRs, invariants)."""

from __future__ import annotations

import json
import re as _re
from datetime import date as _date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.deps import broadcast, get_am, get_project_root, get_ws_manager, llm_phase, ConnectionManager
from skaro_web.api.schemas import (
    ArchAcceptBody,
    ArchReviewBody,
    AdrCreateBody,
    AdrStatusBody,
    ContentBody,
)

router = APIRouter(prefix="/api/architecture", tags=["architecture"])

# Regex to find ## Architectural Invariants section in proposed architecture.
_INVARIANTS_HEADING_RE = _re.compile(
    r"^##\s+Architectural\s+Invariants\s*$", _re.IGNORECASE | _re.MULTILINE
)

# Matches any ## heading (used to find the end of the invariants section).
_NEXT_H2_RE = _re.compile(r"^##\s+", _re.MULTILINE)


def _extract_invariants(text: str) -> str:
    """Extract the Architectural Invariants section from architecture text.

    Returns the section body (without the heading), or empty string if absent.
    """
    match = _INVARIANTS_HEADING_RE.search(text)
    if not match:
        return ""

    body_start = match.end()
    # Find the next ## heading after invariants (= end of section).
    next_heading = _NEXT_H2_RE.search(text, body_start)
    if next_heading:
        body = text[body_start : next_heading.start()]
    else:
        body = text[body_start:]

    return body.strip()


@router.get("")
async def get_architecture(am: ArtifactManager = Depends(get_am)):
    invariants = am.read_invariants()
    architecture = am.read_architecture()
    last_review = am.read_architecture_review()
    adrs = []
    for adr_path in am.list_adrs():
        adrs.append({
            "filename": adr_path.name,
            "content": adr_path.read_text(encoding="utf-8"),
        })
    return {
        "content": architecture,
        "has_architecture": am.has_architecture,
        "architecture_reviewed": am.is_architecture_reviewed,
        "last_review": last_review,
        "invariants": invariants,
        "has_invariants": bool(invariants.strip()),
        "adrs": adrs,
        "adr_count": len(adrs),
    }


@router.post("/review")
async def run_arch_review(
    request: Request,
    payload: ArchReviewBody = ArchReviewBody(),
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    draft = payload.architecture_draft or am.read_architecture()
    domain = payload.domain_description
    if not draft.strip():
        return {"success": False, "message": "Architecture draft is required."}

    from skaro_core.phases.architecture import ArchitecturePhase

    phase = ArchitecturePhase(project_root=project_root)
    async with llm_phase(ws, "architecture", phase):
        result = await phase.run(architecture_draft=draft, domain_description=domain)
    await ws.broadcast({"event": "phase:completed", "phase": "architecture"})
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "artifacts_created": result.artifacts_created,
    }


@router.post("/apply-review")
async def apply_arch_review(
    request: Request,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Apply review recommendations: LLM rewrites architecture."""
    architecture = am.read_architecture()
    if not architecture.strip():
        return {"success": False, "message": "No architecture to improve."}

    review = ""
    review_path = am.skaro / "architecture" / "review.md"
    if review_path.exists():
        review = review_path.read_text(encoding="utf-8")
    if not review.strip():
        return {"success": False, "message": "No review found. Run a review first."}

    prompts_dir = Path(__file__).parent.parent.parent / "skaro_core" / "prompts"
    prompt_path = prompts_dir / "architecture-apply.md"
    if prompt_path.exists():
        prompt = prompt_path.read_text(encoding="utf-8")
    else:
        prompt = (
            "Apply review recommendations to this architecture.\n\n"
            "## Current Architecture\n{architecture}\n\n"
            "## Review\n{review}\n\n"
            "Return the complete improved architecture document."
        )

    prompt = prompt.replace("{architecture}", architecture).replace("{review}", review)

    from skaro_core.phases.base import BasePhase

    class _ApplyReview(BasePhase):
        phase_name = "architecture"

        async def run(self, **kw: Any) -> None:
            pass

    phase = _ApplyReview(project_root=project_root)
    messages = phase._build_messages(prompt)

    async with llm_phase(ws, "architecture-apply", phase):
        response = await phase._stream_collect(messages)

    return {
        "success": True,
        "proposed_architecture": response.strip(),
    }


@router.post("/accept")
async def accept_architecture(
    request: Request,
    payload: ArchAcceptBody,
    am: ArtifactManager = Depends(get_am),
):
    proposed = payload.proposed_architecture

    # Extract ## Architectural Invariants section if present.
    invariants_text = _extract_invariants(proposed)
    if invariants_text:
        am.write_invariants(invariants_text)

    am.write_architecture(proposed)
    await broadcast(request, {"event": "artifact:updated", "artifact": "architecture"})
    return {"success": True, "invariants_extracted": bool(invariants_text)}


@router.post("/approve")
async def approve_architecture(
    request: Request,
    am: ArtifactManager = Depends(get_am),
):
    """Approve (lock) the current architecture and move forward."""
    if not am.has_architecture:
        return {"success": False, "message": "No architecture to approve."}
    am.mark_architecture_reviewed()
    await broadcast(request, {"event": "phase:completed", "phase": "architecture"})
    return {"success": True}


@router.put("")
async def save_architecture(
    request: Request,
    payload: ContentBody,
    am: ArtifactManager = Depends(get_am),
):
    am.write_architecture(payload.content)
    await broadcast(request, {"event": "artifact:updated", "artifact": "architecture"})
    return {"success": True}


# ── Invariants ──────────────────────────────────

@router.get("/invariants")
async def get_invariants(am: ArtifactManager = Depends(get_am)):
    return {"content": am.read_invariants()}


@router.put("/invariants")
async def update_invariants(
    request: Request,
    payload: ContentBody,
    am: ArtifactManager = Depends(get_am),
):
    path = am.write_invariants(payload.content)
    await broadcast(request, {"event": "artifact:updated", "artifact": "invariants"})
    return {"success": True, "path": str(path)}


# ── ADRs ────────────────────────────────────────

@router.get("/adrs")
async def get_adrs(am: ArtifactManager = Depends(get_am)):
    adrs = []
    for adr_path in am.list_adrs():
        content = adr_path.read_text(encoding="utf-8")
        meta = am.parse_adr_metadata(content, adr_path.name)
        adrs.append({
            "filename": adr_path.name,
            "content": content,
            "number": meta.get("number", 0),
            "title": meta.get("title", adr_path.stem),
            "status": meta.get("status", "proposed"),
            "date": meta.get("date", ""),
        })
    return {"adrs": adrs}


@router.post("/adrs")
async def create_adr(
    request: Request,
    payload: AdrCreateBody,
    am: ArtifactManager = Depends(get_am),
):
    existing = am.list_adrs()
    num = len(existing) + 1
    path = am.create_adr(num, payload.title)
    await broadcast(request, {"event": "artifact:created", "artifact": f"ADR-{num:03d}"})
    return {"success": True, "path": str(path), "number": num}


@router.patch("/adrs/{number}/status")
async def update_adr_status(
    number: int,
    request: Request,
    payload: AdrStatusBody,
    am: ArtifactManager = Depends(get_am),
):
    try:
        path = am.update_adr_status(number, payload.status)
    except ValueError as e:
        return {"success": False, "message": str(e)}
    if path is None:
        return {"success": False, "message": f"ADR-{number:03d} not found"}
    await broadcast(request, {"event": "artifact:updated", "artifact": f"ADR-{number:03d}"})
    return {"success": True, "path": str(path)}


@router.put("/adrs/{number}")
async def save_adr_content(
    number: int,
    request: Request,
    payload: ContentBody,
    am: ArtifactManager = Depends(get_am),
):
    path = am.write_adr_content(number, payload.content)
    if not path:
        return {"success": False, "message": f"ADR-{number:03d} not found"}
    await broadcast(request, {"event": "artifact:updated", "artifact": f"ADR-{number:03d}"})
    return {"success": True}


@router.post("/adrs/generate")
async def generate_adrs(
    request: Request,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Generate ADRs from architecture using LLM."""
    architecture = am.read_architecture()
    if not architecture.strip():
        return {"success": False, "message": "Architecture is empty."}

    review = ""
    review_path = am.skaro / "architecture" / "review.md"
    if review_path.exists():
        review = review_path.read_text(encoding="utf-8")

    adr_template = ""
    tpl_path = am.skaro / "templates" / "adr-template.md"
    if tpl_path.exists():
        adr_template = tpl_path.read_text(encoding="utf-8")

    prompts_dir = Path(__file__).parent.parent.parent / "skaro_core" / "prompts"
    prompt_path = prompts_dir / "adr-generate.md"
    if prompt_path.exists():
        prompt = prompt_path.read_text(encoding="utf-8")
    else:
        prompt = (
            "Generate ADRs for this architecture. Return JSON array with "
            "number, title, content fields.\n\nArchitecture:\n{architecture}"
        )

    today = _date.today().isoformat()
    review_section = f"Architecture review feedback:\n{review}" if review.strip() else ""
    prompt = (
        prompt
        .replace("{architecture}", architecture)
        .replace("{review_section}", review_section)
        .replace("{adr_template}", adr_template)
        .replace("{today}", today)
    )

    from skaro_core.phases.base import BasePhase

    class _AdrGen(BasePhase):
        phase_name = "architecture"

        async def run(self, **kw: Any) -> None:
            pass

    gen = _AdrGen(project_root=project_root)
    messages = gen._build_messages(prompt)

    async with llm_phase(ws, "adr-generate", gen):
        response = await gen._stream_collect(messages)

    json_match = _re.search(r"```json\s*\n([\s\S]*?)\n\s*```", response)
    if not json_match:
        return {"success": False, "message": "LLM did not return valid JSON.", "raw": response}

    try:
        adrs_data = json.loads(json_match.group(1))
    except json.JSONDecodeError as e:
        return {"success": False, "message": f"JSON parse error: {e}", "raw": response}

    existing = am.list_adrs()
    start_num = len(existing) + 1

    created = []
    for i, adr in enumerate(adrs_data):
        num = start_num + i
        title = adr.get("title", f"Decision {num}")
        content = adr.get("content", "")

        content = _re.sub(
            r"^(#\s+ADR-)\d+:",
            f"\\g<1>{num:03d}:",
            content,
            count=1,
            flags=_re.MULTILINE,
        )

        slug = title.lower().replace(" ", "-").replace("/", "-")[:50]
        filename = f"adr-{num:03d}-{slug}.md"
        path = am.skaro / "architecture" / filename
        path.write_text(content, encoding="utf-8")
        created.append({"number": num, "title": title, "filename": filename})

    await ws.broadcast({"event": "adrs:generated", "count": len(created)})
    return {"success": True, "created": created, "count": len(created)}
