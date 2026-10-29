"""Tabs and NavList: the horizontal strip and the vertical navigation rail."""

from dataclasses import replace

import pytest

from motui.kernel.cell import Surface
from motui.kernel.geom import Pos
from motui.kernel.glyphs import GLYPHS
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import NavList, Tabs
from tests.testing import key, texts

INDICATOR = Style(underline=True)


# -- Tabs ---------------------------------------------------------------------


def test_tabs_render_one_row_with_the_active_label_marked():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(Constraints(width=40))
    assert len(rows) == 1
    assert rows[0].text == " alpha \u2502 beta \u2502 gamma "
    assert rows[0].segments[1].text == "alpha"
    assert rows[0].segments[1].style.underline is True
    assert rows[0].segments[3].style.underline is False


@pytest.mark.parametrize(
    "start, delta, active, changed",
    [(0, 1, 1, True), (2, -9, 0, True)],
)
def test_tabs_move_clamps_without_wrapping(start, delta, active, changed):
    tabs = Tabs(["a", "b", "c"], index=start)
    assert tabs.move(delta) is changed
    assert tabs.index == active
    assert Tabs(["a", "b"], index=7).index == 1
    assert Tabs([]).move(1) is False


def test_tabs_move_steps_over_disabled_indices():
    tabs = Tabs(["a", "b", "c", "d"], disabled_items={1, 2})
    assert tabs.move(1) is True and tabs.index == 3
    assert tabs.move(1) is False
    assert tabs.move(-1) is True and tabs.index == 0
    assert tabs.move(-1) is False


def test_the_tabs_indicator_follows_the_selection():
    tabs = Tabs(["a", "b"])
    assert tabs.select(1) is True
    segments = tabs.render(Constraints(width=20))[0].segments
    assert segments[1].text == "a" and segments[1].style.underline is False
    assert segments[3].text == "b" and segments[3].style.underline is True


def test_an_unfocused_strip_lowers_the_indicator_hue_and_keeps_the_label():
    active = Style(fg="#abcdef")
    styles = Styles(content=replace(DEFAULT_THEME.content, accent=active))
    plain = Tabs(["a", "b"], styles=styles)
    plain.focused = False
    focused = Tabs(["a", "b"], styles=styles)
    plain_style = plain.render(Constraints(width=20))[0].segments[1].style
    focused_style = focused.render(Constraints(width=20))[0].segments[1].style
    assert plain_style != focused_style
    assert plain.render(Constraints(width=20))[0].segments[1].text == "a"


def test_a_disabled_tab_is_visible_but_not_selectable():
    disabled = Style(fg="#654321")
    tabs = Tabs(
        ["a", "b", "c"],
        disabled_items={1},
        styles=Styles(text=replace(DEFAULT_THEME.text, faint=disabled)),
    )
    assert tabs.on_click(Pos(x=5, y=0)) is False and tabs.index == 0
    assert tabs.select(1) is False
    assert tabs.move(1) is True and tabs.index == 2
    assert tabs.render(Constraints(width=20))[0].segments[3].text == "b"
    assert tabs.render(Constraints(width=20))[0].segments[3].style.fg == "#654321"


def test_an_over_wide_strip_truncates_instead_of_wrapping():
    tabs = Tabs(["alpha", "beta", "gamma"])
    assert texts(tabs, 6) == [" alph\u2026"]
    assert texts(tabs, 0) == [""]


def test_click_maps_the_column_to_the_tab_under_it():
    tabs = Tabs(["a", "b", "c"])
    tabs.render(Constraints(width=20))
    assert tabs.on_click(Pos(x=5, y=0)) is True and tabs.index == 1
    assert tabs.on_click(Pos(x=9, y=0)) is True and tabs.index == 2
    for col in (0, 2, 3, 4, 6, 7, 8, 10, 11, 99, -1):
        assert tabs.on_click(Pos(x=col, y=0)) is False
    for row in (-1, 1, 9):
        assert tabs.on_click(Pos(x=5, y=row)) is False


def test_click_measures_wide_labels_by_display_width():
    tabs = Tabs(["\u4e2d\u6587", "ab"])
    tabs.render(Constraints(width=20))
    assert tabs.on_click(Pos(x=1, y=0)) is True and tabs.index == 0
    assert tabs.on_click(Pos(x=4, y=0)) is True
    assert tabs.on_click(Pos(x=5, y=0)) is False
    assert tabs.on_click(Pos(x=8, y=0)) is True and tabs.index == 1


def test_an_empty_strip_renders_one_empty_row_and_misses_every_cell():
    empty = Tabs([])
    assert texts(empty, 40) == [""]
    assert empty.on_click(Pos(x=0, y=0)) is False
    assert empty.index == 0


def test_tabs_answers_a_surface_and_honours_the_height_budget():
    tabs = Tabs(["a", "b"])
    surface = tabs.render(Constraints(width=20, max_height=1))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == [" a \u2502 b "]
    assert surface.width == 20 and surface.height == 1
    # A zero height budget paints no row; the width still feeds the hits.
    assert tabs.render(Constraints(width=20, max_height=0)).height == 0
    assert tabs.on_click(Pos(x=1, y=0)) is True and tabs.index == 0


# -- NavList ------------------------------------------------------------------


def test_navlist_renders_one_row_per_item_with_the_bar_on_the_active_one():
    nav = NavList(["alpha", "beta", "gamma"])
    assert texts(nav, 20) == ["\u258c alpha", "  beta", "  gamma"]
    assert nav.render(Constraints(width=20))[0].segments[0].text == "\u258c"
    assert nav.render(Constraints(width=20))[1].segments[0].text == " "


def test_the_navlist_bar_follows_the_selection():
    nav = NavList(["a", "b"])
    nav.move(1)
    rows = nav.render(Constraints(width=20))
    assert rows[0].segments[0].text == " "
    assert rows[1].segments[0].text == "\u258c"
    assert rows[1].segments[1].text == " b"


def test_navlist_move_clamps_and_steps_over_disabled_items():
    nav = NavList(["a", "b", "c"], index=0)
    assert nav.move(1) is True and nav.index == 1
    assert nav.move(5) is True and nav.index == 2
    assert nav.move(-9) is True and nav.index == 0
    assert nav.move(-1) is False
    skip = NavList(["a", "b", "c", "d"], disabled_items={1, 2})
    assert skip.move(1) is True and skip.index == 3
    assert skip.move(1) is False
    assert NavList([], index=3).index == 0


def test_a_disabled_navlist_item_is_visible_but_not_selectable():
    nav = NavList(
        ["a", "b", "c"],
        disabled_items={1},
        styles=Styles(text=replace(DEFAULT_THEME.text, faint=Style(italic=True))),
    )
    assert nav.on_click(Pos(x=0, y=1)) is False and nav.index == 0
    assert nav.select(1) is False
    assert nav.move(1) is True and nav.index == 2
    assert nav.render(Constraints(width=20))[1].segments[1].style.italic is True


def test_navlist_click_resolves_the_row_and_ignores_the_column():
    nav = NavList(["a", "b", "c"])
    assert nav.on_click(Pos(x=0, y=2)) is True and nav.index == 2
    assert nav.on_click(Pos(x=99, y=1)) is True and nav.index == 1
    for row in (-1, 3, 9):
        assert nav.on_click(Pos(x=0, y=row)) is False
    assert nav.index == 1


def test_group_rows_render_verbatim_and_refuse_every_verb():
    nav = NavList(["a", "b", "c"], groups=((0, "foundations"), (2, "shell")))
    assert texts(nav, 20) == [
        "  foundations",
        "\u258c a",
        "  b",
        "  shell",
        "  c",
    ]
    assert nav.on_click(Pos(x=0, y=0)) is False and nav.index == 0
    assert nav.on_click(Pos(x=0, y=2)) is True and nav.index == 1
    assert nav.select(0) is True
    assert nav.move(9) is True and nav.index == 2
    assert nav.move(1) is False


def test_an_unfocused_navlist_drops_the_bar_hue_and_keeps_the_label():
    active = Style(fg="#abcdef")
    styles = Styles(content=replace(DEFAULT_THEME.content, accent=active))
    focused = NavList(["a"], styles=styles)
    unfocused = NavList(["a"], styles=styles)
    unfocused.focused = False
    focused_bar = focused.render(Constraints(width=20))[0].segments[0].style
    unfocused_bar = unfocused.render(Constraints(width=20))[0].segments[0].style
    focused_label = focused.render(Constraints(width=20))[0].segments[1].style
    unfocused_label = unfocused.render(Constraints(width=20))[0].segments[1].style
    assert focused_bar != unfocused_bar
    assert focused_label == unfocused_label


def test_an_empty_rail_glyph_collapses_the_gutter():
    nav = NavList(["a", "b"], glyphs=replace(GLYPHS, rail=""))
    assert texts(nav, 20) == ["a", "b"]
    assert nav.bar_space == ""
    wide = NavList(["a", "b"], glyphs=replace(GLYPHS, rail="\u6811"))
    assert texts(wide, 20) == ["\u6811 a", "   b"]
    assert wide.bar_space == " " * 3


def test_an_empty_navlist_renders_zero_rows():
    nav = NavList([])
    assert list(nav.render(Constraints(width=20))) == []
    assert nav.on_click(Pos(x=0, y=0)) is False
    assert nav.move(1) is False


def test_navlist_answers_a_surface_and_honours_the_height_budget():
    nav = NavList(["a", "b", "c"])
    surface = nav.render(Constraints(width=20, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["\u258c a", "  b"]
    assert surface.width == 20 and surface.height == 2
    # The 1.x int spelling still answers the whole rail.
    assert [row.text for row in nav.render(Constraints(width=20))] == ["\u258c a", "  b", "  c"]


def test_a_disabled_navlist_refuses_every_gesture_but_still_renders():
    nav = NavList(["a", "b"], disabled=True)
    assert nav.select(0) is False and nav.move(1) is False
    assert nav.on_click(Pos(x=0, y=0)) is False
    assert texts(nav, 20) == ["\u258c a", "  b"]


# -- the 2.0 keymap and action surface ----------------------------------------


def test_the_navlist_keymap_moves_through_named_actions():
    nav = NavList(["a", "b", "c"])
    assert nav.on_key(key("down")) is True and nav.index == 1
    assert nav.on_key(key("right")) is True and nav.index == 2
    assert nav.on_key(key("up")) is True and nav.index == 1
    assert nav.on_action("next") is True and nav.index == 2
    assert nav.on_action("next") is False  # clamped at the last item
    assert nav.on_action("prev") is True and nav.index == 1
    assert nav.on_action("activate") is False
    assert nav.on_action("nope") is False
    assert nav.on_key(key("enter")) is False
    assert not hasattr(NavList, "handle")
    assert nav.take() is None


def test_an_instance_navlist_keymap_rebind_is_private_to_the_instance():
    nav = NavList(["a", "b", "c"])
    other = NavList(["a", "b", "c"])
    nav.keymap["j"] = "next"
    assert "j" not in NavList.keymap
    assert "j" not in other.keymap
    assert nav.on_key(key("j", "j")) is True and nav.index == 1
    assert other.on_key(key("j", "j")) is False and other.index == 0


def test_the_navlist_typed_hooks_forward_to_click_and_hover():
    nav = NavList(["a", "b", "c"])
    assert nav.on_click(Pos(y=2, x=9)) is True and nav.index == 2
    assert nav.on_hover(Pos(y=2, x=0)) is True
    assert nav.on_hover(Pos(y=2, x=0)) is False
    assert nav.on_hover(None) is True


def test_the_navlist_declares_its_capabilities():
    nav = NavList(["a"])
    assert (nav.focusable, nav.clickable, nav.hoverable, nav.activatable) == (
        True,
        True,
        True,
        False,
    )


# -- the tab strip's 2.0 keymap and action surface ----------------------------


def test_the_tabs_keymap_steps_through_named_actions():
    tabs = Tabs(["a", "b", "c"])
    assert tabs.on_key(key("right")) is True and tabs.index == 1
    assert tabs.on_key(key("down")) is True and tabs.index == 2
    assert tabs.on_key(key("left")) is True and tabs.index == 1
    assert tabs.on_key(key("up")) is True and tabs.index == 0
    assert tabs.on_action("prev") is False  # clamped at the first tab
    assert tabs.on_action("next") is True and tabs.index == 1
    assert tabs.on_action("activate") is True and tabs.take() == "b"
    assert tabs.on_action("nope") is False
    assert tabs.on_key(key("enter")) is False  # the focus layer owns enter
    assert not hasattr(Tabs, "handle")
    assert tabs.take() is None


def test_an_instance_tabs_keymap_rebind_is_private_to_the_instance():
    tabs = Tabs(["a", "b", "c"])
    other = Tabs(["a", "b", "c"])
    tabs.keymap["j"] = "next"
    assert "j" not in Tabs.keymap
    assert "j" not in other.keymap
    assert tabs.on_key(key("j", "j")) is True and tabs.index == 1
    assert other.on_key(key("j", "j")) is False and other.index == 0


def test_the_tabs_typed_hooks_forward_to_click_and_hover():
    tabs = Tabs(["a", "b", "c"])
    tabs.render(Constraints(width=20))
    assert tabs.on_click(Pos(y=0, x=5)) is True and tabs.index == 1
    assert tabs.on_hover(Pos(y=0, x=5)) is True
    assert tabs.on_hover(Pos(y=0, x=5)) is False
    assert tabs.on_hover(None) is True


def test_the_tabs_declares_its_capabilities():
    tabs = Tabs(["a"])
    assert (tabs.focusable, tabs.clickable, tabs.hoverable, tabs.activatable) == (
        True,
        True,
        True,
        True,
    )


def test_the_strip_has_no_second_cursor_implementation():
    from motui.widgets import strip as strip_module

    assert "ClampedCursor" not in dir(strip_module)
    assert strip_module.__all__ == ["Keymap", "LabelStrip"]
