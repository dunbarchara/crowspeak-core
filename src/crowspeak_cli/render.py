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


def highlight(corrections: Corrections, color: bool) -> str:
    """The learner's original message with each flagged span marked.

    Items without a span (the engine couldn't locate the quote), and spans that overlap an
    earlier one, are left unmarked; they still appear in the notes.
    """
    text = corrections.original
    spans: list[tuple[tuple[int, int], CorrectionItem]] = sorted(
        ((item.span, item) for item in corrections.items if item.span is not None),
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


def format_corrections(corrections: Corrections, color: bool = False) -> str:
    """A highlighted reprint of the learner's message followed by one note per item."""
    if corrections.is_correct and not corrections.items:
        praise = corrections.praise or "Looks good!"
        return "  " + _paint(f"✓ {praise}", _GREEN, color)

    lines = [f"  ✎ {highlight(corrections, color)}"]
    for item in corrections.items:
        lines.append(f'      "{item.original}" → "{item.suggestion}"')
        lines.append(_paint(f"        {item.category} · {item.severity}", _DIM, color))
        lines.append(f"        {item.explanation}")
    if corrections.corrected and corrections.corrected != corrections.original:
        lines.append(f"    → {corrections.corrected}")
    if corrections.praise:
        lines.append("  " + _paint(corrections.praise, _GREEN, color))
    return "\n".join(lines)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def format_summary(corrections: Corrections, number: int | None = None, color: bool = False) -> str:
    """One quiet line per message; `/review` (or `/review N`) shows the full notes."""
    if corrections.is_correct and not corrections.items:
        return "  " + _paint("✓ looks good", _GREEN, color)
    errors = sum(1 for item in corrections.items if item.severity == "error")
    parts = []
    if errors:
        parts.append(_count(errors, "error"))
    if len(corrections.items) > errors:
        parts.append(_count(len(corrections.items) - errors, "suggestion"))
    hint = f"/review {number}" if number else "/review"
    return "  " + _paint(f"✎ {', '.join(parts) or 'feedback'} · {hint}", _DIM, color)


def format_analyzer_error(event: AnalyzerError, color: bool = False) -> str:
    """A dim, non-fatal note: the conversation itself is unaffected."""
    return "  " + _paint(f"({event.analyzer} unavailable: {event.message})", _DIM, color)
