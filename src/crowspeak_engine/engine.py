"""Engine: the single entry point for clients."""

from __future__ import annotations

from .features import Features
from .llm.base import LLMProvider
from .prefs import InteractionPrefs
from .session import Learner, Session


class Engine:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def start_session(
        self,
        learner: Learner,
        prefs: InteractionPrefs | None = None,
        features: Features | None = None,
    ) -> Session:
        return Session(learner, self._llm, prefs, features)
