"""Constitution endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from skaro_core.artifacts import ArtifactManager, TEMPLATES_PKG_DIR
from skaro_core.config import load_config, save_config
from skaro_web.api.deps import broadcast, get_am, get_project_root
from skaro_web.api.schemas import ContentBody, ConstitutionSaveBody

router = APIRouter(prefix="/api/constitution", tags=["constitution"])

# ── Presets directory (ships with the package) ─────
_PRESETS_DIR = TEMPLATES_PKG_DIR / "constitution-presets" if TEMPLATES_PKG_DIR else None

# Registry: id → (label, category, filename)
_PRESET_REGISTRY: list[dict[str, str]] = [
    {"id": "react",        "name": "React",        "category": "frontend", "file": "react.md"},
    {"id": "vue",          "name": "Vue.js",       "category": "frontend", "file": "vue.md"},
    {"id": "sveltekit",    "name": "SvelteKit",    "category": "frontend", "file": "sveltekit.md"},
    {"id": "nextjs",       "name": "Next.js",      "category": "frontend", "file": "nextjs.md"},
    {"id": "angular",      "name": "Angular",      "category": "frontend", "file": "angular.md"},
    {"id": "fastapi",      "name": "FastAPI",       "category": "backend",  "file": "fastapi.md"},
    {"id": "django",       "name": "Django",        "category": "backend",  "file": "django.md"},
    {"id": "express",      "name": "Express.js",    "category": "backend",  "file": "express.md"},
    {"id": "nestjs",       "name": "NestJS",        "category": "backend",  "file": "nestjs.md"},
    {"id": "react-native", "name": "React Native",  "category": "mobile",   "file": "react-native.md"},
    {"id": "flutter",      "name": "Flutter",       "category": "mobile",   "file": "flutter.md"},
    {"id": "kotlin-mp",    "name": "Kotlin MP",     "category": "mobile",   "file": "kotlin-mp.md"},
]


@router.get("")
async def get_constitution(am: ArtifactManager = Depends(get_am)):
    return {
        "content": am.read_constitution(),
        "has_constitution": am.has_constitution,
        "validation": am.validate_constitution(),
    }


@router.post("/validate")
async def validate_constitution(am: ArtifactManager = Depends(get_am)):
    result = am.validate_constitution()
    is_valid = all(result.values()) if result else False
    if is_valid:
        am.mark_constitution_validated()
    return {"success": True, "valid": is_valid, "checks": result}


@router.post("/approve")
async def approve_constitution(
    request: Request,
    am: ArtifactManager = Depends(get_am),
):
    """Mark the constitution as approved without structural validation."""
    if not am.has_constitution:
        return {"success": False, "message": "No constitution to approve."}
    am.mark_constitution_validated()
    await broadcast(request, {"event": "artifact:updated", "artifact": "constitution"})
    return {"success": True}


@router.put("")
async def save_constitution(
    request: Request,
    payload: ConstitutionSaveBody,
    am: ArtifactManager = Depends(get_am),
    project_root: Path = Depends(get_project_root),
):
    am.write_constitution(payload.content)
    am.generate_project_gitignore(payload.content)

    # Link skills preset when a preset_id is provided
    if payload.preset_id is not None:
        config = load_config(project_root)
        config.skills.preset = payload.preset_id
        # Reset disabled list when switching presets
        config.skills.disabled = []
        save_config(config, project_root)

    await broadcast(request, {"event": "artifact:updated", "artifact": "constitution"})
    return {"success": True}


@router.get("/presets")
async def list_presets():
    """Return list of available constitution presets (metadata only)."""
    return {"presets": _PRESET_REGISTRY}


@router.get("/presets/{preset_id}")
async def get_preset(preset_id: str):
    """Return the full markdown content for a specific preset."""
    entry = next((p for p in _PRESET_REGISTRY if p["id"] == preset_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    if _PRESETS_DIR is None:
        raise HTTPException(status_code=500, detail="Templates directory not found")
    path = _PRESETS_DIR / entry["file"]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Preset file missing: {entry['file']}")
    return {"id": preset_id, "content": path.read_text(encoding="utf-8")}
