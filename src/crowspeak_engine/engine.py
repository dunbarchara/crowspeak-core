"""Engine: the single entry point for clients."""

from __future__ import annotations

from typing import Any, TypeVar

from .features import Features
from .generators import GenerationError, Generator, GeneratorContext, validate
from .llm.base import LLMProvider
from .llm.providers import JOB_CORRECTIONS, Providers
from .prefs import InteractionPrefs
from .session import Learner, Session

T = TypeVar("T")


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

    async def generate(self, generator: Generator[T], learner: Learner, **params: Any) -> T:
        """Run a structured job that isn't part of a conversation. The generator's `job`
        picks the provider (else the registry default); the reply is validated against
        its schema before `parse` sees it. Raises ProviderError if that provider can't
        return JSON, and GenerationError if the call or the output is unusable."""
        llm = self._providers.for_job(generator.job, "json")
        ctx = GeneratorContext(learner, params)
        try:
            raw = await llm.complete_json(generator.build_prompt(ctx), generator.schema)
        except Exception as e:
            raise GenerationError(f"generator call failed: {e}") from e
        data = validate(raw, generator.schema)
        try:
            return generator.parse(data, ctx)
        except (ValueError, KeyError, TypeError) as e:
            raise GenerationError(f"unusable {generator.name} output: {e}") from e
