"""ScrollPanel: a fixed-height window over a child's rows."""

import pytest

from motui.kernel.geom import Pos
from motui.kernel.cell import Line, Surface
from motui.kernel.document import descend_chain
from motui.kernel.events import KeyEvent
from motui.kernel.glyphs import GLYPHS
from motui.kernel.layout import Constraints, Scroll
from motui.widgets import Input, ScrollPanel
from tests.testing import Rows, key, many, texts, wheel


def view(rows=10, height=3, **kwargs) -> ScrollPanel:
    return ScrollPanel(Rows(*many(rows)), height=height, **kwargs)


def test_a_fixed_height_clips_the_child_to_one_window():
    assert texts(view(), 10) == ["r0", "r1", "r2"]


def test_the_scroll_panel_mounts_its_child_in_the_tree():
    child = Input("hello")
    scroll = ScrollPanel(child, height=2)

    assert scroll.children == [child]
    assert child.parent is scroll
    assert list(scroll.walk()) == [scroll, child]
    assert "hello" in texts(scroll, 10)[0]


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
    assert scroll.on_key(key("down")) is True and scroll.offset == 1
    assert scroll.on_key(key("up")) is True and scroll.offset == 0
    assert scroll.on_key(key("up")) is False
    assert scroll.on_key(key("page_down")) is True and scroll.offset == 3
    assert scroll.on_key(key("page_up")) is True and scroll.offset == 0
    assert scroll.on_key(key("end")) is True and scroll.offset == 7
    assert scroll.on_key(key("home")) is True and scroll.offset == 0


def test_the_vertical_wheel_scrolls_and_other_events_decline():
    scroll = view()
    scroll.render(Constraints(width=10))
    assert scroll.on_mouse(wheel(0, 0, "down")) is True and scroll.offset == 1
    assert scroll.on_mouse(wheel(0, 0, "up")) is True and scroll.offset == 0
    assert scroll.on_mouse(wheel(0, 0, "left")) is False
    assert scroll.on_key(key("enter")) is False


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
    assert scroll.on_drag(Pos(x=9, y=0), "press") is True
    assert scroll.on_drag(Pos(x=9, y=1), "motion") is True and scroll.offset == 3
    assert scroll.on_drag(Pos(x=9, y=2), "motion") is True and scroll.offset == 6
    assert scroll.on_drag(Pos(x=9, y=2), "release") is True
    assert scroll.on_drag(Pos(x=9, y=1), "motion") is False

    scroll.scroll_to(0)
    assert scroll.on_drag(Pos(x=9, y=3), "press") is True and scroll.offset == 4  # below: a page down
    assert scroll.on_drag(Pos(x=9, y=0), "press") is True and scroll.offset == 0  # above: a page up
    assert scroll.on_drag(Pos(x=8, y=0), "press") is False  # content column, not the bar
    assert scroll.on_click(Pos(x=8, y=0)) is False
    assert scroll.on_click(Pos(x=9, y=0)) is True


def test_a_view_without_a_bar_or_a_thumb_declines_drags():
    plain = view(10, 4)
    plain.render(Constraints(width=10))
    assert plain.on_drag(Pos(x=9, y=0), "press") is False
    assert plain.on_click(Pos(x=9, y=0)) is False

    short = view(2, 4, bar=True)
    short.render(Constraints(width=10))
    assert short.on_drag(Pos(x=9, y=0), "press") is False  # content fits: no thumb
    assert short.on_click(Pos(x=9, y=0)) is True  # the bar column is still the view's


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


def test_the_panel_exposes_a_two_axis_non_sticky_scroll_value():
    child = Wide(rows=10)
    scroll = ScrollPanel(child, height=3, axis="both")
    scroll.render(Constraints(width=20))
    value = scroll.scroll
    assert isinstance(value, Scroll)
    assert (value.y.offset, value.y.content, value.y.viewport) == (
        scroll.offset,
        scroll.total_rows,
        scroll.viewport_height,
    )
    assert (value.x.offset, value.x.content, value.x.viewport) == (
        scroll.x_offset,
        scroll.total_columns,
        scroll.viewport_width,
    )
    # The view must never inherit Scroll()'s tail-following y default.
    assert value.y.sticky is False and value.x.sticky is False


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
    assert horizontal.on_mouse(wheel(0, 0, "right")) is True
    assert horizontal.x_offset == 1
    assert horizontal.on_mouse(wheel(0, 0, "left")) is True
    assert horizontal.x_offset == 0
    assert horizontal.on_mouse(wheel(0, 0, "up")) is False
    assert horizontal.on_mouse(wheel(0, 0, "down")) is False

    vertical = view()
    vertical.render(Constraints(width=10))
    assert vertical.on_mouse(wheel(0, 0, "left")) is False
    assert vertical.on_mouse(wheel(0, 0, "right")) is False

    both = ScrollPanel(Wide(rows=10), height=3, axis="both")
    both.render(Constraints(width=20))
    assert both.on_mouse(wheel(0, 0, "right")) is True and both.x_offset == 1
    assert both.on_mouse(wheel(0, 0, "down")) is True and both.offset == 1
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


class RecordingLeaf(Wide):
    """A wide leaf that records the child coordinates a hit resolves to."""

    def __init__(self, columns: int = 200, rows: int = 10) -> None:
        super().__init__(columns, rows)
        self.hits: list[tuple[int, int]] = []

    def child_at(self, row: int, col: int) -> None:
        self.hits.append((row, col))
        return None


def test_a_hit_descends_at_the_scrolled_horizontal_cell():
    child = RecordingLeaf()
    scroll = ScrollPanel(child, height=3, axis="both")
    scroll.render(Constraints(width=20))
    scroll.scroll_to_x(50)
    scroll.scroll_to(4)
    scroll.render(Constraints(width=20))

    chain = descend_chain(scroll, 1, 7)
    assert chain[0] == (scroll, 1, 7)
    assert chain[-1] == (child, 5, 57)
    assert child.hits == [(5, 57)]  # the leaf sees panel col + x offset


def test_a_hit_maps_the_vertical_offset_into_the_child():
    child = RecordingLeaf(rows=10)
    scroll = ScrollPanel(child, height=3)
    scroll.render(Constraints(width=20))
    scroll.scroll_to(6)
    scroll.render(Constraints(width=20))

    chain = descend_chain(scroll, 2, 3)
    assert chain[0] == (scroll, 2, 3)
    assert chain[-1] == (child, 8, 3)
    assert child.hits == [(8, 3)]


def test_the_bars_never_route_a_hit_into_the_child():
    child = RecordingLeaf(rows=10)
    scroll = ScrollPanel(child, height=4, axis="both", bar=True)
    scroll.render(Constraints(width=20))
    scroll.scroll_to_x(30)
    scroll.scroll_to(2)
    scroll.render(Constraints(width=20))

    # A content cell maps through both offsets; the bar cell and row belong
    # to the panel, so the descend chain stops there.
    assert descend_chain(scroll, 0, 0)[-1] == (child, 2, 30)
    assert descend_chain(scroll, 0, 19) == ((scroll, 0, 19),)  # right bar column
    assert descend_chain(scroll, 3, 0) == ((scroll, 3, 0),)  # bottom bar row
    assert descend_chain(scroll, 3, 19) == ((scroll, 3, 19),)  # corner
    assert child.hits == [(2, 30)]
    assert scroll.on_click(Pos(x=0, y=3)) is True  # the bottom bar still takes a click
    assert child.hits == [(2, 30)]


# -- the 2.0 keymap and action surface ----------------------------------------


def test_scroll_actions_drive_the_window_by_name():
    scroll = view()
    scroll.render(Constraints(width=10))
    assert scroll.on_action("next") is True and scroll.offset == 1
    assert scroll.on_action("prev") is True and scroll.offset == 0
    assert scroll.on_action("prev") is False  # clamped at the top
    assert scroll.on_action("page_next") is True and scroll.offset == 3
    assert scroll.on_action("page_prev") is True and scroll.offset == 0
    assert scroll.on_action("last") is True and scroll.offset == 7
    assert scroll.on_action("first") is True and scroll.offset == 0
    assert scroll.on_action("first") is False
    assert scroll.on_action("activate") is False
    assert scroll.on_action("nope") is False
    assert ScrollPanel.keymap["page_down"] == "page_next"
    assert not hasattr(ScrollPanel, "handle")


def test_the_key_hook_routes_through_the_named_actions():
    for name in ("up", "down", "page_up", "page_down", "home", "end"):
        action = ScrollPanel.keymap[name]
        keyed, named = view(), view()
        keyed.render(Constraints(width=10))
        named.render(Constraints(width=10))
        assert keyed.on_key(key(name)) is named.on_action(action)
        assert keyed.offset == named.offset
    assert view().on_key(key("enter")) is False
    assert view().on_key(key("left")) is False


def test_the_key_hook_declines_a_release_and_the_wheel_hook_the_other_axis():
    scroll = view()
    scroll.render(Constraints(width=10))
    assert scroll.on_key(KeyEvent("down", kind="release")) is False
    assert scroll.on_mouse(wheel(0, 0, "down")) is True and scroll.offset == 1
    assert scroll.on_mouse(wheel(0, 0, "up")) is True and scroll.offset == 0
    assert scroll.on_mouse(wheel(0, 0, "left")) is False
    assert scroll.on_mouse(wheel(0, 0, "up")) is False  # clamped at the top
    horizontal = ScrollPanel(Wide(), height=3, axis="x")
    horizontal.render(Constraints(width=20))
    assert horizontal.on_mouse(wheel(0, 0, "up")) is False
    assert horizontal.on_mouse(wheel(0, 0, "right")) is True
    assert horizontal.x_offset == 1


def test_the_horizontal_scroll_actions_move_one_column():
    scroll = ScrollPanel(Wide(), height=3, axis="x")
    scroll.render(Constraints(width=20))
    assert scroll.on_action("scroll_next") is True and scroll.x_offset == 1
    assert scroll.on_action("scroll_prev") is True and scroll.x_offset == 0
    assert scroll.on_action("scroll_prev") is False


def test_an_instance_scroll_keymap_rebind_is_private_to_the_instance():
    scroll, other = view(), view()
    scroll.render(Constraints(width=10))
    other.render(Constraints(width=10))
    scroll.keymap["j"] = "next"
    assert "j" not in ScrollPanel.keymap
    assert "j" not in other.keymap
    assert scroll.on_key(key("j", "j")) is True and scroll.offset == 1
    assert other.on_key(key("j", "j")) is False and other.offset == 0


def test_the_scroll_panel_declares_its_capabilities():
    scroll = view()
    assert (scroll.focusable, scroll.clickable, scroll.hoverable, scroll.activatable) == (
        True,
        True,
        False,
        False,
    )
    assert scroll.take() is None
