"""Transcript value types shared by conversations and events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    # True if the stream that produced this message was cancelled mid-turn
    # (consumer disconnected, task cancelled) rather than finishing normally.
    interrupted: bool = False
    # The model's output with expression tags intact (assistant turns only). `content`
    # is the clean text; `raw` is what goes back to the LLM so it keeps the tag format.
    raw: str | None = None
