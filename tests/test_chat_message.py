"""Tests for mocode_tui.chat.message (Message).

Contract (COMPONENTS.md): ``user`` renders a full-width color band with one
pad cell per side plus one pure band padding row above and below; ``assistant``
is plain; ``thinking`` is dim italic; an unknown role degrades to ``assistant``;
``style`` overrides the role default.  Padding is computed from the width and
the content, never re-typed as a literal.
"""

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import MUTED, Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.chat.message import Message

WIDTH = 80
PAD = " " * WIDTH  # a pure band padding row: full width, no content


def test_user_band_at_width_80():
    rows = Message("user", "hello there").render(WIDTH)
    assert len(rows) == 3  # top padding, content, bottom padding
    assert [row.text for row in rows] == [
        PAD,
        " hello there" + " " * (WIDTH - len(" hello there")),
        PAD,
    ]
    # Every segment of every row carries the band style.
    assert all(seg.style == DEFAULT_THEME.user_bg for row in rows for seg in row.segments)


def test_assistant_and_thinking_have_no_band():
    assert Message("assistant", "hi").render(WIDTH) == [Line.from_text("hi")]
    (row,) = Message("thinking", "hmm").render(WIDTH)
    assert row.text == "hmm"
    assert all(seg.style == MUTED.merge(Style(italic=True)) for seg in row.segments)


def test_unknown_role_degrades_to_assistant():
    assert Message("system", "hello").render(WIDTH) == Message("assistant", "hello").render(WIDTH)


def test_style_overrides_the_role_default():
    rows = Message("user", "hi", style=Style(bg="red")).render(6)
    assert all(seg.style == Style(bg="red") for row in rows for seg in row.segments)
    assert [row.text for row in rows] == [" " * 6, " hi   ", " " * 6]


def test_narrow_width_guard():
    # The two padding rows survive every width; no row exceeds it.
    rows = Message("user", "hello").render(1)
    assert len(rows) >= 3
    assert all(row.width <= 1 for row in rows)
    assert all(seg.style == DEFAULT_THEME.user_bg for row in (rows[0], rows[-1]) for seg in row.segments)
    assert Message("assistant", "hello").render(0) == [Line()]


def test_user_text_area_is_width_minus_two():
    width = 9
    rows = Message("user", "aaa bbb ccc").render(width)
    body = width - 2  # one pad cell per side: the text area the wrap uses

    def fit(piece: str) -> str:
        row = " " + piece  # the leading pad cell, then the wrapped piece
        return row + " " * (width - len(row))  # the fill closes the band

    assert [row.text for row in rows] == [
        " " * width,  # top padding
        fit("aaa bbb"),  # " aaa bbb " -- the piece exactly fills the body
        fit("ccc"),  # " ccc     " -- the fill absorbs what is left
        " " * width,  # bottom padding
    ]
    assert rows[1].segments[0] == Segment(" ", DEFAULT_THEME.user_bg)
