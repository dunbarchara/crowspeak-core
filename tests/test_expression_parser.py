import logging

import pytest

from crowspeak_engine.expression import Expression, ExpressionTagParser


def run(deltas):
    p = ExpressionTagParser()
    items = []
    for d in deltas:
        items += p.feed(d)
    items += p.finish()
    return _merge(items)


def _merge(items):
    out = []
    for i in items:
        if isinstance(i, str) and out and isinstance(out[-1], str):
            out[-1] += i
        else:
            out.append(i)
    return out


def test_no_tag_is_plain_text():
    assert run(["Hello ", "world"]) == ["Hello world"]


def test_leading_tag():
    assert run(["[happy] Bonjour!"]) == [Expression("happy"), "Bonjour!"]


def test_mid_reply_tag_swallows_following_space_only():
    assert run(["Bonjour! [thinking] Et toi ?"]) == [
        "Bonjour! ",
        Expression("thinking"),
        "Et toi ?",
    ]


def test_tag_is_case_and_space_insensitive():
    assert run(["[ Happy ]hi"]) == [Expression("happy"), "hi"]


@pytest.mark.parametrize(
    "text", ["[happy] Bonjour! [thinking] Et toi ?", "a [sad] b [angry] c", "[1] [x y] [] ok"]
)
def test_char_by_char_equals_single_feed(text):
    assert run(list(text)) == run([text])


def test_tag_split_across_deltas():
    assert run(["[ha", "pp", "y", "] hi"]) == [Expression("happy"), "hi"]


def test_whitespace_swallow_spans_deltas():
    assert run(["[happy]", " ", " hi"]) == [Expression("happy"), "hi"]


def test_unknown_word_tag_is_dropped_and_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="crowspeak_engine.expression"):
        assert run(["[ecstatic] hi"]) == ["hi"]
    assert "ecstatic" in caplog.text


def test_non_word_brackets_stay_text():
    assert run(["see [1] and [] and [a b]"]) == ["see [1] and [] and [a b]"]


def test_unclosed_bracket_flushed_after_max_len():
    text = "[" + "x" * 30 + " tail"
    assert run([text]) == [text]


def test_unclosed_bracket_flushed_at_finish():
    assert run(["hi [hap"]) == ["hi [hap"]


def test_nested_open_bracket_restarts():
    assert run(["[[happy] hi"]) == ["[", Expression("happy"), "hi"]
