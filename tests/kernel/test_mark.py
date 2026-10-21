"""The marked-row set and its row prefix: toggle, clear, iteration order and
the glyph pair."""

from __future__ import annotations

from motui.kernel.glyphs import GLYPHS
from motui.kernel.mark import MarkSet, mark_prefix
from motui.kernel.text import visible_width


def test_toggle_answers_the_state_after_the_flip():
    marks = MarkSet()
    assert marks.toggle(3) is True
    assert 3 in marks
    assert marks.toggle(3) is False
    assert 3 not in marks


def test_clear_answers_whether_anything_was_dropped():
    marks = MarkSet([1, 4])
    assert marks.clear() is True
    assert len(marks) == 0 and list(marks) == []
    assert marks.clear() is False


def test_marks_are_stored_raw_and_iteration_is_an_ascending_snapshot():
    marks = MarkSet([5, 1, 5, -2])
    assert list(marks) == [-2, 1, 5]
    marks.toggle(3)
    snapshot = list(marks)
    marks.toggle(7)
    assert snapshot == [-2, 1, 3, 5]
    assert list(marks) == [-2, 1, 3, 5, 7]
    assert len(marks) == 5 and 0 not in marks


def test_the_row_prefix_is_the_marked_glyph_plus_one_separator():
    assert mark_prefix(True) == "[x] "
    assert mark_prefix(False) == "[ ] "
    assert (GLYPHS.check_on, GLYPHS.check_off) == ("[x]", "[ ]")
    assert visible_width(mark_prefix(True)) == 4
    assert visible_width(mark_prefix(False)) == 4


def test_mark_prefix_takes_a_custom_pair_and_seats_each_glyph():
    assert mark_prefix(True, marked_glyph="[X]", unmarked_glyph="( )") == "[X] "
    assert mark_prefix(False, marked_glyph="[X]", unmarked_glyph="( )") == "( ) "
    assert mark_prefix(True, marked_glyph="\u6811", unmarked_glyph="[ ]") == "\u6811 "
    assert mark_prefix(True, marked_glyph="", unmarked_glyph="[ ]") == ""
    assert mark_prefix(False, marked_glyph="", unmarked_glyph="") == ""
