"""World-level session state: one learner, many conversations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .conversation import Conversation
from .errors import UnsupportedSchemaVersion
from .events import SessionStarted
from .features import Features
from .llm.providers import Providers
from .npc import Npc
from .prefs import InteractionPrefs, resolve_prefs
from .profile import LanguageProfile

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Learner:
    """One study track: a target language plus its persisted defaults. `prefs` and
    `features` are the learner's defaults, under any session or conversation override."""

    language: LanguageProfile
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    prefs: InteractionPrefs | None = None
    features: Features | None = None

    def __post_init__(self) -> None:
        if self.language.target is None:
            raise ValueError("a learner must have a target language")

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "language": self.language.to_dict(),
            "prefs": None if self.prefs is None else self.prefs.to_dict(),
            "features": None if self.features is None else self.features.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Learner:
        version = data["schema_version"]
        if version > SCHEMA_VERSION:
            raise UnsupportedSchemaVersion(
                f"learner schema_version {version} is newer than the supported {SCHEMA_VERSION}"
            )
        prefs = data.get("prefs")
        features = data.get("features")
        return cls(
            language=LanguageProfile.from_dict(data["language"]),
            id=data["id"],
            prefs=None if prefs is None else InteractionPrefs.from_dict(prefs),
            features=None if features is None else Features.from_dict(features),
        )


class Session:
    def __init__(
        self,
        learner: Learner,
        providers: Providers,
        prefs: InteractionPrefs | None = None,
        features: Features | None = None,
    ) -> None:
        self.session_id = str(uuid.uuid4())
        self.learner = learner
        self._providers = providers
        self._prefs = prefs
        self._features = features
        self.conversations: dict[str, Conversation] = {}

    @property
    def prefs(self) -> InteractionPrefs | None:
        return self._prefs

    def set_prefs(self, prefs: InteractionPrefs | None) -> None:
        """Change the session-wide defaults. Atomic: raises ConstraintError, changing
        nothing, if an existing conversation's Npc can't accommodate them."""
        for conv in self.conversations.values():
            resolve_prefs(self.learner.language, conv.npc, conv.prefs, prefs, self.learner.prefs)
        self._prefs = prefs

    @property
    def features(self) -> Features | None:
        return self._features

    def set_features(self, features: Features | None) -> None:
        """Change the session-wide feature defaults. Applies from each conversation's
        next turn (a conversation that overrides a flag keeps its own value)."""
        self._features = features

    def start_event(self) -> SessionStarted:
        return SessionStarted(session_id=self.session_id, learner_id=self.learner.id)

    def converse(
        self,
        npc: Npc | None = None,
        prefs: InteractionPrefs | None = None,
        features: Features | None = None,
    ) -> Conversation:
        """Get or create the conversation with `npc` (default: a generic partner who
        natively speaks the learner's target language)."""
        if npc is None:
            npc = Npc.default(native_language=self.learner.language.target)
        existing = self.conversations.get(npc.id)
        if existing is not None:
            return existing
        conv = Conversation(self, npc, self._providers, prefs, features)
        self.conversations[npc.id] = conv
        return conv
