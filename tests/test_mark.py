"""Tests for motui.kernel.mark (MarkSet / mark_prefix).

The mark is the value a marked view keeps: ``toggle`` answers the state
after the flip, ``clear`` whether the view must repaint, and iteration is
an ascending snapshot -- the one order rendering reads.  ``mark_prefix``
is the glyph pair the views lead their rows with.
"""

from motui.kernel.glyphs import MARKED, UNMARKED
from motui.kernel.mark import MarkSet, mark_prefix
from motui.kernel.text import visible_width


def test_toggle_answers_the_state_after_the_flip():
    marks = MarkSet()
    assert marks.toggle(3) is True  # nothing was marked: 3 is now
    assert 3 in marks
    assert marks.toggle(3) is False  # it was marked: now it is not
    assert 3 not in marks


def test_clear_answers_whether_anything_was_dropped():
    marks = MarkSet([1, 4])
    assert marks.clear() is True
    assert len(marks) == 0 and list(marks) == []
    assert marks.clear() is False  # nothing left to drop


def test_marks_are_stored_raw_and_iteration_is_an_ascending_snapshot():
    """The set keeps exactly what the view hands it -- duplicates collapse,
    a negative index is kept -- and iterating answers a sorted copy, so a
    later mark never rewrites an answer already handed out."""
    marks = MarkSet([5, 1, 5, -2])
    assert list(marks) == [-2, 1, 5] and -2 in marks
    marks.toggle(3)
    snapshot = list(marks)
    assert snapshot == [-2, 1, 3, 5]
    marks.toggle(7)
    assert snapshot == [-2, 1, 3, 5]  # a copy, not a live view
    assert list(marks) == [-2, 1, 3, 5, 7]


def test_contains_and_len_read_the_marks():
    empty = MarkSet()
    assert len(empty) == 0 and 1 not in empty
    marks = MarkSet([2, 0])
    assert len(marks) == 2
    assert 0 in marks and 2 in marks and 1 not in marks


def test_the_row_prefix_is_the_three_column_glyph_plus_a_separator():
    """The glyph pair measures three columns; the prefix adds the one
    separator column before the row's own text."""
    assert mark_prefix(True) == "[x] "
    assert mark_prefix(False) == "[ ] "
    assert (MARKED, UNMARKED) == ("[x]", "[ ]")
    assert visible_width(MARKED) == visible_width(UNMARKED) == 3
    assert visible_width(mark_prefix(True)) == visible_width(mark_prefix(False)) == 4


def test_mark_prefix_takes_a_custom_pair_and_seats_each_glyph_alone():
    """The pair is a caller's vocabulary, not a module constant: each answer
    is the chosen glyph's own seat, and an empty glyph seats nothing."""
    assert mark_prefix(True, marked_glyph="[X]", unmarked_glyph="( )") == "[X] "
    assert mark_prefix(False, marked_glyph="[X]", unmarked_glyph="( )") == "( ) "
    assert mark_prefix(True, marked_glyph="\u6811", unmarked_glyph="[ ]") == "\u6811 "
    assert mark_prefix(True, marked_glyph="", unmarked_glyph="[ ]") == ""
    assert mark_prefix(False, marked_glyph="", unmarked_glyph="") == ""
