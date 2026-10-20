"""CursorWindow arithmetic: clamping, the top-stick and centring window
policies, and stepping."""

from __future__ import annotations

from dataclasses import replace

from motui.kernel.cursor import CursorWindow


def test_an_empty_set_has_no_cursor_and_no_window():
    empty = CursorWindow()
    assert empty.clamp(-3) == empty.clamp(0) == empty.clamp(7) == 0
    assert empty.move(1) == empty.move(-1) == empty.move(1, wrap=False) == 0
    for cap in (None, 0, 5):
        for center in (False, True):
            assert CursorWindow(count=0, cap=cap, center=center).range() == (0, 0)


def test_a_window_at_least_as_tall_as_the_rows_renders_every_row():
    for center in (False, True):
        assert CursorWindow(count=4, cap=None, center=center).range() == (0, 4)
        assert CursorWindow(count=4, cap=4, center=center).range() == (0, 4)
        assert CursorWindow(index=99, count=4, cap=9, center=center).range() == (0, 4)


def test_a_nonpositive_cap_renders_no_rows():
    for center in (False, True):
        assert CursorWindow(index=3, count=20, cap=0, center=center).range() == (0, 0)
        assert CursorWindow(index=3, count=20, cap=-4, center=center).range() == (0, 0)


def test_the_default_window_hangs_at_the_top_then_scrolls_one_row_per_step():
    assert CursorWindow(index=0, count=20, cap=6).range() == (0, 6)
    assert CursorWindow(index=5, count=20, cap=6).range() == (0, 6)
    assert CursorWindow(index=6, count=20, cap=6).range() == (1, 7)
    cursor = CursorWindow(count=20, cap=6)
    walked = []
    for _ in range(19):
        cursor = CursorWindow(cursor.move(1), count=20, cap=6)
        walked.append((cursor.index, *cursor.range()))
    assert walked == [
        *((step, 0, 6) for step in range(1, 6)),
        *((step, step - 5, step + 1) for step in range(6, 20)),
    ]


def test_the_centred_window_carries_the_cursor_halfway_where_it_can():
    window = CursorWindow(count=20, cap=6, center=True)
    assert replace(window, index=0).range() == (0, 6)
    assert replace(window, index=2).range() == (0, 6)
    assert replace(window, index=10).range() == (7, 13)
    assert replace(window, index=19).range() == (14, 20)
    assert CursorWindow(index=3, count=5, cap=1).range() == (3, 4)
    assert CursorWindow(index=3, count=5, cap=1, center=True).range() == (3, 4)


def test_a_stale_cursor_is_clamped_before_the_window_is_computed():
    window = CursorWindow(count=20, cap=6)
    assert window.clamp(-1) == 0
    assert window.clamp(99) == 19
    assert CursorWindow(index=50, count=20, cap=6).range() == (14, 20)
    assert CursorWindow(index=-5, count=20, cap=6).range() == (0, 6)
    assert CursorWindow(index=50, count=20, cap=6, center=True).range() == (14, 20)


def test_move_wraps_a_menu_and_clamps_a_data_view():
    assert CursorWindow(index=0, count=5).move(-1) == 4
    assert CursorWindow(index=4, count=5).move(1) == 0
    assert CursorWindow(index=3, count=5).move(7) == 0
    assert CursorWindow(index=0, count=5).move(-1, wrap=False) == 0
    assert CursorWindow(index=4, count=5).move(1, wrap=False) == 4
    assert CursorWindow(index=3, count=5).move(7, wrap=False) == 4
    assert CursorWindow(index=99, count=5).move(0) == 4


def test_either_policy_keeps_the_cursor_row_on_screen():
    for count in range(1, 13):
        for cap in range(1, count + 1):
            for index in range(count):
                for center in (False, True):
                    start, stop = CursorWindow(index, count, cap, center).range()
                    assert start <= index < stop, (index, count, cap, center)
