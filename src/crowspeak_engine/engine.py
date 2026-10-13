"""Engine: the single entry point for clients."""

from __future__ import annotations

from .features import Features
from .llm.base import LLMProvider
from .llm.providers import JOB_CORRECTIONS, Providers
from .prefs import InteractionPrefs
from .session import Learner, Session


class Engine:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        analyzer_llm: LLMProvider | None = None,
        *,
        providers: Providers | None = None,
    ) -> None:
        """Give the engine either a `Providers` registry (which provider runs which job), or
        the shorthand `llm` plus optional `analyzer_llm`. The shorthand is
        `Providers(default=llm, jobs={"corrections": analyzer_llm})`: `analyzer_llm` serves
        corrections (it can be a different, more accurate model than the NPC's) and
        defaults to `llm`."""
        if providers is not None:
            if llm is not None or analyzer_llm is not None:
                raise ValueError("pass either providers= or llm/analyzer_llm, not both")
        elif llm is None:
            raise ValueError("Engine needs providers= or an llm")
        else:
            jobs = {JOB_CORRECTIONS: analyzer_llm} if analyzer_llm is not None else {}
            providers = Providers(default=llm, jobs=jobs)
        self._providers = providers

    @property
    def providers(self) -> Providers:
        return self._providers

    def start_session(
        self,
        learner: Learner,
        prefs: InteractionPrefs | None = None,
        features: Features | None = None,
    ) -> Session:
        return Session(learner, self._providers, prefs, features)
