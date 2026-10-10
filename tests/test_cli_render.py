from crowspeak_cli import render
from crowspeak_cli.cli import _review
from crowspeak_engine import (
    AnalyzerError,
    CorrectionItem,
    Corrections,
    Message,
)

TEXT = "Ayer yo fui al mercado y compré unos manzana."


def _corrections(items=(), *, is_correct=False, praise=None, corrected=None):
    return Corrections(
        language="es-MX",
        original=TEXT,
        corrected=TEXT if corrected is None else corrected,
        is_correct=is_correct,
        items=tuple(items),
        praise=praise,
    )


def _item(original, suggestion, *, severity="error", span="find", explanation="because"):
    if span == "find":
        start = TEXT.index(original)
        span = (start, start + len(original))
    return CorrectionItem(
        original=original,
        suggestion=suggestion,
        category="grammar",
        severity=severity,
        explanation=explanation,
        explanation_language="en",
        span=span,
    )


def test_highlight_brackets_spans_without_color():
    c = _corrections([_item("yo fui", "fui", severity="suggestion"), _item("unos manzana", "x")])
    assert render.highlight(c, color=False) == "Ayer [yo fui] al mercado y compré [unos manzana]."


def test_highlight_uses_ansi_with_color():
    c = _corrections([_item("unos manzana", "unas manzanas")])
    out = render.highlight(c, color=True)
    assert out == "Ayer yo fui al mercado y compré \x1b[4;31munos manzana\x1b[0m."


def test_highlight_skips_missing_overlapping_and_out_of_range_spans():
    c = _corrections(
        [
            _item("yo fui", "fui"),
            _item("fui al", "fue", span=(9, 15)),  # overlaps the first
            _item("nowhere", "x", span=None),
            _item("past end", "x", span=(500, 510)),
        ]
    )
    assert render.highlight(c, color=False) == "Ayer [yo fui] al mercado y compré unos manzana."


def test_format_corrections_lists_notes_and_corrected_text():
    c = _corrections(
        [_item("unos manzana", "unas manzanas", explanation="Feminine plural.")],
        corrected="Ayer yo fui al mercado y compré unas manzanas.",
    )
    out = render.format_corrections(c)
    assert '"unos manzana" → "unas manzanas"' in out
    assert "grammar · error" in out
    assert "Feminine plural." in out
    assert "→ Ayer yo fui al mercado y compré unas manzanas." in out


def test_format_corrections_when_correct():
    c = _corrections(is_correct=True, praise="¡Muy bien!")
    assert render.format_corrections(c) == "  ✓ ¡Muy bien!"
    assert "Looks good" in render.format_corrections(_corrections(is_correct=True))


def test_format_summary_counts_errors_and_suggestions_with_review_hint():
    c = _corrections(
        [
            _item("unos manzana", "unas manzanas"),
            _item("yo fui", "fui", severity="suggestion"),
            _item("al mercado", "a la tienda"),
        ]
    )
    assert render.format_summary(c, 3) == "  ✎ 2 errors, 1 suggestion · /review 3"
    assert render.format_summary(_corrections([_item("yo fui", "fui")]), None) == (
        "  ✎ 1 error · /review"
    )


def test_format_summary_when_correct():
    assert render.format_summary(_corrections(is_correct=True), 1) == "  ✓ looks good"


def test_format_analyzer_error_is_a_dim_note():
    err = AnalyzerError(
        session_id="s", conversation_id="c", speaker_id="user",
        analyzer="corrections", message_id="m", message="boom",
    )  # fmt: skip
    assert render.format_analyzer_error(err) == "  (corrections unavailable: boom)"
    assert render.format_analyzer_error(err, color=True).startswith("  \x1b[2m")


def test_review_picks_last_or_nth_learner_message():
    first = Message(
        role="user", content="uno", corrections=_corrections(is_correct=True, praise="A")
    )
    reply = Message(role="assistant", content="hola")
    second = Message(
        role="user", content="dos", corrections=_corrections(is_correct=True, praise="B")
    )
    history = [first, reply, second, Message(role="assistant", content="ok")]

    assert "B" in _review(history, "", color=False)
    assert "A" in _review(history, "1", color=False)
    assert "No message 3" in _review(history, "3", color=False)
    assert _review(history, "x", color=False) == "Usage: /review [N]"


def test_review_reports_unanalyzed_and_empty_history():
    assert _review([], "", color=False) == "Nothing to review yet."
    history = [Message(role="user", content="hola")]
    assert "not analyzed" in _review(history, "", color=False)
