"""Universal project chat endpoints.

Provides a single set of endpoints that adapt to different page contexts
(constitution, ADR, devplan, features, tasks).  Context type is passed
as a path parameter.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from skaro_core.phases.base import BasePhase
from skaro_web.api.deps import (
    broadcast,
    get_am,
    get_project_root,
    get_ws_manager,
    llm_phase,
    ConnectionManager,
)
from skaro_web.api.schemas import ProjectChatBody

router = APIRouter(prefix="/api/chat", tags=["chat"])

_VALID_CONTEXTS = {
    "constitution",
    "adr",
    "adr-detail",
    "devplan",
    "features",
    "tasks",
}


def _validate_context(context_type: str) -> str | None:
    """Return error message if context_type is invalid, else None."""
    if context_type not in _VALID_CONTEXTS:
        return f"Invalid context type: {context_type}. Valid: {', '.join(sorted(_VALID_CONTEXTS))}"
    return None


@router.post("/{context_type}")
async def chat_send(
    context_type: str,
    request: Request,
    payload: ProjectChatBody,
    project_root: Path = Depends(get_project_root),
    ws: ConnectionManager = Depends(get_ws_manager),
):
    """Send a message in the project chat for the given context."""
    err = _validate_context(context_type)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "message": err})

    from skaro_core.phases.project_chat import ProjectChatPhase
    from skaro_core.phases.base import CancelledByClientError

    phase = ProjectChatPhase(project_root=project_root)
    if payload.provider_override and payload.model_override:
        phase.set_model_override(payload.provider_override, payload.model_override)
    try:
        async with llm_phase(ws, f"chat-{context_type}", phase, request=request):
            result = await phase.chat(
                context_type=context_type,
                context_id=payload.context_id,
                message=payload.message,
                conversation=payload.conversation,
                scope_paths=payload.scope_paths,
            )
    except CancelledByClientError:
        return {
            "success": False,
            "message": "Cancelled by user",
            "files": {},
        }

    return {
        "success": result.success,
        "message": result.message,
        "files": result.data.get("files", {}),
        "task_proposals": result.data.get("task_proposals", []),
    }


@router.get("/{context_type}/conversation")
async def chat_load_conversation(
    context_type: str,
    context_id: str = "",
    project_root: Path = Depends(get_project_root),
):
    """Load persisted conversation for the given context."""
    err = _validate_context(context_type)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "message": err})

    from skaro_core.phases.project_chat import ProjectChatPhase

    phase = ProjectChatPhase(project_root=project_root)
    conversation = phase.load_conversation(context_type, context_id)

    # Enrich assistant messages with file diffs.
    conversation = phase.enrich_conversation(conversation)

    # Estimate context tokens.
    system_msg = phase._build_system_message()
    prompt_tpl = phase._load_prompt_template(f"chat-{context_type}")
    ctx_chars = len(system_msg) + len(prompt_tpl)
    conv_chars = sum(len(t.get("content", "")) for t in conversation)
    est_tokens = (ctx_chars + conv_chars) // 4

    return {
        "conversation": conversation,
        "context_tokens": est_tokens,
    }


@router.delete("/{context_type}/conversation")
async def chat_clear_conversation(
    context_type: str,
    context_id: str = "",
    project_root: Path = Depends(get_project_root),
):
    """Clear conversation for the given context."""
    err = _validate_context(context_type)
    if err:
        return JSONResponse(status_code=400, content={"success": False, "message": err})

    from skaro_core.phases.project_chat import ProjectChatPhase

    phase = ProjectChatPhase(project_root=project_root)
    phase.clear_conversation(context_type, context_id)
    return {"success": True}


@router.post("/{context_type}/apply")
async def chat_apply_file(
    context_type: str,
    request: Request,
    payload: dict,
    project_root: Path = Depends(get_project_root),
):
    """Apply a proposed file from chat to disk."""
    filepath = payload.get("filepath", "")
    content = payload.get("content", "")

    if not filepath or content is None:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "filepath and content are required"},
        )

    try:
        BasePhase._validate_project_path(project_root, filepath)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})

    from skaro_core.phases.project_chat import ProjectChatPhase

    phase = ProjectChatPhase(project_root=project_root)
    result = phase.apply_file(filepath, content)

    if result.success:
        await broadcast(request, {"event": "chat:file_applied", "file": filepath})

    return {"success": result.success, "message": result.message}
