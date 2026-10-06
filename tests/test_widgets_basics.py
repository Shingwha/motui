"""The single-purpose widgets: Spinner, Tabs, ProgressBar, Tree.

Each render is one contract, asserted as texts, widths and style round trips
(no default pinned); the narrow-width fit guard is pinned once, over the set.
The Spinner is frame-and-label state only -- the host (the Composer) paints
it into a rule -- so its tests read the state directly.
"""

import pytest
from dataclasses import replace

from _doubles import texts

from mocode_tui.core.block import Activable, Clickable, Component
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import NONE, SELECTION, Style
from mocode_tui.core.lines import Text
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.autocomplete import Autocomplete
from mocode_tui.widgets.choice import Option, Select
from mocode_tui.widgets.decor import Divider, Notice, Panel
from mocode_tui.widgets.editor import Editor
from mocode_tui.widgets.input import Input
from mocode_tui.widgets.layout import Column, Padding, Row, Spacer
from mocode_tui.widgets.progress import ProgressBar
from mocode_tui.widgets.spinner import DEFAULT_FRAMES, Spinner
from mocode_tui.widgets.tabs import Tabs
from mocode_tui.widgets.tree import Tree, TreeNode

#: Injected styles: they flow back out of the render equal.
ACTIVE = Style(fg="#abcdef")
INACTIVE = Style(fg="#123456")
DONE = Style(fg="#abcdef")
TODO = Style(fg="#123456")


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
}


def _field(text: str) -> Input:
    """An ``Input`` seeded with ``text`` (it takes no ``text=`` argument)."""
    field = Input()
    field.insert(text)
    return field


@pytest.mark.parametrize("name", sorted(_COMPONENTS))
def test_narrow_widths_never_overflow(name):
    for width in (0, 1, 2, 3, 5, 13):
        rows = _COMPONENTS[name]().render(width)
        assert rows and all(row.width <= width for row in rows)


# --- Spinner -------------------------------------------------------------------


def test_the_frame_and_label_are_the_state_a_host_paints():
    spinner = Spinner("working")
    assert spinner.frame == DEFAULT_FRAMES[0]
    assert spinner.text == "working"


def test_advance_steps_the_cycle_and_wraps():
    spinner = Spinner("x")
    spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[1]
    for _ in range(len(DEFAULT_FRAMES) - 1):
        spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[0]  # wrapped around


def test_empty_frames_yield_an_empty_frame():
    spinner = Spinner("idle", frames=())
    assert spinner.frame == ""
    spinner.advance()  # no-op, must not raise
    assert spinner.frame == ""


def test_custom_frames_cycle():
    spinner = Spinner("go", frames=("|", "/", "-", "\\"))
    assert spinner.frame == "|"
    spinner.advance()
    spinner.advance()
    assert spinner.frame == "-"


# --- Tabs ----------------------------------------------------------------------


def test_render_is_one_row_of_space_separated_names():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(40)
    assert len(rows) == 1  # a tab strip is always a single row
    assert rows[0].text == " alpha \u2502 beta \u2502 gamma "
    assert rows[0].segments == (
        Segment(" "),
        Segment("alpha", SELECTION),
        Segment(" \u2502 "),
        Segment("beta", NONE),
        Segment(" \u2502 "),
        Segment("gamma", NONE),
        Segment(" "),
    )
    assert isinstance(tabs, Component)


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


def test_active_highlight_follows_the_selection():
    tabs = Tabs(["a", "b"])
    tabs.move(1)
    segments = tabs.render(20)[0].segments
    assert segments[1].style == NONE  # "a" went quiet
    assert segments[3].style == SELECTION  # "b" is highlighted


def test_an_over_wide_strip_truncates_instead_of_wrapping():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(6)
    assert len(rows) == 1 and rows[0].width == 6
    assert rows[0].text == " alph\u2026"
    assert tabs.render(0) == [Line()]  # a zero painting width empties the row


def test_style_injection_round_trips():
    custom = Tabs(
        ["a", "b"],
        divider="|",
        active_style=ACTIVE,
        inactive_style=INACTIVE,
    )
    segments = custom.render(20)[0].segments
    assert segments[0].text == " " and segments[2].text == " | "  # the custom divider
    assert segments[1] == Segment("a", ACTIVE)
    assert segments[3] == Segment("b", INACTIVE)


def test_empty_tabs_render_one_empty_row():
    rows = Tabs([]).render(10)
    assert len(rows) == 1 and rows[0].text == ""


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


# --- ProgressBar ---------------------------------------------------------------


def _row(bar, width=10):
    rows = bar.render(width)
    assert len(rows) == 1  # a progress bar is exactly one row
    return rows[0]


@pytest.mark.parametrize(
    "fraction, track",
    [(0.0, "\u2591" * 4), (0.5, "\u2588\u2588\u2591\u2591"), (1.0, "\u2588" * 4)],
)
def test_the_track_fills_to_the_fraction(fraction, track):
    assert _row(ProgressBar(fraction, width_chars=4), width=20).text == f"[{track}]"


@pytest.mark.parametrize(
    "value, fraction, track",
    [
        (1.5, 1.0, "\u2588" * 4),  # clamped on construction
        (-0.2, 0.0, "\u2591" * 4),
        (0.75, 0.75, "\u2588\u2588\u2588\u2591"),
    ],
)
def test_fraction_clamps_on_construction_and_assignment(value, fraction, track):
    bar = ProgressBar(value, width_chars=4)
    assert bar.fraction == fraction
    bar.fraction = 2.0
    assert bar.fraction == 1.0
    bar.fraction = value
    assert _row(bar, width=20).text == f"[{track}]"  # a mutation re-renders


def test_label_prefixes_the_track():
    assert _row(ProgressBar(0.5, label="load"), width=10).text == "load [\u2588\u2588\u2591]"
    assert _row(ProgressBar(1.0, label="done"), width=10).text == "done [\u2588\u2588\u2588]"


def test_width_chars_pins_the_track_width():
    assert _row(ProgressBar(0.5, width_chars=4), width=40).text == "[\u2588\u2588\u2591\u2591]"
    # a pinned track (or label) wider than the painting width truncates with an ellipsis
    row = _row(ProgressBar(1.0, width_chars=6, label="x"), width=2)
    assert row.text == "x\u2026" and row.width == 2
    assert _row(ProgressBar(0.5, width_chars=30), width=8).width == 8
    # degenerate widths: the kernel fit pins, composed with the single fit call
    assert _row(ProgressBar(0.5), width=0).text == ""
    assert _row(ProgressBar(0.5), width=1).text == "\u2026"


def test_the_row_round_trips_the_injected_styles():
    # The one pinned five-segment golden: explicit styles and theme fields
    # both flow back out of the render equal.
    explicit = ProgressBar(0.5, width_chars=4, done_style=DONE, todo_style=TODO)
    assert _row(explicit, width=20).segments == (
        Segment(""),
        Segment("["),
        Segment("\u2588\u2588", DONE),
        Segment("\u2591\u2591", TODO),
        Segment("]"),
    )
    theme = replace(DEFAULT_THEME, success=DONE, dim=TODO)
    themed = ProgressBar(0.5, width_chars=4, theme=theme)
    assert _row(themed, width=20).segments == (
        Segment(""),
        Segment("["),
        Segment("\u2588\u2588", DONE),
        Segment("\u2591\u2591", TODO),
        Segment("]"),
    )


def test_is_a_component():
    assert isinstance(ProgressBar(0.4), Component)


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
