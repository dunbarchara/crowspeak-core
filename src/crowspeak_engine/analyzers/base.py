"""The analyzer stage: separate LLM calls that look at the learner's input and return
structured results, off the speaker's critical path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from ..corrections import Corrections
from ..proficiency import Proficiency

# (who said it, what they said). The speaker label is not a persona or an id.
Turn = tuple[Literal["NPC", "LEARNER"], str]


class AnalysisError(Exception):
    """An analyzer's call or output was unusable (surfaced as an AnalyzerError event)."""


@dataclass(frozen=True)
class AnalyzerContext:
    text: str  # the single learner message to analyze (clean text; transcript for voice)
    history: tuple[Turn, ...]  # the few turns before it, oldest first
    target_language: str  # region code allowed, e.g. "es-MX"
    native_language: str
    proficiency: Proficiency


class Analyzer(Protocol):
    name: str

    async def analyze(self, context: AnalyzerContext) -> Corrections: ...
