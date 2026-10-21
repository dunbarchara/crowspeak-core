"""CrowSpeak conversation engine: UI-agnostic; takes input, yields events."""

from .analyzers import AnalysisError, Analyzer, AnalyzerContext, CorrectionsAnalyzer
from .conversation import Conversation
from .conversation_types import Message, Role
from .corrections import CATEGORIES, SEVERITIES, CorrectionItem, Corrections
from .engine import Engine
from .errors import ConstraintError, UnsupportedSchemaVersion
from .events import (
    AnalyzerError,
    ConversationEvent,
    CorrectionsReady,
    EngineError,
    Event,
    ExpressionChange,
    SessionStarted,
    TranscriptDelta,
    TurnCompleted,
)
from .expression import EXPRESSIONS
from .features import Features
from .generators import GenerationError, Generator, GeneratorContext
from .learner_store import InMemoryLearnerStore, LearnerStore
from .llm.base import JSONProvider, LLMProvider
from .llm.providers import JOB_CORRECTIONS, JOB_NPC, ProviderError, Providers
from .npc import Npc
from .prefs import InteractionPrefs
from .proficiency import Proficiency
from .profile import LanguageProfile
from .session import Learner, Session

__all__ = [
    "AnalysisError",
    "Analyzer",
    "AnalyzerContext",
    "AnalyzerError",
    "CATEGORIES",
    "CorrectionItem",
    "Corrections",
    "CorrectionsAnalyzer",
    "CorrectionsReady",
    "JOB_CORRECTIONS",
    "JOB_NPC",
    "JSONProvider",
    "ProviderError",
    "Providers",
    "SEVERITIES",
    "ConstraintError",
    "Conversation",
    "ConversationEvent",
    "EXPRESSIONS",
    "Engine",
    "EngineError",
    "Event",
    "ExpressionChange",
    "Features",
    "GenerationError",
    "Generator",
    "GeneratorContext",
    "InMemoryLearnerStore",
    "InteractionPrefs",
    "LLMProvider",
    "LanguageProfile",
    "Learner",
    "LearnerStore",
    "Message",
    "Npc",
    "Proficiency",
    "Role",
    "Session",
    "SessionStarted",
    "TranscriptDelta",
    "TurnCompleted",
    "UnsupportedSchemaVersion",
]
