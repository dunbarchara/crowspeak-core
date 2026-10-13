"""Turn engine events and values into terminal text. Pure: no I/O, no environment reads.

Callers decide whether color is appropriate (TTY, NO_COLOR) and pass `color`. With
color off the output stays readable: highlighted spans are wrapped in [brackets].
"""

from __future__ import annotations

from crowspeak_engine import AnalyzerError, CorrectionItem, Corrections

_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_GREEN = "\x1b[32m"
_SEVERITY_STYLE = {
    "error": "\x1b[4;31m",  # underlined red
    "suggestion": "\x1b[4;33m",  # underlined yellow
}


def _paint(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def _mark(text: str, severity: str, color: bool) -> str:
    if not color:
        return f"[{text}]"
    return _paint(text, _SEVERITY_STYLE.get(severity, _SEVERITY_STYLE["suggestion"]), True)


def highlight(
    corrections: Corrections, color: bool, items: tuple[CorrectionItem, ...] | None = None
) -> str:
    """The learner's original message with each flagged span marked (`items` by default,
    or pass `corrections.more` for the folded ones).

    Items without a span (the engine couldn't locate the quote), and spans that overlap an
    earlier one, are left unmarked; they still appear in the notes.
    """
    text = corrections.original
    spans: list[tuple[tuple[int, int], CorrectionItem]] = sorted(
        (
            (item.span, item)
            for item in (corrections.items if items is None else items)
            if item.span is not None
        ),
        key=lambda pair: pair[0],
    )
    out: list[str] = []
    pos = 0
    for (start, end), item in spans:
        if start < pos or end > len(text) or start >= end:
            continue
        out.append(text[pos:start])
        out.append(_mark(text[start:end], item.severity, color))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _notes(items: tuple[CorrectionItem, ...], color: bool) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(f'      "{item.original}" → "{item.suggestion}"')
        lines.append(_paint(f"        {item.category} · {item.severity}", _DIM, color))
        lines.append(f"        {item.explanation}")
    return lines


def _corrected_line(corrections: Corrections) -> list[str]:
    if corrections.corrected and corrections.corrected != corrections.original:
        return [f"    → {corrections.corrected}"]
    return []


def _more_label(corrections: Corrections) -> str:
    """`3 more (accents, punctuation)`: the folded items' count and distinct categories."""
    categories = ", ".join(dict.fromkeys(item.category for item in corrections.more))
    return f"{len(corrections.more)} more ({categories})"


def format_corrections(corrections: Corrections, color: bool = False) -> str:
    """A highlighted reprint of the learner's message followed by one note per item.
    Folded items are not listed here; see `format_more_hint` and `format_more`."""
    if corrections.is_correct and not corrections.items and not corrections.more:
        praise = corrections.praise or "Looks good!"
        return "  " + _paint(f"✓ {praise}", _GREEN, color)

    lines = [f"  ✎ {highlight(corrections, color)}"]
    lines += _notes(corrections.items, color)
    lines += _corrected_line(corrections)
    if corrections.praise:
        lines.append("  " + _paint(corrections.praise, _GREEN, color))
    return "\n".join(lines)


def format_more(corrections: Corrections, color: bool = False) -> str:
    """The folded items (minor fixes, or anything over the level's cap): the message with
    their spans marked, one note each, and the full corrected text."""
    if not corrections.more:
        return "  Nothing more to show."
    lines = [f"  ✎ {highlight(corrections, color, corrections.more)}"]
    lines += _notes(corrections.more, color)
    lines += _corrected_line(corrections)
    return "\n".join(lines)


def format_more_hint(corrections: Corrections, number: int, color: bool = False) -> str:
    """A footer for `/review`: how many fixes are folded and how to see them ('' if none)."""
    if not corrections.more:
        return ""
    return "  " + _paint(f"+{_more_label(corrections)} · /review-more {number}", _DIM, color)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def format_summary(corrections: Corrections, number: int | None = None, color: bool = False) -> str:
    """One quiet line per message; `/review` (or `/review N`) shows the full notes, and
    `/review-more` the folded ones."""
    if corrections.is_correct and not corrections.items and not corrections.more:
        return "  " + _paint("✓ looks good", _GREEN, color)
    errors = sum(1 for item in corrections.items if item.severity == "error")
    parts = []
    if errors:
        parts.append(_count(errors, "error"))
    if len(corrections.items) > errors:
        parts.append(_count(len(corrections.items) - errors, "suggestion"))
    if corrections.more:
        label = _more_label(corrections)
        parts.append(f"+{label}" if corrections.items else label)
    # With nothing up front the folded items are the whole story.
    command = "/review" if corrections.items else "/review-more"
    hint = f"{command} {number}" if number else command
    return "  " + _paint(f"✎ {', '.join(parts) or 'feedback'} · {hint}", _DIM, color)


def format_analyzer_error(event: AnalyzerError, color: bool = False) -> str:
    """A dim, non-fatal note: the conversation itself is unaffected."""
    return "  " + _paint(f"({event.analyzer} unavailable: {event.message})", _DIM, color)
