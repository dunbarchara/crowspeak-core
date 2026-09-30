"""CrowSpeak conversation engine: UI-agnostic; takes input, yields events."""

from .conversation import Conversation
from .conversation_types import Message, Role
from .engine import Engine
from .errors import ConstraintError
from .events import (
    ConversationEvent,
    EngineError,
    Event,
    ExpressionChange,
    SessionStarted,
    TranscriptDelta,
    TurnCompleted,
)
from .expression import EXPRESSIONS
from .features import Features
from .llm.base import LLMProvider
from .npc import Npc
from .prefs import InteractionPrefs
from .proficiency import Proficiency
from .profile import LanguageProfile
from .session import Learner, Session

__all__ = [
    "ConstraintError",
    "Conversation",
    "ConversationEvent",
    "EXPRESSIONS",
    "Engine",
    "EngineError",
    "Event",
    "ExpressionChange",
    "Features",
    "InteractionPrefs",
    "LLMProvider",
    "LanguageProfile",
    "Learner",
    "Message",
    "Npc",
    "Proficiency",
    "Role",
    "Session",
    "SessionStarted",
    "TranscriptDelta",
    "TurnCompleted",
]
