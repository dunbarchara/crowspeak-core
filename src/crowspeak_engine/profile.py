"""Language configuration shared by learners and Npcs."""

from __future__ import annotations

from dataclasses import dataclass

from .proficiency import Proficiency


@dataclass(frozen=True)
class Target:
    """A language being learned and the level in it. Kept as one object so a target
    without a level (or a level without a target) cannot be built."""

    language: str  # a region code is allowed, e.g. "es-MX"
    proficiency: Proficiency

    def to_dict(self) -> dict:
        return {"language": self.language, "proficiency": self.proficiency.value}

    @classmethod
    def from_dict(cls, data: dict) -> Target:
        return cls(language=data["language"], proficiency=Proficiency(data["proficiency"]))


@dataclass(frozen=True)
class LanguageProfile:
    """Who someone is linguistically: native language, and optionally a language
    they're learning with their level in it."""

    native: str
    target: Target | None = None

    def __post_init__(self) -> None:
        if self.target is not None and self.target.language == self.native:
            raise ValueError("native and target language must differ")

    def to_dict(self) -> dict:
        return {
            "native": self.native,
            "target": None if self.target is None else self.target.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> LanguageProfile:
        target = data.get("target")
        return cls(
            native=data["native"],
            target=None if target is None else Target.from_dict(target),
        )
