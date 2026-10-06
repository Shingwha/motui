"""Tests for mocode_tui.widgets.choice (Option / Select / Confirm).

``Select`` is the menu: a ``"\u2192 "`` cursor row, a description column
measured over the whole option list, a ``max_rows`` window that follows the
cursor, the ``(i/n)`` counter row it renders while the window scrolls, and a
cursor that wraps around the ends (``wrap=False`` clamps).  ``Confirm`` is
the Yes/No specialization.
"""

import pytest

from mocode_tui.widgets.choice import Confirm, Option, Select
from mocode_tui.core.block import Clickable
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import Theme

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
