"""Base LLM adapter interface and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

from skaro_core.config import LLMConfig


class LLMError(Exception):
    """Raised when LLM API call fails."""

    def __init__(self, message: str, provider: str = "", retriable: bool = False):
        self.provider = provider
        self.retriable = retriable
        super().__init__(message)


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] | None = None


class BaseLLMAdapter(ABC):
    """Abstract interface for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.last_usage: dict[str, int] | None = None

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
    elif provider == "ollama":
        from skaro_core.llm.ollama_adapter import OllamaAdapter
        return OllamaAdapter(config)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: {', '.join(PROVIDER_PRESETS.keys())}"
        )
