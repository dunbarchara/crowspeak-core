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


# --- folded items (`more`) -----------------------------------------------------------


def _with_more(items=(), more=(), **kwargs):
    from dataclasses import replace

    return replace(_corrections(items, **kwargs), more=tuple(more))


def _minor(original, suggestion, category="accents"):
    start = TEXT.index(original)
    return CorrectionItem(
        original=original,
        suggestion=suggestion,
        category=category,
        severity="error",
        explanation="marks matter",
        explanation_language="en",
        span=(start, start + len(original)),
    )


def test_summary_counts_folded_items_and_names_their_categories():
    c = _with_more(
        [_item("unos manzana", "unas manzanas")],
        [_minor("compré", "compre"), _minor("Ayer", "Ayer,", "punctuation")],
    )

    assert render.format_summary(c, 2) == (
        "  ✎ 1 error, +2 more (accents, punctuation) · /review 2"
    )


def test_summary_with_only_folded_items_points_at_review_more():
    c = _with_more(more=[_minor("compré", "compre")])

    assert render.format_summary(c, 1) == "  ✎ 1 more (accents) · /review-more 1"
    assert render.format_summary(c) == "  ✎ 1 more (accents) · /review-more"


def test_only_folded_items_is_not_reported_as_looking_good():
    c = _with_more(more=[_minor("compré", "compre")], corrected="Ayer yo fui al mercado.")

    assert "looks good" not in render.format_summary(c, 1)
    assert "Looks good" not in render.format_corrections(c)


def test_format_corrections_leaves_folded_items_out_and_more_hint_points_to_them():
    c = _with_more([_item("unos manzana", "unas manzanas")], [_minor("compré", "compre")])

    out = render.format_corrections(c)

    assert '"compré"' not in out
    assert render.format_more_hint(c, 3) == "  +1 more (accents) · /review-more 3"
    assert render.format_more_hint(_corrections([_item("yo fui", "fui")]), 1) == ""


def test_format_more_lists_folded_notes_with_marked_spans_and_corrected_text():
    c = _with_more(
        [_item("unos manzana", "unas manzanas")],
        [_minor("compré", "compre")],
        corrected="Ayer yo fui al mercado y compre unas manzanas.",
    )

    out = render.format_more(c)

    assert "[compré]" in out and "[unos manzana]" not in out
    assert '"compré" → "compre"' in out
    assert "accents · error" in out
    assert "→ Ayer yo fui al mercado y compre unas manzanas." in out
    assert render.format_more(_corrections()) == "  Nothing more to show."


def test_review_more_selects_the_folded_list_and_review_adds_the_hint():
    c = _with_more([_item("unos manzana", "unas manzanas")], [_minor("compré", "compre")])
    history = [Message(role="user", content=TEXT, corrections=c)]

    assert '"compré"' in _review(history, "", color=False, more=True)
    reviewed = _review(history, "", color=False)
    assert reviewed.endswith("+1 more (accents) · /review-more 1")
    assert _review(history, "x", color=False, more=True) == "Usage: /review-more [N]"
