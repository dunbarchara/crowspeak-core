"""Shared streaming loop for OpenAI-compatible chat-completions clients."""

from __future__ import annotations

from typing import AsyncIterator


async def stream_deltas(client, model: str, messages: list[dict]) -> AsyncIterator[str]:
    response = await client.chat.completions.create(
        model=model, messages=messages, stream=True
    )
    async for chunk in response:
        # Content-filter chunks arrive with no choices.
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
