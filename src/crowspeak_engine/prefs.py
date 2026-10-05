"""Interaction preferences and their resolution against a learner and an Npc."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ConstraintError
from .npc import Npc
from .profile import LanguageProfile


@dataclass(frozen=True)
class InteractionPrefs:
    """Which language the learner writes in and the Npc replies in.

    Free-form language codes; any combination is valid. None means "use the
    natural default" (see `resolve_prefs`).
    """

    learner_input_language: str | None = None
    npc_response_language: str | None = None


def _pick(candidates: list[str | None], allowed: frozenset[str] | None, what: str) -> str:
    options = [c for c in candidates if c]
    if allowed is None:
        return options[0]
    for c in options:
        if c in allowed:
            return c
    raise ConstraintError(f"no {what} language available within {sorted(allowed)}")


def resolve_prefs(
    learner: LanguageProfile,
    npc: Npc,
    *prefs: InteractionPrefs | None,
) -> tuple[str, str]:
    """Return (input_language, response_language).

    `prefs` is ordered most specific first (conversation, then session). Unset
    values fall back to a natural default that respects the Npc's constraints;
    explicit values that violate them raise ConstraintError.
    """
    given = [p for p in prefs if p is not None]
    input_lang = next((p.learner_input_language for p in given if p.learner_input_language), None)
    response_lang = next((p.npc_response_language for p in given if p.npc_response_language), None)

    if input_lang is None:
        input_lang = _pick([learner.native, learner.target], npc.understands, "input")
    if response_lang is None:
        # Practice partner speaks the learner's target if they know it.
        knows_target = learner.target in (npc.language.native, npc.language.target)
        response_lang = _pick(
            [learner.target if knows_target else None, npc.language.native, npc.language.target],
            npc.speaks,
            "response",
        )

    if npc.understands is not None and input_lang not in npc.understands:
        raise ConstraintError(
            f"{npc.name} only understands {sorted(npc.understands)}, not {input_lang!r}"
        )
    if npc.speaks is not None and response_lang not in npc.speaks:
        raise ConstraintError(
            f"{npc.name} only speaks {sorted(npc.speaks)}, not {response_lang!r}"
        )
    return input_lang, response_lang
