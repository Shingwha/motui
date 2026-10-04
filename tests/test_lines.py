"""Tests for mocode_tui.lines."""

import pytest

from mocode_tui.lines import ELLIPSIS, Line, Segment, wrap_line
from mocode_tui.style import ACCENT, MUTED, RESET, Style, SUCCESS


# --- Segment / Line basics -------------------------------------------------


def test_segment_defaults_and_frozen():
    seg = Segment("hi")
    assert seg.text == "hi"
    assert seg.style == Style()
    with pytest.raises(Exception):
        seg.text = "no"  # type: ignore[misc]


def test_empty_line_views():
    line = Line()
    assert line.segments == ()
    assert line.text == ""
    assert line.width == 0
    assert line.styled() == ""
    assert line == Line.from_text("")


def test_from_text_views():
    line = Line.from_text("hello")
    assert line.text == "hello"
    assert line.width == 5
    assert line.segments == (Segment("hello", Style()),)
    assert line.styled() == "hello\x1b[0m"


def test_styled_shape_with_styles():
    line = Line((Segment("a", ACCENT), Segment("b", MUTED)))
    # Palette-agnostic: the SGR bytes come from the semantic constants, so a
    # palette upgrade never reddens this assertion.
    assert line.styled() == ACCENT.prefix() + "a" + MUTED.prefix() + "b" + RESET
    assert line.width == 2
    assert line.text == "ab"


def test_width_sums_segments_with_cjk():
    line = Line((Segment("ab", Style()), Segment("日本", MUTED)))
    assert line.width == 6


def test_line_is_immutable():
    line = Line.from_text("x")
    with pytest.raises(AttributeError):
        line._segments = ()  # type: ignore[misc]


# --- fit -------------------------------------------------------------------


def test_fit_returns_self_when_it_fits():
    line = Line.from_text("abc")
    assert line.fit(3) is line
    assert line.fit(10) is line


def test_fit_truncates_with_marker():
    line = Line.from_text("abcdef")
    fitted = line.fit(4)
    assert fitted.text == "abc…"
    assert fitted.width == 4
    assert fitted.segments == (Segment("abc…", Style()),)


def test_fit_degenerate_widths():
    line = Line.from_text("abc")
    assert line.fit(0).text == ""
    assert line.fit(-2).text == ""
    assert line.fit(1).text == "…"


def test_fit_wide_chars_stay_within_width():
    fitted = Line.from_text("日本語").fit(4)
    assert fitted.text == "日…"
    assert fitted.width <= 4


def test_fit_keeps_style_of_truncated_segment():
    line = Line((Segment("abcdef", ACCENT),))
    fitted = line.fit(4)
    assert fitted.segments == (Segment("abc…", ACCENT),)
    assert fitted.styled() == ACCENT.prefix() + "abc…" + RESET


def test_fit_across_segments():
    line = Line((Segment("abc", ACCENT), Segment("def", MUTED)))
    fitted = line.fit(4)
    assert fitted.text == "abc…"
    assert fitted.segments == (Segment("abc…", ACCENT),)


# --- pad_to ----------------------------------------------------------------


def test_pad_to_appends_plain_spaces():
    line = Line.from_text("ab")
    padded = line.pad_to(5)
    assert padded.text == "ab   "
    assert padded.width == 5
    assert padded.segments == (Segment("ab", Style()), Segment("   ", Style()))


def test_pad_to_returns_self_when_wide_enough():
    line = Line.from_text("ab")
    assert line.pad_to(2) is line
    assert line.pad_to(1) is line
    assert line.pad_to(0) is line
    assert line.pad_to(-4) is line


def test_pad_to_preserves_existing_styles():
    line = Line((Segment("a", ACCENT),))
    padded = line.pad_to(3)
    assert padded.segments == (Segment("a", ACCENT), Segment("  ", Style()))


# --- filled -----------------------------------------------------------------


def test_filled_degenerate_widths_yield_empty_line():
    assert Line.filled(0) == Line()
    assert Line.filled(-4) == Line()


def test_filled_is_one_spaces_segment_of_exact_width():
    line = Line.filled(5)
    assert line.text == "     "
    assert line.width == 5
    assert line.segments == (Segment("     ", Style()),)


def test_filled_carries_style_in_its_single_segment():
    line = Line.filled(3, SUCCESS)
    assert line.segments == (Segment("   ", SUCCESS),)
    assert line.styled() == SUCCESS.prefix() + "   " + RESET


# --- __add__ ---------------------------------------------------------------


def test_add_concatenates_text_and_segments():
    combined = Line.from_text("ab") + Line.from_text("cd")
    assert combined.text == "abcd"
    assert combined.width == 4


def test_add_keeps_segment_styles():
    combined = Line((Segment("a", ACCENT),)) + Line((Segment("b", MUTED),))
    assert combined.segments == (Segment("a", ACCENT), Segment("b", MUTED))


def test_add_with_non_line_raises_type_error():
    with pytest.raises(TypeError):
        Line.from_text("a") + "b"  # type: ignore[operator]


# --- equality / hash -------------------------------------------------------


def test_equality_and_hash_by_segments():
    assert Line.from_text("a") == Line.from_text("a")
    assert hash(Line.from_text("a")) == hash(Line.from_text("a"))
    assert Line.from_text("a") != Line.from_text("b")
    assert Line.from_text("a") != Line.from_text("a", ACCENT)
    assert Line.from_text("a") != "a"
    assert len({Line.from_text("a"), Line.from_text("a"), Line.from_text("b")}) == 2


# --- wrap_line -------------------------------------------------------------


def test_wrap_line_empty_and_degenerate_widths():
    assert wrap_line(Line(), 10) == [Line()]
    assert wrap_line(Line.from_text("abc"), 0) == [Line()]
    assert wrap_line(Line.from_text("abc"), -1) == [Line()]


def test_wrap_line_fitting_line_is_one_row():
    line = Line.from_text("hello world")
    assert wrap_line(line, 20) == [line]


def test_wrap_line_breaks_at_spaces():
    rows = wrap_line(Line.from_text("hello world"), 5)
    assert rows == [Line.from_text("hello"), Line.from_text("world")]


def test_wrap_line_keeps_style_across_breaks():
    line = Line((Segment("hello world", ACCENT),))
    rows = wrap_line(line, 5)
    assert rows == [
        Line((Segment("hello", ACCENT),)),
        Line((Segment("world", ACCENT),)),
    ]


def test_wrap_line_splits_mixed_segments_at_word_boundaries():
    line = Line((Segment("ab ", ACCENT), Segment("cd ef", MUTED)))
    rows = wrap_line(line, 4)
    assert rows == [
        Line((Segment("ab", ACCENT),)),
        Line((Segment("cd", MUTED),)),
        Line((Segment("ef", MUTED),)),
    ]


def test_wrap_line_hard_breaks_over_long_words():
    rows = wrap_line(Line.from_text("abcdef"), 3)
    assert rows == [Line.from_text("abc"), Line.from_text("def")]


def test_wrap_line_hard_breaks_cjk_runs():
    rows = wrap_line(Line.from_text("日本語"), 5)
    assert rows == [Line.from_text("日本"), Line.from_text("語")]


def test_wrap_line_width_one_terminates_for_wide_chars():
    rows = wrap_line(Line.from_text("日本"), 1)
    assert rows == [Line.from_text("日"), Line.from_text("本")]


def test_wrap_line_drops_break_whitespace():
    assert wrap_line(Line.from_text("  ab  "), 10) == [Line.from_text("ab")]
    assert wrap_line(Line.from_text("   "), 10) == [Line()]


def test_wrap_line_tab_becomes_space():
    rows = wrap_line(Line.from_text("a\tb"), 10)
    assert rows == [Line.from_text("a b")]
    assert rows[0].width == 3


def test_wrap_line_rows_respect_width():
    line = Line((Segment("the quick ", ACCENT), Segment("brown fox", MUTED)))
    rows = wrap_line(line, 10)
    assert [row.text for row in rows] == ["the quick", "brown fox"]
    for row in rows:
        assert row.width <= 10


def test_ellipsis_constant():
    assert ELLIPSIS == "…"
