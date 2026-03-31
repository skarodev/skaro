"""Model listing service.

Coordinates between provider API calls, file cache, and static
``providers.yaml`` baseline to return model lists for the UI.

Usage::

    from skaro_core.llm._model_listing import list_models_for_provider

    result = await list_models_for_provider("openai", project_root, api_key="sk-...")
    # result.source  → "api" | "cache" | "static"
    # result.models  → [ModelInfo(...), ...]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skaro_core.llm._model_cache import (
    get_cached_models,
    put_cached_models,
)
from skaro_core.providers import ModelInfo, get_provider

logger = logging.getLogger("skaro.model_listing")

# Providers that have no public model-listing API.
# For these, we always return the static providers.yaml baseline.
_NO_LISTING_PROVIDERS: frozenset[str] = frozenset({"anthropic"})


@dataclass
class ModelListResult:
    """Result of a model listing request."""

    provider: str
    source: str  # "api" | "cache" | "static"
    models: list[ModelInfo] = field(default_factory=list)
    cached_at: str | None = None
    error: str | None = None


def _model_dicts_to_infos(models: list[dict[str, Any]]) -> list[ModelInfo]:
    """Convert raw dicts to ModelInfo objects."""
    return [
        ModelInfo(
            id=m["id"],
            name=m.get("name", m["id"]),
            context_window=m.get("context_window", 128_000),
            max_output=m.get("max_output", 32_768),
        )
        for m in models
    ]


def _infos_to_dicts(models: list[ModelInfo]) -> list[dict[str, Any]]:
    """Convert ModelInfo objects to dicts for caching."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "context_window": m.context_window,
            "max_output": m.max_output,
        }
        for m in models
    ]


def _static_models(provider_key: str) -> list[ModelInfo]:
    """Return models from providers.yaml (static baseline)."""
    p = get_provider(provider_key)
    if not p:
        return []
    return list(p.models)


async def _fetch_from_api(
    provider_key: str,
    api_key: str | None,
    base_url: str | None,
) -> list[ModelInfo] | None:
    """Call the provider API to list available models.

    Returns ``None`` if the request fails (missing key, network error, etc.).
    Raises ``NotImplementedError`` if the provider doesn't support listing.
    """
    import httpx

    try:
        if provider_key == "ollama":
            return await _fetch_ollama(base_url)
        if provider_key in _NO_LISTING_PROVIDERS:
            raise NotImplementedError(f"{provider_key} does not support model listing")

        # All other providers use OpenAI-compatible /v1/models
        endpoint_map: dict[str, str] = {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "deepseek": "https://api.deepseek.com",
            "qwen": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            "zai": "https://api.z.ai/api/paas/v4",
            "google": "https://generativelanguage.googleapis.com/v1beta/openai",
        }

        api_base = base_url or endpoint_map.get(provider_key)
        if not api_base:
            logger.debug("No API base for %s, skipping fetch", provider_key)
            return None

        if not api_key:
            logger.debug("No API key for %s, skipping fetch", provider_key)
            return None

        api_base = api_base.rstrip("/")
        url = f"{api_base}/models"

        headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
        if provider_key == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/skaro-dev/skaro"
            headers["X-Title"] = "Skaro"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        raw_models = data.get("data", [])
        models: list[ModelInfo] = []
        for m in raw_models:
            model_id = m.get("id", "")
            if not model_id:
                continue
            models.append(ModelInfo(
                id=model_id,
                name=m.get("name") or model_id,
                context_window=m.get("context_length") or m.get("context_window") or 128_000,
                max_output=m.get("max_output") or m.get("top_provider", {}).get("max_completion_tokens") or 32_768,
            ))

        logger.info("Fetched %d models from %s API", len(models), provider_key)
        return models

    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP %d fetching models from %s: %s", exc.response.status_code, provider_key, exc)
        return None
    except Exception as exc:
        logger.warning("Failed to fetch models from %s: %s", provider_key, exc)
        return None


async def _fetch_ollama(base_url: str | None) -> list[ModelInfo] | None:
    """Fetch locally installed models from Ollama."""
    import httpx

    url = (base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Failed to fetch Ollama models: %s", exc)
        return None

    models: list[ModelInfo] = []
    for m in data.get("models", []):
        name = m.get("name", "")
        if not name:
            continue
        # Ollama details may include parameter_size, context_length, etc.
        details = m.get("details", {})
        context = details.get("context_length") or 131_072
        models.append(ModelInfo(
            id=name,
            name=name,
            context_window=context,
            max_output=min(context, 65_536),
        ))

    logger.info("Fetched %d models from Ollama", len(models))
    return models


async def _try_fetch(
    provider_key: str,
    api_key: str | None,
    base_url: str | None,
) -> list[ModelInfo] | None:
    """Wrapper around _fetch_from_api that swallows NotImplementedError."""
    try:
        return await _fetch_from_api(provider_key, api_key, base_url)
    except NotImplementedError:
        return None


async def list_models_for_provider(
    provider_key: str,
    project_root: Path,
    api_key: str | None = None,
    base_url: str | None = None,
    force_refresh: bool = False,
) -> ModelListResult:
    """Return models for a provider with cache/API/static fallback.

    Priority:
    0. If provider doesn't support listing → return static immediately.
    1. If ``force_refresh`` → fetch from API, update cache.
    2. If cache is fresh → return cached.
    3. Fetch from API → update cache on success.
    4. Fallback to static ``providers.yaml``.
    """
    static = _static_models(provider_key)
    static_ids = {m.id for m in static}

    # 0. Provider without model listing API → static only
    if provider_key in _NO_LISTING_PROVIDERS:
        return ModelListResult(
            provider=provider_key,
            source="static",
            models=static,
        )

    # 1. Force refresh
    if force_refresh:
        api_models = await _try_fetch(provider_key, api_key, base_url)
        if api_models is not None:
            put_cached_models(project_root, provider_key, _infos_to_dicts(api_models))
            merged = _merge_models(static, api_models, static_ids)
            return ModelListResult(
                provider=provider_key,
                source="api",
                models=merged,
            )
        # API failed even on force → return static with error
        return ModelListResult(
            provider=provider_key,
            source="static",
            models=static,
            error="Failed to fetch models from API",
        )

    # 2. Check cache
    cached = get_cached_models(project_root, provider_key)
    if cached is not None:
        cached_models = _model_dicts_to_infos(cached)
        merged = _merge_models(static, cached_models, static_ids)
        return ModelListResult(
            provider=provider_key,
            source="cache",
            models=merged,
        )

    # 3. Try API (non-forced)
    api_models = await _try_fetch(provider_key, api_key, base_url)
    if api_models is not None:
        put_cached_models(project_root, provider_key, _infos_to_dicts(api_models))
        merged = _merge_models(static, api_models, static_ids)
        return ModelListResult(
            provider=provider_key,
            source="api",
            models=merged,
        )

    # 4. Fallback to static
    return ModelListResult(
        provider=provider_key,
        source="static",
        models=static,
    )


def _merge_models(
    static: list[ModelInfo],
    fetched: list[ModelInfo],
    static_ids: set[str],
) -> list[ModelInfo]:
    """Merge static (curated) and fetched models.

    Static models come first (curated order), then remaining
    fetched models sorted alphabetically.  Deduplicates by ID —
    for IDs present in both, the static entry wins (better metadata).
    """
    seen: set[str] = set()
    result: list[ModelInfo] = []

    # Static first (curated order preserved)
    for m in static:
        if m.id not in seen:
            seen.add(m.id)
            result.append(m)

    # Fetched models that aren't already in static, sorted
    extra = [m for m in fetched if m.id not in seen]
    extra.sort(key=lambda m: m.id)
    for m in extra:
        seen.add(m.id)
        result.append(m)

    return result
