"""Tests for mocode_tui.components.text (Text / Markdown)."""

from mocode_tui.components.text import Markdown, Text
from mocode_tui.lines import Line, Segment
from mocode_tui.style import ACCENT, CODE, DIM, MUTED, NONE, Style


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


# --- Markdown: block elements ------------------------------------------------


def test_markdown_empty_renders_no_rows():
    assert Markdown("").render(40) == []


def test_markdown_paragraph_joins_soft_breaks():
    rows = Markdown("line one\nline two").render(80)
    assert [row.text for row in rows] == ["line one line two"]


def test_markdown_paragraph_wraps():
    rows = Markdown("the quick brown fox").render(9)
    assert [row.text for row in rows] == ["the quick", "brown fox"]


def test_markdown_heading_strips_markers_and_styles():
    rows = Markdown("## Title").render(40)
    assert [row.text for row in rows] == ["Title"]
    assert rows[0].segments[0].style == ACCENT.merge(Style(underline=True))


def test_markdown_heading_levels_share_accent_family():
    styles = [
        Markdown(f"{'#' * level} H").render(40)[0].segments[0].style for level in (1, 2, 3, 4)
    ]
    # Palette-agnostic: the levels are pinned through the semantic constants
    # and attribute shapes, so a palette upgrade never reddens these.
    assert styles[0] == ACCENT  # h1: the accent constant
    assert styles[1] == ACCENT.merge(Style(underline=True))  # h2: accent + underline
    assert not styles[2].bold and not styles[2].dim  # h3: plain
    assert styles[3].dim  # h4: dim


def test_markdown_fenced_code_block():
    rows = Markdown("```\nx = 1\n```").render(40)
    assert [row.text for row in rows] == ["x = 1"]
    assert rows[0].segments == (Segment("x = 1", CODE),)


def test_markdown_fenced_code_without_close_runs_to_end():
    rows = Markdown("```\nunclosed").render(40)
    assert [row.text for row in rows] == ["unclosed"]


def test_markdown_unordered_list_uses_bullet_marker():
    rows = Markdown("- one\n- two").render(40)
    assert [row.text for row in rows] == ["\u2022 one", "\u2022 two"]
    assert rows[0].segments[0] == Segment("\u2022 ", MUTED)


def test_markdown_ordered_list_keeps_numbers():
    rows = Markdown("1. first\n2. second").render(40)
    assert [row.text for row in rows] == ["1. first", "2. second"]


def test_markdown_unknown_syntax_degrades_to_paragraph():
    rows = Markdown("| a | b |\n> quoted").render(80)
    assert [row.text for row in rows] == ["| a | b | > quoted"]


# --- Markdown: inline elements ------------------------------------------------


def test_markdown_inline_code_bold_italic():
    row = Markdown("a `code` **bold** *em*").render(80)[0]
    assert row.text == "a code bold em"
    styles = {seg.text: seg.style for seg in row.segments}
    assert styles["code"] == CODE
    assert styles["bold"] == Style(bold=True)
    assert styles["em"] == Style(italic=True)


def test_markdown_inline_markers_inside_words_stay_literal():
    row = Markdown("a*b and 2*3 and `oops").render(80)[0]
    assert row.text == "a*b and 2*3 and `oops"
    assert row.segments[0].style == NONE


def test_markdown_heading_can_wrap():
    rows = Markdown("# a very long heading indeed").render(12)
    assert all(row.width <= 12 for row in rows)
    assert "".join(row.text for row in rows).startswith("a very long")


def test_markdown_degenerate_widths_do_not_crash():
    rows = Markdown("# heading\n\n- item").render(1)
    assert all(row.width <= 1 for row in rows)
    rows0 = Markdown("para").render(0)
    assert all(row.width == 0 for row in rows0)
