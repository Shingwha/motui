"""Tests for the layout extras: mocode_tui.widgets.layout (Spacer / Padding).

Contracts (the W4 ticket + the module docstring): ``Spacer`` renders ``rows``
blank rows (``rows <= 0`` renders nothing); ``Padding`` wraps a child's rows
in blank columns/rows (the child paints at ``width - left - right``, every
row fits back to ``width``), and with ``fill_style`` set the blank areas are
painted in that style -- merged *under* the child's own segment styles --
so the block reads as one continuous band.  Row/Column themselves are
covered by ``test_widgets_layout.py``.
"""

from mocode_tui.widgets.layout import Padding, Spacer
from mocode_tui.core.text import Text
from mocode_tui.core.block import Component
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import Style

from _doubles import texts


def texts(component, width=10):
    return [row.text for row in component.render(width)]


def test_spacer_renders_blanktexts():
    assert texts(Spacer(3), 10) == ["", "", ""]
    assert texts(Spacer(), 10) == [""]  # one row by default
    assert Spacer(0).render(10) == []
    assert Spacer(-2).render(10) == []  # negative is clamped to nothing
    assert Spacer(2).render(10) == [Line(), Line()]
    assert isinstance(Spacer(1), Component)


def test_padding_surrounds_the_child_with_plain_spaces():
    # one top row, the content row, one bottom row
    assert texts(Padding(Text("ab"), left=2, right=1, top=1, bottom=1), 10) == [
        "",
        "  ab ",
        "",
    ]
    assert texts(Padding(Text("a\nb"), left=1, right=1), 10) == [" a ", " b "]
    assert texts(Padding(Text("x")), 10) == ["x"]  # all pads default to 0
    assert texts(Padding(Text(""), left=1, top=2), 4) == ["", "", " "]


def test_padding_fits_back_to_the_painting_width():
    padded = Padding(Text("abcdef"), left=1, right=1)
    rows = padded.render(4)  # the child paints at 2 columns and wraps
    assert [row.text for row in rows] == [" ab ", " cd ", " ef "]
    assert all(row.width <= 4 for row in rows)
    assert all(row.width <= 2 for row in Padding(Text("abcdef")).render(2))


def test_fill_paints_the_blank_areas_into_a_continuous_band():
    band = Style(bg="#123456")
    rows = Padding(Text("hi"), left=2, right=2, top=1, bottom=1, fill_style=band).render(8)
    assert len(rows) == 3  # one top row, the content row, one bottom row
    # top and bottom are pure band rows, full width
    assert rows[0] == Line.filled(8, band)
    assert rows[2] == Line.filled(8, band)
    # the content row is one continuous band: pad, child, and the blank
    # columns out to inner + right, every segment carrying the fill
    assert rows[1].segments == (
        Segment("  ", band),
        Segment("hi", band),  # the fill merges *under* the child's style
        Segment("    ", band),  # 0 blank columns to inner (4 - 2) + right (2)
    )
    assert rows[1].text == "  hi    " and rows[1].width == 8
    # one continuous band: every segment carries the fill, and the only
    # RESET is the single trailing one -- no bleed inside the row
    styled = rows[1].styled()
    assert styled.count("\x1b[0m") == 1 and styled.endswith("\x1b[0m")
    assert styled == (
        band.prefix() + "  " + band.prefix() + "hi" + band.prefix() + "    " + "\x1b[0m"
    )


def test_fill_merges_under_the_child_own_style():
    band = Style(bg="#123456")
    child = Text("hi", style=Style(fg="red", bg="#654321"))
    row = Padding(child, left=1, right=1, fill_style=band).render(4)[0]
    assert row.segments == (
        Segment(" ", band),
        # the child's own colors win over the fill
        Segment("hi", Style(fg="red", bg="#654321")),
        Segment(" ", band),
    )


def test_padding_is_a_component():
    assert isinstance(Padding(Text("x")), Component)
    assert texts(Padding(Text("x"), left=1), 6) == [" x"]
