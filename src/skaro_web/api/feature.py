"""Feature planning endpoints: CRUD, chat, confirmation."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.deps import (
    broadcast,
    get_am,
    get_project_root,
    get_ws_manager,
    llm_phase,
    ConnectionManager,
)
from skaro_web.api.schemas import (
    ContentBody,
    FeatureChatBody,
    FeatureConfirmBody,
    FeatureUpdateBody,
)

router = APIRouter(prefix="/api/features", tags=["features"])


# ── List / Create ───────────────────────────────

@router.get("")
async def list_features(am: ArtifactManager = Depends(get_am)):
    features = am.list_features()
    # Refresh auto-statuses for active features
    for f in features:
        if f.get("status") in ("planned", "in-progress"):
            am.refresh_feature_status(f["slug"])
    # Re-read after refresh
    features = am.list_features()
    return {"features": features}


@router.post("")
async def create_feature(
    request: Request,
    am: ArtifactManager = Depends(get_am),
):
    slug = am.create_feature()
    await broadcast(request, {"event": "feature:created", "slug": slug})
    return {"success": True, "slug": slug}


# ── Detail ──────────────────────────────────────

@router.get("/{slug}")
async def get_feature(slug: str, am: ArtifactManager = Depends(get_am)):
    meta = am.read_feature_meta(slug)
    if not meta:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Feature '{slug}' not found."},
        )
    # Refresh status
    am.refresh_feature_status(slug)
    meta = am.read_feature_meta(slug)

    plan = am.read_feature_plan(slug)

    # Resolve linked task details
    task_details = []
    for task_slug in meta.get("tasks", []):
        resolved = am.resolve_task_safe(task_slug)
        if resolved:
            ts = am.get_task_state(*resolved)
            task_details.append({
                "name": ts.name,
                "milestone": ts.milestone,
                "current_phase": ts.current_phase.value,
                "progress_percent": ts.progress_percent,
            })

    # Resolve linked ADR details
    adr_details = []
    for adr_num in meta.get("adrs", []):
        for adr_path in am.list_adrs():
            adr_meta = am.parse_adr_metadata(
                adr_path.read_text(encoding="utf-8"), adr_path.name
            )
            if adr_meta.get("number") == adr_num:
                adr_details.append({
                    "number": adr_num,
                    "title": adr_meta.get("title", ""),
                    "status": adr_meta.get("status", "proposed"),
                })

    return {
        **meta,
        "plan": plan,
        "task_details": task_details,
        "adr_details": adr_details,
    }


@router.patch("/{slug}")
async def update_feature(
    slug: str,
    request: Request,
    payload: FeatureUpdateBody,
    am: ArtifactManager = Depends(get_am),
):
    updates = payload.model_dump(exclude_none=True)
    meta = am.update_feature_meta(slug, **updates)
    if meta is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Feature '{slug}' not found."},
        )
    await broadcast(request, {"event": "feature:updated", "slug": slug})
    return {"success": True, "meta": meta}


@router.delete("/{slug}")
async def delete_feature(
    slug: str,
    request: Request,
    am: ArtifactManager = Depends(get_am),
):
    meta = am.read_feature_meta(slug)
    if not meta:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Feature '{slug}' not found."},
        )

    if meta.get("status") == "draft":
        am.delete_feature(slug)
        await broadcast(request, {"event": "feature:deleted", "slug": slug})
        return {"success": True, "action": "deleted"}
    else:
        am.cancel_feature(slug)
        await broadcast(request, {"event": "feature:cancelled", "slug": slug})
        return {"success": True, "action": "cancelled"}


# ── Chat ────────────────────────────────────────

@router.post("/{slug}/chat")
async def send_feature_chat(
    slug: str,
    request: Request,
    payload: FeatureChatBody,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    if not am.feature_exists(slug):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Feature '{slug}' not found."},
        )

    from skaro_core.phases.feature import FeaturePhase
    from skaro_core.phases.base import CancelledByClientError

    phase = FeaturePhase(project_root=project_root)
    if payload.provider_override and payload.model_override:
        phase.set_model_override(payload.provider_override, payload.model_override)
    try:
        async with llm_phase(ws, "feature", phase, request=request):
            result = await phase.run(
                feature_slug=slug,
                message=payload.message,
                conversation=payload.conversation,
                scope_paths=payload.scope_paths,
            )
    except CancelledByClientError:
        return {
            "success": False,
            "message": "Cancelled by user",
            "conversation": [],
        }

    if result.success:
        await ws.broadcast({"event": "feature:chat_response", "slug": slug})

    return {
        "success": result.success,
        "message": result.message,
        "conversation": result.data.get("conversation", []),
    }


@router.get("/{slug}/conversation")
async def get_feature_conversation(
    slug: str,
    project_root: Path = Depends(get_project_root),
    am: ArtifactManager = Depends(get_am),
):
    if not am.feature_exists(slug):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Feature '{slug}' not found."},
        )

    from skaro_core.phases.feature import FeaturePhase

    phase = FeaturePhase(project_root=project_root)
    conversation = phase.load_conversation(slug)

    arch = am.read_architecture()
    devplan = am.read_devplan()
    ctx_chars = len(arch) + len(devplan)
    conv_chars = sum(len(t.get("content", "")) for t in conversation)
    est_tokens = (ctx_chars + conv_chars) // 4

    return {"conversation": conversation, "context_tokens": est_tokens}


@router.delete("/{slug}/conversation")
async def clear_feature_conversation(
    slug: str,
    project_root: Path = Depends(get_project_root),
):
    from skaro_core.phases.feature import FeaturePhase

    phase = FeaturePhase(project_root=project_root)
    phase.clear_conversation(slug)
    return {"success": True}


# ── Confirm proposal ────────────────────────────

@router.post("/{slug}/confirm")
async def confirm_feature(
    slug: str,
    request: Request,
    payload: FeatureConfirmBody,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    meta = am.read_feature_meta(slug)
    if not meta:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Feature '{slug}' not found."},
        )
    if meta.get("status") != "draft":
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Feature is not in draft status."},
        )

    from skaro_core.phases.feature import FeaturePhase

    phase = FeaturePhase(project_root=project_root)
    result = phase.confirm_proposal(
        slug,
        title=payload.title,
        description=payload.description,
        plan=payload.plan,
        tasks=[t.model_dump() for t in payload.tasks],
        adr=payload.adr.model_dump() if payload.adr else None,
    )

    if result.success:
        await broadcast(request, {"event": "feature:confirmed", "slug": slug})

    return {
        "success": result.success,
        "message": result.message,
        "tasks_created": result.data.get("tasks_created", []),
        "adr_number": result.data.get("adr_number"),
    }


# ── Plan ────────────────────────────────────────

@router.put("/{slug}/plan")
async def save_feature_plan(
    slug: str,
    request: Request,
    payload: ContentBody,
    am: ArtifactManager = Depends(get_am),
):
    if not am.feature_exists(slug):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f"Feature '{slug}' not found."},
        )
    am.write_feature_plan(slug, payload.content)
    await broadcast(request, {"event": "feature:plan_saved", "slug": slug})
    return {"success": True}
