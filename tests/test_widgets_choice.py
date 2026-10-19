"""Tests for motui.widgets.choice (Option / Select / Radio / CheckGroup).

``Select`` is the family's one base: a ``"\u2192 "`` cursor row, a description
column measured over the whole option list, a ``max_rows`` window that follows
the cursor (top-stick by default, centred under ``window=True``), the ``(i/n)``
counter row it renders while the window scrolls, and a cursor that wraps around
the ends (``wrap=False`` clamps).  Its knobs change what a step writes:
``commit=True`` makes the cursor the choice, ``multi=True`` makes the marks the
selection and the rows carry the ``[x] ``/``[ ] `` mark.  ``Radio`` and
``CheckGroup`` are the two form presets of the base.  ``activate()`` is the
family's activation: it takes the option under the cursor into ``chosen``, which the host
reads once -- ``move()`` and a re-filter clear it, and a toggle recomputes it.
``focused`` is the focus flag: while set the cursor row is ``selected_style``,
unset it is that style merged with the theme's ``dim``.
"""

import pytest

from _doubles import texts

from dataclasses import replace

from motui.kernel import Component
from motui.kernel.block import Activable, Clickable
from motui.kernel.lines import Segment
from motui.kernel.style import NONE, Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.widgets import Autocomplete, CheckGroup, Radio
from motui.widgets.choice import FILLED_MARK, Option, Select

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
DESCRIPTION = Style(fg="#123456")
LABEL = Style(bold=True)
TITLE = Style(fg="#fedcba")
PLAIN = Style(fg="#123456")
HOVER = Style(italic=True)
FOCUS = Style(underline=True)

THREE = [Option("one"), Option("two"), Option("three")]


def _banded(text: str, width: int) -> str:
    """An engaged row's rendered text: its own, padded to ``width`` by the band.

    The row-band contract's registered default change: the engaged row's
    band spans the painting width, so the row's text carries the band's
    trailing cells.
    """
    return text + " " * (width - len(text))


@pytest.mark.parametrize(
    "start, delta, index, moved",
    [
        (0, 1, 1, True),
        (2, 1, 0, True),  # off the last row onto the first
        (0, -1, 2, True),  # off the first row onto the last
        (0, 5, 2, True),  # any delta lands inside, modulo the rows
    ],
)
def test_move_wraps_around_the_ends_by_default(start, delta, index, moved):
    select = Select(THREE)
    select.index = start
    assert select.move(delta) is moved
    assert select.index == index
    assert select.selected == THREE[index]


@pytest.mark.parametrize(
    "start, delta, index, moved",
    [
        (0, 5, 2, True),  # clamped at the end
        (2, -9, 0, True),  # clamped at the start
        (0, -1, 0, False),  # already at the top: nothing moved
    ],
)
def test_a_non_wrapping_select_clamps_at_the_ends(start, delta, index, moved):
    select = Select(THREE, wrap=False)
    select.index = start
    assert select.move(delta) is moved
    assert select.index == index


def test_an_empty_list_has_no_selection_and_cannot_move():
    empty = Select([])
    assert empty.selected is None
    assert empty.move(1) is False
    assert empty.render(20) == []  # no rows, and no counter for them


def test_render_marks_the_cursor_row_and_aligns_the_descriptions():
    select = Select(
        [Option("one", description="first"), Option("two"), Option("three", description="third")],
        label_style=LABEL,
        selected_style=SELECTED,
        description_style=DESCRIPTION,
    )
    # The column is lead (2) + the widest label ("three", 5) + the gap (2).
    # The cursor row's band spans the painting width (the registered change).
    assert texts(select, 30) == [
        _banded("\u2192 one    first", 30),
        "  two",
        "  three  third",
    ]
    rows = select.render(30)
    # D3: the cursor row carries the ground_active band underneath its
    # styles -- the marker, the label and the description pad alike -- and
    # the band's trailing cells close the row.
    band = DEFAULT_THEME.ground_active
    assert rows[0].segments == (
        Segment("\u2192 ", band.merge(SELECTED)),
        Segment("one", band.merge(SELECTED)),
        Segment("    ", band),
        Segment("first", band.merge(DESCRIPTION)),
        Segment(" " * 16, band),
    )
    assert rows[1].segments == (Segment("  ", LABEL), Segment("two", LABEL))
    select.move(1)
    assert texts(select, 30)[1] == _banded("\u2192 two", 30)


def test_the_description_column_holds_still_while_the_window_scrolls():
    options = [Option("a", description="x"), Option("a-very-long-label", description="y")]
    options += [Option(f"i{i}", description="z") for i in range(4)]
    menu = Select(options, max_rows=2)
    # The column follows the whole option list, not the rendered window.
    # The cursor row's band spans the painting width (the registered change).
    assert texts(menu, 40)[0] == _banded("\u2192 a" + " " * 18 + "x", 40)
    menu.index = 5
    assert texts(menu, 40)[0] == "  i2" + " " * 17 + "z"


def test_max_rows_windows_the_rows_and_shows_the_counter():
    menu = Select([Option(f"item{i}", description=f"row {i}") for i in range(10)], max_rows=3)
    # The cursor row's band spans the painting width (the registered change);
    # the counter row is a resting row and keeps its own bytes.
    assert texts(menu, 30) == [
        _banded("\u2192 item0  row 0", 30),
        "  item1  row 1",
        "  item2  row 2",
        "(1/10)",
    ]
    menu.index = 5  # the cursor row is the window's last row
    assert texts(menu, 30) == [
        "  item3  row 3",
        "  item4  row 4",
        _banded("\u2192 item5  row 5", 30),
        "(6/10)",
    ]


def test_window_true_centres_the_window_on_the_cursor():
    menu = Select([Option(f"i{i}") for i in range(10)], max_rows=3, window=True)
    # The cursor row's band spans the painting width (the registered change).
    assert texts(menu, 30) == [_banded("\u2192 i0", 30), "  i1", "  i2", "(1/10)"]  # clamped at the head
    menu.index = 5  # the cursor sits half a window down
    assert texts(menu, 30) == ["  i4", _banded("\u2192 i5", 30), "  i6", "(6/10)"]
    menu.index = 9
    assert texts(menu, 30) == ["  i7", "  i8", _banded("\u2192 i9", 30), "(10/10)"]  # and at the tail


@pytest.mark.parametrize(
    "menu",
    [
        Select(THREE),  # fewer rows than max_rows
        Select([Option(f"i{i}") for i in range(3)], max_rows=3),  # exactly max_rows
        Select([Option(f"i{i}") for i in range(12)], max_rows=None),  # no cap at all
    ],
)
def test_a_menu_that_never_scrolls_renders_no_counter(menu):
    assert all(not row.startswith("(") for row in texts(menu, 30))
    assert len(texts(menu, 30)) == len(menu.options)


@pytest.mark.parametrize(
    "row, index, hit",
    [
        (1, 0, True),  # the option under the row
        (2, 1, True),  # a hit even when the cursor already was there
        (0, 1, False),  # the title row is not an option
        (3, 1, False),  # past the last option
        (-1, 1, False),  # before the first option
    ],
)
def test_click_places_the_cursor_on_the_option_under_the_row(row, index, hit):
    select = Select([Option("one"), Option("two")], title="pick")
    select.index = 1
    assert select.click(row, 0) is hit
    assert select.index == index


def test_select_click_ignores_the_column():
    select = Select([Option("one"), Option("two")], title="pick")
    for col in (0, 1, 5, 999):  # a menu row owns the whole width
        select.index = 1
        assert select.click(1, col) is True and select.index == 0
    assert select.click(0, 999) is False  # the title row misses at every column


def test_click_maps_through_the_window_and_ignores_the_counter_row():
    menu = Select([Option(f"item{i}") for i in range(10)], max_rows=3)
    menu.index = 5  # the window is item3..item5, then the counter row
    assert menu.click(0, 0) is True and menu.index == 3
    menu.index = 5
    assert menu.click(2, 0) is True and menu.index == 5
    menu.index = 5
    assert menu.click(3, 0) is False and menu.index == 5  # the counter is not an option


def test_the_window_and_counter_map_the_same_at_any_column():
    menu = Select([Option(f"item{i}") for i in range(10)], max_rows=3)
    menu.render(40)  # the rows are as wide as the menu: the column never narrows one
    for col in (0, 3, 400):
        menu.index = 5
        assert menu.click(0, col) is True and menu.index == 3
        menu.index = 5
        assert menu.click(2, col) is True and menu.index == 5
        menu.index = 5
        assert menu.click(3, col) is False and menu.index == 5  # the counter row


def test_assigning_the_index_clamps_into_the_rows():
    menu = Select(THREE)
    menu.index = 99
    assert menu.index == 2
    menu.index = -4
    assert menu.index == 0
    menu.options = []
    menu.index = 3
    assert menu.index == 0 and menu.selected is None


def test_an_unfocused_menu_dims_the_cursor_row_and_nothing_else():
    select = Select(
        [Option("one", description="first"), Option("two"), Option("three", description="third")],
        label_style=LABEL,
        selected_style=SELECTED,
        description_style=DESCRIPTION,
        focused=False,
    )
    assert select.focused is False
    dim_band = SELECTED.merge(Theme().dim)
    # D3: the unfocused cursor row's band is the ground_active dimmed, and
    # it rests underneath the label style the row already carried -- and it
    # spans the painting width (the registered change).
    band = DEFAULT_THEME.ground_active.merge(Theme().dim)
    rows = select.render(30)
    assert rows[0].segments == (
        Segment("\u2192 ", band.merge(dim_band)),
        Segment("one", band.merge(dim_band)),
        Segment("    ", band),
        Segment("first", band.merge(DESCRIPTION)),  # the description keeps its own dim
        Segment(" " * 16, band),
    )
    assert rows[1].segments == (Segment("  ", LABEL), Segment("two", LABEL))
    assert rows[2].segments == (
        Segment("  ", LABEL),
        Segment("three", LABEL),
        Segment("  "),
        Segment("third", DESCRIPTION),
    )


def test_the_dim_style_comes_from_the_component_theme():
    theme = Theme(dim=DESCRIPTION)
    select = Select([Option("one")], selected_style=SELECTED, focused=False, theme=theme)
    # D3: the band is the theme's ground_active with its dim merged on, and
    # it spans the painting width (the registered change).
    band = theme.ground_active.merge(theme.dim)
    label = SELECTED.merge(theme.dim)
    assert select.render(20)[0].segments == (
        Segment("\u2192 ", band.merge(label)),
        Segment("one", band.merge(label)),
        Segment(" " * 15, band),
    )


def test_activate_takes_the_cursor_option_into_chosen():
    menu = Select(THREE)
    menu.index = 1
    assert menu.activate() is True
    assert menu.chosen == Option("two")
    menu.chosen = None  # the host reads the pick once, then clears it
    assert menu.chosen is None


def test_an_empty_menu_activates_to_nothing():
    empty = Select([])
    assert empty.activate() is False
    assert empty.chosen is None


def test_moving_the_cursor_clears_a_pending_pick():
    menu = Select(THREE)
    assert menu.activate() is True and menu.chosen == Option("one")
    assert menu.move(1) is True
    assert menu.chosen is None


def test_a_committing_select_writes_the_row_it_landed_on():
    form = Select(THREE, commit=True)
    assert form.chosen is None  # nothing picked before the first gesture
    assert form.move(1) is True and form.chosen == Option("two")  # the step is the choice
    assert form.click(2, 0) is True and form.chosen == Option("three")
    assert form.move(-1) is True and form.chosen == Option("two")


def test_a_re_filter_clears_chosen_and_activate_takes_the_match():
    auto = Autocomplete(options=THREE)
    auto.set_query("tw")  # one match, not the universe's cursor row
    assert auto.activate() is True
    assert auto.chosen == Option("two")
    auto.set_query("th")
    assert auto.chosen is None


def test_style_injection_round_trips():
    select = Select(
        [Option("one", description="h"), Option("two")],
        title="T",
        label_style=LABEL,
        selected_style=SELECTED,
        description_style=DESCRIPTION,
        title_style=TITLE,
    )
    select.move(1)
    rows = select.render(40)
    assert rows[0].segments == (Segment("T", TITLE),)  # the title row
    assert rows[1].segments == (
        Segment("  ", LABEL),
        Segment("one", LABEL),
        Segment("  "),
        Segment("h", DESCRIPTION),
    )
    # D3: the cursor row carries the ground_active band underneath -- and it
    # spans the painting width (the registered change).
    band = DEFAULT_THEME.ground_active
    assert rows[2].segments == (
        Segment("\u2192 ", band.merge(SELECTED)),
        Segment("two", band.merge(SELECTED)),
        Segment(" " * 35, band),
    )
    # the theme fields feed the same parameters
    theme = Theme(accent=SELECTED, dim=DESCRIPTION)
    themed = Select([Option("one", description="h")], theme=theme).render(40)
    assert themed[0].segments[0] == Segment("\u2192 ", band.merge(SELECTED))
    assert themed[0].segments[3] == Segment("h", band.merge(DESCRIPTION))
    assert themed[0].segments[-1] == Segment(" " * 32, band)


def test_the_marker_can_be_replaced_and_the_rows_follow_its_width():
    select = Select([Option("one"), Option("two")], marker="\u276f")
    # The cursor row's band spans the painting width (the registered change).
    assert texts(select, 20) == [_banded("\u276f one", 20), "  two"]


# --- Radio: the single-choice preset -----------------------------------------------


def test_radio_renders_one_marked_row_per_label():
    group = Radio(["one", "two", "three"])
    rows = group.render(30)
    assert texts(group, 30) == ["(\u2022) one", "( ) two", "( ) three"]
    assert rows[0].segments == (
        Segment(FILLED_MARK, DEFAULT_THEME.accent),
        Segment("one", DEFAULT_THEME.accent),
    )
    assert rows[1].segments == (Segment("( ) ", NONE), Segment("two", NONE))
    assert isinstance(group, Component)


def test_radio_index_clamps_and_selected_reads_the_label():
    group = Radio(["a", "b", "c"], index=7)
    assert group.index == 2 and group.selected == "c"
    group.index = -4
    assert group.index == 0 and group.selected == "a"
    assert texts(group, 20)[0] == "(\u2022) a"
    empty = Radio([])
    assert empty.index == 0 and empty.selected is None and empty.render(20) == []


def test_radio_move_steps_and_clamps_and_lands_the_new_selection():
    group = Radio(["one", "two", "three"])
    assert group.chosen is None
    assert group.move(1) is True
    assert (group.index, group.chosen) == (1, "two")
    group.chosen = None
    assert group.move(-9) is True  # clamped at the start
    assert (group.index, group.chosen) == (0, "one")
    group.chosen = None
    assert group.move(-1) is False  # already there: nothing moved, nothing chosen
    assert group.chosen is None
    assert Radio([]).move(1) is False


def test_radio_click_is_the_mouse_door_and_ignores_the_column():
    group = Radio(["one", "two", "three"])
    assert isinstance(group, Clickable)
    for col in (0, 3, 40):  # a row owns the whole width
        assert group.click(2, col) is True and group.chosen == "three"
        assert group.index == 2
    assert group.click(2, 0) is True  # a hit even when it already was selected
    for row in (-1, 3, 9):
        group.chosen = None
        assert group.click(row, 0) is False and group.chosen is None
        assert group.index == 2


def test_radio_activate_takes_the_selection_and_reads_once():
    group = Radio(["one", "two"])
    assert isinstance(group, Activable)
    group.move(1)
    group.chosen = None
    assert group.activate() is True and group.chosen == "two"
    assert Radio([]).activate() is False and Radio([]).chosen is None


def test_radio_takes_option_payloads_into_chosen():
    group = Radio([Option("alpha", 1), Option("beta", 2), Option("plain")])
    assert group.labels == ["alpha", "beta", "plain"]
    assert group.move(1) is True and group.chosen == 2
    group.chosen = None
    assert group.click(2, 0) is True and group.chosen == "plain"  # value None: the label
    group.chosen = None
    assert group.move(-1) is True and group.chosen == 2


def test_radio_marks_the_row_under_a_cell_and_clears_back():
    group = Radio(["one", "two", "three"], label_style=PLAIN)
    plain = group.render(20)
    assert group.hover_at(2, 0) is True
    marked = group.render(20)
    assert marked[2].segments[0].style == PLAIN.merge(DEFAULT_THEME.hover)
    assert marked[2].segments[1].style == PLAIN.merge(DEFAULT_THEME.hover)
    assert marked[0] == plain[0] and marked[1] == plain[1]
    assert group.hover_at(2, 9) is False  # the same row: nothing to repaint
    assert group.hover_at(1, 0) is True
    assert group.render(20)[2] == plain[2]  # the old row let the band go
    assert group.hover_at(-1, -1) is True  # the pointer left
    assert group.render(20) == plain  # byte-for-byte the un-hovered rows
    assert group.hover_at(9, 0) is False  # past the labels: nothing was marked
    # the hovered selected row: the pointer's band under its accent label
    # (the group's own selection band is the focused state's)
    assert group.hover_at(0, 0) is True
    assert group.render(20)[0].segments[0].style == DEFAULT_THEME.ground_active.merge(
        DEFAULT_THEME.accent
    )


def test_the_selected_rows_band_is_told_apart_from_the_plain_render():
    def build(focused):
        return Radio(
            ["one", "two"],
            selected_style=SELECTED,
            label_style=PLAIN,
            focused=focused,
        )

    plain, focused = build(False), build(True)
    # The selected row's band (the renamed focus_style, ground_active by
    # default) rests underneath the accent label while the group is focused.
    assert focused.render(20)[0].segments[0] == Segment(
        FILLED_MARK, SELECTED.merge(DEFAULT_THEME.accent)
    )
    assert focused.render(20)[1] == plain.render(20)[1]  # only the selected row carries it
    assert plain.render(20)[0].segments[0] == Segment(FILLED_MARK, DEFAULT_THEME.accent)


def test_the_ground_style_resolves_and_rests_under_every_row():
    ground = Style(fg="#101010")
    select = Select(
        [Option("one", description="d"), Option("two")],
        title="T",
        max_rows=1,
        ground_style=ground,
    )
    rows = select.render(20)
    # The title row, the counter row and the resting rows rest on the ground
    # -- and the ground spans the painting width; only the engaged row swaps
    # the band.
    assert rows[0].segments[0].style == ground  # the title
    assert rows[0].text == _banded("T", 20)
    assert rows[2].text == _banded("(1/2)", 20)
    assert rows[2].segments[0].style == ground.merge(DEFAULT_THEME.dim)
    assert rows[1].segments[0].style == DEFAULT_THEME.ground_active.merge(
        DEFAULT_THEME.accent
    )
    # the theme field is the fallback the explicit style wins over
    themed = Select([Option("one"), Option("two")], theme=replace(DEFAULT_THEME, ground=ground))
    assert themed.render(20)[1].segments[0].style == ground
    assert themed.render(20)[1].text == _banded("  two", 20)


def test_the_groups_take_the_ground_style_under_their_rows():
    ground = Style(fg="#101010")
    # The form rule leaves the unfocused selected row on the ground like any
    # other; the mark column rides it.
    group = Radio(["one", "two"], ground_style=ground)
    assert group.render(20)[1].segments == (
        Segment("( ) ", ground),
        Segment("two", ground),
        Segment(" " * 13, ground),
    )
    assert group.render(20)[1].text == _banded("( ) two", 20)
    checks = CheckGroup(["x", "y"], ground_style=ground)
    assert checks.render(20)[1].segments[0].style == ground
    themed = Radio(["one", "two"], theme=replace(DEFAULT_THEME, ground=ground))
    assert themed.render(20)[1].segments[1].style == ground


# --- CheckGroup: the multiple-choice preset ----------------------------------------


def test_check_group_toggles_marks_and_reads_the_marked_values():
    group = CheckGroup(["apples", "pears", "plums"], marked=(2,), focused=True)
    # The cursor row's band spans the painting width (the registered change).
    assert texts(group, 30) == [
        _banded("\u2192 [ ] apples", 30),
        "  [ ] pears",
        "  [x] plums",
    ]
    assert group.chosen == ["plums"]  # the marks are the selection, in row order
    assert group.toggle() is True  # the row flips and the selection follows
    assert group.chosen == ["apples", "plums"]
    group.move(1)
    assert group.activate() is True  # enter is the same gesture (Toggle semantics)
    assert group.chosen == ["apples", "pears", "plums"]
    assert texts(group, 30)[1] == _banded("\u2192 [x] pears", 30)
    assert CheckGroup([]).toggle() is False  # nothing to flip
    assert CheckGroup(["one"]).chosen is None  # a row at rest: no selection at all


def test_check_group_carries_option_values_into_the_mark_list():
    group = CheckGroup([Option("alpha", 1), "beta", Option("plain")], marked=(0, 2))
    assert group.chosen == [1, "plain"]  # the payload; None falls back to the label


def test_a_multi_select_keeps_the_mark_column_before_the_label():
    menu = Select([Option("one", description="first"), Option("two")], multi=True, marked=(1,))
    # The description column is lead (2) + the mark (4) + the widest label (3) + the gap (2).
    # The cursor row's band spans the painting width (the registered change).
    assert texts(menu, 30) == [
        _banded("\u2192 [ ] one  first", 30),
        "  [x] two",
    ]
    assert menu.chosen == ["two"]


def test_a_multi_select_moves_without_touching_the_marks():
    menu = Select(THREE, multi=True, marked=(1,))
    assert menu.chosen == ["two"]
    assert menu.move(1) is True and menu.index == 1
    assert menu.chosen == ["two"]  # the marks, not the cursor, are the selection
    assert menu.click(2, 0) is True
    assert menu.chosen == ["two"]
