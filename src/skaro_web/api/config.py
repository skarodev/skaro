"""Configuration endpoints.

Secrets handling is transparent to the frontend:
- GET returns the resolved ``api_key`` so the eye-toggle in UI works.
- PUT accepts a plaintext ``api_key``; the backend saves it to
  ``.skaro/secrets.yaml`` and stores only the env-var name in ``config.yaml``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request

from skaro_core.config import (
    ROLE_PHASES,
    SkaroConfig,
    load_config,
    save_config,
    save_secret,
)
from skaro_core.llm.base import PROVIDER_PRESETS
from skaro_core.providers import get_model_ids, get_provider_keys, get_providers
from skaro_web.api.deps import broadcast, get_project_root
from skaro_web.api.schemas import ConfigUpdateBody

router = APIRouter(prefix="/api/config", tags=["config"])


# ── Helpers ──────────────────────────────────────────────

def _env_name_for_provider(provider: str) -> str:
    """Determine the canonical env-var name for a provider."""
    preset = PROVIDER_PRESETS.get(provider)
    if preset and preset[1]:
        return preset[1]
    return f"{provider.upper()}_API_KEY"


def _config_to_frontend(config: SkaroConfig) -> dict:
    """Serialize config for frontend with resolved API keys."""
    data = config.to_dict()

    # Replace internal api_key_env with resolved api_key for frontend
    llm = data.get("llm", {})
    llm.pop("api_key_env", None)
    llm["api_key"] = config.llm.api_key or ""

    for rname, rd in data.get("roles", {}).items():
        if rd and isinstance(rd, dict):
            rd.pop("api_key_env", None)
            rc = config.roles.get(rname)
            if rc and rc.is_active:
                role_llm = config.llm_for_role(rname)
                rd["api_key"] = role_llm.api_key or ""
            else:
                rd["api_key"] = ""

    # Always include execution_env for frontend
    if "execution_env" not in data:
        data["execution_env"] = config.execution_env.to_dict()

    # Always include git config for frontend
    if "git" not in data:
        data["git"] = config.git.to_dict()

    # Always include context config for frontend
    data["context"] = {
        "always_include": config.context_always_include,
        "preflight": config.context_preflight,
    }

    return data


# ── Endpoints ────────────────────────────────────────────

@router.get("")
async def get_config(project_root: Path = Depends(get_project_root)):
    config = load_config(project_root)
    data = _config_to_frontend(config)
    all_providers = get_providers()
    data["_provider_presets"] = {
        k: {
            "name": all_providers[k].name if k in all_providers else k,
            "model": v[0],
            "api_key_env": v[1],
            "needs_key": v[2],
            "models": get_model_ids(k),
        }
        for k, v in PROVIDER_PRESETS.items()
    }
    data["_provider_keys"] = get_provider_keys()
    data["_role_phases"] = ROLE_PHASES
    return data


@router.get("/models/{provider}")
async def get_models(
    provider: str,
    refresh: bool = Query(False, description="Force refresh from API"),
    project_root: Path = Depends(get_project_root),
):
    """Fetch available models for a provider.

    Returns a merged list: curated models from ``providers.yaml`` first,
    then additional models from the provider API (cached with 24h TTL).

    Query params:
        ``refresh=true`` — force re-fetch from provider API.
    """
    from skaro_core.llm._model_listing import list_models_for_provider

    # Resolve API key from config/secrets for this provider
    config = load_config(project_root)
    api_key: str | None = None
    base_url: str | None = None

    if config.llm.provider == provider:
        api_key = config.llm.api_key
        base_url = config.llm.base_url
    else:
        # Check role overrides for this provider
        for rc in config.roles.values():
            if rc.is_active and rc.provider == provider:
                role_llm = config.llm_for_role(
                    next(
                        (r for r, c in config.roles.items() if c is rc),
                        None,
                    )
                )
                api_key = role_llm.api_key
                base_url = role_llm.base_url
                break

    # If still no key, try env-var fallback from provider preset
    if not api_key:
        import os

        from skaro_core.config._secrets import load_secrets

        preset = PROVIDER_PRESETS.get(provider)
        if preset and preset[1]:
            api_key = os.environ.get(preset[1]) or load_secrets().get(preset[1])

    result = await list_models_for_provider(
        provider_key=provider,
        project_root=project_root,
        api_key=api_key,
        base_url=base_url,
        force_refresh=refresh,
    )

    # Separate curated (from providers.yaml) and extra (from API only)
    from skaro_core.providers import get_provider as get_prov

    prov_info = get_prov(provider)
    curated_ids = {m.id for m in prov_info.models} if prov_info else set()

    curated = []
    extra = []
    for m in result.models:
        entry = {
            "id": m.id,
            "name": m.name,
            "context_window": m.context_window,
            "max_output": m.max_output,
        }
        if m.id in curated_ids:
            curated.append(entry)
        else:
            extra.append(entry)

    return {
        "provider": result.provider,
        "source": result.source,
        "curated": curated,
        "extra": extra,
        "error": result.error,
    }


@router.put("")
async def update_config(
    request: Request,
    payload: ConfigUpdateBody,
    project_root: Path = Depends(get_project_root),
):
    raw = payload.to_dict()
    existing = load_config(project_root)

    # ── Extract and save API keys to secrets.yaml ──
    llm_raw = raw.get("llm", {})
    api_key = llm_raw.pop("api_key", None)
    provider = llm_raw.get("provider", "anthropic")

    if api_key:
        env_name = _env_name_for_provider(provider)
        save_secret(env_name, api_key, project_root)
        llm_raw["api_key_env"] = env_name
    else:
        llm_raw["api_key_env"] = existing.llm.api_key_env

    for rname, rd in raw.get("roles", {}).items():
        if rd and isinstance(rd, dict):
            role_key = rd.pop("api_key", None)
            if role_key:
                role_provider = rd.get("provider", provider)
                role_env = _env_name_for_provider(role_provider)
                save_secret(role_env, role_key, project_root)
                rd["api_key_env"] = role_env
            else:
                existing_role = existing.roles.get(rname)
                rd["api_key_env"] = existing_role.api_key_env if existing_role else None

    # Preserve context.always_include from existing config (not editable in UI)
    # and merge with context_preflight from payload
    raw["context"] = {
        "always_include": existing.context_always_include,
        "preflight": raw.pop("context_preflight", True),
    }

    config = SkaroConfig.from_dict(raw)
    save_config(config, project_root)
    await broadcast(request, {"event": "config:updated"})
    return {"success": True}


@router.get("/detect-env")
async def detect_env(project_root: Path = Depends(get_project_root)):
    """Auto-detect execution environment from project files.

    Scans for Dockerfile, docker-compose.yml, .env, venv, etc.
    Returns hints for the frontend to pre-fill environment settings.
    """
    hints: dict = {"docker": False, "services": [], "has_dotenv": False, "has_venv": False}

    # Docker Compose
    compose_names = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
    compose_file = ""
    for name in compose_names:
        if (project_root / name).exists():
            compose_file = name
            break

    if compose_file:
        hints["docker"] = True
        hints["compose_file"] = compose_file
        # Parse services from compose file
        try:
            import yaml

            compose_data = yaml.safe_load((project_root / compose_file).read_text(encoding="utf-8"))
            if isinstance(compose_data, dict) and "services" in compose_data:
                hints["services"] = list(compose_data["services"].keys())
        except Exception:
            pass

    # Dockerfile without compose
    if not compose_file and (project_root / "Dockerfile").exists():
        hints["docker"] = True

    # .env file
    hints["has_dotenv"] = (project_root / ".env").exists()

    # Virtual environment
    for venv_dir in ("venv", ".venv", "env"):
        if (project_root / venv_dir).is_dir():
            hints["has_venv"] = True
            hints["venv_dir"] = venv_dir
            break

    return hints
