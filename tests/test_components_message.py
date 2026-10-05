"""Tests for mocode_tui.components.message (Message).

Contract (COMPONENTS.md): ``user`` renders a full-width color band with one
pad cell per side plus one pure band padding row above and below; ``assistant``
is plain; ``thinking`` is dim italic; an unknown role degrades to ``assistant``;
``style`` overrides the role default.
"""

from mocode_tui.components.message import USER_BG, Message
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import MUTED, Style


def test_user_band_at_width_80():
    rows = Message("user", "hello there").render(80)
    assert len(rows) == 3  # top padding, content, bottom padding
    assert [row.text for row in rows] == [" " * 80, " hello there" + " " * 68, " " * 80]
    # Every segment of every row carries the band style.
    assert all(seg.style == USER_BG for row in rows for seg in row.segments)


def test_assistant_and_thinking_have_no_band():
    assert Message("assistant", "hi").render(80) == [Line.from_text("hi")]
    (row,) = Message("thinking", "hmm").render(80)
    assert row.text == "hmm"
    assert all(seg.style == MUTED.merge(Style(italic=True)) for seg in row.segments)


def test_unknown_role_degrades_to_assistant():
    assert Message("system", "hello").render(80) == Message("assistant", "hello").render(80)


def test_style_overrides_the_role_default():
    rows = Message("user", "hi", style=Style(bg="red")).render(6)
    assert all(seg.style == Style(bg="red") for row in rows for seg in row.segments)
    assert [row.text for row in rows] == [" " * 6, " hi   ", " " * 6]


def test_narrow_width_guard():
    # The two padding rows survive every width; no row exceeds it.
    rows = Message("user", "hello").render(1)
    assert len(rows) >= 3
    assert all(row.width <= 1 for row in rows)
    assert all(seg.style == USER_BG for row in (rows[0], rows[-1]) for seg in row.segments)
    assert Message("assistant", "hello").render(0) == [Line()]


def test_user_text_area_is_width_minus_two():
    rows = Message("user", "aaa bbb ccc").render(9)
    assert [row.text for row in rows] == [" " * 9, " aaa bbb ", " ccc     ", " " * 9]
    assert rows[1].segments[0] == Segment(" ", USER_BG)
