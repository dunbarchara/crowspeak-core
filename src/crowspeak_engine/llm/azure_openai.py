"""Azure AI Foundry (Azure OpenAI) streaming provider."""

from __future__ import annotations

import os
from typing import AsyncIterator

from openai import AsyncAzureOpenAI


class AzureOpenAIProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-10-21",
    ) -> None:
        self._deployment = deployment
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
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        response = await self._client.chat.completions.create(
            model=self._deployment, messages=messages, stream=True
        )
        async for chunk in response:
            # Content-filter chunks arrive with no choices.
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
