"""Corrections analyzer: grammar/vocabulary/spelling feedback on a learner's message."""

from __future__ import annotations

import json
from dataclasses import replace

from ..corrections import CATEGORIES, SEVERITIES, CorrectionItem, Corrections
from ..llm.base import JSONProvider
from ..llm.providers import JOB_CORRECTIONS
from ..proficiency import Proficiency
from .base import AnalysisError, AnalyzerContext

# Most items shown up front per message, by level: beginners get only the main points.
# The rest are not dropped; they go to `Corrections.more`.
MAX_ITEMS = {
    Proficiency.A1: 2,
    Proficiency.A2: 2,
    Proficiency.B1: 3,
    Proficiency.B2: 4,
    Proficiency.C1: 5,
    Proficiency.C2: 5,
}

# Categories folded into `Corrections.more` whatever the cap, by level. The model reports
# every mistake; the engine decides what a beginner sees first. Levels not listed fold nothing.
FOLDED_CATEGORIES: dict[Proficiency, frozenset[str]] = {
    Proficiency.A1: frozenset({"accents", "punctuation"}),
    Proficiency.A2: frozenset({"accents", "punctuation"}),
}

# Tone only: what to show is the engine's decision (above), not the model's.
_LEVEL_HINT = {
    Proficiency.A1: "Keep every explanation to one short, simple sentence.",
    Proficiency.A2: "Keep explanations short and simple.",
}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["corrected", "praise", "items"],
    "properties": {
        "corrected": {"type": "string"},
        "praise": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "original",
                    "suggestion",
                    "category",
                    "severity",
                    "explanation",
                    "confidence",
                ],
                "properties": {
                    "original": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                    "explanation": {"type": "string"},
                    "confidence": {"type": ["number", "null"]},
                },
            },
        },
    },
}


def build_prompt(ctx: AnalyzerContext) -> list[dict]:
    level = ctx.proficiency
    system = "\n".join(
        [
            f"You are a language teacher reviewing ONE message written by a learner of "
            f"{ctx.target_language} (CEFR level {level.value}, native language "
            f"{ctx.native_language}). You are not role-playing and not replying to it.",
            "List every mistake in the learner's message, including missing accents and "
            "punctuation. Do not limit the number of items: the app decides what to show. For "
            "each, `original` must be the exact substring as written, `suggestion` its "
            f"replacement, `category` one of {', '.join(CATEGORIES)}, and `severity` `error` "
            "(wrong) or `suggestion` (correct but unnatural). `corrected` is the whole message "
            "with all of your fixes applied.",
            "`accents` is a missing or wrong diacritic mark on otherwise correct letters (for "
            "example `como` for `cómo`). A different letter (`n` for `ñ`) or a misspelled word "
            "is `spelling`, and missing or wrong marks such as `¡` `¿` `,` `.` are `punctuation`.",
            f"Write every `explanation` in {ctx.native_language}, briefly, naming the rule. "
            f"{_LEVEL_HINT.get(level, '')}".strip(),
            f"Regional variants of {ctx.target_language} are correct: do not flag vocabulary or "
            "forms that are normal in that region. If unsure whether something is wrong, do not "
            "flag it.",
            f"`praise`: one short encouraging sentence in {ctx.native_language} about something "
            "they did well, or null.",
            "Earlier turns are context only (they show what the message answers); never "
            "correct them. If the message has no mistakes, return no items.",
        ]
    )
    history = "\n".join(f"[{who}] {text}" for who, text in ctx.history)
    user = (f"Conversation so far:\n{history}\n\n" if history else "") + (
        f"Learner message to review:\n{ctx.text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _locate(text: str, quote: str, taken: list[tuple[int, int]]) -> tuple[int, int] | None:
    """First occurrence of `quote` in `text` that doesn't overlap an earlier item."""
    start = text.find(quote)
    while start != -1:
        span = (start, start + len(quote))
        if all(span[1] <= a or span[0] >= b for a, b in taken):
            return span
        start = text.find(quote, start + 1)
    return None


def parse_corrections(raw: str, ctx: AnalyzerContext) -> Corrections:
    try:
        data = json.loads(raw)
        items_data = data["items"]
        if not isinstance(items_data, list):
            raise TypeError("items is not a list")
        items: list[CorrectionItem] = []
        for d in items_data:
            category, severity = d["category"], d["severity"]
            if category not in CATEGORIES or severity not in SEVERITIES:
                raise ValueError(f"unknown category/severity: {category!r}/{severity!r}")
            original, suggestion = str(d["original"]), str(d["suggestion"])
            if not original or original == suggestion:
                continue  # nothing to show
            confidence = d.get("confidence")
            items.append(
                CorrectionItem(
                    original=original,
                    suggestion=suggestion,
                    category=category,
                    severity=severity,
                    explanation=str(d["explanation"]),
                    explanation_language=ctx.native_language,
                    confidence=None if confidence is None else float(confidence),
                )
            )
        corrected, praise = str(data["corrected"]), data.get("praise")
    except (ValueError, KeyError, TypeError) as e:  # JSONDecodeError is a ValueError
        raise AnalysisError(f"unusable corrections output: {e}") from e

    # Errors first, then by category in CATEGORIES order (grammar before accents), so the
    # cap keeps the points that matter; the sort is stable within each group.
    items.sort(key=lambda i: (i.severity != "error", CATEGORIES.index(i.category)))
    folded = FOLDED_CATEGORIES.get(ctx.proficiency, frozenset())
    major = [i for i in items if i.category not in folded]
    minor = [i for i in items if i.category in folded]
    cap = MAX_ITEMS[ctx.proficiency]
    shown, rest = major[:cap], major[cap:] + minor  # nothing is dropped

    taken: list[tuple[int, int]] = []  # shared, so no two items claim the same text
    located: list[CorrectionItem] = []
    for item in shown + rest:
        span = _locate(ctx.text, item.original, taken)
        if span is not None:
            taken.append(span)
        located.append(replace(item, span=span))
    return Corrections(
        language=ctx.target_language,
        original=ctx.text,
        corrected=corrected if located else ctx.text,
        is_correct=not located,
        items=tuple(located[: len(shown)]),
        praise=praise if isinstance(praise, str) and praise.strip() else None,
        more=tuple(located[len(shown) :]),
    )


class CorrectionsAnalyzer:
    name = JOB_CORRECTIONS  # an analyzer's name is also the job its provider is assigned to

    def __init__(self, llm: JSONProvider) -> None:
        self._llm = llm

    async def analyze(self, context: AnalyzerContext) -> Corrections:
        try:
            raw = await self._llm.complete_json(build_prompt(context), SCHEMA)
        except Exception as e:
            raise AnalysisError(f"analyzer call failed: {e}") from e
        return parse_corrections(raw, context)
