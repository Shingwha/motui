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

from motui import FocusManager, KeyEvent
from motui.kernel import CursorWindow
from motui.kernel.glyphs import CURSOR
from motui.kernel.lines import Segment
from motui.kernel.style import NONE, Style
from motui.kernel.text import visible_width
from motui.kernel.theme import DEFAULT_THEME
from motui.testing import headless_tui
from motui.widgets import RowBands
from motui.widgets.list import List

#: Injected styles: a round trip through the theme fields, never a pinned
#: default color.
DIM_BAND = Style(fg="#333333")
#: The engaged surface: the keyboard cursor row's band (``ground_active``).
GROUND_ACTIVE = Style(fg="#0000ff", reverse=True)
#: The pointer band: the hovered row's own token (D3), kept distinct from the
#: cursor's so the rehoming is observable.
HOVER = Style(fg="#00ff00", reverse=True)
BANDS = {"dim": DIM_BAND, "ground_active": GROUND_ACTIVE, "hover": HOVER}


def _texts(rows) -> list[str]:
    """The plain texts of an already-rendered row list."""
    return [row.text for row in rows]


def _banded(row, text: str, band: Style) -> None:
    """Assert an engaged row: its own text, the band merged under its cells.

    The band hugs the row's own cells -- a pill behind the text, never a
    ribbon across the pane -- so the row ends at its own text and every
    segment carries the band underneath its own (plain) style.
    """
    assert row.text == text
    assert row.width == len(text)
    assert all(seg.style == band for seg in row.segments)


def _items(count: int) -> list[str]:
    return [f"item {i:04d}" for i in range(count)]


def test_a_thousand_items_render_the_window_and_the_counter_rows():
    lst = List(_items(1000), window=8)
    rows = lst.render(40)
    # Eight item rows and one "down" counter: the 992 rows below are one row.
    assert len(rows) == 9
    # The unfocused cursor row's band is the ground_active merged with the
    # theme's dim -- a pill behind the row's own cells, no trailing pad.
    _banded(rows[0], f"{CURSOR} item 0000", DEFAULT_THEME.dim)
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
        f"{CURSOR} item 0500",
        "  item 0501",
        "  item 0502",
        "  item 0503",
        "\u2193 496 more",
    ]
    _banded(rows[5], f"{CURSOR} item 0500", DEFAULT_THEME.dim)
    # The window never grows past window + 2, whatever the list length.
    for index in (0, 3, 4, 5, 7, 8, 400, 993, 995, 999):
        lst.index = index
        rows = lst.render(40)
        assert len(rows) <= 10
        assert any(row.text.startswith(CURSOR) for row in rows)

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
        f"{CURSOR} item 0999",
    ]
    _banded(lst.render(40)[-1], f"{CURSOR} item 0999", DEFAULT_THEME.dim)


def test_a_short_list_renders_every_item_and_no_counters():
    lst = List(["one", "two", "three"], window=8)
    assert _texts(lst.render(20)) == [
        f"{CURSOR} one",
        "  two",
        "  three",
    ]
    _banded(lst.render(20)[0], f"{CURSOR} one", DEFAULT_THEME.dim)
    assert lst.window == 8  # the window is a cap, not a floor


def test_move_clamps_at_the_ends_and_clears_the_pending_pick():
    lst = List(["a", "b", "c"], window=2)
    assert lst.activate() is True and lst.take_result() == "a"
    assert lst.move(1) is True and lst.index == 1
    assert lst.activate() is True and lst.take_result() == "b"
    assert lst.move(1) is True and lst.index == 2
    assert lst.take_result() is None  # the step cleared it
    assert lst.move(1) is False and lst.index == 2  # the end is a real edge
    assert lst.move(-1) is True and lst.index == 1
    assert lst.move(-5) is True and lst.index == 0
    assert lst.move(-1) is False and lst.index == 0
    assert lst.move(0) is False
    # home/end are the edge jumps; both land the cursor and clear the pick.
    assert lst.activate() is True
    assert lst.end() is True and lst.index == 2 and lst.take_result() is None
    assert lst.end() is False  # already there
    assert lst.activate() is True
    assert lst.home() is True and lst.index == 0 and lst.take_result() is None
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
    assert empty.activate() is False and empty.take_result() is None


def test_activate_lands_the_cursor_item_once():
    lst = List(["a", "b", "c"], window=2)
    lst.index = 1
    assert lst.activate() is True
    assert lst.take_result() == "b"
    assert lst.take_result() is None  # read-once
    lst.index = 2
    assert lst.activate() is True and lst.take_result() == "c"


def test_click_maps_a_rendered_row_onto_an_item_and_takes_it():
    lst = List(_items(100), window=4)
    lst.index = 50
    rows = lst.render(30)
    assert rows[0].text == "\u2191 48 more" and rows[-1].text == "\u2193 48 more"
    assert lst.click(0, 0) is False  # a counter row carries no item
    assert lst.click(len(rows) - 1, 0) is False
    assert lst.click(len(rows), 0) is False  # past the rendered rows
    assert lst.index == 50 and lst.take_result() is None
    assert lst.click(2, 0) is True  # "item 0049": the column is ignored
    assert lst.index == 49 and lst.take_result() == "item 0049"
    assert lst.click(2, 99) is True  # every column of an item row is the row
    assert lst.take_result() == "item 0048"  # the window slid with the cursor
    lst.index = 0  # back to the top: no counter above
    rows = lst.render(30)
    _banded(rows[0], f"{CURSOR} item 0000", DEFAULT_THEME.dim)
    assert lst.click(0, 0) is True and lst.index == 0
    assert lst.take_result() == "item 0000"


def test_the_prefix_jump_scans_from_the_top_case_insensitively():
    lst = List(["alpha", "Beta", "beta two", "Gamma", "delta"], window=3)
    lst.index = 4
    assert lst.activate() is True
    assert lst.handle(KeyEvent("b", "b")) is True
    assert lst.index == 1 and lst.take_result() is None  # "Beta" is the first b-item
    lst.index = 0
    assert lst.handle(KeyEvent("B", "B")) is True and lst.index == 1
    assert lst.handle(KeyEvent("d", "d")) is True and lst.index == 4
    assert lst.handle(KeyEvent("z", "z")) is True  # consumed even with no match
    assert lst.index == 4


def test_handle_consumes_its_own_keys_and_declines_the_hosts():
    lst = List(["a", "b", "c"], window=2)
    assert lst.handle(KeyEvent("down")) is True and lst.index == 1
    assert lst.handle(KeyEvent("up")) is True and lst.index == 0
    assert lst.handle(KeyEvent("end")) is True and lst.index == 2
    assert lst.handle(KeyEvent("home")) is True and lst.index == 0
    # The keys the list does not own stay the host's: the focus tier's tab,
    # the activation's enter, a control chord, a paste -- and "space", whose
    # name is not a single printable character (the jump rule reads names).
    from motui import PasteEvent

    for event in (KeyEvent("enter"), KeyEvent("tab"), KeyEvent("c-n"), KeyEvent("space", " "), PasteEvent("text")):
        assert lst.handle(event) is False
    assert lst.index == 0


def test_prefix_jump_off_leaves_printables_to_the_host():
    lst = List(["alpha", "beta"], prefix_jump=False)
    assert lst.handle(KeyEvent("b", "b")) is False
    assert lst.index == 0
    lst.prefix_jump = True
    assert lst.handle(KeyEvent("b", "b")) is True and lst.index == 1


def test_window_must_be_at_least_one_row():
    with pytest.raises(ValueError):
        List(["a"], window=0)
    with pytest.raises(ValueError):
        List(["a"], window=-3)


def test_hover_enters_moves_and_leaves_with_zero_bytes_on_exit():
    lst = List(["a", "b", "c"], window=2, theme=replace(DEFAULT_THEME, **BANDS))
    base = lst.render(20)
    base_bytes = [row.styled() for row in base]
    # Enter a non-cursor row: only that row repaints, in the pointer's own
    # band (D3: the hovered row reads ``hover``, not the cursor's
    # ``ground_active``).
    assert lst.hover_at(1, 0) is True
    hovered = lst.render(20)
    # The row's own text is untouched; the band rides under its cells only.
    assert [row.text.rstrip() for row in hovered] == [
        row.text.rstrip() for row in base
    ]
    _banded(hovered[1], base[1].text, HOVER)
    assert hovered[1].styled() != base[1].styled()
    assert (hovered[1].segments[0].style, hovered[1].segments[1].style) == (
        HOVER,
        HOVER,
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
    # D3: the pointer's row wears its own ``hover`` token, never the cursor's
    # ``ground_active`` -- one token per signal, so a host that themes the
    # cursor row alone never moves the hover.
    lst.hover_at(1, 0)
    assert lst.render(20)[1].segments[0].style == HOVER
    assert lst.render(20)[0].segments[0].style == GROUND_ACTIVE  # the cursor row: untouched


def test_a_background_band_keeps_the_unfocused_cursor_undimmed():
    """SGR ``dim`` is a foreground attribute: it never rides a background.

    A background band is its own position signal; merging ``dim`` onto it
    would dim the text into the surface instead of weakening the band.
    """
    background = Style(bg="#1b3a5b")
    themed = replace(DEFAULT_THEME, ground_active=background)
    lst = List(["a", "b"], window=2, theme=themed, focused=False)
    assert lst.render(20)[0].segments[0].style == background
    assert lst.render(20)[0].segments[0].style.dim is False
    # Without a background the dim merge is exactly as it was.
    backgroundless = replace(DEFAULT_THEME, ground_active=Style(fg="#0000ff"))
    dimmed = List(["a"], window=1, theme=backgroundless, focused=False).render(20)[0]
    assert dimmed.segments[0].style == Style(fg="#0000ff", dim=True)


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
    ring = FocusManager([lst])
    ring.focus_next()
    assert ring.focused is lst
    assert ring.handle(KeyEvent("down")) is True and lst.index == 1
    assert ring.handle(KeyEvent("down")) is True and lst.index == 2
    assert ring.handle(KeyEvent("enter")) is True
    assert lst.take_result() == "c"  # the host reads the pick exactly once
    assert ring.handle(KeyEvent("home")) is True and lst.index == 0  # the list's own handle


def test_a_real_hit_click_lands_on_the_item_row():
    tui = headless_tui(24, 12)
    lst = List(_items(50), window=5)
    block = tui.add(lst)
    tui.paint()
    hit = tui.hit(3, 1)  # the block's second row: the second item
    assert hit is not None and hit.block is block and (hit.row, hit.col) == (1, 3)
    assert hit.block.component.click(hit.row, hit.col) is True
    assert lst.index == 1 and lst.take_result() == "item 0001"
    miss = tui.hit(3, 5)  # the "↓ N more" counter row
    assert miss is not None and miss.block is block
    assert miss.block.component.click(miss.row, miss.col) is False
    assert lst.index == 1


def test_the_mark_column_appears_with_the_first_mark_and_leaves_the_rows_alone():
    lst = List(["alpha", "beta", "gamma"], window=4)
    plain = _texts(lst.render(30))
    assert not any("[" in row for row in plain)  # unmarked: the bytes the list always had
    assert lst.toggle() is True and list(lst.marked) == [0]
    marked = _texts(lst.render(30))
    # The cursor row's band hugs its cells, so the row ends at its own text.
    assert marked[0] == "\u25b8 [x] alpha"  # the mark rides after the cursor's marker
    assert marked[1] == "  [ ] beta"
    _banded(lst.render(30)[0], "\u25b8 [x] alpha", DEFAULT_THEME.dim)
    lst.toggle()
    assert _texts(lst.render(30)) == plain  # a cleared set is the old rows again


def test_the_revision_names_the_marks_and_the_result_semantics_hold():
    lst = List(["alpha", "beta"], window=2)
    before = lst.revision()
    lst.activate()  # a pick is pending
    lst.toggle()
    assert lst.revision() != before  # the marks are a row input
    assert lst.take_result() == "alpha"  # and the mark gesture left the pick alone
    assert List([]).toggle() is False  # no cursor: no mark, the empty-list rule


# --- the glyph parameters ------------------------------------------------------------


def test_the_glyph_parameters_reach_the_rows():
    lst = List(["a", "b"], window=1, marker=">", more_up="^", more_down="v")
    assert _texts(lst.render(20)) == ["> a", "v 1 more"]
    lst.index = 1
    assert _texts(lst.render(20)) == ["^ 1 more", "> b"]
    # The same top and bottom glyph still tell the counters apart (the row
    # plan carries private tokens, not the glyphs).
    same = List(["a", "b"], window=1, more_up="*", more_down="*")
    assert _texts(same.render(20)) == [f"{CURSOR} a", "* 1 more"]
    assert same.click(1, 0) is False  # still a counter row, not an item


def test_an_empty_marker_seats_nothing():
    lst = List(["alpha", "beta"], window=2, marker="")
    rows = lst.render(20)
    assert _texts(rows) == ["alpha", "beta"]
    assert rows[0].segments[0].text == ""  # no dangling separator column
    assert rows[1].segments[0].text == ""


def test_a_wide_marker_keeps_the_labels_in_one_column():
    """The seat is ``visible_width(marker) + 1``: a CJK glyph takes three
    columns, where a ``len`` measure would have taken two."""
    lst = List(["alpha", "beta"], window=2, marker="\u6811")
    rows = lst.render(20)
    assert _texts(rows) == ["\u6811 alpha", "   beta"]
    assert visible_width(rows[0].segments[0].text) == 3
    assert visible_width(rows[1].segments[0].text) == 3
    # The character offsets differ (one CJK glyph is one code point), the
    # display columns agree -- which is what lines the labels up.
    left = rows[0].text[: rows[0].text.index("alpha")]
    right = rows[1].text[: rows[1].text.index("beta")]
    assert visible_width(left) == visible_width(right) == 3


def test_the_mark_pair_is_padded_to_its_wider_member():
    lst = List(["alpha", "beta"], window=2, mark_pair=("[x]", "\u6811"))
    lst.toggle()  # alpha is marked
    rows = lst.render(20)
    assert rows[0].text == "\u25b8 [x] alpha"
    assert rows[1].text == "  \u6811  beta"  # the narrow member pads to four columns
    assert visible_width(rows[0].segments[1].text) == 4
    assert visible_width(rows[1].segments[1].text) == 4
    lst.index = 1
    lst.toggle()  # beta is marked now, and it is also the cursor row
    rows = lst.render(20)
    assert rows[1].text == "\u25b8 [x] beta"


def test_an_empty_mark_pair_collapses_the_column():
    lst = List(["alpha", "beta"], window=2, mark_pair=("", ""))
    plain = _texts(lst.render(20))
    lst.toggle()
    assert _texts(lst.render(20)) == plain  # the mark is invisible, zero columns


def test_every_glyph_parameter_is_a_revision_input():
    lst = List(["a"])
    for name, value in (
        ("marker", ">"),
        ("more_up", "^"),
        ("more_down", "v"),
        ("mark_pair", ("[X]", "[ ]")),
    ):
        before = lst.revision()
        setattr(lst, name, value)
        assert lst.revision() != before, name


# --- the shared window and the disabled surface --------------------------------------


def test_the_render_window_is_the_centred_cursor_window():
    """The one CursorWindow value keeps the window List always rendered."""
    for index, count, window in ((0, 10, 4), (5, 10, 4), (9, 10, 4), (50, 100, 7)):
        lst = List(_items(count), window=window)
        lst.index = index
        assert lst._visible_range() == CursorWindow(
            index=index, count=count, cap=window, center=True
        ).range()
        # The emitted rows agree: a counter above/below only when the window
        # does not reach the edge, and ``window`` item rows in between.
        rows = lst.render(30)
        items = [row for row in rows if not row.text.endswith(" more")]
        assert len(items) == window


def test_disabled_items_are_visible_but_skipped_and_refused():
    lst = List(["a", "b", "c", "d"], window=4, disabled_items=(1, 2))
    rows = lst.render(20)
    assert [row.text for row in rows] == ["\u25b8 a", "  b", "  c", "  d"]
    assert lst.move(1) is True and lst.index == 3  # 1 and 2 are stepped over
    assert lst.move(1) is False and lst.index == 3  # the edge: no landing left
    assert lst.move(-1) is True and lst.index == 0
    lst.index = 1
    assert lst.activate() is False and lst.take_result() is None
    assert lst.toggle() is False
    assert lst.click(1, 0) is False and lst.take_result() is None
    assert lst.click(3, 0) is True and lst.take_result() == "d"
    # home/end skip the disabled rows too
    lst.index = 3
    assert lst.home() is True and lst.index == 0
    lst.index = 0
    assert lst.end() is True and lst.index == 3


def test_a_disabled_list_refuses_every_gesture_but_still_renders():
    lst = List(["a", "b"], window=2, disabled=True)
    assert lst.move(1) is False and lst.home() is False and lst.end() is False
    assert lst.activate() is False and lst.take_result() is None
    assert lst.click(0, 0) is False and lst.toggle() is False
    assert lst.handle(KeyEvent("down")) is False
    assert [row.text for row in lst.render(20)] == ["\u25b8 a", "  b"]


def test_a_disabled_row_paints_the_disabled_text_and_band():
    lst = List(["a", "b"], window=2, disabled_items=(1,), disabled_style=Style(italic=True))
    row = lst.render(20)[1]
    assert row.text == "  b"
    assert all(seg.style == Style(italic=True) for seg in row.segments)
    # The band defaults to the theme's dim, so it sits under the same text.
    banded = List(["a", "b"], window=2, disabled_items=(1,)).render(20)[1]
    assert banded.segments[0].style == DEFAULT_THEME.dim


def test_the_bands_value_overrides_the_theme_tokens():
    ground = Style(fg="#101010")
    active = Style(fg="#abcdef")
    disabled = Style(fg="#654321")
    bands = RowBands(ground=ground, active=active, disabled=disabled)
    lst = List(["a", "b"], window=2, bands=bands)
    rows = lst.render(20)
    assert rows[0].segments[0].style == active
    assert rows[1].segments[0].style == ground
    assert lst.revision()[-1] == bands
    disabled_rows = List(
        ["a", "b"], window=2, bands=bands, disabled_items=(1,)
    ).render(20)
    assert disabled_rows[1].segments[0].style == disabled.merge(DEFAULT_THEME.dim)
