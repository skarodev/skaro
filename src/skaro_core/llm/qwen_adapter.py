"""Qwen adapter — Alibaba Cloud Model Studio (DashScope).

Uses the OpenAI-compatible ``/compatible-mode/v1`` endpoint so
we can reuse the ``openai`` SDK directly.

Sign up: https://www.alibabacloud.com/en/solutions/generative-ai/model-studio
API key: https://bailian.console.alibabacloud.com/#/api-key

Docs: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
"""

from __future__ import annotations

from typing import AsyncIterator

import openai

from skaro_core.config import LLMConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMError, LLMMessage, LLMResponse, openai_wrap_error

QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class QwenAdapter(BaseLLMAdapter):

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._validate_api_key()
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or QWEN_BASE_URL,
        )

    def _wrap_error(self, exc: Exception) -> LLMError:
        return openai_wrap_error(exc, "qwen")

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
