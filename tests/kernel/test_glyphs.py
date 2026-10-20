"""The glyph vocabulary and the seat rule: glyph plus separator, display-column
measurement and pair alignment."""

from __future__ import annotations

import pytest

from motui.kernel.glyphs import (
    COLLAPSED,
    CURSOR,
    EXPANDED,
    MARKED,
    RADIO_EMPTY,
    RADIO_FILLED,
    THUMB,
    TRACK,
    UNMARKED,
    pair_seat,
    seat,
    seat_width,
)
from motui.kernel.text import visible_width


def test_representative_glyphs_are_the_shipped_marks():
    assert (CURSOR, EXPANDED, COLLAPSED) == ("\u25b8", "\u25be", "\u25b8")
    assert (MARKED, UNMARKED) == ("[x]", "[ ]")
    assert (RADIO_FILLED, RADIO_EMPTY) == ("(\u2022)", "( )")
    assert (TRACK, THUMB) == ("\u2591", "\u2588")


def test_seat_is_the_glyph_plus_one_separator():
    assert seat(MARKED) == "[x] "
    assert seat(RADIO_FILLED) == "(\u2022) "
    assert visible_width(seat(MARKED)) == 4


def test_an_empty_glyph_seats_nothing():
    assert seat("") == ""
    assert seat_width("") == 0
    assert pair_seat("", "") == ""


@pytest.mark.parametrize(
    "glyph, width",
    [("", 0), ("\u25b8", 2), ("[x]", 4), ("\u6811", 3), ("\U0001F600", 3)],
)
def test_seat_width_measures_display_columns(glyph: str, width: int):
    assert seat_width(glyph) == width
    assert visible_width(seat(glyph)) == width


def test_a_pair_seat_aligns_both_members():
    assert pair_seat(MARKED, UNMARKED) == "[x] "
    assert pair_seat(UNMARKED, MARKED) == "[ ] "
    assert seat_width(pair_seat(MARKED, UNMARKED)) == seat_width(
        pair_seat(UNMARKED, MARKED)
    )
    assert pair_seat("+", "[x]") == "+   "
    assert pair_seat("[x]", "+") == "[x] "
    assert pair_seat("+", "\u6811") == "+  "
    assert pair_seat("", "[x]") == " " * 4
