"""Tests for mocode_tui.text.

Contracts (the module docstring + DESIGN/COMPONENTS): ``visible_width`` is the
single width truth (wcwidth, CJK wide, empty = 0); ``wrap_text`` breaks at
spaces, hard-breaks over-long words and CJK runs, keeps a wide character on
its own row when narrower than the width, and yields ``[""]`` for empty input
or ``width <= 0``; ``ellipsize_tail`` marks the cut with a one-column ``…``.
"""

from mocode_tui.text import ellipsize_tail, terminal_size, visible_width, wrap_text


def test_visible_width_empty_ascii_and_wide():
    assert visible_width("") == 0
    assert visible_width("abc") == 3
    assert visible_width("中文") == 4  # wide characters count two columns
    assert visible_width("a中b") == 4
    assert visible_width("\U0001f389") == 2  # emoji


def test_visible_width_non_printable_and_tab():
    assert visible_width("a\x07b") == 2  # the bell contributes nothing
    assert visible_width("\x1b[31m") == 4  # escape dropped, "[31m" counted
    assert visible_width("a\tb") == 3  # a tab counts as exactly one column


def test_ellipsize_tail():
    assert ellipsize_tail("abc", 3) == "abc"  # fits: unchanged
    assert ellipsize_tail("", 3) == ""
    result = ellipsize_tail("abcdef", 4)
    assert result == "abc…" and visible_width(result) == 4
    assert ellipsize_tail("abcdef", 1) == "…"
    assert ellipsize_tail("abcdef", 0) == ""
    assert ellipsize_tail("abcdef", -5) == ""
    assert ellipsize_tail("日本語", 4) == "日…"  # wide chars stay within the budget


def test_wrap_text_empty_and_degenerate_widths():
    assert wrap_text("", 10) == [""]
    assert wrap_text("anything", 0) == [""]
    assert wrap_text("anything", -3) == [""]


def test_wrap_text_breaks_at_spaces():
    assert wrap_text("hello world", 5) == ["hello", "world"]
    assert wrap_text("aa bb cc", 5) == ["aa bb", "cc"]
    assert wrap_text("  ab  ", 10) == ["ab"]  # break whitespace is dropped


def test_wrap_text_hard_breaks_over_long_words_and_cjk():
    assert wrap_text("abcdef", 3) == ["abc", "def"]
    assert wrap_text("日本語", 4) == ["日本", "語"]
    # width 1 terminates: a wide character owns its own row.
    assert wrap_text("日本語abc", 1) == ["日", "本", "語", "a", "b", "c"]


def test_wrap_text_tabs_are_one_space_and_breakable():
    assert wrap_text("a\tb", 10) == ["a b"]
    assert wrap_text("ab\tcd", 3) == ["ab", "cd"]


def test_terminal_size_reports_positive_columns_and_rows():
    cols, rows = terminal_size()
    assert isinstance(cols, int) and cols > 0
    assert isinstance(rows, int) and rows > 0
