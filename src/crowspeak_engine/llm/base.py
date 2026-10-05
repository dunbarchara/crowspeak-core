"""Provider boundary: anything that can stream a chat completion."""

from __future__ import annotations

from typing import AsyncIterator, Protocol


class LLMProvider(Protocol):
    def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield text deltas for the reply to OpenAI-style `messages`."""
        ...


class JSONProvider(Protocol):
    """Optional capability for structured (analyzer) calls: a reply constrained to a
    JSON schema, returned as the raw JSON text."""

    async def complete_json(self, messages: list[dict], schema: dict) -> str: ...
