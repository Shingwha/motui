"""Tests for mocode_tui.widgets.tree (Tree / TreeNode).

Contracts (the W4 ticket + the module docstring): the visible rows are the
depth-first walk of the root nodes through the expanded ones; parents show
``\\u25be``/``\\u25b8`` and leaves keep the indicator column blank so labels
align; indentation is plain spaces (no ``\\u2502`` connectors); ``move``
clamps the cursor inside the visible rows; ``toggle`` expands/collapses the
node under the cursor (no-op on a leaf) and re-clamps the cursor.
"""

from mocode_tui.widgets.tree import Tree, TreeNode
from mocode_tui.core.block import Component
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import SELECTION, Style

from _doubles import texts


def _sample():
    """src/ (collapsed) with two children, one of them a collapsed parent."""
    return TreeNode(
        "src",
        children=[
            TreeNode("app.py"),
            TreeNode("lib", children=[TreeNode("a.py"), TreeNode("b.py")]),
        ],
    )


def test_collapsed_root_renders_one_indented_row():
    tree = Tree([_sample()])
    assert texts(tree, 30) == ["\u25b8 src"]
    assert tree.selected is tree.root_nodes[0]
    assert isinstance(tree, Component)


def test_expand_and_collapse_change_the_visible_rows():
    tree = Tree([_sample()])
    assert tree.toggle() is True  # expand src
    assert tree.root_nodes[0].expanded is True
    # a leaf keeps the 2-wide indicator column blank, so its label lines up
    # with a parent's label at the same depth (column 4 here)
    assert texts(tree, 30) == ["\u25be src", "    app.py", "  \u25b8 lib"]
    assert tree.toggle() is True  # collapse src again
    assert texts(tree, 30) == ["\u25b8 src"]


def test_nested_expansion_indents_with_spaces_only():
    tree = Tree([_sample()])
    tree.toggle()  # src
    assert texts(tree, 30) == ["\u25be src", "    app.py", "  \u25b8 lib"]
    tree.move(2)
    assert tree.selected is tree.root_nodes[0].children[1]  # lib
    assert tree.toggle() is True  # expand lib
    assert texts(tree, 30) == [
        "\u25be src",
        "    app.py",
        "  \u25be lib",
        "      a.py",  # depth 2: 4 indent columns + the 2-wide indicator column
        "      b.py",
    ]
    assert all("\u2502" not in row for row in texts(tree, 30))  # no guide connectors


def test_move_clamps_inside_the_visible_rows():
    tree = Tree([_sample()])
    tree.toggle()
    tree.move(1)
    assert tree.selected.label == "app.py"
    tree.move(-9)
    assert tree.selected.label == "src"  # clamped at the start
    tree.move(99)
    assert tree.selected.label == "lib"  # clamped at the end
    assert tree.move(1) is False  # already at the bottom


def test_toggle_is_idempotent_and_a_leaf_is_a_no_op():
    tree = Tree([_sample()])
    tree.toggle()
    tree.move(2)
    before = texts(tree, 30)
    assert tree.toggle() is True and tree.toggle() is True  # expand, collapse
    assert texts(tree, 30) == before
    leaf_tree = Tree([TreeNode("solo")])
    assert leaf_tree.toggle() is False  # a leaf cannot expand
    assert texts(leaf_tree, 30) == ["  solo"]
    empty = Tree([])
    assert empty.toggle() is False and empty.move(1) is False
    assert empty.selected is None and empty.render(10) == []


def test_collapsing_re_clamps_the_cursor():
    tree = Tree([_sample()])
    tree.toggle()  # expand src
    lib = tree.root_nodes[0].children[1]
    lib.expanded = True  # expand lib as well
    tree.move(2)
    assert tree.selected is lib
    assert tree.toggle() is True  # collapse lib: the cursor stays on lib
    assert tree.selected is lib
    assert texts(tree, 30) == ["\u25be src", "    app.py", "  \u25b8 lib"]

    # a host that mutates expanded behind the tree's back cannot push the
    # cursor (or render) out of range
    lib.expanded = True
    tree.move(4)
    assert tree.selected is lib.children[1]  # b.py
    lib.expanded = False
    assert tree.selected is lib  # clamped back into range
    assert len(tree.render(30)) == 3


def test_row_styles_and_fit_guard():
    tree = Tree(
        [_sample()],
        guide_style=Style(dim=True),
        label_style=Style(fg="blue"),
        cursor_style=SELECTION,
    )
    rows = tree.render(30)
    # the row under the cursor is one continuous band, like a Select row
    assert rows[0].segments == (Segment("\u25b8 src", SELECTION),)
    tree.toggle()  # expand src; the cursor stays on the src row
    tree.move(1)  # step off it onto app.py
    rows = tree.render(30)
    assert rows[0].segments == (
        Segment("\u25be ", Style(dim=True)),
        Segment("src", Style(fg="blue")),
    )
    assert rows[1].segments == (Segment("    app.py", SELECTION),)  # the cursor row
    assert rows[2].segments == (
        Segment("  \u25b8 ", Style(dim=True)),
        Segment("lib", Style(fg="blue")),
    )
    # an over-wide row truncates with an ellipsis instead of wrapping
    long_tree = Tree([TreeNode("a-very-long-node-label")])
    rows = long_tree.render(10)
    assert len(rows) == 1 and rows[0].width == 10
    assert rows[0].text.endswith("\u2026")
