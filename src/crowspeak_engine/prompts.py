"""System-prompt composition for a conversation."""

from __future__ import annotations

from .npc import Npc
from .profile import LanguageProfile
from .proficiency_adapters import get_adapter


def _describe(name: str, p: LanguageProfile) -> str:
    text = f"{name} natively speaks {p.native}"
    if p.target:
        text += f" and is learning {p.target} at CEFR level {p.proficiency.value}"
    return text + "."


def build_system_prompt(
    learner: LanguageProfile,
    npc: Npc,
    input_language: str,
    response_language: str,
) -> str:
    parts = [
        npc.persona,
        _describe("The learner", learner),
        _describe(f"You ({npc.name})", npc.language),
        f"The learner will write to you in {input_language}; "
        f"you must respond only in {response_language}.",
    ]

    # Calibrate to whoever's level matters for the language being spoken: an Npc
    # speaking its own non-native target talks at its own level; otherwise pitch
    # to the learner's level in that language.
    npc_lang = npc.language
    if response_language == npc_lang.target:
        parts.append(get_adapter(response_language, npc_lang.proficiency))
    elif response_language == learner.target:
        parts.append(get_adapter(response_language, learner.proficiency))

    if npc.understands is not None:
        parts.append(
            f"You only understand {', '.join(sorted(npc.understands))}. If the learner "
            "writes in any other language, say in character that you don't understand."
        )
    if npc.speaks is not None:
        parts.append(f"You only speak {', '.join(sorted(npc.speaks))}.")

    return "\n".join(parts)
