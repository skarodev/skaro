"""LLM Providers registry — loads providers.yaml at import time.

Single source of truth for supported providers, models, console URLs,
and environment variable names. Edit ``providers.yaml`` to add/update
providers without touching code.

Usage::

    from skaro_core.providers import get_provider, get_providers, get_model_ids

    provider = get_provider("anthropic")
    all_providers = get_providers()
    model_ids = get_model_ids("groq")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PROVIDERS_FILE = Path(__file__).parent / "providers.yaml"


@dataclass(frozen=True)
class ModelInfo:
    """Single model entry."""

    id: str
    name: str
    context_window: int = 128_000
    max_output: int = 32_768


@dataclass(frozen=True)
class ProviderInfo:
    """Single provider entry."""

    key: str
    name: str
    console_url: str
    api_key_env: str
    needs_key: bool
    default_model: str
    models: tuple[ModelInfo, ...] = field(default_factory=tuple)


# ── Internal cache ───────────────────────────────

_cache: dict[str, ProviderInfo] | None = None


def _load() -> dict[str, ProviderInfo]:
    global _cache
    if _cache is not None:
        return _cache

    with open(_PROVIDERS_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    providers: dict[str, ProviderInfo] = {}
    for key, data in (raw.get("providers") or {}).items():
        models_raw: list[dict[str, Any]] = data.get("models") or []
        models = tuple(
            ModelInfo(
                id=m["id"],
                name=m.get("name", m["id"]),
                context_window=m.get("context_window", 128_000),
                max_output=m.get("max_output", 32_768),
            )
            for m in models_raw
        )
        providers[key] = ProviderInfo(
            key=key,
            name=data.get("name", key),
            console_url=data.get("console_url", ""),
            api_key_env=data.get("api_key_env", ""),
            needs_key=data.get("needs_key", True),
            default_model=data.get("default_model", models[0].id if models else ""),
            models=models,
        )

    _cache = providers
    return _cache


# ── Public API ───────────────────────────────────


def get_providers() -> dict[str, ProviderInfo]:
    """Return all registered providers ``{key: ProviderInfo}``."""
    return _load()


def get_provider(key: str) -> ProviderInfo | None:
    """Lookup a single provider by key (e.g. ``"groq"``)."""
    return _load().get(key)


def get_provider_keys() -> list[str]:
    """Return ordered list of provider keys."""
    return list(_load().keys())


def get_model_ids(provider_key: str) -> list[str]:
    """Return list of model IDs for a provider."""
    p = get_provider(provider_key)
    if not p:
        return []
    return [m.id for m in p.models]


def get_model_choices(provider_key: str) -> list[tuple[str, str]]:
    """Return ``[(display_name, model_id), ...]`` for interactive selectors."""
    p = get_provider(provider_key)
    if not p:
        return []
    return [(m.name, m.id) for m in p.models]
