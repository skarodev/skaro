"""OpenRouter adapter — unified gateway to 400+ LLM models.

OpenRouter exposes an OpenAI-compatible ``/v1/chat/completions``
endpoint, so we reuse the ``openai`` SDK with a custom ``base_url``.

Sign up: https://openrouter.ai/settings/keys  (API key required).

Docs: https://openrouter.ai/docs/quickstart
"""

from __future__ import annotations

from typing import AsyncIterator

import openai

from skaro_core.config import LLMConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMError, LLMMessage, LLMResponse, openai_wrap_error

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(BaseLLMAdapter):

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._validate_api_key()
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://github.com/skaro-dev/skaro",
                "X-Title": "Skaro",
            },
        )

    def _wrap_error(self, exc: Exception) -> LLMError:
        return openai_wrap_error(exc, "openrouter")

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        oai = [{"role": m.role, "content": m.content} for m in messages]
        try:
            resp = await self.client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=oai,
            )
        except LLMError:
            raise
        except Exception as e:
            raise self._wrap_error(e) from e

        usage = None
        if resp.usage:
            usage = {
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
            }
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=resp.model or self.config.model,
            usage=usage,
        )

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        oai = [{"role": m.role, "content": m.content} for m in messages]
        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=oai,
                stream=True,
                stream_options={"include_usage": True},
            )
        except LLMError:
            raise
        except Exception as e:
            raise self._wrap_error(e) from e

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.choices and chunk.choices[0].finish_reason:
                self.last_stop_reason = chunk.choices[0].finish_reason
            if chunk.usage:
                self.last_usage = {
                    "input_tokens": chunk.usage.prompt_tokens,
                    "output_tokens": chunk.usage.completion_tokens,
                }
