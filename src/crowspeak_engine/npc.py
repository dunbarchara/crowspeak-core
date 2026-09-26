"""Npcs: the characters a learner converses with."""

from __future__ import annotations

from dataclasses import dataclass

from .profile import LanguageProfile

DEFAULT_PERSONA = "You are a friendly, conversational language-practice partner."


@dataclass(frozen=True)
class Npc:
    id: str
    name: str
    persona: str
    language: LanguageProfile
    # Opt-in constraints. None means unrestricted.
    understands: frozenset[str] | None = None
    speaks: frozenset[str] | None = None

    @classmethod
    def default(cls, native_language: str, persona: str | None = None) -> Npc:
        """A generic partner who natively speaks `native_language`."""
        return cls(
            id="default",
            name="Partner",
            persona=persona or DEFAULT_PERSONA,
            language=LanguageProfile(native=native_language),
        )
