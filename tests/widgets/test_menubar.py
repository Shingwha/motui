"""MenuBar and ContextMenu: the menu strip and the desktop menu preset."""

from dataclasses import replace

from motui.kernel.cell import Surface
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import ContextMenu, MenuBar, Option, Select
from tests.testing import key, texts


def test_menubar_renders_one_row_with_dividers_and_padding():
    bar = MenuBar(["File", "Edit", "View"])
    rows = bar.render(Constraints(width=40))
    assert len(rows) == 1
    assert rows[0].text == " File \u2502 Edit \u2502 View "
    assert rows[0].segments[1].text == "File"
    assert rows[0].segments[1].style.underline is True
    assert rows[0].segments[3].text == "Edit"
    assert rows[0].segments[3].style.underline is False
    assert MenuBar([]).render(Constraints(width=40))[0].text == ""


def test_menubar_focus_is_visible_on_the_active_label():
    focused = MenuBar(["File", "Edit"])
    unfocused = MenuBar(["File", "Edit"])
    unfocused.focused = False
    focused_style = focused.render(Constraints(width=40))[0].segments[1].style
    unfocused_style = unfocused.render(Constraints(width=40))[0].segments[1].style
    assert unfocused_style == DEFAULT_THEME.content.accent.merge(
        Style(underline=True)
    )
    assert focused_style == unfocused_style.merge(DEFAULT_THEME.controls.focus)
    assert focused_style != unfocused_style


def test_menubar_answers_a_surface_and_honours_the_height_budget():
    bar = MenuBar(["File", "Edit"])
    surface = bar.render(Constraints(width=40, max_height=1))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == [" File \u2502 Edit "]
    assert surface.width == 40 and surface.height == 1
    # A zero height budget paints no row; the width still feeds the hits.
    assert bar.render(Constraints(width=40, max_height=0)).height == 0
    assert bar.on_click(Pos(x=1, y=0)) is True and bar.index == 0


def test_an_over_wide_bar_truncates_and_the_cut_label_carries_no_span():
    bar = MenuBar(["alpha", "beta"])
    row = bar.render(Constraints(width=4))[0]
    assert row.width == 4 and row.text == " al\u2026"
    assert bar.on_click(Pos(x=1, y=0)) is False


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
    bar.render(Constraints(width=40))
    assert bar.on_click(Pos(x=1, y=0)) is True and bar.index == 0
    assert bar.on_click(Pos(x=8, y=0)) is True and bar.index == 1
    assert bar.on_click(Pos(x=15, y=0)) is True and bar.index == 2
    assert bar.on_click(Pos(x=5, y=0)) is False
    assert bar.on_click(Pos(x=19, y=0)) is False
    assert bar.on_click(Pos(x=8, y=1)) is False
    assert bar.on_click(Pos(x=8, y=0)) is True


def test_a_disabled_label_is_visible_but_not_selectable():
    bar = MenuBar(["a", "b", "c"], disabled_items={1})
    assert bar.on_click(Pos(x=5, y=0)) is False and bar.index == 0
    assert bar.select(1) is False
    assert bar.move(1) is True and bar.index == 2
    assert bar.on_action("activate") is True and bar.take() == "c"


def test_a_disabled_label_merges_the_disabled_overlay():
    bar = MenuBar(["a", "b"], disabled_items={1})
    style = bar.render(Constraints(width=20))[0].segments[3].style
    assert style == DEFAULT_THEME.text.faint.merge(
        DEFAULT_THEME.controls.overlay(disabled=True)
    )


def test_a_disabled_bar_refuses_every_gesture():
    bar = MenuBar(["a", "b"], disabled=True)
    assert bar.move(1) is False
    assert bar.select(1) is False
    assert bar.on_click(Pos(x=1, y=0)) is False
    assert bar.on_action("activate") is False and bar.take() is None


def test_hover_at_marks_one_label_and_clears_back():
    theme = replace(
        DEFAULT_THEME,
        surfaces=replace(DEFAULT_THEME.surfaces, hover=Style(underline=True)),
    )
    bar = MenuBar(["File", "Edit"], theme=theme)
    plain = bar.render(Constraints(width=40))
    assert bar.on_hover(Pos(x=8, y=0)) is True
    assert bar.render(Constraints(width=40))[0].segments[3].style.underline is True
    assert bar.on_hover(Pos(x=8, y=0)) is False
    assert bar.on_hover(Pos(x=5, y=0)) is True
    assert bar.render(Constraints(width=40)) == plain
    assert bar.on_hover(None) is False


def test_activate_leaves_the_active_label_pending_once():
    bar = MenuBar(["File", "Edit"])
    assert bar.on_action("activate") is True and bar.take() == "File"
    assert bar.take() is None
    assert bar.move(1) is True
    bar.on_action("activate")
    assert bar.move(-1) is True and bar.take() is None
    assert MenuBar([]).on_action("activate") is False


def test_context_menu_is_the_wrap_and_activate_select_preset():
    menu = ContextMenu([Option("Open"), Option("Save", "save")])
    assert isinstance(menu, Select)
    assert menu.wrap is True and menu.window is False
    assert menu.select(1) is True
    assert menu.on_action("activate") is True and menu.take() == "save"
    assert menu.take() is None


def test_context_menu_renders_its_title_and_moves_over_its_rows():
    menu = ContextMenu([Option("Open"), Option("Quit")], title="File")
    assert texts(menu, 20) == ["File", "\u2192 Open", "  Quit"]
    assert menu.select(1) is True
    assert menu.on_action("activate") is True and menu.take() == "Quit"


# -- the 2.0 keymap and action surface ----------------------------------------


def test_the_menubar_keymap_steps_and_activates_through_named_actions():
    bar = MenuBar(["a", "b"])
    assert bar.on_key(key("right")) is True and bar.index == 1
    assert bar.on_key(key("left")) is True and bar.index == 0
    assert bar.on_key(key("enter")) is False  # the focus layer owns enter
    assert bar.on_action("activate") is True and bar.take() == "a"
    assert bar.on_action("prev") is False  # clamped at the first label
    assert bar.on_action("next") is True and bar.index == 1
    assert bar.on_action("activate") is True and bar.take() == "b"
    assert bar.take() is None
    assert bar.on_action("nope") is False
    assert not hasattr(MenuBar, "handle")
    assert MenuBar.keymap["down"] == "next"


def test_an_instance_menubar_keymap_rebind_is_private_to_the_instance():
    bar = MenuBar(["a", "b"])
    other = MenuBar(["a", "b"])
    bar.keymap["j"] = "next"
    assert "j" not in MenuBar.keymap
    assert "j" not in other.keymap
    assert bar.on_key(key("j", "j")) is True and bar.index == 1
    assert other.on_key(key("j", "j")) is False and other.index == 0


def test_the_menubar_typed_hooks_forward_to_click_and_hover():
    bar = MenuBar(["File", "Edit"])
    bar.render(Constraints(width=40))
    assert bar.on_click(Pos(y=0, x=1)) is True and bar.index == 0
    assert bar.on_hover(Pos(y=0, x=8)) is True
    assert bar.on_hover(Pos(y=0, x=8)) is False
    assert bar.on_hover(None) is True


def test_the_menubar_declares_its_capabilities():
    bar = MenuBar(["a"])
    assert (bar.focusable, bar.clickable, bar.hoverable, bar.activatable) == (
        True,
        True,
        True,
        True,
    )


def test_the_context_menu_inherits_the_choice_keymap():
    menu = ContextMenu([Option("Open"), Option("Quit")])
    assert menu.on_key(key("down")) is True and menu.index == 1
    assert menu.on_action("activate") is True and menu.take() == "Quit"
