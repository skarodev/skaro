"""Architecture endpoints (review, ADRs)."""

from __future__ import annotations

import json
import re as _re
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.deps import broadcast, get_am, get_project_root, get_ws_manager, llm_phase, ConnectionManager
from skaro_web.api.schemas import (
    ArchAcceptBody,
    ArchChatBody,
    ArchReviewBody,
    AdrCreateBody,
    AdrStatusBody,
    ContentBody,
)

router = APIRouter(prefix="/api/architecture", tags=["architecture"])


@router.get("")
async def get_architecture(am: ArtifactManager = Depends(get_am)):
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
        "adrs": adrs,
        "adr_count": len(adrs),
    }


# ── Chat-based architecture generation ────────────


@router.post("/chat")
async def arch_chat(
    request: Request,
    payload: ArchChatBody,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Send a message in the architecture generation chat."""
    from skaro_core.phases.architecture import ArchitecturePhase
    from skaro_core.phases.base import CancelledByClientError

    phase = ArchitecturePhase(project_root=project_root)
    if payload.provider_override and payload.model_override:
        phase.set_model_override(payload.provider_override, payload.model_override)
    try:
        async with llm_phase(ws, "architecture-chat", phase, request=request):
            result = await phase.chat(
                message=payload.message,
                conversation=payload.conversation,
            )
    except CancelledByClientError:
        return {
            "success": False,
            "message": "Cancelled by user",
            "files": {},
            "has_architecture": False,
        }
    return {
        "success": result.success,
        "message": result.message,
        "files": result.data.get("files", {}),
        "has_architecture": result.data.get("has_architecture", False),
    }


@router.get("/chat/conversation")
async def get_arch_chat_conversation(
    project_root: Path = Depends(get_project_root),
):
    """Load persisted architecture chat conversation."""
    from skaro_core.phases.architecture import ArchitecturePhase

    phase = ArchitecturePhase(project_root=project_root)
    conversation = phase.load_chat_conversation()

    # Estimate context: system message (constitution, ADR index) + prompt template
    system_msg = phase._build_system_message()
    prompt_tpl = phase._load_prompt_template("architecture-chat")
    ctx_chars = len(system_msg) + len(prompt_tpl)

    conv_chars = sum(len(t.get("content", "")) for t in conversation)
    est_tokens = (ctx_chars + conv_chars) // 4
    return {
        "conversation": conversation,
        "context_tokens": est_tokens,
    }


@router.delete("/chat/conversation")
async def clear_arch_chat_conversation(
    project_root: Path = Depends(get_project_root),
):
    """Clear architecture chat conversation."""
    from skaro_core.phases.architecture import ArchitecturePhase

    phase = ArchitecturePhase(project_root=project_root)
    phase.clear_chat_conversation()
    return {"success": True}


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

    from skaro_core.phases.architecture import ArchitecturePhase

    phase = ArchitecturePhase(project_root=project_root)

    async with llm_phase(ws, "architecture-apply", phase):
        response = await phase.apply_review(architecture, review)

    return {
        "success": True,
        "proposed_architecture": response,
    }


@router.post("/accept")
async def accept_architecture(
    request: Request,
    payload: ArchAcceptBody,
    am: ArtifactManager = Depends(get_am),
):
    am.write_architecture(payload.proposed_architecture)
    await broadcast(request, {"event": "artifact:updated", "artifact": "architecture"})
    return {"success": True}


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

    from skaro_core.phases.architecture import ArchitecturePhase

    phase = ArchitecturePhase(project_root=project_root)

    async with llm_phase(ws, "adr-generate", phase):
        try:
            adrs_data = await phase.generate_adrs(architecture, review, adr_template)
        except (ValueError, json.JSONDecodeError) as e:
            return {"success": False, "message": str(e)}

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
