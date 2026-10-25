"""ScrollPanel: a fixed-height window over a child's rows."""

import pytest

from motui.kernel.cell import Line, Surface
from motui.kernel.glyphs import GLYPHS
from motui.kernel.layout import Constraints
from motui.widgets import ScrollPanel
from tests.testing import Rows, key, many, texts, wheel


def view(rows=10, height=3, **kwargs) -> ScrollPanel:
    return ScrollPanel(Rows(*many(rows)), height=height, **kwargs)


def test_a_fixed_height_clips_the_child_to_one_window():
    assert texts(view(), 10) == ["r0", "r1", "r2"]


def test_a_predicted_offset_paints_the_matching_slice_and_clamps():
    scroll = ScrollPanel(Rows(*many(10)), height=3, offset=4)
    assert texts(scroll, 10) == ["r4", "r5", "r6"]
    far = ScrollPanel(Rows(*many(10)), height=3, offset=99)
    assert texts(far, 10) == ["r7", "r8", "r9"]
    assert far.offset == 7


def test_a_short_child_is_padded_to_the_fixed_height():
    assert texts(ScrollPanel(Rows("a"), height=3), 10) == ["a", "", ""]


def test_height_none_shows_every_row_and_never_scrolls():
    scroll = ScrollPanel(Rows(*many(10)))
    assert len(texts(scroll, 10)) == 10
    assert scroll.scroll_down(1) is False
    assert scroll.scroll_to(4) is False


def test_scroll_to_reports_only_real_moves_and_clamps():
    scroll = view()
    assert scroll.scroll_to(4) is True
    scroll.render(Constraints(width=10))
    assert scroll.offset == 4
    assert scroll.scroll_to(4) is False
    assert scroll.scroll_to(99) is True and scroll.offset == 7
    assert scroll.scroll_up(9) is True and scroll.offset == 0
    assert scroll.scroll_up(1) is False


def test_the_page_keys_move_one_window_and_the_edges_jump():
    scroll = view()
    scroll.render(Constraints(width=10))
    assert scroll.handle(key("down")) is True and scroll.offset == 1
    assert scroll.handle(key("up")) is True and scroll.offset == 0
    assert scroll.handle(key("up")) is False
    assert scroll.handle(key("page_down")) is True and scroll.offset == 3
    assert scroll.handle(key("page_up")) is True and scroll.offset == 0
    assert scroll.handle(key("end")) is True and scroll.offset == 7
    assert scroll.handle(key("home")) is True and scroll.offset == 0


def test_the_vertical_wheel_scrolls_and_other_events_decline():
    scroll = view()
    scroll.render(Constraints(width=10))
    assert scroll.handle(wheel(0, 0, "down")) is True and scroll.offset == 1
    assert scroll.handle(wheel(0, 0, "up")) is True and scroll.offset == 0
    assert scroll.handle(wheel(0, 0, "left")) is False
    assert scroll.handle(key("enter")) is False


def test_reveal_moves_the_minimum_and_declines_when_visible():
    scroll = view()
    assert scroll.reveal(1) is False
    scroll.render(Constraints(width=10))
    assert scroll.reveal(5) is True and scroll.offset == 3
    assert scroll.reveal(3) is False
    assert scroll.reveal(0) is True and scroll.offset == 0
    assert scroll.reveal(2) is False


def test_child_at_maps_visible_cells_through_the_painted_offset():
    child = Rows(*many(10))
    scroll = ScrollPanel(child, height=3, offset=2)
    scroll.render(Constraints(width=10))
    assert scroll.child_at(0, 0) == (child, 2, 0)
    assert scroll.child_at(2, 9) == (child, 4, 9)
    assert scroll.child_at(3, 0) is None
    assert scroll.child_at(-1, 0) is None


def test_the_bar_reserves_the_last_column_and_paints_track_and_thumb():
    child = Rows(*many(10))
    scroll = ScrollPanel(child, height=4, bar=True)
    rows = scroll.render(Constraints(width=10))
    assert all(row.width == 10 for row in rows)
    assert rows[0].segments[-1].text == GLYPHS.bar_full
    assert rows[1].segments[-1].text == GLYPHS.bar_full
    assert rows[2].segments[-1].text == GLYPHS.bar_empty
    assert scroll.child_at(0, 9) is None
    assert scroll.child_at(0, 8) == (child, 0, 8)


def test_the_bar_thumb_drags_and_the_track_pages():
    scroll = view(10, 4, bar=True)
    scroll.render(Constraints(width=10))
    # 10 rows in a 4-row window: thumb (0, 2), travel 2, span 6.
    assert scroll.drag(0, 9, "press") is True
    assert scroll.drag(1, 9, "motion") is True and scroll.offset == 3
    assert scroll.drag(2, 9, "motion") is True and scroll.offset == 6
    assert scroll.drag(2, 9, "release") is True
    assert scroll.drag(1, 9, "motion") is False

    scroll.scroll_to(0)
    assert scroll.drag(3, 9, "press") is True and scroll.offset == 4  # below: a page down
    assert scroll.drag(0, 9, "press") is True and scroll.offset == 0  # above: a page up
    assert scroll.drag(0, 8, "press") is False  # content column, not the bar
    assert scroll.click(0, 8) is False
    assert scroll.click(0, 9) is True


def test_a_view_without_a_bar_or_a_thumb_declines_drags():
    plain = view(10, 4)
    plain.render(Constraints(width=10))
    assert plain.drag(0, 9, "press") is False
    assert plain.click(0, 9) is False

    short = view(2, 4, bar=True)
    short.render(Constraints(width=10))
    assert short.drag(0, 9, "press") is False  # content fits: no thumb
    assert short.click(0, 9) is True  # the bar column is still the view's


def test_a_child_that_shrinks_pulls_the_offset_back_in_range():
    child = Rows(*many(10))
    scroll = ScrollPanel(child, height=3)
    scroll.render(Constraints(width=10))
    assert scroll.scroll_to(7) is True
    child.texts = ["only"]
    assert texts(scroll, 10) == ["only", "", ""]
    assert scroll.offset == 0


# -- the 2.0 render contract -------------------------------------------------


def test_a_natural_height_view_honours_the_height_budget():
    scroll = ScrollPanel(Rows(*many(5)))
    surface = scroll.render(Constraints(width=10, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["r0", "r1"]
    assert surface.width == 10 and surface.height == 2
    # The 1.x int spelling still shows every child row.
    assert [row.text for row in scroll.render(Constraints(width=10))] == ["r0", "r1", "r2", "r3", "r4"]


def test_an_explicit_height_wins_over_the_height_budget():
    scroll = view(10, 3)
    surface = scroll.render(Constraints(width=10, max_height=1))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["r0", "r1", "r2"]
    assert surface.height == 3


def test_the_axis_accepts_the_three_spellings_and_rejects_others():
    assert ScrollPanel(Rows("a"), axis="y").axis == "y"
    assert ScrollPanel(Rows("a"), axis="x").axis == "x"
    assert ScrollPanel(Rows("a"), axis="both").axis == "both"
    with pytest.raises(ValueError):
        ScrollPanel(Rows("a"), axis="z")


# -- the horizontal axis -----------------------------------------------------


class Wide:
    """A child that ignores its width constraint: ``columns`` wide, ``rows`` tall.

    The horizontal-overflow producer this wave tests against: every row is
    one ASCII pattern wide enough that a window can be located by slicing
    the same pattern.
    """

    def __init__(self, columns: int = 200, rows: int = 3) -> None:
        self.columns = columns
        self.row_count = rows
        self.widths: list[int] = []

    def text(self, row: int) -> str:
        return "".join(
            chr(ord("a") + (row * 26 + col) % 26) for col in range(self.columns)
        )

    def slice(self, row: int, start: int, end: int) -> str:
        return self.text(row)[start:end]

    def render(self, c: Constraints) -> Surface:
        self.widths.append(c.width)
        return Surface.of(
            [Line.from_text(self.text(row)) for row in range(self.row_count)],
            self.columns,
            pad=False,
        )


def test_an_x_view_shows_the_first_window_and_scrolls_to_the_far_right():
    child = Wide()
    scroll = ScrollPanel(child, height=3, axis="x")
    surface = scroll.render(Constraints(width=20))
    assert surface.width == 20 and surface.height == 3
    assert [row.text for row in surface] == [child.slice(i, 0, 20) for i in range(3)]
    assert scroll.viewport_width == 20 and scroll.total_columns == 200

    assert scroll.scroll_x(180) is True
    assert scroll.x_offset == 180
    surface = scroll.render(Constraints(width=20))
    assert [row.text for row in surface] == [child.slice(i, 180, 200) for i in range(3)]
    assert scroll.scroll_x(1000) is False  # already on the clamp
    assert scroll.x_offset == 180
    assert scroll.scroll_x(-1000) is True
    assert scroll.x_offset == 0


def test_a_200_column_child_reaches_its_last_column_in_an_80_column_view():
    child = Wide()
    scroll = ScrollPanel(child, height=3, axis="x")
    scroll.render(Constraints(width=80))
    assert scroll.scroll_x_to_end() is True
    assert scroll.x_offset == 120
    surface = scroll.render(Constraints(width=80))
    assert [row.text for row in surface] == [child.slice(i, 120, 200) for i in range(3)]


def test_both_axes_clamp_independently():
    child = Wide(rows=10)
    scroll = ScrollPanel(child, height=3, axis="both")
    scroll.render(Constraints(width=20))
    assert scroll.scroll_to_x(50) is True
    assert scroll.scroll_to(4) is True
    surface = scroll.render(Constraints(width=20))
    assert (scroll.x_offset, scroll.offset) == (50, 4)
    assert [row.text for row in surface] == [child.slice(4 + i, 50, 70) for i in range(3)]

    scroll.scroll_to_x(999)
    scroll.scroll_to(999)
    scroll.render(Constraints(width=20))
    assert (scroll.x_offset, scroll.offset) == (180, 7)
    scroll.scroll_to_x(0)
    assert scroll.offset == 7 and scroll.x_offset == 0


def test_an_x_view_keeps_every_child_row_at_its_natural_height():
    child = Wide(rows=4)
    surface = ScrollPanel(child, axis="x").render(Constraints(width=20))
    assert surface.height == 4
    assert [row.text for row in surface] == [child.slice(i, 0, 20) for i in range(4)]


def test_x_scrolling_accepts_a_target_before_the_first_render_and_clamps_then():
    child = Wide()
    scroll = ScrollPanel(child, height=3, axis="x")
    assert scroll.scroll_x_to_end() is False  # the extent is not known yet
    assert scroll.scroll_to_x(50) is True
    surface = scroll.render(Constraints(width=20))
    assert scroll.x_offset == 50
    assert [row.text for row in surface] == [child.slice(i, 50, 70) for i in range(3)]
    assert scroll.scroll_x_to_end() is True
    assert scroll.x_offset == 180


def test_the_horizontal_wheel_moves_only_an_x_scrolling_view():
    child = Wide()
    horizontal = ScrollPanel(child, height=3, axis="x")
    horizontal.render(Constraints(width=20))
    assert horizontal.handle(wheel(0, 0, "right")) is True
    assert horizontal.x_offset == 1
    assert horizontal.handle(wheel(0, 0, "left")) is True
    assert horizontal.x_offset == 0
    assert horizontal.handle(wheel(0, 0, "up")) is False
    assert horizontal.handle(wheel(0, 0, "down")) is False

    vertical = view()
    vertical.render(Constraints(width=10))
    assert vertical.handle(wheel(0, 0, "left")) is False
    assert vertical.handle(wheel(0, 0, "right")) is False

    both = ScrollPanel(Wide(rows=10), height=3, axis="both")
    both.render(Constraints(width=20))
    assert both.handle(wheel(0, 0, "right")) is True and both.x_offset == 1
    assert both.handle(wheel(0, 0, "down")) is True and both.offset == 1
    assert both.x_offset == 1


def test_a_y_only_view_declines_horizontal_scrolling():
    scroll = view()
    scroll.render(Constraints(width=10))
    assert scroll.scroll_x(1) is False
    assert scroll.scroll_to_x(5) is False
    assert scroll.scroll_x_to_end() is False


def test_the_bottom_bar_is_the_last_row_and_maps_the_x_thumb():
    child = Wide()
    scroll = ScrollPanel(child, height=3, axis="x", bar=True)
    rows = scroll.render(Constraints(width=10))
    assert len(rows) == 3
    assert [row.width for row in rows] == [10, 10, 10]
    assert [row.text for row in rows[:2]] == [child.slice(i, 0, 10) for i in range(2)]
    assert rows[2].text == GLYPHS.bar_full + GLYPHS.bar_empty * 9
    assert child.widths == [10]

    assert scroll.scroll_x_to_end() is True
    rows = scroll.render(Constraints(width=10))
    assert rows[2].text == GLYPHS.bar_empty * 9 + GLYPHS.bar_full


def test_both_bars_take_the_right_column_and_the_bottom_row():
    child = Wide(rows=10)
    scroll = ScrollPanel(child, height=4, axis="both", bar=True)
    rows = scroll.render(Constraints(width=10))
    assert len(rows) == 4
    assert all(row.width == 10 for row in rows)
    assert [row.text[:-1] for row in rows[:3]] == [child.slice(i, 0, 9) for i in range(3)]
    assert [row.segments[-1].text for row in rows[:3]] == [
        GLYPHS.bar_full,
        GLYPHS.bar_empty,
        GLYPHS.bar_empty,
    ]
    # The bottom row is the x track (first cell full at offset 0) plus the
    # vertical bar's corner cell.
    assert rows[3].text == GLYPHS.bar_full + GLYPHS.bar_empty * 9


def test_the_vertical_only_path_keeps_the_ellipsis_rule():
    scroll = ScrollPanel(Rows("abcdefghijkl"), height=2, bar=True)
    rows = scroll.render(Constraints(width=10))
    # The child renders at 9 columns; the old path clips with ``…``, never
    # with the horizontal hard cut.
    assert rows[0].text == "abcdefgh\u2026" + GLYPHS.bar_empty
    assert rows[1].text == " " * 9 + GLYPHS.bar_empty


def test_child_at_maps_both_offsets_and_owns_the_bars():
    child = Wide(rows=10)
    scroll = ScrollPanel(child, height=4, axis="both", bar=True)
    scroll.render(Constraints(width=20))
    scroll.scroll_to_x(50)
    scroll.scroll_to(4)
    scroll.render(Constraints(width=20))
    assert scroll.child_at(0, 0) == (child, 4, 50)
    assert scroll.child_at(1, 18) == (child, 5, 68)
    assert scroll.child_at(0, 19) is None  # right bar column
    assert scroll.child_at(3, 0) is None  # bottom bar row
    assert scroll.child_at(3, 19) is None  # corner
    assert scroll.child_at(0, 20) is None
    assert scroll.child_at(-1, 0) is None

    before = ScrollPanel(child, height=3, axis="x")
    assert before.child_at(0, 0) is None
