"""The 2.1.2 contract matrix for the choice and navigation families.

These tests are the family's share of ``tests/widgets/test_contracts.py``:
construction shape, the state names, the five verbs, ``take`` semantics,
the keymap descriptor and the ``open`` state.  Behaviour beyond the shared
contract stays in the per-module test files.
"""

import inspect
from dataclasses import replace

from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import (
    Autocomplete,
    CheckboxGroup,
    ComboBox,
    ContextMenu,
    List,
    MenuBar,
    MultiSelect,
    NavList,
    Option,
    RadioGroup,
    Select,
    Table,
    Tabs,
    Tree,
    TreeNode,
)
from tests.testing import key

THREE = [Option("one"), Option("two"), Option("three")]


def _keyword_names(cls) -> list[str]:
    return [
        name
        for name, parameter in inspect.signature(cls).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    ]


def _positional_names(cls) -> list[str]:
    return [
        name
        for name, parameter in inspect.signature(cls).parameters.items()
        if parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]


MAIN_CONTENT = [
    (Tabs, "items"),
    (MenuBar, "items"),
    (NavList, "items"),
    (List, "items"),
    (Table, "rows"),
    (Tree, "nodes"),
    (Select, "options"),
    (MultiSelect, "options"),
    (RadioGroup, "options"),
    (CheckboxGroup, "options"),
    (Autocomplete, "options"),
    (ComboBox, "options"),
    (ContextMenu, "options"),
]


def test_the_main_content_is_the_only_positional_parameter():
    for cls, main in MAIN_CONTENT:
        assert _positional_names(cls) == [main], cls.__name__
        assert main in inspect.signature(cls).parameters


def test_tree_node_keeps_its_two_positional_values():
    assert _positional_names(TreeNode) == ["label", "children"]


def test_the_skin_and_glyph_tail_is_keyword_only():
    for cls, _ in MAIN_CONTENT:
        names = _keyword_names(cls)
        assert names.index("glyphs") < names.index("theme") < names.index("styles"), (
            cls.__name__
        )


def test_the_choice_and_navigation_capabilities():
    widgets = [
        Tabs(["a"]),
        MenuBar(["a"]),
        NavList(["a"]),
        List(["a"]),
        Table([["a"]], headers=["h"]),
        Tree([TreeNode("a")]),
        Select(THREE),
        MultiSelect(THREE),
        RadioGroup(["a"]),
        CheckboxGroup(["a"]),
        Autocomplete(THREE),
        ContextMenu(THREE),
    ]
    for widget in widgets:
        assert widget.focusable is True
        assert widget.clickable is True
        assert widget.hoverable is True
        assert widget.activatable is True


def test_select_moves_and_selected_reads_the_entry():
    for build, expected in [
        (lambda: Tabs(["a", "b"]), "b"),
        (lambda: MenuBar(["a", "b"]), "b"),
        (lambda: NavList(["a", "b"]), "b"),
        (lambda: List(["a", "b"]), "b"),
        (lambda: Table([["a"], ["b"]], headers=["h"]), ["b"]),
        (lambda: Select(THREE), THREE[1]),
    ]:
        widget = build()
        assert widget.index == 0
        assert widget.select(1) is True
        assert widget.index == 1
        assert widget.selected == expected


def test_an_empty_collection_reads_index_zero_and_no_selection():
    for widget in (
        Tabs([]),
        MenuBar([]),
        NavList([]),
        List([]),
        Table([], headers=["h"]),
        Tree([]),
        Select([]),
        Autocomplete([]),
    ):
        assert widget.index == 0
        assert widget.selected is None
        assert widget.move(1) is False
        assert widget.select(0) is False
    assert list(Select([]).render(Constraints(width=20))) == []


def test_a_disabled_row_refuses_selection_and_moves_step_over_it():
    menu = Select(THREE, disabled_items=(1,))
    assert menu.select(1) is False and menu.index == 0
    assert menu.move(1) is True and menu.index == 2
    assert menu.move(-1) is True and menu.index == 0

    listing = List(["a", "b", "c"], disabled_items=(1,))
    assert listing.select(1) is False and listing.index == 0
    assert listing.move(1) is True and listing.index == 2


def test_movement_clears_a_pending_result_and_activation_writes_one():
    menu = Select(THREE)
    assert menu.on_action("activate") is True and menu.take() == "one"
    assert menu.move(1) is True and menu.take() is None
    assert menu.on_action("activate") is True and menu.take() == "two"

    listing = List(["a", "b"])
    assert listing.on_action("activate") is True and listing.take() == "a"
    assert listing.move(1) is True and listing.take() is None


def test_tabs_menubar_and_navlist_activate_their_active_label():
    tabs = Tabs(["a", "b"])
    assert tabs.on_action("activate") is True and tabs.take() == "a"
    assert tabs.take() is None

    bar = MenuBar(["a", "b"], index=1)
    assert bar.on_action("activate") is True and bar.take() == "b"

    nav = NavList(["a", "b"], index=1)
    assert nav.on_action("activate") is True and nav.take() == "b"


def test_an_empty_or_disabled_activation_writes_nothing():
    for widget in (Tabs([]), MenuBar([]), NavList([]), Select([])):
        assert widget.on_action("activate") is False
        assert widget.take() is None

    disabled = MenuBar(["a"], disabled=True)
    assert disabled.on_action("activate") is False
    assert disabled.take() is None


def test_table_take_returns_the_raw_row_object():
    row = ["one", "1"]
    table = Table([row], headers=["name", "value"])
    table.index = 0
    assert table.on_action("activate") is True
    assert table.take() is table.rows[0]


def test_a_fresh_table_reads_the_first_row_but_draws_no_cursor_band():
    styles = Styles(rows=replace(DEFAULT_THEME.rows, active=Style(reverse=True)))
    table = Table([["a"], ["b"]], headers=["h"], styles=styles)
    assert table.index == 0 and table.selected == ["a"]
    assert not any(
        segment.style.reverse
        for row in table.render(Constraints(width=9))
        for segment in row.segments
    )
    assert table.select(0) is False  # already there, but the cursor is now armed
    assert any(
        segment.style.reverse
        for row in table.render(Constraints(width=9))
        for segment in row.segments
    )


def test_the_cursor_keymap_is_shared_and_exposes_the_marking_key():
    widgets = (
        Tabs(["a"]),
        MenuBar(["a"]),
        NavList(["a"]),
        List(["a"]),
        Table([["a"]], headers=["h"]),
        Tree([TreeNode("a")]),
        Select(THREE),
    )
    for widget in widgets:
        assert widget.keymap["down"] == "next"
        assert widget.keymap["up"] == "prev"
        assert widget.keymap["home"] == "first"
        assert widget.keymap["end"] == "last"
        assert widget.keymap["page_down"] == "page_next"

    marking = (
        List(["a"]),
        Table([["a"]], headers=["h"]),
        MultiSelect(THREE),
        CheckboxGroup(["a"]),
    )
    for widget in marking:
        assert widget.keymap["space"] == "toggle"

    assert "space" not in Select(THREE).keymap


def test_the_tree_keymap_folds_with_left_and_right():
    tree = Tree([TreeNode("root", [TreeNode("leaf")])])
    assert tree.keymap["left"] == "close"
    assert tree.keymap["right"] == "open"
    assert "enter" not in tree.keymap


def test_an_instance_keymap_rebind_never_writes_through_the_class_table():
    menu = Select(THREE)
    other = Select(THREE)
    menu.keymap["j"] = "next"
    assert "j" not in Select.keymap
    assert "j" not in other.keymap
    assert menu.on_key(key("j", "j")) is True and menu.index == 1
    assert other.on_key(key("j", "j")) is False and other.index == 0


def test_page_actions_use_the_visible_window():
    menu = Select([Option(f"i{i}") for i in range(10)], max_rows=3)
    assert menu.on_action("page_next") is True and menu.index == 3
    assert menu.on_action("page_prev") is True and menu.index == 0

    listing = List([f"i{i}" for i in range(10)], window=2)
    assert listing.on_action("page_next") is True and listing.index == 2


def test_the_tree_open_state_and_its_verbs():
    root = TreeNode("root", [TreeNode("leaf")])
    tree = Tree([root])
    assert root.open is False
    assert tree.on_action("activate") is True
    assert root.open is True
    assert tree.take() is root
    assert tree.toggle() is True and root.open is False
    assert tree.take() is None  # toggle never emits
    assert tree.on_action("open") is True and root.open is True
    assert tree.on_action("close") is True and root.open is False
    assert tree.on_action("close") is False
    leaf = Tree([TreeNode("solo")])
    assert leaf.on_action("activate") is False
    assert leaf.on_action("toggle") is False


def test_the_radio_group_selected_is_an_option_and_activation_takes_the_value():
    group = RadioGroup([Option("low", 1), Option("high", 2)], index=1)
    assert isinstance(group.selected, Option) and group.selected.label == "high"
    assert group.on_action("activate") is True and group.take() == 2


def test_the_check_group_marks_are_its_result():
    group = CheckboxGroup(["a", "b"], marked=(1,))
    assert group.take() == ["b"]
    assert group.toggle() is True and group.take() == ["a", "b"]
    assert group.move(1) is True and group.take() is None


def test_the_multi_select_toggles_and_emits_its_marked_values():
    menu = MultiSelect([Option("a"), Option("b")])
    assert menu.on_action("activate") is True
    assert menu.take() == ["a"]
    assert menu.on_action("activate") is True
    assert menu.take() is None


def test_context_menu_spells_out_the_menu_knobs():
    menu = ContextMenu(THREE)
    assert menu.wrap is True and menu.window is False
    assert not hasattr(menu, "commit")
    assert menu.on_action("activate") is True and menu.take() == "one"


def test_the_combo_open_is_an_assignable_bool_state():
    combo = ComboBox([Option("alpha"), Option("beta")])
    assert combo.open is False
    combo.open = True
    assert combo.open is True
    assert combo.toggle() is True and combo.open is False
    assert combo.toggle() is True and combo.open is True
    assert combo.on_action("activate") is True and combo.open is False
    assert combo.take() == "alpha"
    assert not hasattr(combo, "is_open")
    assert not callable(combo.open)


def test_the_autocomplete_tail_and_filter_contract():
    auto = Autocomplete([Option("Alpha"), Option("beta")])
    auto.set_query("AL")
    assert auto.selected == Option("Alpha")
    assert auto.on_action("activate") is True and auto.take() == "Alpha"
    auto.set_query("zzz")
    assert auto.selected is None and auto.is_empty is True
    assert auto.on_action("activate") is False


def test_a_click_lands_the_cursor_without_writing_a_pick():
    menu = Select(THREE)
    assert menu.on_click(Pos(x=0, y=1)) is True
    assert menu.index == 1 and menu.take() is None

    listing = List(["a", "b", "c"])
    assert listing.on_click(Pos(x=0, y=2)) is True
    assert listing.index == 2 and listing.take() is None
