"""Azure AI Foundry (Azure OpenAI) streaming provider."""

from __future__ import annotations

import os
from typing import AsyncIterator

from openai import AsyncAzureOpenAI

from ._openai_stream import stream_deltas


class AzureOpenAIProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-12-01-preview",
    ) -> None:
        self._deployment = deployment
        self._endpoint = endpoint
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )

    @classmethod
    def from_env(cls) -> AzureOpenAIProvider:
        """Build from AZURE_OPENAI_* environment variables (callers load any .env)."""
        return cls(
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )

    def describe(self) -> str:
        return f"azure deployment={self._deployment} endpoint={self._endpoint}"

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        async for delta in stream_deltas(self._client, self._deployment, messages):
            yield delta
