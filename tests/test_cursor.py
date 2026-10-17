"""Tests for motui.kernel.cursor (CursorWindow).

The two window policies are pure arithmetic, so the assertions walk the
boundaries: the exact ``(start, stop)`` slice at the edges, the menu
window's step-by-step scroll, the centred window's slides, the defensive
clamp of an out-of-range cursor, and the stepping rule of both a menu
cycle and a data view.  The component that renders through the value is
not imported here: the primitive is pinned on its own.
"""

from dataclasses import replace

from motui.kernel.cursor import CursorWindow


def test_an_empty_set_has_no_cursor_and_no_window():
    """``count == 0``: the cursor clamps to ``0``, the window is empty
    whatever ``cap`` says, and move stays put."""
    empty = CursorWindow()
    assert empty.clamp(-3) == empty.clamp(0) == empty.clamp(7) == 0
    assert empty.move(1) == empty.move(-1) == empty.move(1, wrap=False) == 0
    for cap in (None, 0, 5):
        for center in (False, True):
            assert CursorWindow(count=0, cap=cap, center=center).range() == (0, 0)


def test_a_window_at_least_as_tall_as_the_rows_renders_every_row():
    """``cap is None`` or ``cap >= count`` is the whole sequence under both
    policies; the cursor is clamped first, so a stale index cannot change
    that."""
    for center in (False, True):
        assert CursorWindow(count=4, cap=None, center=center).range() == (0, 4)
        assert CursorWindow(count=4, cap=4, center=center).range() == (0, 4)
        assert CursorWindow(index=99, count=4, cap=9, center=center).range() == (0, 4)


def test_a_nonpositive_cap_renders_no_rows():
    """``cap <= 0``: nothing fits, under either policy."""
    for center in (False, True):
        assert CursorWindow(index=3, count=20, cap=0, center=center).range() == (0, 0)
        assert CursorWindow(index=3, count=20, cap=-4, center=center).range() == (0, 0)


def test_the_default_window_hangs_at_the_top_then_scrolls_one_row_per_step():
    """``count=20, cap=6`` -- the menu policy: rows 0..5 hang at the top,
    then the window walks one row per step with the cursor as its last row."""
    assert CursorWindow(index=0, count=20, cap=6).range() == (0, 6)  # the first row
    assert CursorWindow(index=5, count=20, cap=6).range() == (0, 6)  # the last hanging row
    assert CursorWindow(index=6, count=20, cap=6).range() == (1, 7)  # the first scroll
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
    """``count=20, cap=6`` -- the view policy: the cursor sits at
    ``index - cap // 2``, clamped at both ends."""
    window = CursorWindow(count=20, cap=6, center=True)
    assert replace(window, index=0).range() == (0, 6)  # the top end clamps the start
    assert replace(window, index=2).range() == (0, 6)  # ... still clamped
    assert replace(window, index=10).range() == (7, 13)  # the cursor at the middle row
    assert replace(window, index=19).range() == (14, 20)  # the bottom end clamps the start


def test_a_one_row_window_shows_only_the_cursor_row():
    """``cap=1`` is the smallest budget; the cursor still stays on screen
    under either policy (``cap // 2 == 0``, so the centring window
    degenerates to the top-stick one)."""
    for center in (False, True):
        assert CursorWindow(index=0, count=5, cap=1, center=center).range() == (0, 1)
        assert CursorWindow(index=3, count=5, cap=1, center=center).range() == (3, 4)
        assert CursorWindow(index=4, count=5, cap=1, center=center).range() == (4, 5)


def test_an_out_of_range_cursor_is_clamped_before_the_window_is_computed():
    """The defensive rule: a stale cursor can never move the window off the
    rows."""
    window = CursorWindow(count=20, cap=6)
    assert window.clamp(-1) == 0
    assert window.clamp(99) == 19
    assert CursorWindow(index=50, count=20, cap=6).range() == (14, 20)
    assert CursorWindow(index=-5, count=20, cap=6).range() == (0, 6)
    assert CursorWindow(index=50, count=20, cap=6, center=True).range() == (14, 20)
    assert CursorWindow(index=-5, count=20, cap=6, center=True).range() == (0, 6)


def test_move_wraps_a_menu_and_clamps_a_data_view():
    """``wrap=True`` is the menu cycle -- off the last row onto the first
    and back; ``wrap=False`` is the data view -- the ends hold."""
    assert CursorWindow(index=0, count=5).move(-1) == 4
    assert CursorWindow(index=4, count=5).move(1) == 0
    assert CursorWindow(index=3, count=5).move(7) == 0  # (3 + 7) % 5
    assert CursorWindow(index=0, count=5).move(-1, wrap=False) == 0
    assert CursorWindow(index=4, count=5).move(1, wrap=False) == 4
    assert CursorWindow(index=3, count=5).move(7, wrap=False) == 4
    # Either way the answer is a legal cursor, a stale index included.
    assert CursorWindow(index=99, count=5).move(0) == 4
    assert CursorWindow(index=99, count=5).move(0, wrap=False) == 4


def test_either_policy_keeps_the_cursor_row_on_screen():
    """The one invariant behind both policies, over every small shape."""
    for count in range(1, 13):
        for cap in range(1, count + 1):
            for index in range(count):
                for center in (False, True):
                    start, stop = CursorWindow(index, count, cap, center).range()
                    assert start <= index < stop, (index, count, cap, center)
