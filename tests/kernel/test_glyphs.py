"""The glyph vocabulary and the seat rule: glyph plus separator, display-column
measurement and pair alignment."""

from __future__ import annotations

from dataclasses import fields

from wcwidth import wcswidth

from motui.kernel.glyphs import (
    COLLAPSED,
    CURSOR,
    EXPANDED,
    GLYPHS,
    MARKED,
    RADIO_EMPTY,
    RADIO_FILLED,
    THUMB,
    TRACK,
    UNMARKED,
    Border,
    Glyphs,
    pair_seat,
    seat,
    seat_width,
)
from motui.kernel.text import visible_width

#: Single-cell glyph fields.  The pair fields (``radio_*``/``check_*``) and
#: the separator are deliberately multi-column and are checked separately.
SINGLE_COLUMN_FIELDS = (
    "prompt",
    "cursor",
    "rail",
    "fold_open",
    "fold_closed",
    "more_up",
    "more_down",
    "bar_full",
    "bar_empty",
    "slider_track",
    "slider_thumb",
    "horizontal_rule",
    "vertical_rule",
    "quote",
    "notice_info",
    "notice_success",
    "notice_warn",
    "notice_error",
    "diff_add",
    "diff_remove",
    "diff_context",
)

#: Characters with Emoji presentation (or an Emoji variation selector) are
#: rejected from the default vocabulary: terminals would render them two
#: cells wide and break the row geometry.
REJECTED_EMOJI = frozenset(
    "\u2139\u2714\u2716\u2610\u2611\u26a0\u2757\u274c\u2705"
    "\u2612\u263a\u263b\u260e\u2706\u2708\u2709\u270f\u2702"
)

BORDER_FACTORIES = (
    Border.square,
    Border.rounded,
    Border.heavy,
    Border.double,
    Border.ascii,
    Border.none,
)


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


def test_seat_width_measures_display_columns():
    for glyph, width in (("", 0), ("\u25b8", 2), ("[x]", 4), ("\u6811", 3), ("\U0001F600", 3)):
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


def test_the_default_vocabulary_is_glyphs():
    assert Glyphs() == GLYPHS
    assert hash(Glyphs()) == hash(GLYPHS)


def test_every_single_glyph_field_measures_one_column():
    for name in SINGLE_COLUMN_FIELDS:
        glyph = getattr(GLYPHS, name)
        assert len(glyph) == 1, name
        assert wcswidth(glyph) == 1, name


def test_the_vocabulary_sequences_hold_one_column_members():
    for glyph in (*GLYPHS.bullets, *GLYPHS.spinner):
        assert len(glyph) == 1
        assert wcswidth(glyph) == 1
    assert wcswidth(GLYPHS.separator) == 3
    for pair in (
        GLYPHS.radio_off,
        GLYPHS.radio_on,
        GLYPHS.check_off,
        GLYPHS.check_on,
        GLYPHS.check_indeterminate,
    ):
        assert wcswidth(pair) == len(pair) == 3


def test_the_default_vocabulary_rejects_emoji_presentation():
    values = []
    for field in fields(Glyphs):
        value = getattr(GLYPHS, field.name)
        if isinstance(value, Border):
            values.extend(getattr(value, mark.name) for mark in fields(Border))
        elif isinstance(value, tuple):
            values.extend(value)
        else:
            values.append(value)
    for glyph in values:
        rejected = sorted(set(glyph) & REJECTED_EMOJI)
        assert not rejected, f"{glyph!r} carries {rejected}"


def test_border_styles_keep_one_column_geometry():
    for factory in BORDER_FACTORIES:
        border = factory()
        assert isinstance(border, Border)
        marks = [getattr(border, mark.name) for mark in fields(Border)]
        assert all(len(mark) == 1 and wcswidth(mark) == 1 for mark in marks)


def test_border_factories_name_the_documented_vocabularies():
    assert Border.square() == Border()
    assert Border.rounded().top_left == "\u256d"
    assert Border.heavy().cross == "\u254b"
    assert Border.double().left == "\u2551"
    assert Border.ascii().top_left == "+" and Border.ascii().left == "|"
    assert all(
        getattr(Border.none(), mark.name) == " " for mark in fields(Border)
    )
