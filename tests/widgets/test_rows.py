"""StatusLine, ShortcutBar and Notice: the one-row furniture."""

import pytest

from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Notice, ShortcutBar, StatusLine

from tests.testing import texts


def test_status_line_puts_the_left_at_the_start_and_the_right_near_the_end():
    line = StatusLine(left=["left"], right=["right"])
    assert texts(line, 20) == ["left" + " " * 10 + "right"]


@pytest.mark.parametrize("width", [5, 8])
def test_an_over_wide_status_line_keeps_the_left_and_cuts_the_right_tail(width):
    row = texts(StatusLine(left=["left"], right=["right"]), width)[0]
    assert row.startswith("left") and row.endswith("\u2026")
    assert len(row) == width


def test_explicit_element_styles_beat_the_gutter_and_theme():
    accent = Style(fg="#abcdef")
    line = StatusLine(left=[("L", accent), "x"], gap_style=Style(bold=True))
    segments = line.render(10)[0].segments
    assert segments[0].text == "L" and segments[0].style == accent
    assert segments[1].text.startswith("x")
    assert segments[1].style == DEFAULT_THEME.dim


def test_shortcut_bar_renders_key_label_pairs_with_a_separator():
    bar = ShortcutBar([("c-n", "next"), ("c-p", "prev")])
    assert texts(bar, 40) == ["c-n next \u00b7 c-p prev"]
    segments = bar.render(40)[0].segments
    assert segments[0].text == "c-n" and segments[0].style == DEFAULT_THEME.accent
    assert segments[1].text == " next" and segments[1].style == DEFAULT_THEME.dim
    custom = ShortcutBar([("a", "b"), ("c", "d")], separator=" | ")
    assert texts(custom, 20) == ["a b | c d"]
    assert texts(ShortcutBar([]), 20) == [""]


def test_a_shortcut_bar_truncates_instead_of_wrapping():
    bar = ShortcutBar([("c-n", "a very long description")])
    row = bar.render(10)[0]
    assert row.width == 10 and row.text.endswith("\u2026")


@pytest.mark.parametrize(
    "level, expected",
    [("info", "hello"), ("warn", "WARNING: hello"), ("error", "ERROR: hello"), ("odd", "hello")],
)
def test_a_notice_prefixes_its_declared_level(level, expected):
    assert texts(Notice("hello", level=level), 30) == [expected]


def test_a_leveled_notice_prefix_carries_the_level_style():
    row = Notice("bad", level="error").render(20)[0]
    assert row.segments[0].text == "ERROR: "
    assert row.segments[0].style == DEFAULT_THEME.error


def test_a_narrow_notice_truncates_instead_of_wrapping():
    row = Notice("a long warning", level="warn").render(8)[0]
    assert row.width == 8 and row.text.endswith("\u2026")
