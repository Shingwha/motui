"""Tests for mocode_tui.components.text (Text)."""

from mocode_tui.components.text import Text
from mocode_tui.lines import Line, Segment
from mocode_tui.style import DIM


# --- Text -------------------------------------------------------------------


def test_text_defaults_to_empty_row():
    assert Text().text == ""
    assert Text().render(40) == [Line()]


def test_text_single_line():
    assert [row.text for row in Text("hello").render(40)] == ["hello"]


def test_text_keeps_blank_lines():
    rows = Text("a\n\nb").render(10)
    assert [row.text for row in rows] == ["a", "", "b"]


def test_text_wraps_at_spaces():
    rows = Text("hello world").render(5)
    assert [row.text for row in rows] == ["hello", "world"]
    assert all(row.width <= 5 for row in rows)


def test_text_hard_breaks_long_word():
    rows = Text("abcdefgh").render(3)
    assert [row.text for row in rows] == ["abc", "def", "gh"]


def test_text_cjk_rows_stay_within_width():
    rows = Text("日本語テスト").render(4)
    assert [row.text for row in rows] == ["日本", "語テ", "スト"]
    assert [row.width for row in rows] == [4, 4, 4]


def test_text_style_applies_to_every_row():
    rows = Text("ab\ncd", style=DIM).render(10)
    assert rows[0].segments == (Segment("ab", DIM),)
    assert rows[1].segments == (Segment("cd", DIM),)


def test_text_degenerate_widths_do_not_crash():
    # width=1 hard-breaks every character (wrap_text's documented rule).
    assert [row.text for row in Text("hello").render(1)] == ["h", "e", "l", "l", "o"]
    assert Text("hello").render(0) == [Line()]
    assert Text("").render(1) == [Line()]
