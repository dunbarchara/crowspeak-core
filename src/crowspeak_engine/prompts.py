"""System-prompt composition for a conversation."""

from __future__ import annotations

from typing import Sequence

from .npc import Npc
from .proficiency_adapters import get_adapter
from .profile import LanguageProfile

# Feedback on the other person's language comes from analyzers, never from the Npc, so the
# prompt must not cast the Npc as a teacher. Markdown is banned because clients render the
# reply as plain text (terminal, speech bubble, TTS).
_CONDUCT = (
    "Have a natural conversation, the way a person would. Do not teach: never correct "
    "mistakes, point out errors, or explain grammar or vocabulary unless you are asked "
    "to directly. Just understand what they meant and reply to it. Reply in plain text "
    "only, with no markdown, bold, or bullet lists."
)


def _describe(name: str, p: LanguageProfile) -> str:
    text = f"{name} natively speaks {p.native}"
    if p.target:
        text += f" and speaks {p.target} at CEFR level {p.proficiency.value}"
    return text + "."


def build_system_prompt(
    learner: LanguageProfile,
    npc: Npc,
    input_language: str,
    response_language: str,
    expressions: Sequence[str] = (),
) -> str:
    parts = [
        npc.persona,
        _describe("The person you are talking with", learner),
        _describe(f"You ({npc.name})", npc.language),
        f"They will write to you in {input_language}; "
        f"you must respond only in {response_language}.",
        _CONDUCT,
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
            f"You only understand {', '.join(sorted(npc.understands))}. If they "
            "write in any other language, say in character that you don't understand."
        )
    if npc.speaks is not None:
        parts.append(f"You only speak {', '.join(sorted(npc.speaks))}.")

    if expressions:
        tags = ", ".join(f"[{e}]" for e in expressions)
        parts.append(
            f"Begin every reply with exactly one expression tag in square brackets, chosen "
            f"from: {tags}. The tag says how you are delivering the line. Tags are always "
            "English and lower-case: never translate them and never mention them. If your "
            "mood changes, you may put another tag before a later sentence. For example, a "
            'cheerful reply starts with "[happy]" followed by your normal reply text.'
        )

    return "\n".join(parts)
