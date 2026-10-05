"""Engine: the single entry point for clients."""

from __future__ import annotations

from .features import Features
from .llm.base import LLMProvider
from .prefs import InteractionPrefs
from .session import Learner, Session


class Engine:
    def __init__(self, llm: LLMProvider, analyzer_llm: LLMProvider | None = None) -> None:
        """`analyzer_llm` serves analyzer calls (corrections); defaults to `llm`. It can be
        a different, more accurate model than the speaker's."""
        self._llm = llm
        self._analyzer_llm = analyzer_llm

    def start_session(
        self,
        learner: Learner,
        prefs: InteractionPrefs | None = None,
        features: Features | None = None,
    ) -> Session:
        return Session(learner, self._llm, prefs, features, self._analyzer_llm)
