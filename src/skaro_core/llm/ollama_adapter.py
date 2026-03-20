"""Ollama adapter — free local LLM inference via https://ollama.com."""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from skaro_core.config import LLMConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMError, LLMMessage, LLMResponse

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class OllamaAdapter(BaseLLMAdapter):

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = (config.base_url or DEFAULT_OLLAMA_URL).rstrip("/")

    def _validate_api_key(self) -> None:
        pass  # Ollama doesn't need a key

    def _wrap_error(self, exc: Exception) -> LLMError:
        if isinstance(exc, httpx.ConnectError):
            return LLMError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?",
                provider="ollama",
            )
        if isinstance(exc, httpx.HTTPStatusError):
            return LLMError(
                f"Ollama HTTP error {exc.response.status_code}: {exc.response.text[:200]}",
                provider="ollama",
            )
        return LLMError(f"Ollama request failed: {exc}", provider="ollama")

    def _to_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.config.model,
                        "messages": self._to_messages(messages),
                        "stream": False,
                        "options": {
                            "temperature": self.config.temperature,
                            "num_predict": self.config.max_tokens,
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except LLMError:
            raise
        except Exception as e:
            raise self._wrap_error(e) from e

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", self.config.model),
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
        )

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.config.model,
                        "messages": self._to_messages(messages),
                        "stream": True,
                        "options": {
                            "temperature": self.config.temperature,
                            "num_predict": self.config.max_tokens,
                        },
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            text = chunk.get("message", {}).get("content", "")
                            if text:
                                yield text
                            if chunk.get("done"):
                                self.last_usage = {
                                    "input_tokens": chunk.get("prompt_eval_count", 0),
                                    "output_tokens": chunk.get("eval_count", 0),
                                }
                                done_reason = chunk.get("done_reason", "stop")
                                if done_reason == "length":
                                    self.last_stop_reason = "max_tokens"
                                else:
                                    self.last_stop_reason = "end_turn"
                                break
                        except json.JSONDecodeError:
                            continue
        except LLMError:
            raise
        except Exception as e:
            raise self._wrap_error(e) from e
