"""Corrections analyzer: grammar/vocabulary/spelling feedback on a learner's message."""

from __future__ import annotations

import json
from dataclasses import replace

from ..corrections import CATEGORIES, SEVERITIES, CorrectionItem, Corrections
from ..llm.base import JSONProvider
from ..proficiency import Proficiency
from .base import AnalysisError, AnalyzerContext

# Most items shown per message, by level: beginners get only the main points.
MAX_ITEMS = {
    Proficiency.A1: 2,
    Proficiency.A2: 2,
    Proficiency.B1: 3,
    Proficiency.B2: 4,
    Proficiency.C1: 5,
    Proficiency.C2: 5,
}

_LEVEL_HINT = {
    Proficiency.A1: "Be very gentle: flag only errors that block understanding.",
    Proficiency.A2: "Be gentle: skip naturalness suggestions and minor slips.",
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
    limits = f"Only flag what a {level.value} learner should reasonably get right, and report "
    limits += (
        f"at most {MAX_ITEMS[level]} items, most important first. {_LEVEL_HINT.get(level, '')}"
    )
    system = "\n".join(
        [
            f"You are a language teacher reviewing ONE message written by a learner of "
            f"{ctx.target_language} (CEFR level {level.value}, native language "
            f"{ctx.native_language}). You are not role-playing and not replying to it.",
            "List the mistakes in the learner's message. For each, `original` must be the exact "
            "substring as written, `suggestion` its replacement, `category` one of "
            f"{', '.join(CATEGORIES)}, and `severity` `error` (wrong) or `suggestion` "
            "(correct but unnatural). `corrected` is the whole message with your fixes applied.",
            f"Write every `explanation` in {ctx.native_language}, briefly, naming the rule.",
            limits.strip(),
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

    items.sort(key=lambda i: i.severity != "error")  # stable: errors first
    items = items[: MAX_ITEMS[ctx.proficiency]]
    taken: list[tuple[int, int]] = []
    located: list[CorrectionItem] = []
    for item in items:
        span = _locate(ctx.text, item.original, taken)
        if span is not None:
            taken.append(span)
        located.append(replace(item, span=span))
    return Corrections(
        language=ctx.target_language,
        original=ctx.text,
        corrected=corrected if located else ctx.text,
        is_correct=not located,
        items=tuple(located),
        praise=praise if isinstance(praise, str) and praise.strip() else None,
    )


class CorrectionsAnalyzer:
    name = "corrections"

    def __init__(self, llm: JSONProvider) -> None:
        self._llm = llm

    async def analyze(self, context: AnalyzerContext) -> Corrections:
        try:
            raw = await self._llm.complete_json(build_prompt(context), SCHEMA)
        except Exception as e:
            raise AnalysisError(f"analyzer call failed: {e}") from e
        return parse_corrections(raw, context)
