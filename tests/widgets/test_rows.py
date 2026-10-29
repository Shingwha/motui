"""StatusLine, ShortcutBar and Notice: the one-row furniture."""

from dataclasses import replace

import pytest

from motui.kernel.glyphs import GLYPHS
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import Notice, ShortcutBar, StatusLine

from tests.testing import texts


def test_status_line_puts_the_left_at_the_start_and_the_right_near_the_end():
    line = StatusLine(left=["left"], right=["right"])
    assert texts(line, 20) == ["left" + " " * 10 + "right"]


@pytest.mark.parametrize("width", [5])
def test_an_over_wide_status_line_keeps_the_left_and_cuts_the_right_tail(width):
    row = texts(StatusLine(left=["left"], right=["right"]), width)[0]
    assert row.startswith("left") and row.endswith("\u2026")
    assert len(row) == width


def test_explicit_element_styles_beat_the_gutter_and_theme():
    accent = Style(fg="#abcdef")
    faint = replace(DEFAULT_THEME.text, faint=Style(bold=True))
    line = StatusLine(left=[("L", accent), "x"], styles=Styles(text=faint))
    segments = line.render(Constraints(width=10))[0].segments
    assert segments[0].text == "L" and segments[0].style == accent
    assert segments[1].text.startswith("x")
    assert segments[1].style == faint.faint


def test_shortcut_bar_renders_key_label_pairs_with_a_separator():
    bar = ShortcutBar([("c-n", "next"), ("c-p", "prev")])
    assert texts(bar, 40) == ["c-n next \u00b7 c-p prev"]
    segments = bar.render(Constraints(width=40))[0].segments
    assert segments[0].text == "c-n" and segments[0].style == DEFAULT_THEME.content.accent
    assert segments[1].text == " next" and segments[1].style == DEFAULT_THEME.text.faint
    custom = ShortcutBar(
        [("a", "b"), ("c", "d")],
        glyphs=replace(GLYPHS, separator=" | "),
    )
    assert texts(custom, 20) == ["a b | c d"]
    assert texts(ShortcutBar([]), 20) == [""]


@pytest.mark.parametrize(
    "level, expected",
    [
        ("info", "i hello"),
        ("success", "\u2713 hello"),
        ("warn", "! hello"),
        ("error", "\u00d7 hello"),
        ("odd", "i hello"),
    ],
)
def test_a_notice_leads_with_its_level_glyph(level, expected):
    assert texts(Notice("hello", level=level), 30) == [expected]


def test_a_leveled_notice_prefix_carries_the_level_style():
    row = Notice("bad", level="error").render(Constraints(width=20))[0]
    assert row.segments[0].text == "\u00d7 "
    assert row.segments[0].style == DEFAULT_THEME.status.danger
    success = Notice("ok", level="success").render(Constraints(width=20))[0]
    assert success.segments[0].text == "\u2713 "
    assert success.segments[0].style == DEFAULT_THEME.status.success


def test_a_narrow_notice_truncates_instead_of_wrapping():
    row = Notice("a long warning", level="warn").render(Constraints(width=8))[0]
    assert row.width == 8 and row.text.endswith("\u2026")
