"""Tests for mocode_tui.components.message (Message)."""

import pytest

from mocode_tui.components.message import Message, THINKING, USER_BG
from mocode_tui.lines import Line, Segment
from mocode_tui.style import MUTED, Style

_ROLES = ("user", "assistant", "thinking")


# --- shapes per role -----------------------------------------------------------


def test_user_band_pads_both_sides_with_styled_fill():
    rows = Message("user", "hi").render(10)
    assert rows[1] == Line(
        (Segment(" ", USER_BG), Segment("hi", USER_BG), Segment("       ", USER_BG))
    )
    assert rows[1].text == " hi       "
    assert rows[1].width == 10


def test_user_band_every_segment_carries_the_band_style():
    row = Message("user", "hello there").render(14)[1]
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
    assert rows[1].text == " hi   "
    assert all(seg.style == Style(bg="red") for seg in rows[1].segments)
    # The padding rows follow the override too.
    assert all(seg.style == Style(bg="red") for row in (rows[0], rows[-1]) for seg in row.segments)


def test_style_overrides_assistant_and_thinking():
    assert Message("assistant", "hi", style=Style(fg="yellow")).render(8) == [
        Line.from_text("hi", Style(fg="yellow"))
    ]
    assert Message("thinking", "hi", style=Style(fg="yellow")).render(8) == [
        Line.from_text("hi", Style(fg="yellow"))
    ]


# --- in-band padding (W11) ---------------------------------------------------------


def test_user_band_wraps_content_in_pure_band_padding_rows():
    rows = Message("user", "hi").render(10)
    assert len(rows) == 3  # top padding, content, bottom padding
    assert [row.text for row in rows] == [" " * 10, " hi       ", " " * 10]
    for row in (rows[0], rows[-1]):
        assert row.segments  # a padded row is a real row, not an empty one
        assert all(seg.style == USER_BG for seg in row.segments)
        assert row.width == 10


def test_user_padding_rows_carry_one_band_styled_segment_each():
    rows = Message("user", "hi").render(10)
    assert rows[0].segments == (Segment(" " * 10, USER_BG),)
    assert rows[-1].segments == (Segment(" " * 10, USER_BG),)


def test_assistant_and_thinking_have_no_padding_rows():
    assert len(Message("assistant", "hi").render(10)) == 1
    assert len(Message("thinking", "hi").render(10)) == 1
    assert Message("assistant", "a\nb").render(10) == [Line.from_text("a"), Line.from_text("b")]


def test_user_padding_survives_every_degenerate_width():
    for width in range(0, 4):
        rows = Message("user", "hello").render(width)
        assert len(rows) >= 3  # the two padding rows always come out
        assert all(row.width <= width for row in rows)
        for row in (rows[0], rows[-1]):  # first and last stay pure band rows
            assert all(seg.style == USER_BG for seg in row.segments)
    assert Message("user", "hello").render(0) == [Line()] * 3


# --- wrapping ---------------------------------------------------------------------


def test_user_text_area_is_width_minus_two():
    rows = Message("user", "aaa bbb ccc").render(9)
    assert [row.text for row in rows] == [" " * 9, " aaa bbb ", " ccc     ", " " * 9]
    assert [row.width for row in rows] == [9, 9, 9, 9]


def test_assistant_wraps_at_width():
    assert Message("assistant", "aaa bbb ccc").render(7) == [
        Line.from_text("aaa bbb"),
        Line.from_text("ccc"),
    ]


def test_user_band_wraps_cjk_at_the_inner_width():
    rows = Message("user", "日本語").render(7)
    assert [row.text for row in rows] == [" " * 7, " 日本  ", " 語    ", " " * 7]
    assert all(row.width == 7 for row in rows)


def test_wide_text_fills_the_band_exactly():
    rows = Message("user", "日本語のメッセージ").render(20)
    assert [row.text for row in rows] == [" " * 20, " 日本語のメッセージ ", " " * 20]
    assert all(row.width == 20 for row in rows)


# --- degenerate widths --------------------------------------------------------------


@pytest.mark.parametrize("role", _ROLES)
def test_zero_width_renders_one_empty_row(role):
    rows = Message(role, "hello").render(0)
    assert all(row == Line() for row in rows)
    # Only the banded user role carries in-band padding rows.
    assert len(rows) == (3 if role == "user" else 1)


@pytest.mark.parametrize("role", _ROLES)
def test_width_one_does_not_crash_and_stays_within_width(role):
    rows = Message(role, "hello").render(1)
    assert rows
    assert all(row.width <= 1 for row in rows)


# --- empty text -----------------------------------------------------------------------


def test_empty_text_user_renders_a_band_wrapped_in_padding():
    rows = Message("user", "").render(6)
    assert len(rows) == 3
    assert rows[1] == Line((Segment(" ", USER_BG), Segment("     ", USER_BG)))
    assert all(seg.style == USER_BG for seg in rows[1].segments)
    assert all(seg.style == USER_BG for row in (rows[0], rows[2]) for seg in row.segments)


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
