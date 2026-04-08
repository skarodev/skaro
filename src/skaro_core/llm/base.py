"""Base LLM adapter interface and factory."""

from __future__ import annotations

import platform
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

from skaro_core.config import LLMConfig

# ── Fix: OpenAI SDK + httpx crash on non-English OS ──────────────
# The openai SDK passes platform.version() into HTTP headers via httpx.
# On non-English macOS/Linux (ru_RU, zh_CN, etc.), platform.version()
# returns non-ASCII characters. httpx 0.28+ encodes headers as ASCII
# and crashes with UnicodeEncodeError.
# Fix: monkey-patch platform.version to strip non-ASCII once at import.
_original_platform_version = platform.version
platform.version = lambda: re.sub(r"[^\x00-\x7F]", "", _original_platform_version())


class LLMError(Exception):
    """Raised when LLM API call fails."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        retriable: bool = False,
        status_code: int | None = None,
    ):
        self.provider = provider
        self.retriable = retriable
        self.status_code = status_code
        super().__init__(message)


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str
    cache: bool = False  # hint for prompt caching (provider-specific)


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] | None = None
    # Cache statistics (provider-specific): cache_creation_input_tokens, cache_read_input_tokens
    cache_stats: dict[str, int] | None = None


class BaseLLMAdapter(ABC):
    """Abstract interface for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.last_usage: dict[str, int] | None = None
        self.last_stop_reason: str | None = None

    @abstractmethod
    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        ...

    @abstractmethod
    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        ...

    def _validate_api_key(self) -> None:
        if not self.config.api_key:
            preset = PROVIDER_PRESETS.get(self.config.provider)
            env_hint = f" or set env variable: {preset[1]}" if preset and preset[1] else ""
            raise ValueError(
                f"API key not found for {self.config.provider}. "
                f"Enter it in Settings{env_hint}"
            )

    def _wrap_error(self, exc: Exception) -> LLMError:
        """Convert a provider-specific exception into :class:`LLMError`.

        Subclasses should override to map their SDK exceptions.
        """
        return LLMError(f"LLM request failed: {exc}", provider=self.config.provider)


def openai_wrap_error(exc: Exception, provider: str) -> LLMError:
    """Map ``openai.*`` exceptions to :class:`LLMError`.

    Works for OpenAI and Groq adapters (both use the ``openai`` SDK).
    """
    import openai

    if isinstance(exc, openai.RateLimitError):
        return LLMError(
            f"{provider.title()} rate limit exceeded. {exc}",
            provider=provider, retriable=True,
        )
    if isinstance(exc, openai.AuthenticationError):
        return LLMError(
            f"{provider.title()} authentication failed (401). Check your API key in Settings.",
            provider=provider, status_code=401,
        )
    if isinstance(exc, openai.PermissionDeniedError):
        return LLMError(
            f"{provider.title()} permission denied (403). Your API key may lack required permissions.",
            provider=provider, status_code=403,
        )
    if isinstance(exc, openai.APIError):
        return LLMError(f"{provider.title()} API error: {exc}", provider=provider)
    return LLMError(f"{provider.title()} request failed: {exc}", provider=provider)


def _build_presets() -> dict[str, tuple[str, str, bool]]:
    """Build PROVIDER_PRESETS from providers.yaml registry.

    Returns ``{provider_key: (default_model, api_key_env, needs_key)}``.
    """
    from skaro_core.providers import get_providers

    presets: dict[str, tuple[str, str, bool]] = {}
    for key, info in get_providers().items():
        presets[key] = (info.default_model, info.api_key_env, info.needs_key)
    return presets


# (default_model, default_api_key_env, needs_key)
# Derived from providers.yaml — do not edit here.
PROVIDER_PRESETS: dict[str, tuple[str, str, bool]] = _build_presets()


def create_llm_adapter(config: LLMConfig) -> BaseLLMAdapter:
    """Factory: create adapter based on provider name."""
    provider = config.provider.lower()

    if provider == "anthropic":
        from skaro_core.llm.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter(config)
    elif provider == "openai":
        from skaro_core.llm.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(config)
    elif provider == "groq":
        from skaro_core.llm.groq_adapter import GroqAdapter
        return GroqAdapter(config)
    elif provider == "openrouter":
        from skaro_core.llm.openrouter_adapter import OpenRouterAdapter
        return OpenRouterAdapter(config)
    elif provider == "deepseek":
        from skaro_core.llm.deepseek_adapter import DeepSeekAdapter
        return DeepSeekAdapter(config)
    elif provider == "qwen":
        from skaro_core.llm.qwen_adapter import QwenAdapter
        return QwenAdapter(config)
    elif provider == "zai":
        from skaro_core.llm.zai_adapter import ZaiAdapter
        return ZaiAdapter(config)
    elif provider == "google":
        from skaro_core.llm.google_adapter import GoogleAdapter
        return GoogleAdapter(config)
    elif provider == "ollama":
        from skaro_core.llm.ollama_adapter import OllamaAdapter
        return OllamaAdapter(config)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: {', '.join(PROVIDER_PRESETS.keys())}"
        )
