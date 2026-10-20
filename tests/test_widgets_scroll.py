"""Tests for motui.widgets.scroll: the clipped, scrolling window.

The window arithmetic (clipping, padding, clamping), the three scroll
doors and ``reveal``, the key/wheel routing, the scrollbar column, the
container mapping and the revision snapshot a sealed block follows.
"""

from __future__ import annotations

import pytest

from _doubles import Rows, texts

from motui.kernel import (
    Block,
    Component,
    KeyEvent,
    Line,
    MouseEvent,
    Revisioned,
    Segment,
    Theme,
)
from motui.kernel.glyphs import THUMB, TRACK
from motui.kernel.style import Style
from motui.widgets import ScrollView


class _RevisionedRows:
    """A mutable child whose revision is its rows plus a counter."""

    def __init__(self, *rows: str) -> None:
        self.rows = list(rows)
        self.tick = 0

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(row).fit(width) for row in self.rows]

    def revision(self) -> object:
        return (tuple(self.rows), self.tick)


class _WidthRecorder:
    """A child that records every render width and answers one row."""

    def __init__(self) -> None:
        self.widths: list[int] = []

    def render(self, width: int) -> list[Line]:
        self.widths.append(width)
        return [Line.from_text("x").fit(width)]


def _view(*rows: str, **kwargs) -> ScrollView:
    return ScrollView(Rows(*rows), **kwargs)


# ---------------------------------------------------------------------------
# The window: clipping, padding, height=None
# ---------------------------------------------------------------------------


def test_a_fixed_height_clips_the_child_to_one_window():
    view = _view(*[f"r{i}" for i in range(10)], height=3)
    assert texts(view, 20) == ["r0", "r1", "r2"]
    assert (view.total_rows, view.viewport_height, view.offset) == (10, 3, 0)


def test_a_predicted_offset_paints_the_matching_slice():
    view = _view(*[f"r{i}" for i in range(10)], height=3, offset=4)
    assert texts(view, 20) == ["r4", "r5", "r6"]
    assert view.offset == 4


def test_a_short_child_is_padded_to_the_fixed_height():
    view = _view("one", "two", height=5)
    assert texts(view, 20) == ["one", "two", "", "", ""]


def test_height_none_shows_every_row_and_never_scrolls():
    view = _view(*[f"r{i}" for i in range(4)])
    assert texts(view, 20) == ["r0", "r1", "r2", "r3"]
    assert view.viewport_height == 4
    assert view.scroll_down(5) is False
    assert view.scroll_to(2) is False
    assert view.offset == 0


def test_an_empty_child_is_zero_rows_or_a_blank_padded_window():
    assert texts(ScrollView(Rows()), 10) == []
    assert texts(ScrollView(Rows(), height=3), 10) == ["", "", ""]


def test_an_over_wide_child_row_is_fitted_back_to_the_painting_width():
    class Wide:
        def render(self, width: int) -> list[Line]:
            return [Line.from_text("x" * 50)]

    rows = ScrollView(Wide(), height=1).render(10)
    assert rows[0].width <= 10


# ---------------------------------------------------------------------------
# Offsets and the scroll doors
# ---------------------------------------------------------------------------


def test_an_initial_offset_past_the_end_is_clamped_on_render():
    view = _view(*[f"r{i}" for i in range(10)], height=3, offset=99)
    assert texts(view, 20) == ["r7", "r8", "r9"]
    assert view.offset == 7


def test_scroll_to_clamps_and_reports_only_real_moves():
    view = _view(*[f"r{i}" for i in range(10)], height=3)
    view.render(20)
    assert view.scroll_to(5) is True
    assert view.offset == 5
    assert view.scroll_to(5) is False
    assert view.scroll_to(99) is True
    assert view.offset == 7
    assert view.scroll_to(99) is False
    assert view.scroll_to(-4) is True
    assert view.offset == 0


def test_scroll_up_and_down_step_and_clamp_at_the_edges():
    view = _view(*[f"r{i}" for i in range(10)], height=3)
    view.render(20)
    assert view.scroll_down(2) is True
    assert view.offset == 2
    assert view.scroll_up(1) is True
    assert view.offset == 1
    assert view.scroll_up(99) is True
    assert view.offset == 0
    assert view.scroll_up(1) is False
    assert view.scroll_down(99) is True
    assert view.offset == 7
    assert view.scroll_down(1) is False
    # A negative step is not a reverse scroll: it moves nowhere.
    assert view.scroll_up(-3) is False and view.offset == 7


def test_a_child_that_shrinks_pulls_the_offset_back_in_range():
    child = _RevisionedRows(*[f"r{i}" for i in range(10)])
    view = ScrollView(child, height=3)
    view.render(20)
    assert view.scroll_to(7) is True
    child.rows = child.rows[:4]
    assert texts(view, 20) == ["r1", "r2", "r3"]
    assert view.offset == 1


def test_reveal_moves_the_minimum_and_clamps_into_the_child():
    view = _view(*[f"r{i}" for i in range(10)], height=3)
    view.render(20)
    assert view.reveal(0) is False
    assert view.reveal(4) is True  # one past the window: the window slides one
    assert view.offset == 2
    assert view.reveal(2) is False  # already visible at the top
    assert view.reveal(1) is True
    assert view.offset == 1
    assert view.reveal(99) is True  # clamped to the last row
    assert view.offset == 7
    assert view.reveal(-5) is True  # clamped to the first row
    assert view.offset == 0
    assert view.reveal(2) is False  # the last visible row, no move needed


def test_reveal_declines_before_a_render_and_for_an_empty_child():
    assert ScrollView(Rows("a"), height=2).reveal(0) is False
    empty = ScrollView(Rows(), height=2)
    empty.render(10)
    assert empty.reveal(0) is False


# ---------------------------------------------------------------------------
# Keys and wheel
# ---------------------------------------------------------------------------


def test_the_scroll_keys_move_one_row_or_one_window():
    view = _view(*[f"r{i}" for i in range(12)], height=4)
    view.render(20)
    assert view.handle(KeyEvent("down")) is True
    assert view.offset == 1
    assert view.handle(KeyEvent("up")) is True
    assert view.offset == 0
    assert view.handle(KeyEvent("page_down")) is True
    assert view.offset == 4
    assert view.handle(KeyEvent("page_up")) is True
    assert view.offset == 0
    assert view.handle(KeyEvent("end")) is True
    assert view.offset == 8
    assert view.handle(KeyEvent("home")) is True
    assert view.offset == 0


def test_a_key_that_moves_nothing_is_not_consumed():
    view = _view(*[f"r{i}" for i in range(4)], height=4)
    view.render(20)
    for key in ("up", "down", "page_up", "page_down", "home", "end"):
        assert view.handle(KeyEvent(key)) is False, key
    assert view.handle(KeyEvent("tab")) is False
    assert view.handle(KeyEvent("a", "a")) is False
    assert view.handle(KeyEvent("down", kind="release")) is False


def test_the_vertical_wheel_scrolls_and_the_horizontal_one_declines():
    view = _view(*[f"r{i}" for i in range(10)], height=3)
    view.render(20)
    assert view.handle(MouseEvent("wheel_down", kind="wheel")) is True
    assert view.offset == 1
    assert view.handle(MouseEvent("wheel_up", kind="wheel")) is True
    assert view.offset == 0
    assert view.handle(MouseEvent("wheel_up", kind="wheel")) is False
    assert view.handle(MouseEvent("wheel_left", kind="wheel")) is False
    assert view.handle(MouseEvent("left", kind="press")) is False


# ---------------------------------------------------------------------------
# The container door
# ---------------------------------------------------------------------------


def test_child_at_maps_visible_cells_through_the_painted_offset():
    child = Rows(*[f"r{i}" for i in range(10)])
    view = ScrollView(child, height=3)
    assert view.child_at(0, 0) is None  # not rendered yet
    view.render(20)
    assert view.child_at(0, 2) == (child, 0, 2)
    view.scroll_to(4)
    view.render(20)
    assert view.child_at(0, 0) == (child, 4, 0)
    assert view.child_at(2, 7) == (child, 6, 7)


def test_child_at_declines_padding_and_out_of_range_cells():
    view = ScrollView(Rows("one"), height=4)
    view.render(10)
    assert view.child_at(0, 0)[1:] == (0, 0)
    assert view.child_at(1, 0) is None  # padding
    assert view.child_at(4, 0) is None  # past the window
    assert view.child_at(0, -1) is None
    assert view.child_at(-1, 0) is None


# ---------------------------------------------------------------------------
# The scrollbar
# ---------------------------------------------------------------------------


def test_the_scrollbar_reserves_the_last_column_and_child_width():
    child = _WidthRecorder()
    view = ScrollView(child, height=4, scrollbar=True)
    rows = view.render(10)
    assert child.widths == [9]
    assert all(row.width == 10 for row in rows)


def test_the_scrollbar_paints_track_cells_and_a_proportional_thumb():
    view = _view(*[f"r{i}" for i in range(8)], height=4, scrollbar=True)
    rows = view.render(6)
    column = [row.text[-1] for row in rows]
    assert all(cell in (TRACK, THUMB) for cell in column)
    assert column[0] == THUMB  # the thumb starts at the top
    assert column.count(THUMB) >= 1
    assert view.scroll_to(4) is True
    moved = [row.text[-1] for row in view.render(6)]
    assert moved[-1] == THUMB  # the thumb reaches the bottom
    assert moved != column


def test_a_content_that_fits_fills_the_thumb_and_no_track():
    view = _view("one", "two", height=4, scrollbar=True)
    column = [row.text[-1] for row in view.render(8)]
    assert column == [THUMB] * 4


def test_the_scrollbar_bands_come_from_the_theme():
    track = Style(fg="#101010")
    thumb = Style(fg="#abcdef")
    theme = Theme(scrollbar=track, scrollbar_thumb=thumb)
    view = ScrollView(Rows(*[f"r{i}" for i in range(8)]), height=4,
                      scrollbar=True, theme=theme)
    rows = view.render(5)
    last = [row.segments[-1] for row in rows]
    assert last[0] == Segment("\u2588", thumb)
    assert last[-1] == Segment("\u2591", track)


def test_a_scrollbar_column_is_not_the_childs():
    child = Rows(*[f"r{i}" for i in range(6)])
    view = ScrollView(child, height=3, scrollbar=True)
    view.render(8)
    assert view.child_at(0, 6) == (child, 0, 6)  # inner width is 7
    assert view.child_at(0, 7) is None  # the bar
    assert view.child_at(0, 8) is None


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------


def test_the_snapshot_covers_the_child_and_the_three_knobs():
    child = _RevisionedRows("a")
    view = ScrollView(child, height=2)
    view.render(10)
    before = view.revision()
    assert view.scroll_to(0) is False
    child.rows = ["a", "b", "c"]
    assert view.revision() != before
    before = view.revision()
    view.height = 1
    assert view.revision() != before
    before = view.revision()
    view.scrollbar = True
    assert view.revision() != before


def test_a_child_without_revision_contributes_its_identity():
    child = Rows("a")
    view = ScrollView(child)
    assert view.revision()[0] == id(child)
    assert ScrollView(Rows("a")).revision() != view.revision()


def test_a_none_snapshot_falls_back_to_identity():
    class Off:
        def render(self, width: int) -> list[Line]:
            return [Line.from_text("x")]

        def revision(self) -> object:
            return None

    child = Off()
    assert ScrollView(child).revision()[0] == id(child)


def test_a_sealed_block_around_the_view_follows_the_childs_revision():
    child = _RevisionedRows("a")
    view = ScrollView(child, height=2)
    block = Block("scroll", view)
    assert [row.text for row in block.rows(10)] == ["a", ""]
    block.seal()
    child.rows = ["a", "b", "c"]
    child.tick += 1
    assert [row.text for row in block.rows(10)] == ["a", "b"]


def test_a_scroll_view_is_a_component_and_a_container():
    view = _view("a")
    assert isinstance(view, Component)
    assert isinstance(view, Revisioned)
