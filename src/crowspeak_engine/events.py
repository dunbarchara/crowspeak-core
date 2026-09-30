"""Domain events yielded by the engine. Clients render these however they like."""

from __future__ import annotations

from dataclasses import dataclass

from .conversation_types import Message, Role


@dataclass(frozen=True, kw_only=True)
class Event:
    session_id: str


@dataclass(frozen=True, kw_only=True)
class SessionStarted(Event):
    learner_id: str


@dataclass(frozen=True, kw_only=True)
class ConversationEvent(Event):
    conversation_id: str
    speaker_id: str  # npc id, or "user"


@dataclass(frozen=True, kw_only=True)
class TranscriptDelta(ConversationEvent):
    text: str
    role: Role
    final: bool = False


@dataclass(frozen=True, kw_only=True)
class ExpressionChange(ConversationEvent):
    """How the speaker is delivering what follows. Always precedes a turn's first text."""

    label: str


@dataclass(frozen=True, kw_only=True)
class TurnCompleted(ConversationEvent):
    message: Message


@dataclass(frozen=True, kw_only=True)
class EngineError(ConversationEvent):
    message: str
    recoverable: bool = True
