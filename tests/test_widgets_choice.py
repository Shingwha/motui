"""Tests for motui.widgets.choice (Option / Select / RadioGroup / CheckboxGroup).

``Select`` is the family's one base: a ``"\u2192 "`` cursor row, a description
column measured over the whole option list, a ``max_rows`` window that follows
the cursor (top-stick by default, centred under ``window=True``), the ``(i/n)``
counter row it renders while the window scrolls, and a cursor that wraps around
the ends (``wrap=False`` clamps).  Its knobs change what a step writes:
``commit=True`` makes the cursor the choice, ``multi=True`` makes the marks the
selection and the rows carry the ``[x] ``/``[ ] `` mark.  ``RadioGroup`` and
``CheckboxGroup`` are the two form presets of the base.  ``activate()`` is the
family's activation: it leaves the option under the cursor pending, and the
host reads it once through ``take_result()`` -- ``move()`` and a re-filter
clear it, and a toggle recomputes it.
``focused`` is the focus flag: while set the cursor row is ``cursor_text_style``,
unset it is that style merged with the theme's ``dim``.
"""

import pytest

from _doubles import texts

from dataclasses import replace

from motui.kernel import Component
from motui.kernel.block import Activable, Clickable
from motui.kernel.glyphs import RADIO_EMPTY, RADIO_FILLED, pair_seat
from motui.kernel.lines import Segment
from motui.kernel.style import NONE, Style
from motui.kernel.text import visible_width
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.widgets import Autocomplete, CheckboxGroup, RadioGroup, RowBands
from motui.widgets.choice import Option, Select

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
DESCRIPTION = Style(fg="#123456")
LABEL = Style(bold=True)
TITLE = Style(fg="#fedcba")
PLAIN = Style(fg="#123456")
HOVER = Style(italic=True)
FOCUS = Style(underline=True)

THREE = [Option("one"), Option("two"), Option("three")]

#: The filled radio row's own seat (the pair is padded to its wider member).
FILLED_SEAT = pair_seat(RADIO_FILLED, RADIO_EMPTY)


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
        cursor_text_style=SELECTED,
        description_style=DESCRIPTION,
    )
    # The column is lead (2) + the widest label ("three", 5) + the gap (2).
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(select, 30) == [
        "\u2192 one    first",
        "  two",
        "  three  third",
    ]
    rows = select.render(30)
    # D3: the cursor row carries the ground_active band underneath its
    # styles -- the marker, the label and the description pad alike -- and
    # the band hugs the row's own four segments, a pill with no trailing
    # pad.  D1: that band is NONE under
    # the default theme, so the row is its own four segments with no pad
    # (``test_an_unfocused_menu_dims_the_cursor_row_and_nothing_else`` pins
    # the banded case through the merge-dim rule).
    assert rows[0].segments == (
        Segment("\u2192 ", SELECTED),
        Segment("one", SELECTED),
        Segment("    "),
        Segment("first", DESCRIPTION),
    )
    assert rows[1].segments == (Segment("  ", LABEL), Segment("two", LABEL))
    select.move(1)
    assert texts(select, 30)[1] == "\u2192 two"


def test_the_description_column_holds_still_while_the_window_scrolls():
    options = [Option("a", description="x"), Option("a-very-long-label", description="y")]
    options += [Option(f"i{i}", description="z") for i in range(4)]
    menu = Select(options, max_rows=2)
    # The column follows the whole option list, not the rendered window.
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(menu, 40)[0] == "\u2192 a" + " " * 18 + "x"
    menu.index = 5
    assert texts(menu, 40)[0] == "  i2" + " " * 17 + "z"


def test_max_rows_windows_the_rows_and_shows_the_counter():
    menu = Select([Option(f"item{i}", description=f"row {i}") for i in range(10)], max_rows=3)
    # D1: the cursor row's band is NONE, so the cursor row and the counter
    # row alike keep their own bytes.
    assert texts(menu, 30) == [
        "\u2192 item0  row 0",
        "  item1  row 1",
        "  item2  row 2",
        "(1/10)",
    ]
    menu.index = 5  # the cursor row is the window's last row
    assert texts(menu, 30) == [
        "  item3  row 3",
        "  item4  row 4",
        "\u2192 item5  row 5",
        "(6/10)",
    ]


def test_window_true_centres_the_window_on_the_cursor():
    menu = Select([Option(f"i{i}") for i in range(10)], max_rows=3, window=True)
    # D1: the cursor row's band is NONE, so every row keeps its own bytes.
    assert texts(menu, 30) == ["\u2192 i0", "  i1", "  i2", "(1/10)"]  # clamped at the head
    menu.index = 5  # the cursor sits half a window down
    assert texts(menu, 30) == ["  i4", "\u2192 i5", "  i6", "(6/10)"]
    menu.index = 9
    assert texts(menu, 30) == ["  i7", "  i8", "\u2192 i9", "(10/10)"]  # and at the tail


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
        cursor_text_style=SELECTED,
        description_style=DESCRIPTION,
        focused=False,
    )
    assert select.focused is False
    dim_band = SELECTED.merge(Theme().dim)
    # D3: the unfocused cursor row's band is the ground_active dimmed, and
    # it rests underneath the label style the row already carried -- and it
    # hugs the row's own cells, a pill behind the label, no trailing pad.
    band = DEFAULT_THEME.ground_active.merge(Theme().dim)
    rows = select.render(30)
    assert rows[0].segments == (
        Segment("\u2192 ", band.merge(dim_band)),
        Segment("one", band.merge(dim_band)),
        Segment("    ", band),
        Segment("first", band.merge(DESCRIPTION)),  # the description keeps its own dim
    )
    assert rows[0].text == "\u2192 one    first"  # the band hugs the row's cells
    assert rows[1].segments == (Segment("  ", LABEL), Segment("two", LABEL))
    assert rows[2].segments == (
        Segment("  ", LABEL),
        Segment("three", LABEL),
        Segment("  "),
        Segment("third", DESCRIPTION),
    )


def test_the_dim_style_comes_from_the_component_theme():
    theme = Theme(dim=DESCRIPTION)
    select = Select([Option("one")], cursor_text_style=SELECTED, focused=False, theme=theme)
    # D3: the band is the theme's ground_active with its dim merged on, and
    # it hugs the row's own cells (a pill, no trailing pad).
    band = theme.ground_active.merge(theme.dim)
    label = SELECTED.merge(theme.dim)
    assert select.render(20)[0].segments == (
        Segment("\u2192 ", band.merge(label)),
        Segment("one", band.merge(label)),
    )
    assert select.render(20)[0].text == "\u2192 one"


def test_a_background_band_keeps_the_unfocused_text_undimmed():
    """SGR ``dim`` is a foreground attribute: it never rides a background.

    A band with an explicit background is its own position signal; merging
    ``dim`` onto it would dim the text into the surface.  Both choice paths
    are covered: the Select band (``ground_active``) and the label style the
    form presets paint.  A background-less band still dims as before.
    """
    band = Style(bg="#1b3a5b")
    select = Select(
        [Option("one")],
        cursor_text_style=SELECTED,
        focused=False,
        theme=Theme(ground_active=band),
    )
    row = select.render(20)[0]
    assert row.segments[0].style == band.merge(SELECTED)
    assert row.segments[0].style.dim is False
    # The label-style path: the selected style itself carries the background
    # (the band does too, so the band path is out of the way and only the
    # style's own merge rule is observed).
    styled_style = Style(fg="#abcdef", bg="#1b3a5b")
    styled = Select(
        [Option("one")],
        cursor_text_style=styled_style,
        focused=False,
        theme=Theme(ground_active=band),
    )
    row = styled.render(20)[0]
    assert row.segments[0].style == band.merge(styled_style)
    assert row.segments[0].style.dim is False
    # The form presets never dim their pick (their own rule), so their
    # selected style reaches the row untouched whether it carries a bg or not.
    form_style = Style(fg="#abcdef", bg="#1b3a5b")
    for group in (RadioGroup(["one"], active_style=form_style, focused=False),
                  CheckboxGroup(["one"], active_style=form_style, focused=False)):
        assert group.render(20)[0].segments[0].style.dim is False
    # Without a background the dim merge is exactly as it was.
    plain = Select([Option("one")], cursor_text_style=SELECTED, focused=False)
    assert plain.render(20)[0].segments[0].style == SELECTED.merge(DEFAULT_THEME.dim)


def test_activate_takes_the_cursor_option_once():
    menu = Select(THREE)
    menu.index = 1
    assert menu.activate() is True
    assert menu.take_result() == Option("two")
    assert menu.take_result() is None  # read-once: the take cleared it


def test_an_empty_menu_activates_to_nothing():
    empty = Select([])
    assert empty.activate() is False
    assert empty.take_result() is None


def test_moving_the_cursor_clears_a_pending_pick():
    menu = Select(THREE)
    assert menu.activate() is True
    assert menu.move(1) is True
    assert menu.take_result() is None


def test_a_committing_select_writes_the_row_it_landed_on():
    form = Select(THREE, commit=True)
    assert form.take_result() is None  # nothing picked before the first gesture
    assert form.move(1) is True and form.take_result() == Option("two")  # the step is the choice
    assert form.click(2, 0) is True and form.take_result() == Option("three")
    assert form.move(-1) is True and form.take_result() == Option("two")


def test_a_re_filter_clears_the_pending_result_and_activate_takes_the_match():
    auto = Autocomplete(options=THREE)
    auto.set_query("tw")  # one match, not the universe's cursor row
    assert auto.activate() is True
    assert auto.take_result() == Option("two")
    auto.set_query("th")
    assert auto.take_result() is None


def test_style_injection_round_trips():
    select = Select(
        [Option("one", description="h"), Option("two")],
        title="T",
        label_style=LABEL,
        cursor_text_style=SELECTED,
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
    # hugs the row's own cells, a pill behind the text.  D1: that band is
    # NONE under the default theme, so the row is its own two segments with
    # no pad.
    assert rows[2].segments == (
        Segment("\u2192 ", SELECTED),
        Segment("two", SELECTED),
    )
    # the theme fields feed the same parameters
    theme = Theme(accent=SELECTED, dim=DESCRIPTION)
    themed = Select([Option("one", description="h")], theme=theme).render(40)
    assert themed[0].segments[0] == Segment("\u2192 ", SELECTED)
    assert themed[0].segments[3] == Segment("h", DESCRIPTION)
    assert themed[0].segments[-1] == Segment("h", DESCRIPTION)


def test_the_marker_can_be_replaced_and_the_rows_follow_its_width():
    select = Select([Option("one"), Option("two")], marker="\u276f")
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(select, 20) == ["\u276f one", "  two"]


# --- RadioGroup: the single-choice preset -----------------------------------------------


def test_radio_renders_one_marked_row_per_label():
    group = RadioGroup(["one", "two", "three"])
    rows = group.render(30)
    assert texts(group, 30) == ["(\u2022) one", "( ) two", "( ) three"]
    assert rows[0].segments == (
        Segment(FILLED_SEAT, DEFAULT_THEME.accent),
        Segment("one", DEFAULT_THEME.accent),
    )
    assert rows[1].segments == (Segment("( ) ", NONE), Segment("two", NONE))
    assert isinstance(group, Component)


def test_radio_index_clamps_and_selected_reads_the_label():
    group = RadioGroup(["a", "b", "c"], index=7)
    assert group.index == 2 and group.selected == "c"
    group.index = -4
    assert group.index == 0 and group.selected == "a"
    assert texts(group, 20)[0] == "(\u2022) a"
    empty = RadioGroup([])
    assert empty.index == 0 and empty.selected is None and empty.render(20) == []


def test_radio_move_steps_and_clamps_and_lands_the_new_selection():
    group = RadioGroup(["one", "two", "three"])
    assert group.take_result() is None
    assert group.move(1) is True
    assert (group.index, group.take_result()) == (1, "two")
    assert group.move(-9) is True  # clamped at the start
    assert (group.index, group.take_result()) == (0, "one")
    assert group.move(-1) is False  # already there: nothing moved, nothing chosen
    assert group.take_result() is None
    assert RadioGroup([]).move(1) is False


def test_radio_click_is_the_mouse_door_and_ignores_the_column():
    group = RadioGroup(["one", "two", "three"])
    assert isinstance(group, Clickable)
    for col in (0, 3, 40):  # a row owns the whole width
        assert group.click(2, col) is True and group.take_result() == "three"
        assert group.index == 2
    assert group.click(2, 0) is True  # a hit even when it already was selected
    assert group.take_result() == "three"
    for row in (-1, 3, 9):
        assert group.click(row, 0) is False and group.take_result() is None
        assert group.index == 2


def test_radio_activate_takes_the_selection_and_reads_once():
    group = RadioGroup(["one", "two"])
    assert isinstance(group, Activable)
    group.move(1)
    assert group.take_result() == "two"  # the step's own pick
    assert group.activate() is True and group.take_result() == "two"
    assert group.take_result() is None
    assert RadioGroup([]).activate() is False and RadioGroup([]).take_result() is None


def test_radio_takes_option_payloads_as_the_result():
    group = RadioGroup([Option("alpha", 1), Option("beta", 2), Option("plain")])
    assert group.labels == ["alpha", "beta", "plain"]
    assert group.move(1) is True and group.take_result() == 2
    assert group.click(2, 0) is True and group.take_result() == "plain"  # value None: the label
    assert group.move(-1) is True and group.take_result() == 2


def test_radio_marks_the_row_under_a_cell_and_clears_back():
    group = RadioGroup(["one", "two", "three"], label_style=PLAIN)
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
        return RadioGroup(
            ["one", "two"],
            active_style=SELECTED,
            label_style=PLAIN,
            focused=focused,
        )

    plain, focused = build(False), build(True)
    # The selected row's band (the renamed focus_style, ground_active by
    # default) rests underneath the accent label while the group is focused.
    assert focused.render(20)[0].segments[0] == Segment(
        FILLED_SEAT, SELECTED.merge(DEFAULT_THEME.accent)
    )
    assert focused.render(20)[1] == plain.render(20)[1]  # only the selected row carries it
    assert plain.render(20)[0].segments[0] == Segment(FILLED_SEAT, DEFAULT_THEME.accent)


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
    # -- a pill behind each row's own cells, no trailing pad; only the
    # engaged row swaps the band.
    assert rows[0].segments == (Segment("T", ground),)  # the title
    assert rows[0].text == "T"
    assert rows[2].segments == (Segment("(1/2)", ground.merge(DEFAULT_THEME.dim)),)
    assert rows[2].text == "(1/2)"
    assert rows[1].segments[0].style == DEFAULT_THEME.ground_active.merge(
        DEFAULT_THEME.accent
    )
    # the theme field is the fallback the explicit style wins over
    themed = Select([Option("one"), Option("two")], theme=replace(DEFAULT_THEME, ground=ground))
    assert themed.render(20)[1].segments[0].style == ground
    assert themed.render(20)[1].text == "  two"


def test_the_groups_take_the_ground_style_under_their_rows():
    ground = Style(fg="#101010")
    # The form rule leaves the unfocused selected row on the ground like any
    # other; the mark column rides it.
    group = RadioGroup(["one", "two"], ground_style=ground)
    assert group.render(20)[1].segments == (
        Segment("( ) ", ground),
        Segment("two", ground),
    )
    assert group.render(20)[1].text == "( ) two"  # the ground hugs the row's cells
    checks = CheckboxGroup(["x", "y"], ground_style=ground)
    assert checks.render(20)[1].segments[0].style == ground
    themed = RadioGroup(["one", "two"], theme=replace(DEFAULT_THEME, ground=ground))
    assert themed.render(20)[1].segments[1].style == ground


# --- CheckboxGroup: the multiple-choice preset ----------------------------------------


def test_check_group_toggles_marks_and_reads_the_marked_values():
    group = CheckboxGroup(["apples", "pears", "plums"], marked=(2,), focused=True)
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(group, 30) == [
        "\u2192 [ ] apples",
        "  [ ] pears",
        "  [x] plums",
    ]
    assert group.take_result() == ["plums"]  # the marks are the selection, in row order
    assert group.toggle() is True  # the row flips and the selection follows
    assert group.take_result() == ["apples", "plums"]
    group.move(1)
    assert group.activate() is True  # enter is the same gesture (Toggle semantics)
    assert group.take_result() == ["apples", "pears", "plums"]
    assert texts(group, 30)[1] == "\u2192 [x] pears"
    assert CheckboxGroup([]).toggle() is False  # nothing to flip
    assert CheckboxGroup(["one"]).take_result() is None  # a row at rest: no selection at all


def test_check_group_carries_option_values_into_the_mark_list():
    group = CheckboxGroup([Option("alpha", 1), "beta", Option("plain")], marked=(0, 2))
    assert group.take_result() == [1, "plain"]  # the payload; None falls back to the label


def test_a_multi_select_keeps_the_mark_column_before_the_label():
    menu = Select([Option("one", description="first"), Option("two")], multi=True, marked=(1,))
    # The description column is lead (2) + the mark (4) + the widest label (3) + the gap (2).
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(menu, 30) == [
        "\u2192 [ ] one  first",
        "  [x] two",
    ]
    assert menu.take_result() == ["two"]


def test_a_multi_select_moves_without_touching_the_marks():
    menu = Select(THREE, multi=True, marked=(1,))
    assert menu.take_result() == ["two"]
    assert menu.move(1) is True and menu.index == 1
    assert menu.take_result() is None  # a move mints no pick
    assert menu.toggle() is True  # unmark "two": the marks, not the cursor, are the selection
    assert menu.take_result() is None
    assert menu.toggle() is True  # mark it again
    assert menu.take_result() == ["two"]


# --- the glyph parameters ------------------------------------------------------------


def test_an_empty_select_marker_collapses_its_seat():
    select = Select([Option("one", description="d"), Option("two")], marker="")
    rows = select.render(20)
    assert texts(select, 20) == ["one  d", "two"]  # the description column loses the seat
    assert rows[0].segments[0].text == ""
    assert rows[1].segments[0].text == ""  # no dangling separator space
    assert select.revision()[3] == ""  # the marker is a row input


def test_a_wide_select_marker_keeps_the_labels_in_one_column():
    select = Select([Option("one"), Option("two")], marker="\u6811")
    rows = select.render(20)
    assert texts(select, 20) == ["\u6811 one", "   two"]
    assert visible_width(rows[0].segments[0].text) == 3
    assert visible_width(rows[1].segments[0].text) == 3
    # The description column is measured with the seat, not ``len(marker)``.
    wide = Select(
        [Option("one", description="d"), Option("two", description="e")], marker="\u6811"
    )
    assert texts(wide, 20) == ["\u6811 one  d", "   two  e"]


def test_the_multi_mark_pair_is_padded_to_its_wider_member():
    menu = Select(
        [Option("one"), Option("two")], multi=True, mark_pair=("\u6811", "")
    )
    menu.toggle()
    rows = menu.render(20)
    assert texts(menu, 20) == ["\u2192 \u6811 one", "     two"]
    assert visible_width(rows[0].segments[1].text) == 3
    assert visible_width(rows[1].segments[1].text) == 3
    assert menu.take_result() == ["one"]


def test_an_empty_mark_pair_collapses_the_multi_column():
    menu = Select([Option("one"), Option("two")], multi=True, mark_pair=("", ""))
    menu.toggle()
    assert texts(menu, 20) == ["\u2192 one", "  two"]


def test_radio_renders_its_own_seat_pair_and_pads_both_members():
    group = RadioGroup(["a", "b"], empty="( )", filled="\u6811")
    rows = group.render(20)
    assert texts(group, 20) == ["\u6811  a", "( ) b"]
    assert visible_width(rows[0].segments[0].text) == 4
    assert visible_width(rows[1].segments[0].text) == 4
    # Both empty: the group collapses to labels, the selection carried by style.
    bare = RadioGroup(["a", "b"], empty="", filled="")
    assert texts(bare, 20) == ["a", "b"]
    # One empty member: the filled state keeps the pair's width.
    half = RadioGroup(["a", "b"], empty="", filled=">")
    assert texts(half, 20) == ["> a", "  b"]


def test_check_group_takes_its_mark_pair_and_keeps_the_marked_set():
    group = CheckboxGroup(["a", "b"], marked=(1,), mark_pair=("\u6811", ""))
    rows = group.render(20)
    assert rows[0].segments[1].text == "   "  # unmarked: the empty member pads
    assert rows[1].segments[1].text == "\u6811 "
    assert visible_width(rows[0].segments[1].text) == 3
    assert group.take_result() == ["b"]
    # Both empty: no mark column at all, the rows read as a plain select.
    plain = CheckboxGroup(["a"], mark_pair=("", ""))
    assert plain.render(20)[0].text == "\u2192 a"


def test_every_choice_glyph_parameter_is_a_revision_input():
    select = Select(THREE)
    before = select.revision()
    select.marker = ">"
    assert select.revision() != before
    multi = Select(THREE, multi=True)
    before = multi.revision()
    multi.mark_pair = ("[X]", "[ ]")
    assert multi.revision() != before
    group = RadioGroup(["a"])
    for name, value in (("empty", "(  )"), ("filled", "(o)")):
        before = group.revision()
        setattr(group, name, value)
        assert group.revision() != before, name
    checks = CheckboxGroup(["a"])
    before = checks.revision()
    checks.mark_pair = ("[X]", "[ ]")
    assert checks.revision() != before


# --- the cursor vocabulary and the disabled surface --------------------------------


def test_select_home_end_and_select_place_the_cursor_on_enabled_rows():
    menu = Select(THREE, disabled_items=(1,))
    menu.index = 1
    assert menu.select(2) is True and menu.index == 2
    assert menu.select(2) is False  # already there: nothing moved
    assert menu.select(1) is False  # a disabled row is refused
    assert menu.home() is True and menu.index == 0
    assert menu.end() is True and menu.index == 2
    assert menu.home() is True and menu.index == 0
    assert menu.home() is False  # already on the first enabled row
    assert Select([]).select(0) is False


def test_move_steps_over_disabled_items_and_stops_when_direction_is_closed():
    menu = Select(THREE, disabled_items=(1,))
    assert menu.move(1) is True and menu.index == 2  # skipped the disabled row
    assert menu.move(-1) is True and menu.index == 0  # and back over it
    clamp = Select(THREE, wrap=False, disabled_items=(1,))
    assert clamp.move(1) is True and clamp.index == 2  # the step skips the disabled row
    assert clamp.move(1) is False and clamp.index == 2  # the edge closed the direction
    closed = Select(THREE, wrap=False, disabled_items=(1, 2))
    assert closed.move(1) is False and closed.index == 0  # no enabled landing on the way on
    all_off = Select(THREE, disabled_items=(0, 1, 2))
    assert all_off.move(1) is False and all_off.move(-1) is False


def test_a_disabled_select_refuses_every_gesture_but_still_renders():
    menu = Select(THREE, disabled=True)
    assert menu.move(1) is False and menu.select(1) is False
    assert menu.click(0, 0) is False and menu.activate() is False
    assert menu.home() is False and menu.end() is False
    assert menu.take_result() is None
    assert menu.render(20)[0].segments[0].style == DEFAULT_THEME.dim


def test_disabled_items_paint_the_disabled_band_and_refuse_activation():
    menu = Select(THREE, disabled_items=(1,), disabled_style=Style(italic=True))
    rows = menu.render(20)
    assert rows[1].segments[1].style == Style(italic=True)
    assert menu.click(1, 0) is False
    menu.index = 1
    assert menu.activate() is False


def test_the_groups_refuse_option_descriptions():
    with pytest.raises(ValueError, match="description"):
        RadioGroup([Option("one", description="explained")])
    with pytest.raises(ValueError, match="description"):
        CheckboxGroup([Option("one", description="explained")])


def test_checkbox_group_click_moves_the_cursor_and_toggles_the_row():
    """The P0: a click is the multi-select's selection act, not a bare move."""
    group = CheckboxGroup(["one", "two", "three"])
    assert group.click(2, 0) is True
    assert group.index == 2 and group.take_result() == ["three"]
    assert group.click(2, 0) is True  # the same row flips back
    assert group.index == 2 and group.take_result() is None
    assert group.click(0, 0) is True and group.take_result() == ["one"]
    assert group.click(0, 5) is True  # the column is ignored
    assert group.click(9, 0) is False  # the counter/row gap is not an option
    disabled = CheckboxGroup(["one", "two"], disabled_items=(1,))
    assert disabled.click(1, 0) is False and disabled.take_result() is None


def test_radio_group_and_checkbox_group_honor_disabled_items():
    radio = RadioGroup(["one", "two", "three"], disabled_items=(1,))
    assert radio.move(1) is True and radio.index == 2
    assert radio.take_result() == "three"
    assert radio.click(1, 0) is False and radio.take_result() is None
    checks = CheckboxGroup(["one", "two"], disabled=True)
    assert checks.click(0, 0) is False and checks.toggle() is False
    assert checks.activate() is False and checks.take_result() is None


# --- the shared bands -----------------------------------------------------------------


def test_select_bands_override_the_theme_tokens():
    ground = Style(fg="#101010")
    active = Style(fg="#abcdef")
    hover = Style(fg="#123456")
    menu = Select(
        THREE,
        bands=RowBands(ground=ground, active=active, hover=hover, dim=Style(dim=True)),
    )
    rows = menu.render(20)
    assert rows[0].segments[0].style == active.merge(DEFAULT_THEME.accent)  # cursor
    assert rows[1].segments[0].style == ground  # a resting row
    menu.hover_at(1, 0)
    assert menu.render(20)[1].segments[0].style == hover
    assert menu.revision()[-4] == menu.bands
    # An explicit style parameter still wins over the band token.
    explicit = Select(THREE, bands=RowBands(ground=ground), ground_style=Style(fg="#202020"))
    assert explicit.render(20)[1].segments[0].style == Style(fg="#202020")


def test_the_form_groups_compose_the_band_tokens_without_dimming_the_pick():
    active = Style(fg="#abcdef")
    hover = Style(fg="#123456")
    ground = Style(fg="#101010")
    bands = RowBands(ground=ground, active=active, hover=hover)
    for group in (RadioGroup(["a", "b"], bands=bands, focused=True),
                  CheckboxGroup(["a", "b"], bands=bands, focused=True)):
        rows = group.render(20)
        # The engaged band rests under the pick's accent label.
        assert rows[0].segments[0].style == active.merge(DEFAULT_THEME.accent)
        group.hover_at(1, 0)
        assert group.render(20)[1].segments[0].style == hover
        group.focused = False
        group.hover_at(-1, -1)
        # The group never dims its pick: the band is the ground, the label
        # keeps its accent.
        assert group.render(20)[0].segments[0].style == ground.merge(DEFAULT_THEME.accent)
