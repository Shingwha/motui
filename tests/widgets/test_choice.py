"""Select and its presets: cursor, window, result and the multi-mark groups."""

from dataclasses import replace

import pytest

from motui.kernel.glyphs import GLYPHS
from motui.kernel.cell import Surface
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import CheckboxGroup, MultiSelect, Option, RadioGroup, Select

from tests.testing import texts

THREE = [Option("one"), Option("two"), Option("three")]


# -- Select: the cursor -------------------------------------------------------


@pytest.mark.parametrize(
    "start, delta, index",
    [(0, 1, 1), (2, 1, 0), (0, -1, 2)],
)
def test_move_wraps_around_the_ends_by_default(start, delta, index):
    select = Select(THREE)
    select.index = start
    assert select.move(delta) is True
    assert select.index == index and select.selected == THREE[index]


@pytest.mark.parametrize("start, delta, index, moved", [(0, 5, 2, True), (0, -1, 0, False)])
def test_a_non_wrapping_select_clamps_at_the_ends(start, delta, index, moved):
    select = Select(THREE, wrap=False)
    select.index = start
    assert select.move(delta) is moved
    assert select.index == index


def test_an_empty_list_has_no_selection_and_cannot_move():
    empty = Select([])
    assert empty.selected is None
    assert empty.move(1) is False
    assert list(empty.render(20)) == []


def test_assigning_the_index_clamps_into_the_rows():
    menu = Select(THREE)
    menu.index = 99
    assert menu.index == 2
    menu.index = -4
    assert menu.index == 0
    menu.options = []
    menu.index = 3
    assert menu.index == 0 and menu.selected is None


def test_select_home_and_end_land_on_enabled_rows():
    menu = Select(THREE, disabled_items=(1,))
    menu.index = 1
    assert menu.select(2) is True and menu.index == 2
    assert menu.select(2) is False
    assert menu.select(1) is False
    assert menu.home() is True and menu.index == 0
    assert menu.end() is True and menu.index == 2
    assert menu.home() is True and menu.index == 0
    assert menu.home() is False
    assert Select([]).select(0) is False


# -- Select: rendering --------------------------------------------------------


def test_render_marks_the_cursor_row_and_aligns_descriptions():
    select = Select(
        [Option("one", description="first"), Option("two"), Option("three", description="third")]
    )
    assert texts(select, 30) == ["\u2192 one    first", "  two", "  three  third"]
    select.move(1)
    assert texts(select, 30)[1] == "\u2192 two"


def test_the_description_column_holds_still_while_the_window_scrolls():
    options = [Option("a", description="x"), Option("a-very-long-label", description="y")]
    options += [Option(f"i{i}", description="z") for i in range(4)]
    menu = Select(options, max_rows=2)
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
    menu.index = 5
    assert texts(menu, 30) == [
        "  item3  row 3",
        "  item4  row 4",
        "\u2192 item5  row 5",
        "(6/10)",
    ]


def test_window_true_centres_the_window_on_the_cursor():
    menu = Select([Option(f"i{i}") for i in range(10)], max_rows=3, window=True)
    assert texts(menu, 30) == ["\u2192 i0", "  i1", "  i2", "(1/10)"]
    menu.index = 5
    assert texts(menu, 30) == ["  i4", "\u2192 i5", "  i6", "(6/10)"]
    menu.index = 9
    assert texts(menu, 30) == ["  i7", "  i8", "\u2192 i9", "(10/10)"]


@pytest.mark.parametrize(
    "menu",
    [Select(THREE)],
)
def test_a_menu_that_never_scrolls_renders_no_counter(menu):
    rows = texts(menu, 30)
    assert all(not row.startswith("(") for row in rows)
    assert len(rows) == len(menu.options)


def test_the_glyph_vocabulary_replaces_the_cursor_and_its_wide_seat():
    assert texts(Select(THREE, glyphs=replace(GLYPHS, cursor="\u276f")), 20)[0] == "\u276f one"
    wide = Select(
        [Option("one", description="d"), Option("two", description="e")],
        glyphs=replace(GLYPHS, cursor="\u6811"),
    )
    assert texts(wide, 20) == ["\u6811 one  d", "   two  e"]


def test_an_empty_cursor_glyph_collapses_its_seat():
    select = Select(
        [Option("one", description="d"), Option("two")],
        glyphs=replace(GLYPHS, cursor=""),
    )
    assert texts(select, 20) == ["one  d", "two"]


def test_an_unfocused_menu_wears_the_inactive_band():
    select = Select(THREE)
    select.focused = False
    rows = select.render(20)
    assert any(
        seg.style.bg == DEFAULT_THEME.rows.inactive.bg for seg in rows[0].segments
    )
    assert rows[0].segments[1].style.fg == DEFAULT_THEME.content.accent.fg
    assert rows[1].segments[1].style.fg is None


def test_a_theme_assignment_repaints_the_next_render():
    menu = Select(THREE)
    plain = menu.render(20)
    theme = replace(DEFAULT_THEME, text=replace(DEFAULT_THEME.text, base=Style(underline=True)))
    menu.theme = theme
    repainted = menu.render(20)
    assert repainted != plain
    assert any(seg.style.underline for seg in repainted[1].segments)


@pytest.mark.parametrize(
    "row, index, hit",
    [(1, 0, True), (0, 1, False), (3, 1, False), (-1, 1, False)],
)
def test_click_places_the_cursor_on_the_option_under_the_row(row, index, hit):
    select = Select([Option("one"), Option("two")], title="pick")
    select.index = 1
    assert select.click(row, 0) is hit
    assert select.index == index


def test_click_ignores_the_column_and_maps_through_the_window():
    select = Select([Option("one"), Option("two")], title="pick")
    for col in (0, 3, 400):
        select.index = 1
        assert select.click(1, col) is True and select.index == 0
    menu = Select([Option(f"item{i}") for i in range(10)], max_rows=3)
    menu.index = 5
    assert menu.click(0, 0) is True and menu.index == 3
    menu.index = 5
    assert menu.click(2, 0) is True and menu.index == 5
    menu.index = 5
    assert menu.click(3, 0) is False and menu.index == 5


def test_activate_leaves_the_cursor_option_pending_once():
    menu = Select(THREE)
    menu.index = 1
    assert menu.activate() is True
    assert menu.take_result() == Option("two")
    assert menu.take_result() is None


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
    assert form.take_result() is None
    assert form.move(1) is True and form.take_result() == Option("two")
    assert form.click(2, 0) is True and form.take_result() == Option("three")


def test_a_disabled_select_refuses_every_gesture_but_still_renders():
    menu = Select(THREE, disabled=True)
    assert menu.move(1) is False and menu.select(1) is False
    assert menu.click(0, 0) is False and menu.activate() is False
    assert menu.home() is False and menu.end() is False
    assert menu.render(20)[0].segments[1].style.fg == DEFAULT_THEME.text.faint.fg


def test_disabled_items_are_skipped_refused_and_painted_dim():
    menu = Select(
        THREE,
        disabled_items=(1,),
        styles=Styles(text=replace(DEFAULT_THEME.text, faint=Style(italic=True))),
    )
    assert menu.move(1) is True and menu.index == 2
    assert menu.move(-1) is True and menu.index == 0
    assert menu.render(20)[1].segments[1].style == Style(italic=True)
    assert menu.click(1, 0) is False
    menu.index = 1
    assert menu.activate() is False


# -- RadioGroup ---------------------------------------------------------------


def test_radio_renders_one_marked_row_per_label():
    group = RadioGroup(["one", "two", "three"])
    assert texts(group, 30) == ["(\u2022) one", "( ) two", "( ) three"]
    row = group.render(30)[0]
    assert row.segments[0].style == DEFAULT_THEME.content.accent
    assert row.segments[1].style == DEFAULT_THEME.text.base


def test_radio_index_clamps_and_selected_reads_the_label():
    group = RadioGroup(["a", "b", "c"], index=7)
    assert group.index == 2 and group.selected == "c"
    group.index = -4
    assert group.index == 0 and group.selected == "a"
    assert texts(group, 20)[0] == "(\u2022) a"
    empty = RadioGroup([])
    assert empty.index == 0 and empty.selected is None
    assert list(empty.render(20)) == []


def test_radio_move_clamps_and_leaves_the_new_selection_pending():
    group = RadioGroup(["one", "two", "three"])
    assert group.take_result() is None
    assert group.move(1) is True
    assert (group.index, group.take_result()) == (1, "two")
    assert group.move(-9) is True
    assert (group.index, group.take_result()) == (0, "one")
    assert group.move(-1) is False and group.take_result() is None


def test_radio_click_selects_the_row_and_ignores_the_column():
    group = RadioGroup(["one", "two", "three"])
    for col in (0, 3, 40):
        assert group.click(2, col) is True and group.take_result() == "three"
    assert group.click(2, 0) is True and group.take_result() == "three"
    for row in (-1, 3, 9):
        assert group.click(row, 0) is False and group.take_result() is None


def test_radio_takes_option_payloads_and_falls_back_to_the_label():
    group = RadioGroup([Option("alpha", 1), Option("beta", 2), Option("plain")])
    assert group.labels == ["alpha", "beta", "plain"]
    assert group.click(1, 0) is True and group.take_result() == 2
    assert group.click(2, 0) is True and group.take_result() == "plain"


def test_radio_skips_and_refuses_disabled_items():
    radio = RadioGroup(["one", "two", "three"], disabled_items=(1,))
    assert radio.move(1) is True and radio.index == 2
    assert radio.take_result() == "three"
    assert radio.click(1, 0) is False and radio.take_result() is None


def test_the_focused_group_carries_the_active_band_under_its_pick():
    styles = Styles(rows=replace(DEFAULT_THEME.rows, active=Style(underline=True)))
    focused = RadioGroup(["one", "two"], styles=styles)
    focused.focused = True
    unfocused = RadioGroup(["one", "two"], styles=styles)
    assert all(seg.style.underline for seg in focused.render(20)[0].segments)
    assert not any(seg.style.underline for seg in unfocused.render(20)[0].segments)


# -- CheckboxGroup ------------------------------------------------------------


def test_check_group_toggles_marks_and_reads_the_marked_values():
    group = CheckboxGroup(["apples", "pears", "plums"], marked=(2,))
    assert texts(group, 30) == ["\u2192 [ ] apples", "  [ ] pears", "  [x] plums"]
    assert group.take_result() == ["plums"]
    assert group.toggle() is True
    assert group.take_result() == ["apples", "plums"]
    group.move(1)
    assert group.activate() is True
    assert group.take_result() == ["apples", "pears", "plums"]


def test_check_group_click_moves_the_cursor_and_toggles_the_row():
    group = CheckboxGroup(["one", "two", "three"])
    assert group.click(2, 0) is True
    assert group.index == 2 and group.take_result() == ["three"]
    assert group.click(2, 0) is True and group.take_result() is None
    assert group.click(0, 5) is True and group.take_result() == ["one"]
    assert group.click(9, 0) is False


def test_a_disabled_check_group_refuses_every_gesture():
    checks = CheckboxGroup(["one", "two"], disabled=True)
    assert checks.click(0, 0) is False and checks.toggle() is False
    assert checks.activate() is False and checks.take_result() is None


def test_a_multi_select_keeps_the_mark_column_before_the_label():
    menu = MultiSelect([Option("one", description="first"), Option("two")], marked=(1,))
    assert texts(menu, 30) == ["\u2192 [ ] one  first", "  [x] two"]
    assert menu.take_result() == ["two"]
    assert menu.move(1) is True and menu.take_result() is None


@pytest.mark.parametrize("group", [RadioGroup, CheckboxGroup])
def test_the_form_groups_refuse_option_descriptions(group):
    with pytest.raises(ValueError, match="description"):
        group([Option("one", description="explained")])


def test_the_custom_glyph_pairs_pad_to_the_wider_member():
    menu = MultiSelect(
        [Option("one"), Option("two")],
        glyphs=replace(GLYPHS, check_on="\u6811", check_off=""),
    )
    menu.toggle()
    rows = menu.render(20)
    assert [row.segments[1].text for row in rows] == ["\u6811 ", "   "]
    plain = MultiSelect(
        [Option("one"), Option("two")],
        glyphs=replace(GLYPHS, check_on="", check_off=""),
    )
    plain.toggle()
    assert texts(plain, 20) == ["\u2192 one", "  two"]
    group = RadioGroup(
        ["a", "b"], glyphs=replace(GLYPHS, radio_off="", radio_on=">")
    )
    assert texts(group, 20) == ["> a", "  b"]


# -- the 2.0 render contract -------------------------------------------------


def test_select_answers_a_surface_and_honours_the_height_budget():
    menu = Select(THREE)
    surface = menu.render(Constraints(width=20, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["\u2192 one", "  two"]
    assert surface.width == 20 and surface.height == 2
    # The 1.x int spelling still answers the natural window.
    assert [row.text for row in menu.render(20)] == [
        "\u2192 one",
        "  two",
        "  three",
    ]
