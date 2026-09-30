"""Optional engine capabilities, toggled per session and per conversation.

Features are additive and opt-in: a consumer that sets nothing gets the simplest contract
(plain text, no extra events, no extra prompt text). Like `InteractionPrefs`, a value is
set at the session level as a default and may be overridden per conversation; `None`
means "not set here, fall through". Flags are read at the start of each turn, so
changing one applies from the next turn.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Features:
    # Ask the speaker for expression tags and emit ExpressionChange events.
    expression: bool | None = None


@dataclass(frozen=True)
class ResolvedFeatures:
    expression: bool = False


def resolve_features(*features: Features | None) -> ResolvedFeatures:
    """Merge feature layers, ordered most specific first (conversation, then session)."""
    given = [f for f in features if f is not None]

    def pick(name: str, default: bool) -> bool:
        return next((v for f in given if (v := getattr(f, name)) is not None), default)

    return ResolvedFeatures(expression=pick("expression", False))
