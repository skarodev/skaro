"""Anthropic Claude LLM adapter with prompt caching support."""

from __future__ import annotations

from typing import AsyncIterator

import anthropic

from skaro_core.config import LLMConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMError, LLMMessage, LLMResponse


class AnthropicAdapter(BaseLLMAdapter):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._validate_api_key()
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)

    def _wrap_error(self, exc: Exception) -> LLMError:
        if isinstance(exc, anthropic.RateLimitError):
            return LLMError(f"Anthropic rate limit exceeded. {exc}", provider="anthropic", retriable=True)
        if isinstance(exc, anthropic.AuthenticationError):
            return LLMError(
                "Anthropic authentication failed (401). Check your API key in Settings.",
                provider="anthropic", status_code=401,
            )
        if isinstance(exc, anthropic.PermissionDeniedError):
            return LLMError(
                "Anthropic permission denied (403). Your API key may lack required permissions.",
                provider="anthropic", status_code=403,
            )
        if isinstance(exc, anthropic.APIError):
            return LLMError(f"Anthropic API error: {exc}", provider="anthropic")
        return LLMError(f"Anthropic request failed: {exc}", provider="anthropic")

    def _prepare_messages(
        self, messages: list[LLMMessage],
    ) -> tuple[list[dict] | str, list[dict]]:
        """Split system messages out and apply cache_control hints.

        Returns ``(system, chat_messages)`` where *system* is either a plain
        string (no caching) or a list of content blocks (with optional
        ``cache_control``).
        """
        system_parts: list[dict] = []
        chat_messages: list[dict] = []
        any_system_cached = False

        for msg in messages:
            if msg.role == "system":
                block: dict = {"type": "text", "text": msg.content}
                if msg.cache:
                    block["cache_control"] = {"type": "ephemeral"}
                    any_system_cached = True
                system_parts.append(block)
            else:
                if msg.cache:
                    # Structured content with cache_control
                    content = [
                        {
                            "type": "text",
                            "text": msg.content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                else:
                    content = msg.content
                chat_messages.append({"role": msg.role, "content": content})

        # If no caching was requested, fall back to plain string for system
        # (avoids unnecessary structured format for non-caching calls).
        if not any_system_cached and system_parts:
            plain = "\n".join(p["text"] for p in system_parts).strip()
            return plain, chat_messages

        return system_parts, chat_messages

    @staticmethod
    def _extract_cache_stats(usage) -> dict[str, int] | None:
        """Extract prompt caching statistics from an Anthropic usage object."""
        stats: dict[str, int] = {}
        if hasattr(usage, "cache_creation_input_tokens") and usage.cache_creation_input_tokens:
            stats["cache_creation_input_tokens"] = usage.cache_creation_input_tokens
        if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
            stats["cache_read_input_tokens"] = usage.cache_read_input_tokens
        return stats if stats else None

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        system, chat_messages = self._prepare_messages(messages)

        try:
            response = await self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system if system else anthropic.NOT_GIVEN,
                messages=chat_messages,
            )
        except LLMError:
            raise
        except Exception as e:
            raise self._wrap_error(e) from e

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            cache_stats=self._extract_cache_stats(response.usage),
        )

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        system, chat_messages = self._prepare_messages(messages)

        try:
            async with self.client.messages.stream(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system if system else anthropic.NOT_GIVEN,
                messages=chat_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                # Capture usage after stream completes
                final = await stream.get_final_message()
                if final and final.usage:
                    self.last_usage = {
                        "input_tokens": final.usage.input_tokens,
                        "output_tokens": final.usage.output_tokens,
                    }
                    # Store cache stats for tracking
                    cache_stats = self._extract_cache_stats(final.usage)
                    if cache_stats:
                        self.last_usage.update(cache_stats)
                if final:
                    self.last_stop_reason = final.stop_reason
        except LLMError:
            raise
        except Exception as e:
            raise self._wrap_error(e) from e
