"""MenuBar and ContextMenu: the menu strip and the desktop menu preset."""

from dataclasses import replace

from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import ContextMenu, MenuBar, Option, Select

from tests.testing import texts


def test_menubar_renders_one_row_with_dividers_and_padding():
    bar = MenuBar(["File", "Edit", "View"])
    rows = bar.render(40)
    assert len(rows) == 1
    assert rows[0].text == " File \u2502 Edit \u2502 View "
    assert rows[0].segments[1].text == "File"
    assert rows[0].segments[1].style.underline is False
    assert rows[0].segments[3].text == "Edit"
    assert MenuBar([]).render(40)[0].text == ""


def test_an_over_wide_bar_truncates_and_the_cut_label_carries_no_span():
    bar = MenuBar(["alpha", "beta"])
    row = bar.render(4)[0]
    assert row.width == 4 and row.text == " al\u2026"
    assert bar.click(0, 1) is False


def test_menubar_move_clamps_and_steps_over_disabled():
    bar = MenuBar(["a", "b", "c"], index=7)
    assert bar.index == 2
    assert bar.move(1) is False
    assert bar.move(-1) is True and bar.index == 1
    assert bar.select(0) is True and bar.select(0) is False
    skip = MenuBar(["a", "b", "c", "d"], disabled_items={1, 2})
    assert skip.move(1) is True and skip.index == 3
    assert skip.move(1) is False
    assert MenuBar([]).move(1) is False


def test_menubar_click_maps_the_last_render_span_table():
    bar = MenuBar(["File", "Edit", "View"])
    bar.render(40)
    assert bar.click(0, 1) is True and bar.index == 0
    assert bar.click(0, 8) is True and bar.index == 1
    assert bar.click(0, 15) is True and bar.index == 2
    assert bar.click(0, 5) is False
    assert bar.click(0, 19) is False
    assert bar.click(1, 8) is False
    assert bar.click(0, 8) is True


def test_a_disabled_label_is_visible_but_not_selectable():
    bar = MenuBar(["a", "b", "c"], disabled_items={1})
    assert bar.click(0, 5) is False and bar.index == 0
    assert bar.select(1) is False
    assert bar.move(1) is True and bar.index == 2
    assert bar.activate() is True and bar.take_result() == "c"


def test_a_disabled_bar_refuses_every_gesture():
    bar = MenuBar(["a", "b"], disabled=True)
    assert bar.move(1) is False
    assert bar.select(1) is False
    assert bar.click(0, 1) is False
    assert bar.activate() is False and bar.take_result() is None


def test_hover_at_marks_one_label_and_clears_back():
    theme = replace(DEFAULT_THEME, surfaces=replace(DEFAULT_THEME.surfaces, hover=Style(underline=True)))
    bar = MenuBar(["File", "Edit"], theme=theme)
    plain = bar.render(40)
    assert bar.hover_at(0, 8) is True
    assert bar.render(40)[0].segments[3].style.underline is True
    assert bar.hover_at(0, 8) is False
    assert bar.hover_at(0, 5) is True
    assert bar.render(40) == plain
    assert bar.hover_at(-1, -1) is False


def test_activate_leaves_the_active_label_pending_once():
    bar = MenuBar(["File", "Edit"])
    assert bar.activate() is True and bar.take_result() == "File"
    assert bar.take_result() is None
    assert bar.move(1) is True
    bar.activate()
    assert bar.move(-1) is True and bar.take_result() is None
    assert MenuBar([]).activate() is False


def test_context_menu_is_the_wrap_and_activate_select_preset():
    menu = ContextMenu([Option("Open"), Option("Save", "save")])
    assert isinstance(menu, Select)
    assert menu.commit is False and menu.wrap is True and menu.window is False
    assert menu.select(1) is True
    assert menu.activate() is True and menu.take_result() == Option("Save", "save")
    assert menu.take_result() is None


def test_context_menu_renders_its_title_and_refuses_disabled_items():
    menu = ContextMenu([Option("Open"), Option("Quit")], title="File")
    assert texts(menu, 20) == ["File", "\u2192 Open", "  Quit"]
    disabled = ContextMenu([Option("Open"), Option("Quit")], disabled_items={1})
    assert disabled.select(1) is False
    assert disabled.activate() is True and disabled.take_result() == Option("Open")
