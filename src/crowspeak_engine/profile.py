"""Language configuration shared by learners and Npcs."""

from __future__ import annotations

from dataclasses import dataclass

from .proficiency import Proficiency


@dataclass(frozen=True)
class LanguageProfile:
    """Who someone is linguistically: native language, and optionally a language
    they're learning with their level in it."""

    native: str
    target: str | None = None
    proficiency: Proficiency | None = None

    def __post_init__(self) -> None:
        if self.target is None:
            if self.proficiency is not None:
                raise ValueError("proficiency requires a target language")
            return
        if self.target == self.native:
            raise ValueError("native and target language must differ")
        if self.proficiency is None:
            raise ValueError("a target language requires a proficiency")
