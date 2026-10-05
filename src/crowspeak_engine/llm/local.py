"""Local OpenAI-compatible streaming provider (Ollama, llama.cpp server, etc.)."""

from __future__ import annotations

import os
from typing import AsyncIterator

from openai import AsyncOpenAI

from ._openai_stream import complete_json, stream_deltas

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.1"


class LocalOpenAIProvider:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_key: str = "ollama",
    ) -> None:
        self._model = model
        # Local servers ignore the key, but the client requires a non-empty one.
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    @classmethod
    def from_env(cls) -> LocalOpenAIProvider:
        """Build from LOCAL_LLM_* environment variables (callers load any .env)."""
        return cls(
            base_url=os.environ.get("LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ.get("LOCAL_LLM_MODEL", DEFAULT_MODEL),
        )

    def describe(self) -> str:
        return f"local model={self._model} base_url={self._client.base_url}"

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        async for delta in stream_deltas(self._client, self._model, messages):
            yield delta

    async def complete_json(self, messages: list[dict], schema: dict) -> str:
        return await complete_json(self._client, self._model, messages, schema)
