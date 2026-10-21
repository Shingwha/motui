"""Text measurement and wrapping contracts: visible_width, wrap_text,
fit_text, ellipsize_tail and the Text component.

The measure is the toolkit's single width truth: a grapheme cluster counts
its base cell, continuation characters count nothing, and a tab counts one
column.  Wrapping, fitting and truncation all share it, so no rendered row
overflows the width it was asked to fit in.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.kernel import Text
from motui.kernel.lines import Line, Segment
from motui.kernel.style import Style

ACCENT = Style(fg="#58a6ff", bold=True)
DIM = Style(dim=True)
from motui.kernel.text import (
    ellipsize_tail,
    fit_text,
    index_bounds_at_columns,
    visible_width,
    wrap_text,
)
from motui.kernel.theme import DEFAULT_THEME
from tests.testing import texts

#: Inputs whose whole-string measure disagrees with a per-character sum:
#: VS16-widened bases, a ZWJ family, combining marks, wide CJK and tabs.
NASTY = [
    "\u26a0\ufe0f Blocked",
    "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466",
    "e\u0301e\u0301e\u0301",
    "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8",
    "a\tb\tc",
    "\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f end",
    "caf\u00e9 \U0001F600 \u4e2d\u6587",
    "x\U0001F468\u200D\U0001F469\u200Dy",
]


def test_visible_width_counts_ascii_wide_and_emoji_cells():
    assert visible_width("") == 0
    assert visible_width("abc") == 3
    assert visible_width("\u4e2d\u6587") == 4
    assert visible_width("a\u4e2db") == 4
    assert visible_width("\U0001F389") == 2


def test_visible_width_drops_controls_and_counts_a_tab_as_one_column():
    assert visible_width("a\x07b") == 2
    assert visible_width("\x1b[31m") == 4
    assert visible_width("a\tb") == 3


def test_visible_width_measures_zwj_skin_tone_and_flag_clusters():
    family = "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"
    assert visible_width(family) == 2
    assert visible_width("\U0001F9D1\U0001F3FD\u200D\U0001F4BB") == 2
    assert visible_width("\U0001F3F3\uFE0F\u200D\U0001F308") == 2
    assert visible_width("\U0001F44B\U0001F3FD") == 2
    assert visible_width("\U0001F1EF\U0001F1F5") == 2


def test_combining_marks_ride_the_base_cluster():
    assert visible_width("e\u0301") == 1
    assert visible_width("1\u20e3") == 1
    assert visible_width("\u4e2d\u0301") == 2
    assert visible_width("e\u0301\u0302\u0303") == 1
    assert visible_width("\u0301") == 0
    assert visible_width("\u0301abc") == 3


def test_variation_selectors_widen_or_keep_the_base_cell():
    assert visible_width("\u2764\ufe0f") == 2
    assert visible_width("\u2764\ufe0e") == 1
    assert visible_width("\u2764\U000E0100") == 1
    assert visible_width("\u2764\ufe0f\ufe0f") == 2
    assert visible_width("\ufe0fabc") == 3
    assert visible_width("\U000E0100") == 0


def test_the_zero_width_joiner_joins_the_next_cell():
    assert visible_width("a\u200db") == 1
    assert visible_width("a\u200d") == 1
    assert visible_width("\u200dabc") == 3
    assert visible_width("a\u200d\u200db") == 1


def test_regional_indicators_pair_into_one_flag_cell():
    assert visible_width("\U0001F1EF") == 2
    assert visible_width("\U0001F1EF\U0001F1F5") == 2
    assert visible_width("\U0001F1EF\U0001F1F5\U0001F1E8") == 4
    assert visible_width("\U0001F1EF\U0001F1F5\U0001F1E8\U0001F1F3") == 4


@pytest.mark.parametrize(
    "text, expected",
    [
        ("\u26a0\ufe0f Blocked", 10),
        ("\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466", 2),
        ("e\u0301e\u0301e\u0301", 3),
        ("\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8", 14),
        ("a\tb\tc", 5),
        ("caf\u00e9 \U0001F600 \u4e2d\u6587", 12),
    ],
)
def test_visible_width_measures_the_mixed_corpus(text: str, expected: int):
    assert visible_width(text) == expected


def test_wrap_text_empty_and_nonpositive_width():
    assert wrap_text("", 10) == [""]
    assert wrap_text("anything", 0) == [""]
    assert wrap_text("anything", -3) == [""]


def test_wrap_text_breaks_at_spaces_and_drops_break_whitespace():
    assert wrap_text("hello world", 5) == ["hello", "world"]
    assert wrap_text("aa bb cc", 5) == ["aa bb", "cc"]
    assert wrap_text("  ab  ", 10) == ["ab"]
    assert wrap_text("a b", 3) == ["a b"]


def test_wrap_text_hard_breaks_overlong_words():
    assert wrap_text("abcdef", 3) == ["abc", "def"]
    assert wrap_text("abcdefg", 3) == ["abc", "def", "g"]


def test_wrap_text_hard_breaks_wide_cells_at_width_one():
    assert wrap_text("\u65e5\u672c\u8a9e", 4) == ["\u65e5\u672c", "\u8a9e"]
    assert wrap_text("\u65e5\u672c\u8a9eabc", 1) == [
        "\u65e5",
        "\u672c",
        "\u8a9e",
        "a",
        "b",
        "c",
    ]


def test_wrap_text_normalizes_tabs_to_breakable_spaces():
    assert wrap_text("a\tb", 10) == ["a b"]
    assert wrap_text("ab\tcd", 3) == ["ab", "cd"]


def test_wrap_text_rows_reassemble_the_words():
    for text in NASTY:
        for width in range(2, 13):
            rows = wrap_text(text, width)
            joined = "".join(rows).replace(" ", "")
            assert joined == text.replace(" ", "").replace("\t", ""), (text, width)
            assert all(rows)


def test_fit_text_returns_a_prefix_within_budget():
    for text in NASTY:
        for budget in range(len(text) + 3):
            result = fit_text(text, budget)
            assert text.startswith(result)
            assert visible_width(result) <= budget


def test_fit_text_is_greedy_and_keeps_clusters_whole():
    for text in NASTY:
        for budget in range(len(text) + 3):
            result = fit_text(text, budget)
            if len(result) < len(text):
                assert visible_width(text[: len(result) + 1]) > budget
    assert fit_text("e\u0301x", 1) == "e\u0301"
    assert fit_text("\u2764\U000E0100x", 1) == "\u2764\U000E0100"
    assert fit_text("\u4e2d\u0301", 1) == ""


def test_fit_text_returns_the_whole_text_or_nothing():
    assert fit_text("abcdef", 6) == "abcdef"
    assert fit_text("abcdef", 99) == "abcdef"
    assert fit_text("\u26a0\ufe0f Blocked", 10) == "\u26a0\ufe0f Blocked"
    assert fit_text("abcdef", 0) == ""
    assert fit_text("abcdef", -3) == ""


def test_ellipsize_tail_keeps_its_documented_shape():
    assert ellipsize_tail("abc", 3) == "abc"
    assert ellipsize_tail("abcdef", 4) == "abc\u2026"
    assert ellipsize_tail("abcdef", 1) == "\u2026"
    assert ellipsize_tail("abcdef", 0) == ""
    assert ellipsize_tail("abcdef", -5) == ""
    assert ellipsize_tail("\u65e5\u672c\u8a9e", 4) == "\u65e5\u2026"


def test_ellipsize_tail_never_overflows_the_budget():
    for text in NASTY:
        for budget in range(len(text) + 3):
            assert visible_width(ellipsize_tail(text, budget)) <= budget
    assert ellipsize_tail("\u26a0\ufe0f Blocked", 4) == "\u26a0\ufe0f \u2026"


def test_index_bounds_snap_columns_down_to_cluster_starts():
    assert index_bounds_at_columns("a\u754cb", 0, 1, 2, 3, 4) == (0, 1, 1, 2, 3)
    assert index_bounds_at_columns("a\u26a0\ufe0fB", 2) == (1,)
    assert index_bounds_at_columns("abc", -3, 0, 99) == (0, 0, 3)
    assert index_bounds_at_columns("", 5) == (0,)
    assert index_bounds_at_columns("abc") == ()


def test_text_renders_verbatim_lines_and_keeps_blank_rows():
    assert texts(Text("hello"), 80) == ["hello"]
    assert texts(Text("a\n\nb"), 80) == ["a", "", "b"]


def test_text_wraps_lines_at_the_width():
    rows = Text("hello world").render(5)
    assert [row.text for row in rows] == ["hello", "world"]
    assert all(row.width <= 5 for row in rows)


def test_text_applies_its_style_to_every_row():
    rows = Text("ab\ncd", style=DIM).render(10)
    assert all(segment.style == DIM for row in rows for segment in row.segments)


def test_text_is_mutable_for_streaming():
    stream = Text("one ")
    assert texts(stream, 80) == ["one"]
    stream.text += "two"
    assert texts(stream, 80) == ["one two"]


def test_text_degrades_at_width_one_and_zero():
    assert texts(Text("hi"), 1) == ["h", "i"]
    assert texts(Text("hi"), 0) == [""]


class SpanText(Text):
    """Text whose row carries one inline span, the documented subclass seam."""

    def _rows_for(self, width: int) -> list[Line]:
        return [
            Line(
                [
                    Segment("see ", Style()),
                    Segment(
                        "docs",
                        ACCENT,
                        link="https://example.invalid",
                        action="open",
                    ),
                    Segment(" now", Style()),
                ]
            ).fit(width)
        ]


def test_text_inline_spans_answer_a_click_once():
    field = SpanText()
    field.render(40)
    assert field.click(0, 0) is False
    assert field.click(0, 12) is False
    assert field.click(0, 5) is True
    assert field.take_result() == "open"
    assert field.take_result() is None


def test_text_hover_merges_the_themed_band_over_the_span():
    band = Style(fg="#ff00ff", reverse=True)
    field = SpanText(theme=replace(DEFAULT_THEME, surfaces=replace(DEFAULT_THEME.surfaces, hover=band)))
    field.render(40)
    assert field.hover_at(0, 5) is True
    hovered = field.render(40)[0]
    assert hovered.segments[1].style == ACCENT.merge(band)
    assert hovered.segments[1].text == "docs"
    assert field.hover_at(0, 5) is False
    assert field.hover_at(-1, -1) is True


def test_plain_text_rows_decline_clicks_and_hovers():
    field = Text("hello")
    field.render(10)
    assert field.hover_at(0, 0) is False
    assert field.click(0, 0) is False
    assert field.take_result() is None
