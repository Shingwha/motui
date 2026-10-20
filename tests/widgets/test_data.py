"""List, Table and Tree: windowed data views, their cursors and gestures."""

import pytest

from motui.kernel.style import Style
from motui.widgets import List, Option, Table, TreeNode, Tree

from tests.testing import key, many, paste, texts


# -- List ---------------------------------------------------------------------


def test_a_long_list_renders_a_window_and_counters():
    lst = List(many(1000), window=8)
    rows = texts(lst, 40)
    assert len(rows) == 9
    assert rows[0] == "\u25b8 r0" and rows[-1] == "\u2193 992 more"
    lst.index = 500
    assert texts(lst, 40) == [
        "\u2191 496 more",
        "  r496",
        "  r497",
        "  r498",
        "  r499",
        "\u25b8 r500",
        "  r501",
        "  r502",
        "  r503",
        "\u2193 496 more",
    ]


def test_a_short_list_renders_every_item_without_counters():
    lst = List(["one", "two", "three"], window=8)
    assert texts(lst, 20) == ["\u25b8 one", "  two", "  three"]


def test_move_clamps_at_the_ends_and_clears_the_pending_pick():
    lst = List(["a", "b", "c"], window=2)
    assert lst.activate() is True and lst.take_result() == "a"
    assert lst.move(1) is True and lst.index == 1 and lst.take_result() is None
    assert lst.move(9) is True and lst.index == 2
    assert lst.move(1) is False
    assert lst.move(-9) is True and lst.index == 0
    assert lst.move(0) is False
    assert lst.end() is True and lst.index == 2
    assert lst.end() is False
    assert lst.home() is True and lst.index == 0


def test_index_clamps_and_an_empty_list_is_inert():
    lst = List(["a", "b", "c"])
    lst.index = 99
    assert lst.index == 2
    lst.index = -7
    assert lst.index == 0
    empty = List()
    empty.index = 5
    assert empty.index == 0 and empty.render(20) == []
    assert empty.move(1) is False and empty.activate() is False
    assert empty.home() is False and empty.end() is False


def test_activate_lands_the_cursor_item_once():
    lst = List(["a", "b", "c"], window=2)
    lst.index = 1
    assert lst.activate() is True and lst.take_result() == "b"
    assert lst.take_result() is None


def test_click_maps_rendered_rows_and_refuses_the_counter_rows():
    lst = List(many(100), window=4)
    lst.index = 50
    rows = texts(lst, 30)
    assert rows[0] == "\u2191 48 more" and rows[-1] == "\u2193 48 more"
    assert lst.click(0, 0) is False
    assert lst.click(len(rows) - 1, 0) is False
    assert lst.click(len(rows), 0) is False
    assert lst.click(2, 99) is True
    assert lst.index == 49 and lst.take_result() == "r49"


def test_the_prefix_jump_scans_from_the_top_case_insensitively():
    lst = List(["alpha", "Beta", "beta two", "Gamma", "delta"], window=3)
    lst.index = 4
    assert lst.handle(key("b", "b")) is True
    assert lst.index == 1
    assert lst.handle(key("d", "d")) is True and lst.index == 4
    assert lst.handle(key("z", "z")) is True and lst.index == 4


def test_handle_consumes_its_own_keys_and_declines_the_hosts():
    lst = List(["a", "b", "c"], window=2)
    assert lst.handle(key("down")) is True and lst.index == 1
    assert lst.handle(key("up")) is True and lst.index == 0
    assert lst.handle(key("end")) is True and lst.index == 2
    assert lst.handle(key("home")) is True and lst.index == 0
    for event in (key("enter"), key("tab"), key("c-n"), key("space", " "), paste("text")):
        assert lst.handle(event) is False


def test_prefix_jump_off_leaves_printables_to_the_host():
    lst = List(["alpha", "beta"], prefix_jump=False)
    assert lst.handle(key("b", "b")) is False and lst.index == 0
    lst.prefix_jump = True
    assert lst.handle(key("b", "b")) is True and lst.index == 1


@pytest.mark.parametrize("window", [0, -3])
def test_the_list_window_must_hold_at_least_one_row(window):
    with pytest.raises(ValueError):
        List(["a"], window=window)


def test_the_mark_column_appears_with_the_first_mark():
    lst = List(["alpha", "beta", "gamma"], window=4)
    plain = texts(lst, 30)
    assert lst.toggle() is True and list(lst.marked) == [0]
    assert texts(lst, 30) == ["\u25b8 [x] alpha", "  [ ] beta", "  [ ] gamma"]
    assert lst.toggle() is True
    assert texts(lst, 30) == plain


def test_the_glyph_parameters_reach_the_rows_and_counters():
    lst = List(["a", "b"], window=1, marker=">", more_up="^", more_down="v")
    assert texts(lst, 20) == ["> a", "v 1 more"]
    lst.index = 1
    assert texts(lst, 20) == ["^ 1 more", "> b"]
    wide = List(["alpha"], window=1, marker="\u6811")
    assert texts(wide, 20) == ["\u6811 alpha"]
    bare = List(["alpha", "beta"], window=2, marker="")
    assert texts(bare, 20) == ["alpha", "beta"]


def test_the_mark_pair_is_padded_to_its_wider_member():
    lst = List(["alpha", "beta"], window=2, mark_pair=("[x]", "\u6811"))
    lst.toggle()
    rows = lst.render(20)
    assert rows[0].text == "\u25b8 [x] alpha"
    assert rows[1].text == "  \u6811  beta"


def test_disabled_items_are_visible_but_skipped_and_refused():
    lst = List(["a", "b", "c", "d"], window=4, disabled_items=(1, 2))
    assert texts(lst, 20) == ["\u25b8 a", "  b", "  c", "  d"]
    assert lst.move(1) is True and lst.index == 3
    assert lst.move(1) is False
    lst.index = 1
    assert lst.activate() is False and lst.take_result() is None
    assert lst.toggle() is False
    assert lst.click(1, 0) is False


def test_a_disabled_list_refuses_every_gesture_but_still_renders():
    lst = List(["a", "b"], window=2, disabled=True)
    assert lst.move(1) is False and lst.home() is False and lst.end() is False
    assert lst.activate() is False and lst.click(0, 0) is False
    assert lst.handle(key("down")) is False
    assert texts(lst, 20) == ["\u25b8 a", "  b"]


def test_rows_are_fitted_to_the_painting_width():
    lst = List(["a very long item text", "b"], window=2)
    rows = lst.render(10)
    assert all(row.width <= 10 for row in rows)
    assert rows[0].text.endswith("\u2026") and rows[0].width == 10


# -- Table --------------------------------------------------------------------


def test_the_grid_keeps_one_width_and_rules_between_rows():
    rows = Table(["A"], [["1"], ["2"], ["3"]]).render(9)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2510",
        "\u2502 A \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 1 \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 2 \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 3 \u2502",
        "\u2514\u2500\u2500\u2500\u2518",
    ]
    assert len({row.width for row in rows}) == 1


def test_an_over_wide_grid_shrinks_and_ellipsizes():
    rows = Table(["A", "B"], [["xxxxxxxxxx", "y"]]).render(12)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2510",
        "\u2502 A    \u2502 B \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",
        "\u2502 xxx\u2026 \u2502 y \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2518",
    ]


@pytest.mark.parametrize("width", [0, 1])
def test_a_degenerate_width_keeps_the_frame_structure(width):
    rows = Table(["A", "B"], [["1", "2"]]).render(width)
    assert len(rows) == 5
    assert all(row.width <= width for row in rows)


def test_columns_are_measured_by_visible_width():
    rows = Table(["\u540d\u524d"], [["\u65e5\u672c"]]).render(10)
    assert rows[3].text == "\u2502 \u65e5\u672c \u2502"
    assert len({row.width for row in rows}) == 1


def test_the_column_and_border_styles_reach_their_cells():
    injected = Style(underline=True)
    rows = Table(
        ["A", "B"],
        [[("1", injected), "x"]],
        first_column_style=Style(bold=True),
        border_style=Style(italic=True),
    ).render(12)
    assert rows[1].segments[1].style.bold is False
    assert rows[1].segments[1].style.italic is False
    assert rows[3].segments[1].style.underline is True
    assert rows[3].segments[1].style.italic is False
    assert rows[0].segments[0].style.italic is True


@pytest.mark.parametrize(
    "aligns, header, data",
    [
        (
            ["right", "center", "left"],
            "\u2502 l \u2502 c  \u2502 r    \u2502",
            "\u2502 a \u2502 bb \u2502 cccc \u2502",
        ),
        (["middle"], "\u2502 x \u2502", "\u2502 y \u2502"),
    ],
)
def test_alignments_pad_inside_the_column_budget(aligns, header, data):
    if len(aligns) == 3:
        rows = Table(["l", "c", "r"], [["a", "bb", "cccc"]], aligns=aligns).render(20)
    else:
        rows = Table(["x"], [["y"]], aligns=aligns).render(12)
    assert rows[1].text == header and rows[3].text == data


def test_the_cursor_bands_the_data_cells_of_its_row_only():
    band = Style(reverse=True)
    table = Table(["A", "B"], [["1", "x"], ["2", "y"]], active_style=band)
    table.index = 1
    rows = table.render(12)
    assert any(seg.style.reverse for seg in rows[5].segments)
    assert not any(seg.style.reverse for seg in rows[3].segments)
    assert not any(seg.style.reverse for seg in rows[1].segments)
    assert [row.text for row in rows] == [
        row.text for row in Table(["A", "B"], [["1", "x"], ["2", "y"]]).render(12)
    ]


def test_index_clamps_and_none_clears_the_cursor():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    assert table.index is None
    table.index = 99
    assert table.index == 2 and table.selected == ["3"]
    table.index = -5
    assert table.index == 0
    table.index = None
    assert table.index is None and table.selected is None
    empty = Table(["A"], [])
    empty.index = 0
    assert empty.index is None and empty.selected is None


def test_move_clamps_and_the_first_step_lands_on_the_edge_it_leaves():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    assert table.move(1) is True and table.index == 0
    assert table.move(-1) is False
    assert table.move(2) is True and table.index == 2
    assert table.move(1) is False
    up = Table(["A"], [["1"], ["2"], ["3"]])
    assert up.move(-1) is True and up.index == 2
    assert Table(["A"], []).move(1) is False


def test_click_maps_rendered_data_rows_and_misses_the_frame():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    rendered = table.render(9)
    assert table.click(3, 0) is True and table.index == 0
    assert table.click(5, 99) is True and table.index == 1
    assert table.click(7, 0) is True and table.index == 2
    for row in (0, 1, 2, 4, 6, 8, 9, -1):
        assert table.click(row, 0) is False
    assert table.index == 2
    assert len(rendered) == 9


def test_activate_takes_the_row_index_once():
    table = Table(["A"], [["1"], ["2"]])
    assert table.activate() is False and table.take_result() is None
    table.index = 1
    assert table.activate() is True and table.take_result() == 1
    assert table.take_result() is None


def test_a_step_or_a_landing_click_clears_a_pending_result():
    table = Table(["A"], [["1"], ["2"]])
    table.index = 1
    assert table.activate() is True
    assert table.move(0) is False and table.take_result() is None
    assert table.activate() is True
    assert table.click(3, 0) is True and table.take_result() is None


def test_sort_by_orders_on_the_rendered_text_and_is_stable():
    table = Table(["state", "note"], [["b", "2"], ["a", "1"], ["b", "0"]])
    assert table.sort_by(0) is True
    assert [row.text for row in table.render(16)] == [
        row.text for row in Table(["state", "note"], [["a", "1"], ["b", "2"], ["b", "0"]]).render(16)
    ]
    assert table.sort_by(0) is False
    assert table.sort_by(0, reverse=True) is True
    assert [row.text for row in table.render(16)] == [
        row.text
        for row in Table(["state", "note"], [["b", "2"], ["b", "0"], ["a", "1"]]).render(16)
    ]
    assert Table(["A"], []).sort_by(0) is False


def test_sort_by_keeps_the_cursor_and_marks_on_their_records():
    table = Table(["k"], [["c"], ["a"], ["b"]])
    table.index = 0
    assert table.toggle() is True
    assert table.sort_by(0) is True
    assert table.index == 2 and table.selected == ["c"]
    assert list(table.marked) == [2]
    assert any("[x] c" in row.text for row in table.render(20))


def test_set_widths_pins_budgets_and_the_render_clamps_them():
    table = Table(["A", "B"], [["xx", "yyyyyyyy"]])
    natural = [row.text for row in table.render(30)]
    table.set_widths([6, 2])
    pinned = [row.text for row in table.render(30)]
    assert pinned[1] == "\u2502 A      \u2502 B  \u2502"
    assert pinned[3] == "\u2502 xx     \u2502 y\u2026 \u2502"
    table.set_widths(None)
    assert [row.text for row in table.render(30)] == natural
    table.set_widths([40, 40])
    squeezed = table.render(20)
    assert len({row.width for row in squeezed}) == 1
    assert squeezed[0].width <= 20


@pytest.mark.parametrize("width", [6, 12, 30])
def test_header_line_is_the_grids_own_header_row(width):
    table = Table(["state", "note"], [["ok", "fine"]], aligns=["left", "right"])
    line = table.header_line(width)
    assert line is not None and line == table.render(width)[1]
    assert Table([], [["x"]]).header_line(20) is None


def test_the_mark_column_rides_the_first_cell_of_every_data_row():
    table = Table(["name", "value"], [["alpha", "1"], ["beta", "2"]])
    plain = [row.text for row in table.render(40)]
    table.index = 1
    assert table.toggle() is True and list(table.marked) == [1]
    marked = [row.text for row in table.render(40)]
    assert any("[x] beta" in text for text in marked)
    assert any("[ ] alpha" in text for text in marked)
    assert len(marked) == len(plain)
    table.toggle()
    assert [row.text for row in table.render(40)] == plain


def test_disabled_rows_and_tables_refuse_their_gestures():
    table = Table(["A"], [["0"], ["1"], ["2"], ["3"]], disabled_items=(1, 2))
    assert table.move(1) is True and table.index == 0
    assert table.move(1) is True and table.index == 3
    table.index = 1
    assert table.activate() is False and table.toggle() is False
    assert table.click(5, 0) is False
    assert table.click(9, 0) is True and table.index == 3
    dead = Table(["A"], [["1"]], disabled=True)
    assert dead.move(1) is False and dead.click(3, 0) is False


# -- Tree ---------------------------------------------------------------------


def sample() -> TreeNode:
    """A collapsed folder with a leaf and a nested collapsed folder."""
    return TreeNode(
        "src",
        children=[
            TreeNode("app.py"),
            TreeNode("lib", children=[TreeNode("a.py"), TreeNode("b.py")]),
        ],
    )


def test_a_collapsed_root_renders_one_row():
    tree = Tree([sample()])
    assert texts(tree, 30) == ["\u25b8 src"]
    assert tree.selected is tree.root_nodes[0]


def test_activate_expands_and_collapses_the_visible_rows():
    tree = Tree([sample()])
    assert tree.activate() is True
    assert texts(tree, 30) == ["\u25be src", "    app.py", "  \u25b8 lib"]
    assert tree.activate() is True
    assert texts(tree, 30) == ["\u25b8 src"]


def test_nested_expansion_indents_with_spaces_only():
    tree = Tree([sample()])
    tree.activate()
    tree.move(2)
    assert tree.activate() is True
    assert texts(tree, 30) == [
        "\u25be src",
        "    app.py",
        "  \u25be lib",
        "      a.py",
        "      b.py",
    ]
    assert all("\u2502" not in row for row in texts(tree, 30))


def test_move_clamps_inside_the_visible_rows():
    tree = Tree([sample()])
    tree.activate()
    tree.move(1)
    assert tree.selected.label == "app.py"
    tree.move(-9)
    assert tree.selected.label == "src"
    tree.move(99)
    assert tree.selected.label == "lib"
    assert tree.move(1) is False


def test_click_places_the_cursor_on_the_visible_row_and_ignores_the_column():
    tree = Tree([sample()])
    tree.activate()
    for col in (0, 3, 999):
        assert tree.click(1, col) is True and tree.selected.label == "app.py"
    for row in (-1, 3, 9):
        assert tree.click(row, 0) is False
    assert tree.selected.label == "app.py"


def test_a_leaf_and_an_empty_tree_decline_activation():
    leaf = Tree([TreeNode("solo")])
    assert leaf.activate() is False and texts(leaf, 20) == ["  solo"]
    empty = Tree([])
    assert empty.activate() is False and empty.move(1) is False
    assert empty.selected is None and empty.render(10) == []


def test_collapsing_re_clamps_the_cursor_into_the_new_rows():
    tree = Tree([sample()])
    tree.activate()
    lib = tree.root_nodes[0].children[1]
    lib.expanded = True
    tree.move(2)
    assert tree.activate() is True and tree.selected is lib
    assert len(tree.render(30)) == 3
    lib.expanded = True
    tree.move(4)
    lib.expanded = False
    assert tree.selected is lib


def test_filter_prunes_to_the_matches_and_keeps_ancestors_open():
    tree = Tree(
        [
            sample(),
            TreeNode("docs", children=[TreeNode("guide")]),
        ]
    )
    assert tree.filter("lib") is True
    assert texts(tree, 30) == ["\u25be src", "  \u25b8 lib"]
    assert tree.filter("B.PY") is True
    assert texts(tree, 30) == ["\u25be src", "  \u25be lib", "      b.py"]
    assert tree.filter("guide") is True
    assert texts(tree, 30) == ["\u25be docs", "    guide"]
    assert tree.filter("nope") is True
    assert tree.render(30) == [] and tree.selected is None
    assert tree.filter(None) is True
    assert tree.filter(None) is False


def test_filter_never_rewrites_the_users_expansion_flags():
    tree = Tree([sample()])
    src = tree.root_nodes[0]
    src.children[1].expanded = True
    before = texts(tree, 30)
    assert tree.filter("a.py") is True
    assert src.expanded is False and src.children[1].expanded is True
    assert tree.filter(None) is True
    assert texts(tree, 30) == before


def test_jump_walks_the_next_visible_label_and_wraps():
    tree = Tree([sample()])
    src = tree.root_nodes[0]
    src.expanded = True
    src.children[1].expanded = True
    src.children[1].children[1].label = "Beta"
    assert tree.jump("b") is True and tree.selected.label == "Beta"
    assert tree.jump("s") is True and tree.selected.label == "src"
    assert tree.jump("B") is True and tree.selected.label == "Beta"
    assert tree.jump("B") is False
    assert tree.jump("z") is False and tree.jump("") is False and tree.jump("ab") is False


def test_the_fold_glyphs_are_parameters():
    custom = Tree([sample()], expanded="v", collapsed=">")
    custom.activate()
    assert texts(custom, 30) == ["v src", "    app.py", "  > lib"]
    bare = Tree([sample()], expanded="", collapsed="")
    bare.activate()
    assert texts(bare, 30) == ["src", "  app.py", "  lib"]
    wide = Tree([sample()], expanded="\u5f00", collapsed="\u5173")
    wide.activate()
    assert texts(wide, 30) == ["\u5f00 src", "     app.py", "  \u5173 lib"]


def test_disabled_nodes_are_skipped_and_refused():
    tree = Tree(
        [
            TreeNode("a"),
            TreeNode("b", disabled=True),
            TreeNode("c"),
        ]
    )
    assert tree.move(1) is True and tree.selected.label == "c"
    assert tree.click(1, 0) is False
    tree.move(-9)
    assert tree.activate() is False  # a leaf, and the first row is enabled
    dead = Tree([sample()], disabled=True)
    assert dead.move(1) is False and dead.click(0, 0) is False
    assert dead.activate() is False
