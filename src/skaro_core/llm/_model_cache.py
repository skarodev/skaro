"""File-based model cache with per-provider TTL.

Stores fetched model lists in ``.skaro/models_cache/{provider}.json``
so they survive restarts.  Each file contains::

    {
        "cached_at": "2026-03-31T12:00:00Z",
        "models": [{"id": "...", "name": "...", "context_window": ..., "max_output": ...}, ...]
    }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("skaro.model_cache")

DEFAULT_TTL_SECONDS = 86_400  # 24 hours

_CACHE_DIR_NAME = "models_cache"


def _cache_dir(project_root: Path) -> Path:
    return project_root / ".skaro" / _CACHE_DIR_NAME


def _cache_file(project_root: Path, provider: str) -> Path:
    # Sanitise provider key for filesystem safety
    safe = provider.replace("/", "_").replace("\\", "_")
    return _cache_dir(project_root) / f"{safe}.json"


def get_cached_models(
    project_root: Path,
    provider: str,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> list[dict[str, Any]] | None:
    """Return cached models if fresh, else ``None``."""
    path = _cache_file(project_root, provider)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age > ttl:
            logger.debug("Cache expired for %s (age=%.0fs, ttl=%d)", provider, age, ttl)
            return None
        return data["models"]
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Corrupt cache for %s, ignoring: %s", provider, exc)
        return None


def put_cached_models(
    project_root: Path,
    provider: str,
    models: list[dict[str, Any]],
) -> None:
    """Write models to cache file."""
    cache_dir = _cache_dir(project_root)
    cache_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "models": models,
    }
    path = _cache_file(project_root, provider)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("Cached %d models for %s", len(models), provider)


def invalidate_cache(project_root: Path, provider: str) -> None:
    """Remove cache file for a provider."""
    path = _cache_file(project_root, provider)
    if path.exists():
        path.unlink()
        logger.debug("Invalidated cache for %s", provider)


def get_cache_age(project_root: Path, provider: str) -> float | None:
    """Return cache age in seconds, or ``None`` if no cache."""
    path = _cache_file(project_root, provider)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
        return (datetime.now(timezone.utc) - cached_at).total_seconds()
    except (json.JSONDecodeError, KeyError, ValueError):
        return None
