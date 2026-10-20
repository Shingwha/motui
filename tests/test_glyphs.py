"""Tests for motui.kernel.glyphs: the vocabulary and the seat rule.

The fifteen constants are the shipped marks -- the rows' structural
vocabulary -- and the three helpers are the one seat rule every row
component renders through: glyph + separator, measured in display columns
(``visible_width``, never ``len``), a state pair padded to its wider
member, and the empty glyph seating zero columns.
"""

import pytest

from motui.kernel.glyphs import (
    COLLAPSED,
    CURSOR,
    EXPANDED,
    MARKED,
    MENU_CURSOR,
    MORE_DOWN,
    MORE_UP,
    RAIL_BAR,
    RADIO_EMPTY,
    RADIO_FILLED,
    TASK_DONE,
    TASK_OPEN,
    THUMB,
    TRACK,
    UNMARKED,
    pair_seat,
    seat,
    seat_width,
)
from motui.kernel.text import visible_width


def test_the_vocabulary_is_the_fifteen_shipped_marks():
    assert (CURSOR, MENU_CURSOR, RAIL_BAR) == ("\u25b8", "\u2192", "\u258c")
    assert (EXPANDED, COLLAPSED) == ("\u25be", "\u25b8")
    assert (RADIO_EMPTY, RADIO_FILLED) == ("( )", "(\u2022)")
    assert (MARKED, UNMARKED) == ("[x]", "[ ]")
    assert (MORE_UP, MORE_DOWN) == ("\u2191", "\u2193")
    assert (TRACK, THUMB) == ("\u2591", "\u2588")
    assert (TASK_OPEN, TASK_DONE) == ("\u2610", "\u2611")


def test_seat_is_the_glyph_plus_one_separator():
    assert seat(MARKED) == "[x] "
    assert seat(MENU_CURSOR) == "\u2192 "
    assert seat(RADIO_FILLED) == "(\u2022) "


def test_an_empty_glyph_seats_nothing():
    assert seat("") == ""
    assert seat_width("") == 0
    assert pair_seat("", "") == ""


def test_seat_width_measures_display_columns_not_characters():
    assert seat_width(MARKED) == 4  # three glyph columns + the separator
    assert seat_width(RADIO_EMPTY) == 4  # three + one
    # A CJK glyph is two columns wide: the seat is three, not two.
    assert visible_width("\u6811") == 2
    assert seat_width("\u6811") == 3
    assert seat("\u6811") == "\u6811 "


def test_a_pair_seat_aligns_both_members():
    assert pair_seat(MARKED, UNMARKED) == "[x] "
    assert pair_seat(UNMARKED, MARKED) == "[ ] "
    assert seat_width(pair_seat(MARKED, UNMARKED)) == seat_width(
        pair_seat(UNMARKED, MARKED)
    )
    assert pair_seat(RADIO_FILLED, RADIO_EMPTY) == "(\u2022) "
    # A narrow member is padded to the wide one; the wide one is unchanged.
    assert pair_seat("+", "[x]") == "+   "  # the two-column seat padded to four
    assert pair_seat("[x]", "+") == "[x] "
    # A wide CJK member sets the pair's width; the ASCII member pads to it.
    assert pair_seat("+", "\u6811") == "+  "  # the two-column seat padded to three
    assert pair_seat("\u6811", "+") == "\u6811 "


def test_a_pair_seat_with_an_empty_member_keeps_the_wider_width():
    assert pair_seat("", "[x]") == " " * 4  # the empty state pads 4 columns
    assert pair_seat("[x]", "") == "[x] "
    assert pair_seat("", "\u6811") == " " * 3


@pytest.mark.parametrize(
    "glyph, width",
    [
        ("", 0),
        ("\u25b8", 2),
        ("[x]", 4),
        ("\u6811", 3),
        ("\U0001f600", 3),  # an emoji is two columns: the seat is three
    ],
)
def test_seat_width_is_the_visible_width_plus_one(glyph, width):
    assert seat_width(glyph) == (visible_width(glyph) + 1 if glyph else 0) == width
    assert visible_width(seat(glyph)) == width
