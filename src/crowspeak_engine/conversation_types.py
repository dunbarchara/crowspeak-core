"""Transcript value types shared by conversations and events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from .corrections import Corrections

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
    # Identifies the message so late results (corrections) can be matched to it.
    # Not part of equality: two messages with the same text are equal.
    id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    # Feedback on a learner message. None = not analyzed; an empty result = nothing found.
    # Never sent to the speaker LLM.
    corrections: Corrections | None = None
