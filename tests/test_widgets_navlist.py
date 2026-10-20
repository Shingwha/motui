"""NavList: the vertical navigation rail -- the Tabs-symmetric case set.

The same behaviours the tab strip's section pins, one row per item instead
of one row per strip: the render shape (bar, seat and label), the clamped,
never-wrapping, disabled-skipping move, the disabled row that refuses
click and select but still takes the hover band, the row-as-cell click and
the pointer marking, the style knobs' defaults and round trip, the
focus rule (the bar drops a hue, the label is not dimmed) and the
no-color readability assertion: the bar glyph, not a color, tells the
active row from the rest.  No filler: every case here is one the
``Tabs`` section states for the horizontal axis.
"""

from dataclasses import replace

from motui.kernel import Component
from motui.kernel.block import Clickable, Focusable
from motui.kernel.glyphs import RAIL_BAR
from motui.kernel.lines import Segment
from motui.kernel.style import Style
from motui.kernel.text import visible_width
from motui.kernel.theme import DEFAULT_THEME
from motui.testing import headless_tui
from motui.widgets import RowBands
from motui.widgets.navlist import NavList
from motui.widgets.tabs import Tabs

#: The contract's defaults: the bar glyph and the seat a row without one wears.
BAR = RAIL_BAR
SEAT = " "

#: Injected styles: they flow back out of the render equal.
ACTIVE = Style(fg="#abcdef")
INACTIVE = Style(fg="#123456")
DISABLED = Style(fg="#654321")
BAR_STYLE = Style(fg="#0f0f0f")
BAR_ACTIVE = Style(fg="#f0f0f0")


def test_render_is_one_row_per_item_with_the_bar_on_the_active_one():
    nav = NavList(["alpha", "beta", "gamma"])
    rows = nav.render(20)
    # D1: the active row's band is NONE, so the row keeps its own bytes and
    # its own width; the resting rows are unchanged.
    assert [row.text for row in rows] == [
        "\u258c alpha",
        "  beta",
        "  gamma",
    ]
    assert [row.width for row in rows] == [7, 6, 7]
    # The defaults: the active row is accent label + accent bar, the others
    # are dim labels over the blank seat in the muted bar band.
    # D3: the active row carries the ground_active band underneath both --
    # which is NONE under the default theme (D1).
    assert rows[0].segments == (
        Segment("\u258c", DEFAULT_THEME.accent),
        Segment(" alpha", DEFAULT_THEME.accent),
    )
    assert rows[1].segments == (
        Segment(" ", DEFAULT_THEME.muted),
        Segment(" beta", DEFAULT_THEME.dim),
    )
    assert isinstance(nav, Component)
    assert NavList([]).render(20) == []  # an empty list renders zero rows
    narrow = NavList(["a-very-long-label"]).render(6)
    assert len(narrow) == 1 and narrow[0].width == 6
    assert narrow[0].text == "\u258c a-v\u2026"  # a row truncates, never wraps


def test_move_clamps_without_wrapping_and_steps_over_the_disabled():
    nav = NavList(["a", "b", "c"], index=0)
    assert nav.move(1) is True and nav.index == 1
    assert nav.move(5) is True and nav.index == 2  # clamped at the end
    assert nav.move(-9) is True and nav.index == 0  # clamped, no wrap-around
    assert nav.move(-1) is False and nav.index == 0
    assert nav.select(1) is True and nav.select(1) is False  # already active
    assert NavList(["a", "b"], index=7).index == 1  # clamped on construction
    assert NavList([], index=3).index == 0
    assert NavList([]).move(1) is False
    skip = NavList(["a", "b", "c", "d"], disabled_items={1, 2})
    assert skip.move(1) is True and skip.index == 3  # 1 and 2 are stepped over
    assert skip.move(1) is False and skip.index == 3  # the edge: no landing left
    assert skip.move(-1) is True and skip.index == 0  # and back across both
    assert skip.move(-1) is False and skip.index == 0


def test_the_bar_follows_the_selection():
    nav = NavList(["a", "b"])
    nav.move(1)
    rows = nav.render(20)
    assert rows[0].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),  # "a" went back to the blank seat
        Segment(" a", DEFAULT_THEME.dim),
    )
    # D3: the new active row carries the ground_active band under its bar
    # and accent label -- NONE under the default theme (D1), so the row is
    # its own two segments.
    assert rows[1].segments == (
        Segment(BAR, DEFAULT_THEME.accent),  # "b" took the bar
        Segment(" b", DEFAULT_THEME.accent),
    )


def test_a_disabled_item_is_visible_but_not_selectable():
    nav = NavList(["a", "b", "c"], disabled_items={1}, disabled_style=DISABLED)
    rows = nav.render(20)
    assert rows[1].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),  # the bar stays with the active row
        Segment(" b", DISABLED),
    )
    assert nav.click(1, 0) is False and nav.index == 0  # a click is refused
    assert nav.click(1, 99) is False  # the column is ignored either way
    assert nav.select(1) is False and nav.index == 0  # so is a select
    assert nav.hover_at(1, 0) is True  # the pointer still marks it ...
    # ... and the whole marked row wears the ground_active band, the seat
    # included (the hover is the row's band now, not the label's alone) --
    # NONE under the default theme (D1), so the row is its own two segments.
    assert nav.render(20)[1].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),
        Segment(" b", DISABLED),
    )
    assert nav.move(1) is True and nav.index == 2  # the step skips it
    assert nav.hover_at(-1, -1) is True  # the pointer left
    assert nav.render(20)[1].segments[1] == Segment(" b", DISABLED)


def test_click_resolves_the_row_and_ignores_the_column():
    nav = NavList(["a", "b", "c"])
    assert isinstance(nav, Clickable)
    assert nav.click(2, 0) is True and nav.index == 2
    assert nav.click(1, 99) is True and nav.index == 1  # the row is the cell
    assert nav.click(1, -5) is True  # and the column never misses it
    assert nav.click(1, 0) is True  # a hit even when it already was active
    for row in (-1, 3, 9):  # outside the list: rows that stand for no item
        assert nav.click(row, 0) is False and nav.index == 1
    assert NavList([]).click(0, 0) is False  # no item to hit


def test_hover_marks_the_row_under_the_pointer_and_clears_back():
    nav = NavList(["a", "b"], inactive_style=INACTIVE)
    assert isinstance(nav, Focusable) and nav.focused is True
    plain = nav.render(20)
    assert nav.hover_at(1, 0) is True  # a row is the whole cell: col is ignored
    assert nav.render(20)[0] == plain[0]  # an unmarked row is untouched
    # The marked row wears the ground_active band over its whole width, the
    # seat included -- NONE under the default theme (D1), so the row is its
    # own two segments.
    assert nav.render(20)[1].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),
        Segment(" b", INACTIVE),
    )
    assert nav.hover_at(1, 0) is False  # the same row: nothing changed
    assert nav.hover_at(2, 0) is True  # past the last row: the marking clears
    assert nav.render(20) == plain
    assert nav.hover_at(-1, -1) is False  # nothing was marked: no change


def test_style_injection_round_trips():
    nav = NavList(
        ["a", "b"],
        bar="#",
        active_style=ACTIVE,
        inactive_style=INACTIVE,
        bar_style=BAR_STYLE,
        bar_active_style=BAR_ACTIVE,
    )
    rows = nav.render(20)
    # D3: the active row carries the ground_active band underneath -- NONE
    # under the default theme (D1), so the row is its own two segments.
    assert rows[0].segments == (
        Segment("#", BAR_ACTIVE),
        Segment(" a", ACTIVE),
    )
    assert rows[1].segments == (Segment(SEAT, BAR_STYLE), Segment(" b", INACTIVE))
    assert nav.render(20)[0].segments[0].text == "#"  # the custom bar glyph


def test_an_unfocused_list_drops_the_bar_and_keeps_the_label():
    """D3: unfocused lowers the bar's hue; the label is not dimmed."""
    nav = NavList(
        ["a", "b"],
        active_style=ACTIVE,
        inactive_style=INACTIVE,
        focused=False,
    )
    assert isinstance(nav, Focusable) and nav.focused is False
    rows = nav.render(20)
    # The bar takes the theme's muted *whole* -- muted carries a fg, so there
    # is no "lower the weight only" merge; the glyph stays.  D3: the active
    # row carries the ground_active band underneath, the label never dimmed --
    # NONE under the default theme (D1), so the row is its own two segments.
    assert rows[0].segments == (
        Segment(BAR, DEFAULT_THEME.accent.merge(DEFAULT_THEME.muted)),
        Segment(" a", ACTIVE),
    )
    assert rows[1].segments == (Segment(SEAT, DEFAULT_THEME.muted), Segment(" b", INACTIVE))
    nav.focused = True
    assert nav.render(20)[0].segments[0] == Segment(BAR, DEFAULT_THEME.accent)


def test_the_indicator_survives_with_every_color_turned_off():
    """No-color readability: the bar glyph -- not a hue -- is the mark."""
    plain = Style()
    nav = NavList(
        ["a", "b"],
        active_style=plain,
        inactive_style=plain,
        bar_style=plain,
        bar_active_style=plain,
    )
    rows = nav.render(20)
    # D3: the active row's seat wears the band (an attribute, not a color)
    # beside the glyph; the rest's stays plain.  D1: that band is NONE under
    # the default theme, so the row keeps its own bytes.
    assert rows[0].segments[0] == Segment(BAR, plain)
    assert rows[1].segments[0] == Segment(SEAT, plain)  # ... and the rest's
    assert (rows[0].text, rows[1].text) == ("\u258c a", "  b")  # one shape, one mark


def test_a_bar_of_empty_string_collapses_the_whole_seat():
    nav = NavList(["a", "b"], bar="", active_style=ACTIVE, inactive_style=INACTIVE)
    rows = nav.render(20)
    assert [row.text for row in rows] == ["a", "b"]  # zero-column gutter
    assert [row.segments[0].text for row in rows] == ["", ""]
    # D3: the active row's label still carries its own style (the band is
    # NONE under the default theme, D1).
    assert rows[0].segments[1] == Segment("a", ACTIVE)
    assert rows[1].segments[1] == Segment("b", INACTIVE)
    assert nav.bar_space == ""  # the derived gutter is empty too


def test_the_bar_glyph_is_a_parameter_and_a_wide_bar_widens_its_column():
    assert NavList(["a", "b"], bar=">").render(20)[0].text == "> a"
    wide = NavList(["a", "b"], bar="\u6811")
    rows = wide.render(20)
    # The bar column is the glyph's display width (2), so the label sits at
    # column 3 on the active row and on the blank one alike.
    assert rows[0].text == "\u6811 a"
    assert rows[1].text == "   b"
    assert visible_width(rows[0].text[: rows[0].text.index("a")]) == 3
    assert visible_width(rows[1].text[: rows[1].text.index("b")]) == 3
    assert wide.bar_space == " " * 3  # seat_width(bar): the column plus its separator


def test_an_explicit_bar_space_sets_the_separators_width():
    nav = NavList(["a", "b"], bar=">", bar_space="  ")
    assert [row.text for row in nav.render(20)] == [">  a", "   b"]
    # ... and the labels still share one column (3).
    assert nav.bar_space == "   "


def test_the_ground_style_resolves_and_rests_under_the_resting_rows():
    ground = Style(fg="#101010")
    nav = NavList(["a", "b"], ground_style=ground)
    rows = nav.render(20)
    # The resting row rests on the ground, its own styles riding on top --
    # the ground hugs the row's own cells, a pill behind the text.
    assert rows[1].segments == (
        Segment(SEAT, ground.merge(DEFAULT_THEME.muted)),
        Segment(" b", ground.merge(DEFAULT_THEME.dim)),
    )
    assert rows[1].text == "  b"  # no trailing pad: the band is not a ribbon
    # a group row rests on the ground too; the active row swaps the band.
    grouped = NavList(["a"], groups=((0, "top"),), ground_style=ground)
    grows = grouped.render(20)
    assert grows[0].segments[1].style == ground.merge(DEFAULT_THEME.muted)
    assert grows[1].segments[0].style == DEFAULT_THEME.ground_active.merge(
        DEFAULT_THEME.accent
    )
    # the theme field is the fallback the explicit style wins over
    themed = NavList(["a", "b"], theme=replace(DEFAULT_THEME, ground=ground))
    assert themed.render(20)[1].segments[1].style == ground.merge(DEFAULT_THEME.dim)


def test_group_rows_render_verbatim_in_group_style_over_a_blank_seat():
    """A group row is one row of chrome among the items: the seat stays blank,
    the label is the caller's own spelling (never re-cased) and its style is
    the one knob -- ``theme.muted`` when none is given."""
    nav = NavList(["a", "b", "c"], groups=((0, "foundations"), (2, "shell")))
    rows = nav.render(20)
    # D1: the active row's band is NONE, so the active row keeps its own
    # bytes; the group rows and the resting items keep theirs.
    assert [row.text for row in rows] == [
        "  foundations",
        "\u258c a",
        "  b",
        "  shell",
        "  c",
    ]
    assert len(rows) == len(nav.items) + 2  # the rows are items + groups
    assert rows[0].segments == (  # the bar column is blank, the label muted
        Segment(SEAT, DEFAULT_THEME.muted),
        Segment(" foundations", DEFAULT_THEME.muted),
    )
    assert rows[3].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),
        Segment(" shell", DEFAULT_THEME.muted),
    )
    group = Style(fg="#fedcba")
    assert NavList(["a"], groups=((0, "top"),), group_style=group).render(20)[0].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),
        Segment(" top", group),
    )
    assert NavList([], groups=((0, "top"),)).render(20) == []  # empty: nothing to group


def test_group_rows_refuse_click_and_select_and_steps_count_items_only():
    """A group row is transparent to the verbs: the rendered row hits no item,
    ``select``/``active`` speak item indices, and ``move`` walks across the
    rows in between -- clamped at the item range, as ever."""
    nav = NavList(["a", "b"], groups=((0, "top"),))
    assert nav.click(0, 0) is False and nav.index == 0  # the group row is no item
    assert nav.click(2, 0) is True and nav.index == 1  # the row under it maps to item 1
    assert nav.select(0) is True and nav.index == 0  # item index, not rendered row
    assert nav.move(1) is True and nav.index == 1  # the step crosses the group row
    assert nav.move(1) is False and nav.index == 1  # the item range still clamps
    assert nav.move(-9) is True and nav.index == 0
    assert NavList(["a", "b"], groups=((0, "t"),), disabled_items={1}).click(2, 0) is False


def test_the_pointer_marks_items_only_and_a_group_row_clears_it():
    nav = NavList(["a", "b"], groups=((0, "top"),), inactive_style=INACTIVE)
    assert nav.hover_at(1, 0) is True  # the rendered row of the active item "a"
    assert nav.render(20)[1].segments[1] == Segment(
        " a", DEFAULT_THEME.accent.merge(DEFAULT_THEME.hover)
    )
    assert nav.hover_at(0, 0) is True  # onto the group row: no item under it
    rows = nav.render(20)
    assert rows[0].segments == (  # the group row never takes the band
        Segment(SEAT, DEFAULT_THEME.muted),
        Segment(" top", DEFAULT_THEME.muted),
    )
    # D3: the active row keeps its accent label with the band underneath.
    assert rows[1].segments[1] == Segment(
        " a", DEFAULT_THEME.ground_active.merge(DEFAULT_THEME.accent)
    )  # the mark cleared
    assert nav.hover_at(2, 0) is True  # the group is behind: item "b" marks by its row
    # D1: the marked row's band is NONE under the default theme, so the label
    # keeps its own style alone (a themed ``hover`` still bands the row's own
    # cells, a pill with no trailing pad).
    assert nav.render(20)[2].segments[1] == Segment(
        " b", DEFAULT_THEME.ground_active.merge(INACTIVE)
    )
    assert nav.hover_at(9, 0) is True and nav.hover_at(-1, -1) is False


# --- the sealed block's revision (F5) ------------------------------------------


WIDTH = 40


def _sealed(component):
    """A sealed block holding ``component``, warmed twice (the probe's shape)."""
    tui = headless_tui(80, 24)
    block = tui.add(component, id="w")
    block.seal()
    block.rows(WIDTH)
    block.rows(WIDTH)
    return block


def _fresh(block, component) -> bool:
    cached = [row.styled() for row in block.rows(WIDTH)]
    direct = [row.styled() for row in component.render(WIDTH)]
    return cached == direct


def test_a_sealed_tabs_hover_reaches_the_screen():
    strip = Tabs(["alpha", "beta", "gamma"])
    block = _sealed(strip)
    col = strip.render(WIDTH)[0].text.index("beta") + 1
    assert strip.hover_at(0, col) is True
    assert _fresh(block, strip)


def test_a_sealed_tabs_focus_flag_reaches_the_screen():
    strip = Tabs(["alpha", "beta"])
    block = _sealed(strip)
    strip.focused = False
    assert _fresh(block, strip)


def test_a_sealed_tabs_selection_reaches_the_screen():
    strip = Tabs(["alpha", "beta", "gamma"])
    block = _sealed(strip)
    assert strip.select(2) is True
    assert _fresh(block, strip)


def test_a_sealed_navlists_hover_reaches_the_screen():
    nav = NavList(["alpha", "beta", "gamma"])
    block = _sealed(nav)
    assert nav.hover_at(2, 0) is True
    assert _fresh(block, nav)


def test_a_sealed_navlists_focus_flag_reaches_the_screen():
    nav = NavList(["alpha", "beta"])
    block = _sealed(nav)
    nav.focused = False
    assert _fresh(block, nav)


def test_a_sealed_navlists_selection_reaches_the_screen():
    nav = NavList(["alpha", "beta", "gamma"])
    block = _sealed(nav)
    assert nav.select(2) is True
    assert _fresh(block, nav)


# --- the read-only index and gutter, the disabled rail and the shared bands ---------


def test_index_is_read_only_and_bar_space_is_a_derived_read_only_property():
    nav = NavList(["a", "b"])
    assert nav.index == 0 and nav.bar_space == "  "
    nav.select(1)
    assert nav.index == 1
    for name in ("index", "bar_space"):
        try:
            setattr(nav, name, "")
        except AttributeError:
            pass
        else:  # pragma: no cover - both are read-only properties
            raise AssertionError(f"NavList.{name} must be read-only")


def test_a_disabled_rail_refuses_every_gesture_but_still_renders():
    nav = NavList(["a", "b"], disabled=True)
    assert nav.select(0) is False and nav.move(1) is False
    assert nav.click(0, 0) is False
    assert nav.index == 0
    assert [row.text for row in nav.render(20)] == ["\u258c a", "  b"]


def test_the_bands_value_replaces_the_rail_tokens():
    ground = Style(fg="#101010")
    active = Style(fg="#abcdef")
    nav = NavList(
        ["a", "b"],
        bands=RowBands(ground=ground, active=active, dim=Style(dim=True)),
    )
    rows = nav.render(20)
    # The band rests underneath the row's own bar/label styles.
    assert rows[0].segments[0].style == active.merge(DEFAULT_THEME.accent)
    assert rows[0].segments[1].style == active.merge(DEFAULT_THEME.accent)
    assert rows[1].segments[0].style == ground.merge(DEFAULT_THEME.muted)
    assert rows[1].segments[1].style == ground.merge(DEFAULT_THEME.dim)
    assert nav.revision()[-2] == nav.bands
