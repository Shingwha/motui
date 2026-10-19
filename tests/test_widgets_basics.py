
from dataclasses import replace

from motui import Table, TUI
from motui.kernel import Component, HeadlessScreen
from motui.kernel.block import Activable, Clickable, Focusable
from motui.kernel.lines import Line, Segment
from motui.kernel.lines import Text
from motui.kernel.style import SELECTION, Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import (
    Autocomplete,
    Collapsible,
    Column,
    Divider,
    Notice,
    Padding,
    Panel,
    ProgressBar,
    Radio,
    Row,
    ShortcutBar,
    Slider,
    Spacer,
    Spinner,
    TreeNode,
)
from motui.widgets.action import Button, Checkbox, Link
from motui.widgets.choice import Option, Select
from motui.widgets.textfield import Editor, Input
from motui.interaction.palette import Palette
from motui.widgets.rows import StatusLine
from motui.widgets.tabs import Tabs
from motui.widgets.tree import Tree

"""The strip and data-view widgets: Tabs and Tree.

Each render is one contract, asserted as texts, widths and style round trips
(no default pinned); the narrow-width fit guard is pinned once, over the set
of components it names (Spinner and the other value indicators now live in
``test_widgets_indicators.py``).

The file ends with the table's memory (render-cost W2): the table's own
tests live in ``test_widgets_table.py``, which that wave's write scope kept
untouched, so the two block-level cases -- the memo hit with its in-place
edit, and the sealed block's hover reaching the screen -- ride here.
"""

import pytest
from dataclasses import replace

from _doubles import texts


#: Injected styles: they flow back out of the render equal.
ACTIVE = Style(fg="#abcdef")
INACTIVE = Style(fg="#123456")
DONE = Style(fg="#abcdef")
TODO = Style(fg="#123456")
DISABLED = Style(fg="#654321")
DIVIDER = Style(fg="#0f0f0f")
#: The horizontal indicator's shape (D2): the underline the active label wears.
INDICATOR = Style(underline=True)


# --- the fit guard: one behavior, every component, every width -----------------

#: The component set the ``row.width <= width`` guard is pinned on, once.
_COMPONENTS = {
    "Tabs": lambda: Tabs(["alpha", "beta"]),
    "ProgressBar": lambda: ProgressBar(0.5),
    "Tree": lambda: Tree([TreeNode("a-long-node-label")]),
    "Notice": lambda: Notice("a long warning message", level="warn"),
    "Divider": lambda: Divider(label="a long working label"),
    "Panel": lambda: Panel(Text("a long body")),
    "Spacer": lambda: Spacer(2),
    "Padding": lambda: Padding(Text("a long body"), left=2),
    "Row": lambda: Row([Text("a long body")]),
    "Column": lambda: Column([Text("a long body")]),
    "Select": lambda: Select([Option("a long option")]),
    "Autocomplete": lambda: Autocomplete(options=[Option("a long option")]),
    "Input": lambda: _field("a long typed value"),
    "Editor": lambda: Editor(text="a long typed value"),
    "Button": lambda: Button("a long label"),
    "Checkbox": lambda: Checkbox("a long label"),
    "Link": lambda: Link("a long link target"),
    "StatusLine": lambda: StatusLine(left=("a long left",), right=("a long right",)),
    "Palette": lambda: _opened_palette(),
    "Radio": lambda: Radio(["a long label", "another long label"]),
    "Slider": lambda: Slider(5),
    "Collapsible": lambda: Collapsible("a long title", Text("a long body")),
    "ShortcutBar": lambda: ShortcutBar([("c-n", "a long label"), ("c-p", "another")]),
}


def _field(text: str) -> Input:
    """An ``Input`` seeded with ``text`` (it takes no ``text=`` argument)."""
    field = Input()
    field.insert(text)
    return field


def _opened_palette() -> Palette:
    """An open ``Palette`` (closed it renders zero rows -- nothing to guard)."""
    tui = TUI(screen=HeadlessScreen(80, 8), interactive=False)
    palette = Palette(tui, [Option("/help", value="help")])
    palette.open()
    return palette




# --- Tabs ----------------------------------------------------------------------


def test_render_is_one_row_of_space_separated_names():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(40)
    assert len(rows) == 1  # a tab strip is always a single row
    assert rows[0].text == " alpha \u2502 beta \u2502 gamma "
    # The defaults (D4): the active label in the accent *plus* the underline
    # indicator, the others dim, each divider in its own muted style.
    assert rows[0].segments == (
        Segment(" "),
        Segment("alpha", DEFAULT_THEME.accent.merge(INDICATOR)),
        Segment(" \u2502 ", DEFAULT_THEME.muted),
        Segment("beta", DEFAULT_THEME.dim),
        Segment(" \u2502 ", DEFAULT_THEME.muted),
        Segment("gamma", DEFAULT_THEME.dim),
        Segment(" "),
    )
    assert isinstance(tabs, Component)
    assert Tabs([]).render(40) == [Line()]  # an empty strip's one empty row


@pytest.mark.parametrize(
    "start, delta, active, changed",
    [
        (0, 1, 1, True),
        (0, 5, 2, True),  # clamped at the end
        (2, -9, 0, True),  # clamped at the start, no wrap-around
        (0, -1, 0, False),  # already at the top: nothing changed
    ],
)
def test_move_clamps_without_wrapping(start, delta, active, changed):
    tabs = Tabs(["a", "b", "c"], active=start)
    assert tabs.move(delta) is changed
    assert tabs.active == active
    assert tabs.select(1) is (active != 1)  # already active: nothing changed
    assert Tabs(["a", "b"], active=7).active == 1  # clamped on construction
    assert Tabs([], active=3).active == 0
    assert Tabs([]).move(1) is False


def test_move_steps_over_the_disabled_indices():
    tabs = Tabs(["a", "b", "c", "d"], disabled={1, 2})
    assert tabs.move(1) is True and tabs.active == 3  # 1 and 2 are stepped over
    assert tabs.move(1) is False and tabs.active == 3  # the edge: no landing left
    assert tabs.move(-1) is True and tabs.active == 0  # and back across both
    assert tabs.move(-1) is False and tabs.active == 0
    one = Tabs(["a", "b"], disabled={1})  # the only step out is disabled
    assert one.move(1) is False and one.active == 0


def test_active_highlight_follows_the_selection():
    tabs = Tabs(["a", "b"])
    tabs.move(1)
    segments = tabs.render(20)[0].segments
    assert segments[1] == Segment("a", DEFAULT_THEME.dim)  # "a" went quiet
    assert segments[3] == Segment("b", DEFAULT_THEME.accent.merge(INDICATOR))


def test_a_disabled_label_is_visible_but_not_selectable():
    tabs = Tabs(["a", "b", "c"], disabled={1}, disabled_style=DISABLED)
    rows = tabs.render(20)  # " a \u2502 b \u2502 c ": "b" spans cell 5
    assert rows[0].segments[3] == Segment("b", DISABLED)  # the disabled style
    assert tabs.click(0, 5) is False and tabs.active == 0  # a click is refused
    assert tabs.select(1) is False and tabs.active == 0  # so is a select
    assert tabs.hover_at(0, 5) is True  # the pointer still marks it ...
    assert tabs.render(20)[0].segments[3] == Segment(
        "b", DISABLED.merge(DEFAULT_THEME.hover),  # ... with the hover band
    )
    assert tabs.move(1) is True and tabs.active == 2  # the step skips it
    assert tabs.hover_at(-1, -1) is True  # the pointer left
    assert tabs.render(20)[0].segments[3] == Segment("b", DISABLED)


def test_the_indicator_survives_with_every_color_turned_off():
    """No-color readability: the underline -- not a hue -- is the mark."""
    plain = Style()
    strip = Tabs(
        ["a", "b"], active_style=plain, inactive_style=plain, indicator_style=plain
    )
    segments = strip.render(20)[0].segments
    assert segments[1].style.underline is True  # the active label is marked ...
    assert segments[3].style.underline is False  # ... the inactive one is not
    assert (segments[1].text, segments[3].text) == ("a", "b")  # the same glyphs


def test_an_over_wide_strip_truncates_instead_of_wrapping():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(6)
    assert len(rows) == 1 and rows[0].width == 6
    assert rows[0].text == " alph\u2026"
    assert tabs.render(0) == [Line()]  # a zero painting width empties the row


def test_style_injection_round_trips_with_the_indicator_on_top():
    """The active segment is ``active_style`` + the indicator, in that order."""
    custom = Tabs(
        ["a", "b"],
        divider="|",
        active_style=ACTIVE,
        inactive_style=INACTIVE,
        divider_style=DIVIDER,
        indicator_style=INDICATOR,
    )
    segments = custom.render(20)[0].segments
    assert segments[0].text == " " and segments[2].text == " | "  # the custom divider
    assert segments[2] == Segment(" | ", DIVIDER)  # the divider's own style
    assert segments[1] == Segment("a", ACTIVE.merge(INDICATOR))
    assert segments[3] == Segment("b", INACTIVE)


def test_an_unfocused_strip_drops_the_indicator_and_keeps_the_label():
    """D3: unfocused lowers the indicator's hue; the label is not dimmed."""
    strip = Tabs(["a", "b"], active_style=ACTIVE, inactive_style=INACTIVE, focused=False)
    assert isinstance(strip, Focusable) and strip.focused is False
    segments = strip.render(20)[0].segments
    # The indicator takes the theme's muted *whole* -- muted carries a fg, so
    # there is no "lower the weight only" merge; the underline stays.
    assert segments[1] == Segment("a", ACTIVE.merge(DEFAULT_THEME.muted).merge(INDICATOR))
    assert segments[2] == Segment(" \u2502 ", DEFAULT_THEME.muted)  # the divider's own
    assert segments[3] == Segment("b", INACTIVE)  # an inactive label is untouched
    strip.focused = True
    assert strip.render(20)[0].segments[1] == Segment(
        "a", ACTIVE.merge(DEFAULT_THEME.accent).merge(INDICATOR)
    )


def test_click_maps_the_column_to_the_tab_under_it():
    tabs = Tabs(["a", "b", "c"])
    assert isinstance(tabs, Clickable)
    tabs.render(20)  # the strip is " a \u2502 b \u2502 c ": labels at 1 / 5 / 9
    assert tabs.click(0, 5) is True and tabs.active == 1  # the middle tab
    assert tabs.click(0, 9) is True and tabs.active == 2  # the last tab
    assert tabs.click(0, 5) is True  # a hit even when it already was active
    assert tabs.click(0, 1) is True and tabs.active == 0  # back to the first
    for col in (0, 2, 3, 4, 6, 7, 8, 10, 11, 99, -1):  # padding, dividers, past the end
        assert tabs.click(0, col) is False and tabs.active == 0
    for row in (-1, 1, 9):  # the strip paints one row: any other row misses
        assert tabs.click(row, 5) is False and tabs.active == 0
    assert Tabs([]).click(0, 0) is False  # no tab to hit


def test_click_counts_wide_labels_by_display_width():
    tabs = Tabs(["\u4e2d\u6587", "ab"])  # each CJK character measures two columns
    tabs.render(20)  # " \u4e2d\u6587 \u2502 ab ": the wide label spans cells 1-4
    assert tabs.click(0, 1) is True and tabs.active == 0  # the label's first cell
    assert tabs.click(0, 4) is True  # ...and its last: four columns wide, not two
    for col in (0, 5, 6, 7, 11):  # the padding, the divider, past the end
        assert tabs.click(0, col) is False and tabs.active == 0
    assert tabs.click(0, 8) is True and tabs.active == 1  # "ab" starts after the gap


def test_click_follows_the_strips_own_divider_and_negative_columns():
    tabs = Tabs(["a", "b"], divider="::")
    tabs.render(20)  # " a :: b ": the divider spans 2-5, "b" starts at 6
    assert tabs.click(0, 6) is True and tabs.active == 1
    assert tabs.click(0, 3) is False and tabs.active == 1  # inside the divider
    assert tabs.click(0, -5) is False and tabs.active == 1  # before the strip


def test_an_empty_strip_misses_every_cell():
    empty = Tabs([])
    for row, col in ((0, 0), (0, 9), (1, 3), (-1, -1)):
        assert empty.click(row, col) is False


def test_click_before_the_first_render_maps_against_the_default_width():
    tabs = Tabs(["a"])  # never rendered: the 80-column default geometry
    assert tabs.click(0, 1) is True and tabs.active == 0
    assert tabs.click(0, 2) is False  # the trailing padding, same as after a render


def test_click_maps_against_the_last_render_not_the_first():
    tabs = Tabs(["alpha", "beta"])
    tabs.render(40)  # untruncated: "alpha" spans cells 1-5
    assert tabs.click(0, 1) is True and tabs.active == 0
    tabs.render(6)  # truncated to " alph\u2026": no label covers cell 1 any more
    assert tabs.click(0, 1) is False and tabs.active == 0




# --- Tree ----------------------------------------------------------------------


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
    assert tree.activate() is True  # expand src
    assert tree.root_nodes[0].expanded is True
    # a leaf keeps the 2-wide indicator column blank, so its label lines up
    # with a parent's label at the same depth (column 4 here)
    assert texts(tree, 30) == ["\u25be src", "    app.py", "  \u25b8 lib"]
    assert tree.activate() is True  # collapse src again
    assert texts(tree, 30) == ["\u25b8 src"]


def test_nested_expansion_indents_with_spaces_only():
    tree = Tree([_sample()])
    tree.activate()  # src
    assert texts(tree, 30) == ["\u25be src", "    app.py", "  \u25b8 lib"]
    tree.move(2)
    assert tree.selected is tree.root_nodes[0].children[1]  # lib
    assert tree.activate() is True  # expand lib
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
    tree.activate()
    tree.move(1)
    assert tree.selected.label == "app.py"
    tree.move(-9)
    assert tree.selected.label == "src"  # clamped at the start
    tree.move(99)
    assert tree.selected.label == "lib"  # clamped at the end
    assert tree.move(1) is False  # already at the bottom


def test_the_ground_style_resolves_and_rests_under_every_row():
    ground = Style(fg="#101010")
    tree = Tree([_sample()], ground_style=ground)
    tree.activate()  # rows: src / app.py / lib
    rows = tree.render(20)
    # The resting rows rest on the ground, the guide's and the label's own
    # styles riding on top of it; the cursor row swaps the band.
    assert rows[1].segments[0].style == ground.merge(DEFAULT_THEME.dim)
    assert rows[1].segments[1].style == ground
    assert rows[0].segments[0].style == DEFAULT_THEME.ground_active
    # the theme field is the fallback the explicit style wins over
    themed = Tree([_sample()], theme=replace(DEFAULT_THEME, ground=ground))
    assert themed.render(20)[0].segments[0].style == DEFAULT_THEME.ground_active


def test_click_places_the_cursor_on_the_visible_node_row():
    tree = Tree([_sample()])
    assert isinstance(tree, Clickable)
    assert isinstance(tree, Activable)  # expanding/collapsing is its activation
    tree.activate()  # rows: src / app.py / lib
    assert tree.click(1, 0) is True and tree.selected.label == "app.py"
    assert tree.click(1, 0) is True  # a hit even when the cursor already was there
    for row in (-1, 3, 9):
        assert tree.click(row, 0) is False and tree.selected.label == "app.py"
    assert Tree([]).click(0, 0) is False  # no node to hit


def test_tree_click_ignores_the_column():
    tree = Tree([_sample()])
    tree.activate()
    for col in (0, 3, 40, 999):  # a node row owns the whole width
        assert tree.click(1, col) is True and tree.selected.label == "app.py"
    assert tree.click(9, 40) is False  # past the last node: no hit at any column


def test_tree_rows_map_the_same_at_any_column():
    tree = Tree([_sample()])
    tree.activate()  # rows: src / app.py / lib -- indented, labels trailing
    tree.render(30)  # the rendered rows are what the click maps against
    for col in (0, 2, 8, 120):
        assert tree.click(2, col) is True and tree.selected.label == "lib"
        assert tree.click(3, col) is False and tree.selected.label == "lib"  # past the end


def test_activate_is_idempotent_and_a_leaf_is_a_no_op():
    tree = Tree([_sample()])
    tree.activate()
    tree.move(2)
    before = texts(tree, 30)
    assert tree.activate() is True and tree.activate() is True  # expand, collapse
    assert texts(tree, 30) == before
    leaf_tree = Tree([TreeNode("solo")])
    assert leaf_tree.activate() is False  # a leaf cannot expand
    assert texts(leaf_tree, 30) == ["  solo"]
    empty = Tree([])
    assert empty.activate() is False and empty.move(1) is False
    assert empty.selected is None and empty.render(10) == []


def test_collapsing_re_clamps_the_cursor():
    tree = Tree([_sample()])
    tree.activate()  # expand src
    lib = tree.root_nodes[0].children[1]
    lib.expanded = True  # expand lib as well
    tree.move(2)
    assert tree.selected is lib
    assert tree.activate() is True  # collapse lib: the cursor stays on lib
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
    tree.activate()  # expand src; the cursor stays on the src row
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


def test_an_unfocused_tree_dims_the_cursor_row_only():
    tree = Tree(
        [_sample()],
        guide_style=Style(dim=True),
        label_style=Style(fg="blue"),
        cursor_style=SELECTION,
        focused=False,
    )
    assert isinstance(tree, Focusable) and tree.focused is False
    band = SELECTION.merge(DEFAULT_THEME.dim)
    rows = tree.render(30)
    assert rows[0].segments == (Segment("\u25b8 src", band),)  # the cursor row
    tree.activate()  # expand src; the cursor stays on the src row
    tree.move(1)  # step off it onto app.py
    rows = tree.render(30)
    assert rows[0].segments == (
        Segment("\u25be ", Style(dim=True)),
        Segment("src", Style(fg="blue")),
    )
    assert rows[1].segments == (Segment("    app.py", band),)  # the new cursor row
    assert rows[2].segments == (  # an uncursored row is untouched
        Segment("  \u25b8 ", Style(dim=True)),
        Segment("lib", Style(fg="blue")),
    )


# --- Tree: filter and prefix jump -------------------------------------------------


def _deep_tree():
    """src (collapsed) with a nested lib, and a second root -- the allowlist."""
    return Tree(
        [
            TreeNode(
                "src",
                children=[
                    TreeNode("app.py"),
                    TreeNode("lib", children=[TreeNode("a.py"), TreeNode("b.py")]),
                ],
            ),
            TreeNode("docs", children=[TreeNode("guide")]),
        ]
    )


def test_filter_prunes_to_the_matches_and_keeps_their_ancestors():
    tree = _deep_tree()
    assert tree.filter("lib") is True  # case-insensitive substring
    # lib matches; src is its ancestor (kept and rendered open -- the chain
    # to the hit).  lib itself has no *matching* child below it, so nothing
    # is kept under it and its own indicator stays folded; docs is gone.
    assert texts(tree, 30) == ["\u25be src", "  \u25b8 lib"]
    # A deeper query keeps the whole chain and prunes the siblings.
    assert tree.filter("B.PY") is True
    assert texts(tree, 30) == ["\u25be src", "  \u25be lib", "      b.py"]
    # A query matching a leaf keeps only its chain.
    assert tree.filter("guide") is True
    assert texts(tree, 30) == ["\u25be docs", "    guide"]
    # Nothing matches: no rows at all -- and every verb declines politely.
    assert tree.filter("nope") is True
    assert tree.render(30) == [] and tree.selected is None
    assert tree.move(1) is False and tree.activate() is False
    assert tree.click(0, 0) is False and tree.hover_at(0, 0) is False
    # The empty query matches every label (the substring rule): the whole
    # tree shows, every chain open.
    assert tree.filter("") is True
    assert texts(tree, 30) == [
        "\u25be src",
        "    app.py",
        "  \u25be lib",
        "      a.py",
        "      b.py",
        "\u25be docs",
        "    guide",
    ]
    # None clears; the same query twice (and clearing an unfiltered tree)
    # are no-ops that answer False.
    assert tree.filter(None) is True
    assert tree.filter(None) is False
    assert tree.filter("lib") is True and tree.filter("lib") is False
    assert tree.filter(None) is True


def test_filter_never_rewrites_the_users_expansion_set():
    tree = _deep_tree()
    src, docs = tree.root_nodes
    src.children[1].expanded = True  # the user expanded lib (src stays folded)
    before = texts(tree, 30)
    assert before == ["\u25b8 src", "\u25b8 docs"]  # src folded: lib is not visible
    assert tree.filter("a.py") is True
    assert texts(tree, 30) == ["\u25be src", "  \u25be lib", "      a.py"]  # open chains
    # The flags were read, never written: the filter's open chains (the
    # indicators included) are derived from the match structure.
    assert src.expanded is False and src.children[1].expanded is True
    # The cursor went back to the top row for the new list.
    assert tree.selected is src
    # Clearing restores the user's own rows, byte for byte.
    assert tree.filter(None) is True
    assert texts(tree, 30) == before
    assert (src.expanded, src.children[1].expanded) == (False, True)
    # activate() keeps working while filtered -- the flag flips (the fold
    # waits for the filter to clear), and the filter is not disturbed.
    tree.filter("b.py")
    assert tree.activate() is True  # src has children: the flag flips
    assert src.expanded is True
    assert texts(tree, 30) == ["\u25be src", "  \u25be lib", "      b.py"]
    tree.filter(None)
    # The fold shows: src opened by activate(), lib still expanded by the
    # user, app.py back, docs untouched.
    assert texts(tree, 30) == [
        "\u25be src",
        "    app.py",
        "  \u25be lib",
        "      a.py",
        "      b.py",
        "\u25b8 docs",
    ]


def test_filter_rows_are_the_click_and_hover_rows():
    tree = _deep_tree()
    tree.filter("py")  # src / app.py / lib / a.py / b.py: five rows, chains open
    assert tree.click(4, 0) is True and tree.selected.label == "b.py"
    assert tree.click(1, 40) is True and tree.selected.label == "app.py"
    assert tree.click(5, 0) is False  # past the filtered rows
    assert tree.hover_at(3, 0) is True  # a.py
    rows = tree.render(30)
    assert any(seg.style.reverse for seg in rows[3].segments)
    # The cursor row is the filtered row 0, and the band follows it.
    tree.move(-9)
    rows = tree.render(30)
    assert rows[0].segments == (Segment("\u25be src", DEFAULT_THEME.selection),)


def test_jump_walks_the_next_matching_visible_row_and_wraps():
    tree = _deep_tree()
    src, docs = tree.root_nodes
    assert (src.expanded, docs.expanded) == (False, False)
    src.expanded = True
    src.children[1].expanded = True
    src.children[1].children[1].label = "Beta"  # a capital B for the case rule
    # Visible rows: src / app.py / lib / a.py / Beta / docs (docs folded).
    assert texts(tree, 30) == [
        "\u25be src",
        "    app.py",
        "  \u25be lib",
        "      a.py",
        "      Beta",
        "\u25b8 docs",
    ]
    assert tree.selected is src
    assert tree.jump("b") is True and tree.selected.label == "Beta"  # case-insensitive
    assert tree.jump("s") is True and tree.selected.label == "src"  # wraps around
    assert tree.jump("d") is True and tree.selected.label == "docs"
    # A single visible match: the cursor parks on it (True the first time)
    # and a second press answers False -- the hop would be to itself.
    assert tree.jump("B") is True and tree.selected.label == "Beta"
    assert tree.jump("B") is False and tree.selected.label == "Beta"  # the only B
    assert tree.jump("a") is True and tree.selected.label == "app.py"  # the next "a"
    assert tree.jump("a") is True and tree.selected.label == "a.py"  # ... and the next
    # Misses and non-characters decline without moving.
    assert tree.jump("z") is False and tree.selected.label == "a.py"
    assert tree.jump("") is False and tree.jump("ab") is False
    assert tree.jump("\t") is False and tree.jump("\x01") is False
    assert tree.selected.label == "a.py"
    empty = Tree([])
    assert empty.jump("a") is False and empty.selected is None
    # The scan runs over the *visible* rows, the filtered ones included.
    tree.filter("lib")  # two rows: src (kept ancestor) and lib (the hit)
    assert texts(tree, 30) == ["\u25be src", "  \u25b8 lib"]
    assert tree.jump("s") is False  # src is current: the hop is to itself
    assert tree.jump("l") is True and tree.selected.label == "lib"
    assert tree.jump("s") is True and tree.selected.label == "src"  # wraps in the prune
    assert tree.jump("a") is False  # a.py is not visible under the filter


# --- the table's memory: the revision protocol's table end (render-cost W2) ----


def test_the_table_remembers_its_grid_until_a_row_input_moves():
    """The memo hit hands out its own list, and an in-place edit misses.

    ``Table.rows`` is the host's bare list, so the snapshot the memory
    compares must be a copy: a rewritten cell has to move it exactly as a
    moved cursor does, or the remembered grid would freeze a table the host
    is editing (D7).  The hit is observed through row *identity* -- a
    rebuilt grid makes new ``Line`` values even where they compare equal --
    and the returned list is fresh, because the memory keeps its own.
    """
    table = Table(["a"], [["1"], ["2"]])
    first = table.render(20)
    hit = table.render(20)
    assert hit == first and hit is not first  # the caller owns the list ...
    assert hit[3] is first[3]  # ... while the grid's rows are the very same values
    table.rows[0][0] = "changed"  # in place: the same list objects all along
    edited = table.render(20)
    assert edited[3] is not first[3] and "changed" in edited[3].text
    table.index = 1  # the cursor is a row input too: the band moves
    assert table.render(20) != edited  # same texts, different bands
    table.rows = [["solo"]]  # and so is a rebinding of the whole row list
    assert len(table.render(20)) == 5  # a bare frame around one data row


def test_a_sealed_tables_hover_reaches_the_screen():
    """The D4 regression, as the probe's F3 asserts it: the band lands.

    A sealed block's rows are cached, so a marking that never moves the
    block's revision would repaint nothing -- the bug the revision token
    fixes.  The marked row is the first **data** row: the table's own
    render starts with the top rule, the header and the header rule, so
    that is row 3 of the component's output (``hover_at`` resolves a frame
    row to no row, exactly as ``click`` does).
    """
    tui = TUI(screen=HeadlessScreen(60, 10), interactive=False)
    table = Table(["a", "b"], [["1", "2"], ["3", "4"], ["5", "6"]])
    tui.add(table).seal()
    tui.paint()
    before = [row.styled() for row in tui.rows]
    assert table.hover_at(3, 0) is True  # the first data row, under three frame rows
    tui.paint()
    assert [row.styled() for row in tui.rows] != before
