"""OpenAI LLM adapter (compatible with OpenAI API and OpenAI-compatible endpoints)."""

from __future__ import annotations

import re
from typing import AsyncIterator

import openai

from skaro_core.config import LLMConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMError, LLMMessage, LLMResponse, openai_wrap_error

# Models that require `max_completion_tokens` instead of `max_tokens`.
# Covers: o1-*, o3-*, gpt-4.1*, gpt-5*, and their variants.
_MAX_COMPLETION_TOKENS_RE = re.compile(
    r"^(o[13]|gpt-(4\.1|5))", re.IGNORECASE,
)


class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._validate_api_key()
        kwargs: dict = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self.client = openai.AsyncOpenAI(**kwargs)

    def _wrap_error(self, exc: Exception) -> LLMError:
        return openai_wrap_error(exc, "openai")

    def _token_limit_kwargs(self) -> dict[str, int]:
        """Return the correct token-limit parameter for the current model.

        Newer OpenAI models (o1, o3, gpt-4.1, gpt-5+) reject ``max_tokens``
        and require ``max_completion_tokens``.  Older models and
        OpenAI-compatible third-party endpoints still expect ``max_tokens``.
        """
        if _MAX_COMPLETION_TOKENS_RE.match(self.config.model):
            return {"max_completion_tokens": self.config.max_tokens}
        return {"max_tokens": self.config.max_tokens}

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                messages=oai_messages,
                **self._token_limit_kwargs(),
            )
        except LLMError:
            raise
        except Exception as e:
            raise self._wrap_error(e) from e

        content = response.choices[0].message.content or ""
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        return LLMResponse(content=content, model=response.model or self.config.model, usage=usage)

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]
        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                messages=oai_messages,
                stream=True,
                stream_options={"include_usage": True},
                **self._token_limit_kwargs(),
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
