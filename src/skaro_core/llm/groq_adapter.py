"""Groq adapter — free-tier cloud LLM.

Sign up: https://console.groq.com  (free API key, generous limits).

Free models (2025):
  llama-3.3-70b-versatile   — best quality
  llama-3.1-8b-instant      — fastest
  gemma2-9b-it
  mixtral-8x7b-32768
"""

from __future__ import annotations

from typing import AsyncIterator

import openai

from skaro_core.config import LLMConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMError, LLMMessage, LLMResponse, openai_wrap_error

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqAdapter(BaseLLMAdapter):

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._validate_api_key()
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or GROQ_BASE_URL,
        )

    def _wrap_error(self, exc: Exception) -> LLMError:
        return openai_wrap_error(exc, "groq")

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
