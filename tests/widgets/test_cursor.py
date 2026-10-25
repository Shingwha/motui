"""Cursor arithmetic: clamping, disabled stepping, edge jumps, and the three
window policies."""

from __future__ import annotations

from motui.widgets.cursor import Cursor


def test_an_empty_set_has_no_cursor_and_no_window():
    empty = Cursor()
    assert empty.clamp(-3) == empty.clamp(0) == empty.clamp(7) == 0
    assert empty.select(0) is False
    assert empty.move(1) is False and empty.move(-1) is False
    assert empty.home() is False and empty.end() is False
    for anchor in ("top", "center", "bottom"):
        for size in (0, 5):
            assert empty.window(size, anchor=anchor) == (0, 0)


def test_a_window_at_least_as_tall_as_the_rows_renders_every_row():
    for anchor in ("top", "center", "bottom"):
        assert Cursor(count=4).window(4, anchor=anchor) == (0, 4)
        assert Cursor(index=99, count=4).window(9, anchor=anchor) == (0, 4)


def test_a_nonpositive_size_renders_no_rows():
    for anchor in ("top", "center", "bottom"):
        assert Cursor(index=3, count=20).window(0, anchor=anchor) == (0, 0)
        assert Cursor(index=3, count=20).window(-4, anchor=anchor) == (0, 0)


def test_the_top_window_hangs_at_the_top_then_scrolls_one_row_per_step():
    assert Cursor(index=0, count=20).window(6, anchor="top") == (0, 6)
    assert Cursor(index=5, count=20).window(6, anchor="top") == (0, 6)
    assert Cursor(index=6, count=20).window(6, anchor="top") == (1, 7)
    cursor = Cursor(count=20)
    walked = []
    for _ in range(19):
        cursor.move(1)
        walked.append((cursor.index, *cursor.window(6, anchor="top")))
    assert walked == [
        *((step, 0, 6) for step in range(1, 6)),
        *((step, step - 5, step + 1) for step in range(6, 20)),
    ]


def test_the_centred_window_carries_the_cursor_halfway_where_it_can():
    assert Cursor(index=0, count=20).window(6, anchor="center") == (0, 6)
    assert Cursor(index=2, count=20).window(6, anchor="center") == (0, 6)
    assert Cursor(index=10, count=20).window(6, anchor="center") == (7, 13)
    assert Cursor(index=19, count=20).window(6, anchor="center") == (14, 20)
    assert Cursor(index=3, count=5).window(1, anchor="center") == (3, 4)
    assert Cursor(index=3, count=5).window(1, anchor="top") == (3, 4)


def test_the_bottom_window_pins_the_tail():
    assert Cursor(index=0, count=20).window(6, anchor="bottom") == (14, 20)
    assert Cursor(index=19, count=20).window(6, anchor="bottom") == (14, 20)


def test_a_stale_cursor_is_clamped_before_the_window_is_computed():
    assert Cursor(count=20).clamp(-1) == 0
    assert Cursor(count=20).clamp(99) == 19
    assert Cursor(index=50, count=20).window(6, anchor="top") == (14, 20)
    assert Cursor(index=-5, count=20).window(6, anchor="top") == (0, 6)
    assert Cursor(index=50, count=20).window(6, anchor="center") == (14, 20)


def test_move_wraps_a_menu_and_clamps_a_data_view():
    menu = Cursor(index=0, count=5, wrap=True)
    assert menu.move(-1) is True and menu.index == 4
    assert menu.move(1) is True and menu.index == 0
    assert menu.move(7) is True and menu.index == 2
    view = Cursor(index=0, count=5, wrap=False)
    assert view.move(-1) is False and view.index == 0
    view.select(4)
    assert view.move(1) is False and view.index == 4
    assert view.move(7) is False and view.index == 4
    assert Cursor(index=3, count=5).move(0) is False


def test_move_steps_over_disabled_rows_and_select_refuses_them():
    cursor = Cursor(count=5, disabled=(1, 2))
    assert cursor.move(1) is True and cursor.index == 3
    assert cursor.move(1) is True and cursor.index == 4
    assert cursor.move(1) is False
    assert cursor.select(1) is False and cursor.index == 4
    assert cursor.select(-9) is True and cursor.index == 0
    dead = Cursor(count=3, disabled=(0, 1, 2), wrap=True)
    assert dead.move(1) is False and dead.index == 0


def test_home_and_end_land_on_the_first_and_last_enabled_row():
    cursor = Cursor(index=2, count=5, disabled=(0, 4))
    assert cursor.home() is True and cursor.index == 1
    assert cursor.end() is True and cursor.index == 3
    assert cursor.end() is False
    assert Cursor(count=3, disabled=(0, 1, 2)).home() is False


def test_the_top_and_centred_windows_keep_the_cursor_row_on_screen():
    for count in range(1, 13):
        for size in range(1, count + 1):
            for index in range(count):
                for anchor in ("top", "center"):
                    start, stop = Cursor(index=index, count=count).window(
                        size, anchor=anchor
                    )
                    assert start <= index < stop, (index, count, size, anchor)
