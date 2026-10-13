"""Job registry: which provider runs which job.

A *job* is a plain string naming a piece of LLM work (`npc`, an analyzer's name, a
generator's name, or anything a consumer defines). A job resolves to the provider
assigned to it, else to the registry's default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

from .base import LLMProvider

JOB_NPC = "npc"
JOB_CORRECTIONS = "corrections"

# What a job needs from its provider: a streamed reply, or a JSON-schema constrained one.
Needs = Literal["stream", "json"]
_METHOD: dict[str, str] = {"stream": "stream", "json": "complete_json"}


class ProviderError(ValueError):
    """A job has no provider that can do what it needs."""


def _describe(provider: object) -> str:
    describe = getattr(provider, "describe", None)
    return describe() if callable(describe) else type(provider).__name__


@dataclass(frozen=True)
class Providers:
    default: LLMProvider
    jobs: Mapping[str, LLMProvider] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # A read-only copy, so changing the caller's dict later can't change the registry.
        object.__setattr__(self, "jobs", MappingProxyType(dict(self.jobs)))

    def for_job(self, name: str, needs: Needs = "stream") -> LLMProvider:
        """The provider for job `name`: its own if assigned, else the default.

        Raises ProviderError if that provider lacks the capability the job needs.
        """
        provider = self.jobs.get(name, self.default)
        method = _METHOD[needs]
        if not hasattr(provider, method):
            source = "assigned to it" if name in self.jobs else "the default"
            raise ProviderError(
                f"job {name!r} needs a provider with {method}(), but {source} "
                f"({_describe(provider)}) has none; assign one with "
                f"Providers(jobs={{{name!r}: ...}})"
            )
        return provider
