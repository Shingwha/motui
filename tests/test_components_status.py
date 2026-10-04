"""Tests for mocode_tui.components.status (StatusBar / StatusSegment)."""

from mocode_tui.components.status import StatusBar, StatusSegment
from mocode_tui.lines import Line


def test_status_segment_defaults():
    assert StatusSegment("x") == StatusSegment("x", 0)
    assert StatusSegment("x", 3).priority == 3


def test_empty_bar_renders_blank_row():
    assert StatusBar().render(20) == [Line()]


def test_segments_join_with_single_space_by_priority_order():
    bar = StatusBar(segments=[StatusSegment("low", 0), StatusSegment("high", 5)])
    assert [row.text for row in bar.render(20)] == ["high low"]


def test_low_priority_dropped_first_when_width_runs_out():
    bar = StatusBar(segments=[StatusSegment("aaa", 1), StatusSegment("bbb", 0)])
    assert [row.text for row in bar.render(7)] == ["aaa bbb"]
    assert [row.text for row in bar.render(6)] == ["aaa"]  # " bbb" no longer fits


def test_high_priority_survives_a_drop():
    bar = StatusBar(segments=[StatusSegment("first", 9), StatusSegment("second", 1)])
    assert [row.text for row in bar.render(6)] == ["first"]


def test_priority_beats_insertion_order_both_ways():
    bar = StatusBar(segments=[StatusSegment("keep", 2), StatusSegment("gone", 0)])
    bar2 = StatusBar(segments=[StatusSegment("gone", 0), StatusSegment("keep", 2)])
    assert [row.text for row in bar.render(6)] == ["keep"]
    assert [row.text for row in bar2.render(6)] == ["keep"]


def test_segment_method_appends():
    bar = StatusBar()
    bar.segment("left", 1)
    bar.segment("right", 0)
    assert [row.text for row in bar.render(20)] == ["left right"]


def test_over_wide_row_is_truncated():
    bar = StatusBar(segments=[StatusSegment("abcdef", 0)])
    row = bar.render(3)[0]
    assert row.text == "ab\u2026"
    assert row.width == 3


def test_zero_and_negative_widths_do_not_crash():
    bar = StatusBar(segments=[StatusSegment("x", 0)])
    assert bar.render(0) == [Line()]
    assert bar.render(-2) == [Line()]


def test_ties_keep_insertion_order():
    bar = StatusBar(segments=[StatusSegment("one", 0), StatusSegment("two", 0)])
    assert [row.text for row in bar.render(20)] == ["one two"]
