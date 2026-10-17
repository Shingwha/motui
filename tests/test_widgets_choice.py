"""Tests for motui.widgets.choice (Option / Select / Confirm).

``Select`` is the menu: a ``"\u2192 "`` cursor row, a description column
measured over the whole option list, a ``max_rows`` window that follows the
cursor, the ``(i/n)`` counter row it renders while the window scrolls, and a
cursor that wraps around the ends (``wrap=False`` clamps).  ``Confirm`` is
the Yes/No specialization.  ``activate()`` is the family's activation: it
takes the option under the cursor into ``chosen``, which the host reads
once -- ``move()`` and a re-filter clear it.  ``focused`` is the focus flag:
while set the cursor row is ``selected_style``, unset it is that style
merged with the theme's ``dim``.
"""

import pytest

from motui.widgets.choice import Confirm, Option, Select
from motui.widgets.autocomplete import Autocomplete
from motui.kernel.block import Activable, Clickable, Focusable
from motui.kernel.lines import Segment
from motui.kernel.style import Style
from motui.kernel.theme import Theme

from _doubles import texts

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
DESCRIPTION = Style(fg="#123456")
LABEL = Style(bold=True)
TITLE = Style(fg="#fedcba")
DANGER = Style(fg="#0f0f0f")

THREE = [Option("one"), Option("two"), Option("three")]


def test_option_fields_and_defaults():
    assert Option("Save") == Option("Save", None, "")
    entry = Option("x", value=1, description="ctrl-s")
    assert entry.value == 1 and entry.description == "ctrl-s"


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
    assert texts(select, 30) == ["\u2192 one    first", "  two", "  three  third"]
    rows = select.render(30)
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
    assert texts(menu, 40)[0] == "\u2192 a" + " " * 18 + "x"
    menu.index = 5
    assert texts(menu, 40)[0] == "  i2" + " " * 17 + "z"


def test_max_rows_windows_the_rows_and_shows_the_counter():
    menu = Select([Option(f"item{i}", description=f"row {i}") for i in range(10)], max_rows=3)
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


def test_confirm_maps_the_same_at_any_column():
    confirm = Confirm("Delete?")
    for col in (0, 12, 999):
        assert confirm.click(0, col) is False  # the message row is not an option
        assert confirm.click(1, col) is True and confirm.selected == Option("Yes", True)
        assert confirm.click(2, col) is True and confirm.selected == Option("No", False)


def test_assigning_the_index_clamps_into_the_rows():
    menu = Select(THREE)
    menu.index = 99
    assert menu.index == 2
    menu.index = -4
    assert menu.index == 0
    menu.options = []
    menu.index = 3
    assert menu.index == 0 and menu.selected is None


def test_choice_components_are_clickable():
    assert isinstance(Select(THREE), Clickable)
    assert isinstance(Confirm("Delete?"), Clickable)


def test_the_menu_family_is_activable():
    assert isinstance(Select(THREE), Activable)
    assert isinstance(Confirm("Delete?"), Activable)
    assert isinstance(Autocomplete(options=THREE), Activable)


def test_the_menu_family_is_focusable():
    assert isinstance(Select(THREE), Focusable)
    assert isinstance(Confirm("Delete?"), Focusable)
    assert isinstance(Autocomplete(options=THREE), Focusable)


def test_a_focused_menu_renders_the_same_bytes_as_the_default():
    """``focused=True`` is the default: the flag changes no byte while set."""
    kwargs = dict(
        title="pick",
        label_style=LABEL,
        selected_style=SELECTED,
        description_style=DESCRIPTION,
        title_style=TITLE,
    )
    options = [Option("one", description="first"), Option("two")]
    explicit = Select(options, focused=True, **kwargs)
    default = Select(options, **kwargs)
    for width in (0, 6, 30):
        assert explicit.render(width) == default.render(width)
    assert explicit.render(30)[1].segments[0] == Segment("\u2192 ", SELECTED)


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
    rows = select.render(30)
    assert rows[0].segments == (
        Segment("\u2192 ", dim_band),
        Segment("one", dim_band),
        Segment("    "),
        Segment("first", DESCRIPTION),  # the description keeps its own dim
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
    band = SELECTED.merge(DESCRIPTION)
    assert select.render(20)[0].segments == (
        Segment("\u2192 ", band),
        Segment("one", band),
    )


def test_an_unfocused_confirm_dims_its_yes_no_row():
    confirm = Confirm("Delete?")
    assert Confirm("Delete?").focused is True
    confirm.focused = False
    band = Theme().accent.merge(Theme().dim)
    rows = confirm.render(30)
    assert rows[0].segments == (Segment("Delete?", Style()),)  # the message row
    assert rows[1].segments == (Segment("\u2192 ", band), Segment("Yes", band))
    assert rows[2].segments == (Segment("  "), Segment("No"))


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


def test_a_re_filter_clears_chosen_and_activate_takes_the_match():
    auto = Autocomplete(options=THREE)
    auto.set_query("tw")  # one match, not the universe's cursor row
    assert auto.activate() is True
    assert auto.chosen == Option("two")
    auto.set_query("th")
    assert auto.chosen is None


def test_confirm_activation_hands_back_the_boolean_choice():
    confirm = Confirm("Delete?")
    assert confirm.activate() is True
    assert confirm.chosen == Option("Yes", True)
    confirm.chosen = None
    assert confirm.move(1) is True
    assert confirm.activate() is True
    assert confirm.chosen == Option("No", False)


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
    assert rows[2].segments == (Segment("\u2192 ", SELECTED), Segment("two", SELECTED))
    # the theme fields feed the same parameters
    theme = Theme(accent=SELECTED, dim=DESCRIPTION)
    themed = Select([Option("one", description="h")], theme=theme).render(40)
    assert themed[0].segments[0] == Segment("\u2192 ", SELECTED)
    assert themed[0].segments[-1] == Segment("h", DESCRIPTION)


def test_the_marker_can_be_replaced_and_the_rows_follow_its_width():
    select = Select([Option("one"), Option("two")], marker="\u276f")
    assert texts(select, 20) == ["\u276f one", "  two"]


def test_confirm_is_a_two_option_select():
    confirm = Confirm("Delete file?")
    assert confirm.selected == Option("Yes", True)
    assert confirm.move(1) is True and confirm.selected == Option("No", False)
    assert confirm.move(1) is True and confirm.selected == Option("Yes", True)  # wraps
    assert texts(Confirm("Quit?"), 30) == ["Quit?", "\u2192 Yes", "  No"]
    assert confirm.click(0, 0) is False  # the message row
    assert confirm.click(1, 0) is True and confirm.selected == Option("Yes", True)
    assert confirm.click(2, 0) is True and confirm.selected == Option("No", False)


def test_a_dangerous_confirm_styles_its_message():
    theme = Theme(error=DANGER)
    row = Confirm("Delete everything?", danger=True, theme=theme).render(40)[0]
    assert row.segments == (Segment("Delete everything?", DANGER),)
    # without danger the message is unstyled
    plain = Confirm("Delete everything?", theme=theme).render(40)[0]
    assert plain.segments == (Segment("Delete everything?", Style()),)
