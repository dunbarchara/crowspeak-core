"""Shared streaming loop for OpenAI-compatible chat-completions clients."""

from __future__ import annotations

from typing import AsyncIterator


async def stream_deltas(client, model: str, messages: list[dict]) -> AsyncIterator[str]:
    response = await client.chat.completions.create(model=model, messages=messages, stream=True)
    async for chunk in response:
        # Content-filter chunks arrive with no choices.
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def complete_json(client, model: str, messages: list[dict], schema: dict) -> str:
    """One non-streaming call whose reply must match `schema`; returns the JSON text."""
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "analysis", "schema": schema, "strict": True},
        },
    )
    return response.choices[0].message.content or ""
