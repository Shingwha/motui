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

from motui.kernel import Component
from motui.kernel.block import Clickable, Focusable
from motui.kernel.lines import Segment
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets.navlist import NavList

#: The contract's defaults: the bar glyph and the seat a row without one wears.
BAR = "\u258c"
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
    assert [row.text for row in rows] == ["\u258c alpha", "  beta", "  gamma"]
    assert [row.width for row in rows] == [7, 6, 7]
    # The defaults (D4): the active row is accent label + accent bar, the
    # others are dim labels over the blank seat in the muted bar band.
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
    nav = NavList(["a", "b", "c"], active=0)
    assert nav.move(1) is True and nav.active == 1
    assert nav.move(5) is True and nav.active == 2  # clamped at the end
    assert nav.move(-9) is True and nav.active == 0  # clamped, no wrap-around
    assert nav.move(-1) is False and nav.active == 0
    assert nav.select(1) is True and nav.select(1) is False  # already active
    assert NavList(["a", "b"], active=7).active == 1  # clamped on construction
    assert NavList([], active=3).active == 0
    assert NavList([]).move(1) is False
    skip = NavList(["a", "b", "c", "d"], disabled={1, 2})
    assert skip.move(1) is True and skip.active == 3  # 1 and 2 are stepped over
    assert skip.move(1) is False and skip.active == 3  # the edge: no landing left
    assert skip.move(-1) is True and skip.active == 0  # and back across both
    assert skip.move(-1) is False and skip.active == 0


def test_the_bar_follows_the_selection():
    nav = NavList(["a", "b"])
    nav.move(1)
    rows = nav.render(20)
    assert rows[0].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),  # "a" went back to the blank seat
        Segment(" a", DEFAULT_THEME.dim),
    )
    assert rows[1].segments == (
        Segment(BAR, DEFAULT_THEME.accent),  # "b" took the bar
        Segment(" b", DEFAULT_THEME.accent),
    )


def test_a_disabled_item_is_visible_but_not_selectable():
    nav = NavList(["a", "b", "c"], disabled={1}, disabled_style=DISABLED)
    rows = nav.render(20)
    assert rows[1].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),  # the bar stays with the active row
        Segment(" b", DISABLED),
    )
    assert nav.click(1, 0) is False and nav.active == 0  # a click is refused
    assert nav.click(1, 99) is False  # the column is ignored either way
    assert nav.select(1) is False and nav.active == 0  # so is a select
    assert nav.hover_at(1, 0) is True  # the pointer still marks it ...
    assert nav.render(20)[1].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),  # ... the bar does not move
        Segment(" b", DISABLED.merge(DEFAULT_THEME.hover)),  # the label takes the band
    )
    assert nav.move(1) is True and nav.active == 2  # the step skips it
    assert nav.hover_at(-1, -1) is True  # the pointer left
    assert nav.render(20)[1].segments[1] == Segment(" b", DISABLED)


def test_click_resolves_the_row_and_ignores_the_column():
    nav = NavList(["a", "b", "c"])
    assert isinstance(nav, Clickable)
    assert nav.click(2, 0) is True and nav.active == 2
    assert nav.click(1, 99) is True and nav.active == 1  # the row is the cell
    assert nav.click(1, -5) is True  # and the column never misses it
    assert nav.click(1, 0) is True  # a hit even when it already was active
    for row in (-1, 3, 9):  # outside the list: rows that stand for no item
        assert nav.click(row, 0) is False and nav.active == 1
    assert NavList([]).click(0, 0) is False  # no item to hit


def test_hover_marks_the_row_under_the_pointer_and_clears_back():
    nav = NavList(["a", "b"], inactive_style=INACTIVE)
    assert isinstance(nav, Focusable) and nav.focused is True
    plain = nav.render(20)
    assert nav.hover_at(1, 0) is True  # a row is the whole cell: col is ignored
    assert nav.render(20)[0] == plain[0]  # an unmarked row is untouched
    assert nav.render(20)[1].segments == (
        Segment(SEAT, DEFAULT_THEME.muted),
        Segment(" b", INACTIVE.merge(DEFAULT_THEME.hover)),
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
    assert rows[0].segments == (Segment("#", BAR_ACTIVE), Segment(" a", ACTIVE))
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
    # is no "lower the weight only" merge; the glyph stays.
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
    assert rows[0].segments[0] == Segment(BAR, plain)  # the active row's seat ...
    assert rows[1].segments[0] == Segment(SEAT, plain)  # ... and the rest's
    assert (rows[0].text, rows[1].text) == ("\u258c a", "  b")  # one shape, one mark


def test_a_bar_of_empty_string_leaves_the_state_to_the_foreground():
    nav = NavList(["a", "b"], bar="", active_style=ACTIVE, inactive_style=INACTIVE)
    rows = nav.render(20)
    assert [row.text for row in rows] == ["  a", "  b"]  # every row one shape
    assert rows[0].segments[1] == Segment(" a", ACTIVE)  # the hue carries the state
    assert rows[1].segments[1] == Segment(" b", INACTIVE)


def test_group_rows_render_verbatim_in_group_style_over_a_blank_seat():
    """A group row is one row of chrome among the items: the seat stays blank,
    the label is the caller's own spelling (never re-cased) and its style is
    the one knob -- ``theme.muted`` when none is given."""
    nav = NavList(["a", "b", "c"], groups=((0, "foundations"), (2, "shell")))
    rows = nav.render(20)
    assert [row.text for row in rows] == ["  foundations", "\u258c a", "  b", "  shell", "  c"]
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
    assert nav.click(0, 0) is False and nav.active == 0  # the group row is no item
    assert nav.click(2, 0) is True and nav.active == 1  # the row under it maps to item 1
    assert nav.select(0) is True and nav.active == 0  # item index, not rendered row
    assert nav.move(1) is True and nav.active == 1  # the step crosses the group row
    assert nav.move(1) is False and nav.active == 1  # the item range still clamps
    assert nav.move(-9) is True and nav.active == 0
    assert NavList(["a", "b"], groups=((0, "t"),), disabled={1}).click(2, 0) is False


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
    assert rows[1].segments[1] == Segment(" a", DEFAULT_THEME.accent)  # the mark cleared
    assert nav.hover_at(2, 0) is True  # the group is behind: item "b" marks by its row
    assert nav.render(20)[2].segments[1] == Segment(" b", INACTIVE.merge(DEFAULT_THEME.hover))
    assert nav.hover_at(9, 0) is True and nav.hover_at(-1, -1) is False
