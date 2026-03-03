"""Import project API endpoints.

Provides:
  GET  /api/import/scan   — dry-run scan: file counts and token estimate
  POST /api/import/run    — start full LLM analysis (streams via WebSocket)
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from skaro_core.artifacts import ArtifactManager
from skaro_core.config import load_config
from skaro_core.phases.import_analyze import ImportAnalyzePhase
from skaro_core.phases.repo_scan import RepoScanner
from skaro_web.api.deps import broadcast, get_am, get_project_root, get_ws_manager, llm_phase

router = APIRouter(prefix="/api/import", tags=["import"])


class ImportRunBody(BaseModel):
    project_name: str = ""


# ── GET /api/import/scan ─────────────────────────────────────────────────────


@router.get("/scan")
async def get_scan_info(
    request: Request,
    am: ArtifactManager = Depends(get_am),
):
    """Return a dry-run scan summary (no LLM call)."""
    cfg = load_config(am.root)
    scanner = RepoScanner(
        am.root,
        token_limit=cfg.import_config.token_limit,
        max_file_size=cfg.import_config.max_file_size,
    )

    scan = await asyncio.to_thread(scanner.scan)
    skaroignored = await asyncio.to_thread(scanner.skaroignored_files)

    return {
        "files_included": len(scan.files),
        "files_skipped": len(scan.skipped_paths),
        "files_skaroignored": skaroignored,
        "estimated_tokens": scan.estimated_tokens,
        "token_limit": cfg.import_config.token_limit,
        "sampled": scan.sampled,
        "tree": scan.format_tree(),
    }


# ── POST /api/import/run ─────────────────────────────────────────────────────


@router.post("/run")
async def run_import(
    request: Request,
    payload: ImportRunBody,
    am: ArtifactManager = Depends(get_am),
):
    """Start the full LLM import analysis. Progress is streamed via WebSocket."""
    cfg = load_config(am.root)

    # Ensure project is initialized (CLI does this before calling import,
    # but direct API usage may skip it).
    if not am.is_initialized:
        am.init_project()

    project_name = payload.project_name.strip() or cfg.project_name or am.root.name

    phase = ImportAnalyzePhase(project_root=am.root, config=cfg)
    ws_manager = get_ws_manager(request)

    async with llm_phase(ws_manager, "import_analyze", phase_obj=phase):
        result = await phase.run(project_name=project_name)

    if result.success:
        await broadcast(request, {
            "event": "import:complete",
            "artifacts_created": result.artifacts_created,
            "scan": result.data.get("scan", {}),
        })

    return {
        "success": result.success,
        "message": result.message[:500] if not result.success else "Import complete.",
        "artifacts_created": result.artifacts_created,
        "scan": result.data.get("scan", {}),
    }
