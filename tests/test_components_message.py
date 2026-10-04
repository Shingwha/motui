"""Tests for mocode_tui.components.message (Message)."""

import pytest

from mocode_tui.components.message import Message, THINKING, USER_BG
from mocode_tui.lines import Line, Segment
from mocode_tui.style import MUTED, Style

_ROLES = ("user", "assistant", "thinking")


# --- shapes per role -----------------------------------------------------------


def test_user_band_pads_both_sides_with_styled_fill():
    rows = Message("user", "hi").render(10)
    assert rows == [
        Line((Segment(" ", USER_BG), Segment("hi", USER_BG), Segment("       ", USER_BG)))
    ]
    assert rows[0].text == " hi       "
    assert rows[0].width == 10


def test_user_band_every_segment_carries_the_band_style():
    row = Message("user", "hello there").render(14)[0]
    assert row.segments  # not an empty row
    assert all(seg.style == USER_BG for seg in row.segments)
    assert row.width == 14


def test_assistant_rows_are_plain_and_unindented():
    assert Message("assistant", "hi").render(10) == [Line.from_text("hi")]
    assert Message("assistant", "a\nb").render(10) == [Line.from_text("a"), Line.from_text("b")]


def test_assistant_keeps_blank_lines_as_blank_rows():
    rows = Message("assistant", "a\n\nb").render(6)
    assert rows == [Line.from_text("a"), Line(), Line.from_text("b")]


def test_thinking_is_dim_gray_italic():
    row = Message("thinking", "hmm").render(20)[0]
    assert row.text == "hmm"
    (style,) = {seg.style for seg in row.segments}
    assert style == MUTED.merge(Style(italic=True)) == THINKING
    assert style.fg == MUTED.fg and style.italic is True  # palette-agnostic


def test_unknown_role_degrades_to_assistant():
    assert Message("system", "hello").render(20) == Message("assistant", "hello").render(20)
    assert Message("", "hello").render(20) == Message("assistant", "hello").render(20)


# --- style override ---------------------------------------------------------------


def test_style_overrides_the_user_band():
    rows = Message("user", "hi", style=Style(bg="red")).render(6)
    assert rows[0].text == " hi   "
    assert all(seg.style == Style(bg="red") for seg in rows[0].segments)


def test_style_overrides_assistant_and_thinking():
    assert Message("assistant", "hi", style=Style(fg="yellow")).render(8) == [
        Line.from_text("hi", Style(fg="yellow"))
    ]
    assert Message("thinking", "hi", style=Style(fg="yellow")).render(8) == [
        Line.from_text("hi", Style(fg="yellow"))
    ]


# --- wrapping ---------------------------------------------------------------------


def test_user_text_area_is_width_minus_two():
    rows = Message("user", "aaa bbb ccc").render(9)
    assert [row.text for row in rows] == [" aaa bbb ", " ccc     "]
    assert [row.width for row in rows] == [9, 9]


def test_assistant_wraps_at_width():
    assert Message("assistant", "aaa bbb ccc").render(7) == [
        Line.from_text("aaa bbb"),
        Line.from_text("ccc"),
    ]


def test_user_band_wraps_cjk_at_the_inner_width():
    rows = Message("user", "日本語").render(7)
    assert [row.text for row in rows] == [" 日本  ", " 語    "]
    assert all(row.width == 7 for row in rows)


def test_wide_text_fills_the_band_exactly():
    rows = Message("user", "日本語のメッセージ").render(20)
    assert [row.text for row in rows] == [" 日本語のメッセージ "]
    assert rows[0].width == 20


# --- degenerate widths --------------------------------------------------------------


@pytest.mark.parametrize("role", _ROLES)
def test_zero_width_renders_one_empty_row(role):
    assert Message(role, "hello").render(0) == [Line()]


@pytest.mark.parametrize("role", _ROLES)
def test_width_one_does_not_crash_and_stays_within_width(role):
    rows = Message(role, "hello").render(1)
    assert rows
    assert all(row.width <= 1 for row in rows)


# --- empty text -----------------------------------------------------------------------


def test_empty_text_user_renders_a_bare_band():
    rows = Message("user", "").render(6)
    assert rows == [Line((Segment(" ", USER_BG), Segment("     ", USER_BG)))]
    assert all(seg.style == USER_BG for seg in rows[0].segments)


@pytest.mark.parametrize("role", ["assistant", "thinking"])
def test_empty_text_other_roles_render_one_empty_row(role):
    assert Message(role, "").render(6) == [Line()]


# --- the width invariant ---------------------------------------------------------------


@pytest.mark.parametrize("role", _ROLES)
@pytest.mark.parametrize("width", range(0, 15))
def test_rows_never_exceed_width(role, width):
    rows = Message(role, "hello 日本語 world, a longer tail").render(width)
    assert rows
    assert all(row.width <= width for row in rows)


@pytest.mark.parametrize("width", range(0, 15))
def test_lone_wide_char_band_stays_within_width(width):
    rows = Message("user", "日").render(width)
    assert rows
    assert all(row.width <= width for row in rows)
