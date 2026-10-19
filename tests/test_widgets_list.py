"""Tests for motui.widgets.list (List).

The window over a long sequence -- only ``window`` item rows plus the two
counter rows, the cursor always inside and the window sliding by half a
window -- the controller verbs (``move`` clamps, ``home``/``end``, the
landing ``click``), ``activate``/``chosen`` read once, the prefix jump
``handle`` consumes, the three hover states with byte-for-byte returns, the
focus dim, and the empty-list degenerate.
"""

from dataclasses import replace

import pytest

from motui import FocusRing, Key
from motui.kernel.style import NONE, Style
from motui.kernel.theme import DEFAULT_THEME
from motui.testing import headless_tui
from motui.widgets.list import MARKER, List

#: Injected styles: a round trip through the theme fields, never a pinned
#: default color.
DIM_BAND = Style(fg="#333333")
#: The engaged surface: the cursor row's band and the pointer's are the one
#: ``ground_active`` token (D2), so both rows read it.
GROUND_ACTIVE = Style(fg="#0000ff", reverse=True)
BANDS = {"dim": DIM_BAND, "ground_active": GROUND_ACTIVE}


def _texts(rows) -> list[str]:
    """The plain texts of an already-rendered row list."""
    return [row.text for row in rows]


def _items(count: int) -> list[str]:
    return [f"item {i:04d}" for i in range(count)]


def test_a_thousand_items_render_the_window_and_the_counter_rows():
    lst = List(_items(1000), window=8)
    rows = lst.render(40)
    # Eight item rows and one "down" counter: the 992 rows below are one row.
    assert len(rows) == 9
    assert rows[0].text == f"{MARKER} item 0000"
    assert rows[1].text == "  item 0001"
    assert rows[-1].text == "\u2193 992 more"

    lst.index = 500  # the window follows: four rows on either side
    rows = lst.render(40)
    assert _texts(rows) == [
        "\u2191 496 more",
        "  item 0496",
        "  item 0497",
        "  item 0498",
        "  item 0499",
        f"{MARKER} item 0500",
        "  item 0501",
        "  item 0502",
        "  item 0503",
        "\u2193 496 more",
    ]
    # The window never grows past window + 2, whatever the list length.
    for index in (0, 3, 4, 5, 7, 8, 400, 993, 995, 999):
        lst.index = index
        rows = lst.render(40)
        assert len(rows) <= 10
        assert any(row.text.startswith(MARKER) for row in rows)

    lst.index = 999  # the last item: no window below, a full counter above
    assert _texts(lst.render(40)) == [
        "\u2191 992 more",
        "  item 0992",
        "  item 0993",
        "  item 0994",
        "  item 0995",
        "  item 0996",
        "  item 0997",
        "  item 0998",
        f"{MARKER} item 0999",
    ]


def test_a_short_list_renders_every_item_and_no_counters():
    lst = List(["one", "two", "three"], window=8)
    assert _texts(lst.render(20)) == [f"{MARKER} one", "  two", "  three"]
    assert lst.window == 8  # the window is a cap, not a floor


def test_move_clamps_at_the_ends_and_clears_the_pending_pick():
    lst = List(["a", "b", "c"], window=2)
    lst.chosen = "b"
    assert lst.move(1) is True and lst.index == 1
    lst.chosen = "c"
    assert lst.move(1) is True and lst.index == 2
    assert lst.chosen is None  # the step cleared it
    assert lst.move(1) is False and lst.index == 2  # the end is a real edge
    assert lst.move(-1) is True and lst.index == 1
    assert lst.move(-5) is True and lst.index == 0
    assert lst.move(-1) is False and lst.index == 0
    assert lst.move(0) is False
    # home/end are the edge jumps; both land the cursor and clear the pick.
    lst.chosen = "a"
    assert lst.end() is True and lst.index == 2 and lst.chosen is None
    assert lst.end() is False  # already there
    lst.chosen = "c"
    assert lst.home() is True and lst.index == 0 and lst.chosen is None
    assert lst.home() is False


def test_index_clamps_on_assignment_and_an_empty_list_has_none():
    lst = List(["a", "b", "c"])
    lst.index = 99
    assert lst.index == 2
    lst.index = -7
    assert lst.index == 0
    empty = List()
    empty.index = 5
    assert empty.index == 0
    assert empty.render(20) == []
    assert empty.move(1) is False and empty.home() is False and empty.end() is False
    assert empty.activate() is False and empty.chosen is None


def test_activate_lands_the_cursor_item_once():
    lst = List(["a", "b", "c"], window=2)
    lst.index = 1
    assert lst.activate() is True
    assert lst.chosen == "b"
    lst.chosen = None  # the host reads it once and resets it
    lst.index = 2
    assert lst.activate() is True and lst.chosen == "c"


def test_click_maps_a_rendered_row_onto_an_item_and_takes_it():
    lst = List(_items(100), window=4)
    lst.index = 50
    rows = lst.render(30)
    assert rows[0].text == "\u2191 48 more" and rows[-1].text == "\u2193 48 more"
    assert lst.click(0, 0) is False  # a counter row carries no item
    assert lst.click(len(rows) - 1, 0) is False
    assert lst.click(len(rows), 0) is False  # past the rendered rows
    assert lst.index == 50 and lst.chosen is None
    assert lst.click(2, 0) is True  # "item 0049": the column is ignored
    assert lst.index == 49 and lst.chosen == "item 0049"
    assert lst.click(2, 99) is True  # every column of an item row is the row
    lst.index = 0  # back to the top: no counter above
    rows = lst.render(30)
    assert rows[0].text == f"{MARKER} item 0000"
    assert lst.click(0, 0) is True and lst.index == 0 and lst.chosen == "item 0000"


def test_the_prefix_jump_scans_from_the_top_case_insensitively():
    lst = List(["alpha", "Beta", "beta two", "Gamma", "delta"], window=3)
    lst.index = 4
    assert lst.handle(Key("b", "b")) is True
    assert lst.index == 1 and lst.chosen is None  # "Beta" is the first b-item
    lst.index = 0
    assert lst.handle(Key("B", "B")) is True and lst.index == 1
    assert lst.handle(Key("d", "d")) is True and lst.index == 4
    assert lst.handle(Key("z", "z")) is True  # consumed even with no match
    assert lst.index == 4


def test_handle_consumes_its_own_keys_and_declines_the_hosts():
    lst = List(["a", "b", "c"], window=2)
    assert lst.handle(Key("down")) is True and lst.index == 1
    assert lst.handle(Key("up")) is True and lst.index == 0
    assert lst.handle(Key("end")) is True and lst.index == 2
    assert lst.handle(Key("home")) is True and lst.index == 0
    # The keys the list does not own stay the host's: the focus tier's tab,
    # the activation's enter, a control chord, a paste -- and "space", whose
    # name is not a single printable character (the jump rule reads names).
    from motui import Paste

    for event in (Key("enter"), Key("tab"), Key("c-n"), Key("space", " "), Paste("text")):
        assert lst.handle(event) is False
    assert lst.index == 0


def test_prefix_jump_off_leaves_printables_to_the_host():
    lst = List(["alpha", "beta"], prefix_jump=False)
    assert lst.handle(Key("b", "b")) is False
    assert lst.index == 0
    lst.prefix_jump = True
    assert lst.handle(Key("b", "b")) is True and lst.index == 1


def test_window_must_be_at_least_one_row():
    with pytest.raises(ValueError):
        List(["a"], window=0)
    with pytest.raises(ValueError):
        List(["a"], window=-3)


def test_hover_enters_moves_and_leaves_with_zero_bytes_on_exit():
    lst = List(["a", "b", "c"], window=2, theme=replace(DEFAULT_THEME, **BANDS))
    base = lst.render(20)
    base_bytes = [row.styled() for row in base]
    # Enter a non-cursor row: only that row repaints, in the engaged band.
    assert lst.hover_at(1, 0) is True
    hovered = lst.render(20)
    assert _texts(hovered) == _texts(base)
    assert hovered[1].styled() != base[1].styled()
    assert (hovered[1].segments[0].style, hovered[1].segments[1].style) == (
        GROUND_ACTIVE,
        GROUND_ACTIVE,
    )
    assert hovered[0].styled() == base_bytes[0]
    # Moving within the row changes nothing; leaving it does.
    assert lst.hover_at(1, 1) is False
    assert [row.styled() for row in lst.render(20)] == [
        base_bytes[0],
        hovered[1].styled(),
        base_bytes[2],
    ]
    assert lst.hover_at(-1, -1) is True
    assert [row.styled() for row in lst.render(20)] == base_bytes
    # A counter row carries no item: hovering it clears the marking.
    lst.index = 0
    assert lst.hover_at(0, 0) is True  # the cursor row
    assert lst.hover_at(2, 0) is True  # the "↓ N more" row: no item
    assert lst.render(20)[2].styled() == base_bytes[2]
    lst.hover_at(-1, -1)


def test_the_cursor_band_takes_the_hover_and_the_focus_rules():
    theme = replace(DEFAULT_THEME, **BANDS)
    lst = List(["a", "b"], window=2, theme=theme, focused=False)
    rows = lst.render(20)
    # Unfocused: the cursor row is the engaged band dimmed; the other row
    # keeps the default style.
    assert rows[0].segments[0].style == GROUND_ACTIVE.merge(DIM_BAND)
    assert rows[1].segments[0].style == NONE
    lst.focused = True
    assert lst.render(20)[0].segments[0].style == GROUND_ACTIVE
    # The pointer's row wears the same engaged band the cursor does (D2:
    # the keyboard cursor and the hovered row share the one ground_active
    # token), so a hover over the cursor row adds nothing and a hover over
    # the resting row gives it the cursor's own band.
    lst.hover_at(0, 0)
    assert lst.render(20)[0].segments[0].style == GROUND_ACTIVE
    lst.hover_at(1, 0)
    assert lst.render(20)[1].segments[0].style == GROUND_ACTIVE


def test_rows_are_fitted_to_the_width():
    lst = List(["a very long item text", "b"], window=2)
    rows = lst.render(10)
    assert all(row.width <= 10 for row in rows)
    assert rows[0].text.endswith("\u2026") and rows[0].width == 10


def test_the_ground_style_resolves_and_rests_under_every_row():
    ground = Style(fg="#101010")
    lst = List(["a", "b", "c", "d"], window=2, ground_style=ground, focused=True)
    rows = lst.render(20)
    # Every row rests on the ground: the resting row, the counter row (the
    # dim text style riding on top of it) and the cursor row, whose engaged
    # band swaps the ground out from under it.
    assert rows[1].segments[0].style == ground
    assert rows[1].segments[1].style == ground
    assert rows[2].text.startswith("\u2193")
    assert rows[2].segments[0].style == ground.merge(DEFAULT_THEME.dim)
    assert rows[0].segments[0].style == DEFAULT_THEME.ground_active
    # the theme field is the fallback the explicit style wins over
    themed = List(["a", "b"], window=2, theme=replace(DEFAULT_THEME, ground=ground))
    assert themed.render(20)[1].segments[0].style == ground


def test_the_focus_ring_routes_its_keys_to_the_list():
    lst = List(["a", "b", "c"], window=2)
    ring = FocusRing([lst])
    assert ring.focused is lst
    assert ring.handle(Key("down")) is True and lst.index == 1
    assert ring.handle(Key("down")) is True and lst.index == 2
    assert ring.handle(Key("enter")) is True
    assert lst.chosen == "c"  # the host reads the pick exactly once
    lst.chosen = None
    assert ring.handle(Key("home")) is True and lst.index == 0  # the list's own handle


def test_a_real_hit_test_click_lands_on_the_item_row():
    tui = headless_tui(24, 12)
    lst = List(_items(50), window=5)
    block = tui.add(lst)
    tui.paint()
    hit = tui.hit_test(3, 1)  # the block's second row: the second item
    assert hit is not None and hit.block is block and (hit.row, hit.col) == (1, 3)
    assert hit.block.component.click(hit.row, hit.col) is True
    assert lst.index == 1 and lst.chosen == "item 0001"
    miss = tui.hit_test(3, 5)  # the "↓ N more" counter row
    assert miss is not None and miss.block is block
    assert miss.block.component.click(miss.row, miss.col) is False
    assert lst.index == 1


def test_the_mark_column_appears_with_the_first_mark_and_leaves_the_rows_alone():
    lst = List(["alpha", "beta", "gamma"], window=4)
    plain = _texts(lst.render(30))
    assert not any("[" in row for row in plain)  # unmarked: the bytes the list always had
    assert lst.toggle() is True and list(lst.marked) == [0]
    marked = _texts(lst.render(30))
    assert marked[0] == "\u25b8 [x] alpha"  # the mark rides after the cursor's marker
    assert marked[1] == "  [ ] beta"
    lst.toggle()
    assert _texts(lst.render(30)) == plain  # a cleared set is the old rows again


def test_the_revision_names_the_marks_and_the_chosen_semantics_hold():
    lst = List(["alpha", "beta"], window=2)
    before = lst.revision()
    lst.activate()  # a pick is pending
    lst.toggle()
    assert lst.revision() != before  # the marks are a row input
    assert lst.chosen == "alpha"  # and the mark gesture left the pick alone
    lst.chosen = None
    assert List([]).toggle() is False  # no cursor: no mark, the empty-list rule
