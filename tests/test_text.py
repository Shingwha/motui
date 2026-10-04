"""Tests for mocode_tui.text."""

from mocode_tui.text import (
    ELLIPSIS,
    TAB_WIDTH,
    ellipsize_tail,
    terminal_size,
    visible_width,
    wrap_text,
)


# --- visible_width ---------------------------------------------------------


def test_visible_width_empty_and_ascii():
    assert visible_width("") == 0
    assert visible_width("abc") == 3
    assert visible_width("hello, world!") == 13


def test_visible_width_cjk_and_mixed():
    assert visible_width("中文") == 4
    assert visible_width("a中b") == 4
    assert visible_width("日本語") == 6


def test_visible_width_emoji():
    assert visible_width("🎉") == 2
    assert visible_width("hi🎉!") == 5


def test_visible_width_non_printable_contributes_zero():
    assert visible_width("a\x07b") == 2
    assert visible_width("\x00") == 0
    assert visible_width("\x1b[31m") == 4  # escape dropped, "[31m" counted


def test_visible_width_tab_counts_as_tab_width():
    assert visible_width("a\tb") == 1 + TAB_WIDTH + 1
    assert TAB_WIDTH == 1


# --- ellipsize_tail --------------------------------------------------------


def test_ellipsize_tail_fits_unchanged():
    assert ellipsize_tail("abc", 3) == "abc"
    assert ellipsize_tail("abc", 10) == "abc"
    assert ellipsize_tail("", 3) == ""


def test_ellipsize_tail_truncates_with_marker():
    result = ellipsize_tail("abcdef", 4)
    assert result == "abc…"
    assert visible_width(result) == 4


def test_ellipsize_tail_boundary_widths():
    assert ellipsize_tail("abcdef", 1) == "…"
    assert ellipsize_tail("abcdef", 0) == ""
    assert ellipsize_tail("abcdef", -5) == ""


def test_ellipsize_tail_wide_chars():
    result = ellipsize_tail("日本語", 4)
    assert result == "日…"
    assert visible_width(result) <= 4


# --- wrap_text -------------------------------------------------------------


def test_wrap_text_empty_and_degenerate_widths():
    assert wrap_text("", 10) == [""]
    assert wrap_text("anything", 0) == [""]
    assert wrap_text("anything", -3) == [""]


def test_wrap_text_single_word_fits():
    assert wrap_text("hello", 10) == ["hello"]
    assert wrap_text("hello", 5) == ["hello"]


def test_wrap_text_breaks_at_spaces():
    assert wrap_text("hello world", 5) == ["hello", "world"]
    assert wrap_text("aa bb cc", 5) == ["aa bb", "cc"]
    assert wrap_text("a b c", 3) == ["a b", "c"]


def test_wrap_text_hard_breaks_over_long_words():
    assert wrap_text("abcdef", 3) == ["abc", "def"]
    assert wrap_text("abcdef", 4) == ["abcd", "ef"]


def test_wrap_text_hard_breaks_cjk_runs():
    assert wrap_text("日本語", 5) == ["日本", "語"]
    assert wrap_text("日本語", 4) == ["日本", "語"]


def test_wrap_text_width_one_terminates_for_wide_chars():
    assert wrap_text("abc", 1) == ["a", "b", "c"]
    assert wrap_text("日", 1) == ["日"]  # wide char owns its own row
    assert wrap_text("日本", 1) == ["日", "本"]
    assert wrap_text("日本語abc", 1) == ["日", "本", "語", "a", "b", "c"]


def test_wrap_text_drops_break_whitespace_keeps_interior():
    assert wrap_text("  ab  ", 10) == ["ab"]
    assert wrap_text("a  b", 10) == ["a  b"]
    assert wrap_text("a  b  c", 4) == ["a  b", "c"]


def test_wrap_text_tab_is_one_space_and_breakable():
    assert wrap_text("a\tb", 10) == ["a b"]
    assert wrap_text("ab\tcd", 3) == ["ab", "cd"]


def test_wrap_text_long_cjk_input_terminates():
    text = "日" * 200
    rows = wrap_text(text, 8)
    assert len(rows) == 50  # 4 wide chars per 8-column row
    assert all(visible_width(row) == 8 for row in rows)
    assert "".join(rows) == text


def test_wrap_text_rows_respect_width_for_words():
    rows = wrap_text("the quick brown fox jumps", 10)
    for row in rows:
        assert visible_width(row) <= 10
    assert rows == [
        "the quick",
        "brown fox",
        "jumps",
    ]


# --- terminal_size ---------------------------------------------------------


def test_terminal_size_returns_positive_columns_and_rows():
    cols, rows = terminal_size()
    assert isinstance(cols, int) and cols > 0
    assert isinstance(rows, int) and rows > 0


def test_terminal_size_honours_environment_override(monkeypatch):
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "40")
    assert terminal_size() == (120, 40)


def test_ellipsis_constant_is_one_column():
    assert ELLIPSIS == "…"
    assert visible_width(ELLIPSIS) == 1
