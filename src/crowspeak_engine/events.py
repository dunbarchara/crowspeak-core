"""Domain events yielded by the engine. Clients render these however they like."""

from __future__ import annotations

from dataclasses import dataclass

from .conversation_types import Message, Role
from .corrections import Corrections


@dataclass(frozen=True, kw_only=True)
class Event:
    session_id: str


@dataclass(frozen=True, kw_only=True)
class SessionStarted(Event):
    learner_id: str


@dataclass(frozen=True, kw_only=True)
class ConversationEvent(Event):
    conversation_id: str
    speaker_id: str  # whoever is talking: an npc id, or "user" (to become the learner id)


@dataclass(frozen=True, kw_only=True)
class TranscriptDelta(ConversationEvent):
    text: str
    role: Role
    final: bool = False


@dataclass(frozen=True, kw_only=True)
class ExpressionChange(ConversationEvent):
    """How the NPC is delivering what follows. Always precedes a turn's first text."""

    label: str


@dataclass(frozen=True, kw_only=True)
class TurnCompleted(ConversationEvent):
    message: Message


@dataclass(frozen=True, kw_only=True)
class EngineError(ConversationEvent):
    message: str
    recoverable: bool = True


@dataclass(frozen=True, kw_only=True)
class CorrectionsReady(ConversationEvent):
    """Feedback on the learner's message `message_id`. Follows that turn's TurnCompleted."""

    message_id: str
    corrections: Corrections


@dataclass(frozen=True, kw_only=True)
class AnalyzerError(ConversationEvent):
    """An analyzer failed. Non-fatal: the conversation itself is unaffected."""

    analyzer: str
    message_id: str
    message: str
