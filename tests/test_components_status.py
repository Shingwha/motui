"""Tests for mocode_tui.components.status (StatusBar / StatusSegment).

Contract: priority-ordered footer cells via ``segment(text, priority)`` --
highest priority kept, the lowest dropped first to fit; an empty bar renders
one blank row so a pinned footer keeps its height (COMPONENTS.md).
"""

from mocode_tui.components.status import StatusBar, StatusSegment
from mocode_tui.lines import Line


def test_priority_order_and_lowest_dropped_first():
    bar = StatusBar(segments=[StatusSegment("aaa", 1), StatusSegment("bbb", 0)])
    assert [row.text for row in bar.render(7)] == ["aaa bbb"]
    assert [row.text for row in bar.render(6)] == ["aaa"]  # " bbb" no longer fits
    # Priority beats insertion order in both directions.
    flipped = StatusBar(segments=[StatusSegment("bbb", 0), StatusSegment("aaa", 1)])
    assert [row.text for row in flipped.render(6)] == ["aaa"]


def test_empty_bar_renders_one_blank_row():
    assert StatusBar().render(20) == [Line()]


def test_segment_method_appends_cells():
    bar = StatusBar()
    bar.segment("left", 1)
    bar.segment("right", 0)
    assert [row.text for row in bar.render(20)] == ["left right"]


def test_narrow_width_truncates_the_survivor():
    row = StatusBar(segments=[StatusSegment("abcdef", 0)]).render(3)[0]
    assert row.text == "ab\u2026"
    assert row.width == 3
