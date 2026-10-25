"""ScrollView: a fixed-height window over a child's rows."""

from motui.kernel.glyphs import GLYPHS
from motui.widgets import ScrollView

from tests.testing import Rows, key, many, texts, wheel


def view(rows=10, height=3, **kwargs) -> ScrollView:
    return ScrollView(Rows(*many(rows)), height=height, **kwargs)


def test_a_fixed_height_clips_the_child_to_one_window():
    assert texts(view(), 10) == ["r0", "r1", "r2"]


def test_a_predicted_offset_paints_the_matching_slice_and_clamps():
    scroll = ScrollView(Rows(*many(10)), height=3, offset=4)
    assert texts(scroll, 10) == ["r4", "r5", "r6"]
    far = ScrollView(Rows(*many(10)), height=3, offset=99)
    assert texts(far, 10) == ["r7", "r8", "r9"]
    assert far.offset == 7


def test_a_short_child_is_padded_to_the_fixed_height():
    assert texts(ScrollView(Rows("a"), height=3), 10) == ["a", "", ""]


def test_height_none_shows_every_row_and_never_scrolls():
    scroll = ScrollView(Rows(*many(10)))
    assert len(texts(scroll, 10)) == 10
    assert scroll.scroll_down(1) is False
    assert scroll.scroll_to(4) is False


def test_scroll_to_reports_only_real_moves_and_clamps():
    scroll = view()
    assert scroll.scroll_to(4) is True
    scroll.render(10)
    assert scroll.offset == 4
    assert scroll.scroll_to(4) is False
    assert scroll.scroll_to(99) is True and scroll.offset == 7
    assert scroll.scroll_up(9) is True and scroll.offset == 0
    assert scroll.scroll_up(1) is False


def test_the_page_keys_move_one_window_and_the_edges_jump():
    scroll = view()
    scroll.render(10)
    assert scroll.handle(key("down")) is True and scroll.offset == 1
    assert scroll.handle(key("up")) is True and scroll.offset == 0
    assert scroll.handle(key("up")) is False
    assert scroll.handle(key("page_down")) is True and scroll.offset == 3
    assert scroll.handle(key("page_up")) is True and scroll.offset == 0
    assert scroll.handle(key("end")) is True and scroll.offset == 7
    assert scroll.handle(key("home")) is True and scroll.offset == 0


def test_the_vertical_wheel_scrolls_and_other_events_decline():
    scroll = view()
    scroll.render(10)
    assert scroll.handle(wheel(0, 0, "down")) is True and scroll.offset == 1
    assert scroll.handle(wheel(0, 0, "up")) is True and scroll.offset == 0
    assert scroll.handle(wheel(0, 0, "left")) is False
    assert scroll.handle(key("enter")) is False


def test_reveal_moves_the_minimum_and_declines_when_visible():
    scroll = view()
    assert scroll.reveal(1) is False
    scroll.render(10)
    assert scroll.reveal(5) is True and scroll.offset == 3
    assert scroll.reveal(3) is False
    assert scroll.reveal(0) is True and scroll.offset == 0
    assert scroll.reveal(2) is False


def test_child_at_maps_visible_cells_through_the_painted_offset():
    child = Rows(*many(10))
    scroll = ScrollView(child, height=3, offset=2)
    scroll.render(10)
    assert scroll.child_at(0, 0) == (child, 2, 0)
    assert scroll.child_at(2, 9) == (child, 4, 9)
    assert scroll.child_at(3, 0) is None
    assert scroll.child_at(-1, 0) is None


def test_the_bar_reserves_the_last_column_and_paints_track_and_thumb():
    child = Rows(*many(10))
    scroll = ScrollView(child, height=4, bar=True)
    rows = scroll.render(10)
    assert all(row.width == 10 for row in rows)
    assert rows[0].segments[-1].text == GLYPHS.bar_full
    assert rows[1].segments[-1].text == GLYPHS.bar_full
    assert rows[2].segments[-1].text == GLYPHS.bar_empty
    assert scroll.child_at(0, 9) is None
    assert scroll.child_at(0, 8) == (child, 0, 8)


def test_the_bar_thumb_drags_and_the_track_pages():
    scroll = view(10, 4, bar=True)
    scroll.render(10)
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
    plain.render(10)
    assert plain.drag(0, 9, "press") is False
    assert plain.click(0, 9) is False

    short = view(2, 4, bar=True)
    short.render(10)
    assert short.drag(0, 9, "press") is False  # content fits: no thumb
    assert short.click(0, 9) is True  # the bar column is still the view's


def test_a_child_that_shrinks_pulls_the_offset_back_in_range():
    child = Rows(*many(10))
    scroll = ScrollView(child, height=3)
    scroll.render(10)
    assert scroll.scroll_to(7) is True
    child.texts = ["only"]
    assert texts(scroll, 10) == ["only", "", ""]
    assert scroll.offset == 0
