"""The generator stage: structured LLM jobs that aren't tied to a conversation turn,
such as generating a day's task scenarios for a learner."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol, TypeVar

from ..proficiency import Proficiency
from ..session import Learner

T_co = TypeVar("T_co", covariant=True)


class GenerationError(Exception):
    """A generator's call or output was unusable."""


@dataclass(frozen=True)
class GeneratorContext:
    learner: Learner  # the whole learner, so richer data can flow in without an API change
    params: Mapping[str, Any] = field(default_factory=dict)  # per-call arguments

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    @property
    def target_language(self) -> str:
        return self.learner.target.language

    @property
    def native_language(self) -> str:
        return self.learner.language.native

    @property
    def proficiency(self) -> Proficiency:
        return self.learner.target.proficiency


class Generator(Protocol[T_co]):
    name: str
    job: str  # the job its provider is assigned to; defaults to `name` by convention
    schema: dict

    def build_prompt(self, ctx: GeneratorContext) -> list[dict]: ...

    def parse(self, data: Any, ctx: GeneratorContext) -> T_co:
        """Turn schema-valid decoded JSON into the generator's output type."""
        ...
