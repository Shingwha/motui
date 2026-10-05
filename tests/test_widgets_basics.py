"""The single-purpose widgets: Spinner, StatusBar, Tabs, ProgressBar, Tree.

Each render is one contract -- the braille cycle, the priority footer, the
one-row tab strip, the fraction track, the depth-first tree walk -- asserted
as row texts, widths, and injected-style round trips (no default pinned).
"""

import pytest
from dataclasses import replace

from _doubles import texts

from mocode_tui.core.block import Component
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import NONE, SELECTION, Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.progress import ProgressBar
from mocode_tui.widgets.spinner import DEFAULT_FRAMES, Spinner
from mocode_tui.widgets.status import StatusBar, StatusSegment
from mocode_tui.widgets.tabs import Tabs
from mocode_tui.widgets.tree import Tree, TreeNode

#: Injected styles: they flow back out of the render equal.
ACTIVE = Style(fg="#abcdef")
INACTIVE = Style(fg="#123456")
DONE = Style(fg="#abcdef")
TODO = Style(fg="#123456")


# --- Spinner -------------------------------------------------------------------


def test_the_frame_and_label_render_on_one_row():
    spinner = Spinner("working")
    assert [row.text for row in spinner.render(80)] == [f"{DEFAULT_FRAMES[0]} working"]


def test_advance_steps_the_cycle_and_wraps():
    spinner = Spinner("x")
    spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[1]
    for _ in range(len(DEFAULT_FRAMES) - 1):
        spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[0]  # wrapped around


def test_empty_frames_render_the_label_only():
    spinner = Spinner("idle", frames=())
    assert spinner.render(20)[0].text == "idle"
    spinner.advance()  # no-op, must not raise
    assert spinner.render(20)[0].text == "idle"


def test_custom_frames_cycle():
    spinner = Spinner("go", frames=("|", "/", "-", "\\"))
    assert spinner.render(20)[0].text == "| go"
    spinner.advance()
    spinner.advance()
    assert spinner.render(20)[0].text == "- go"


def test_an_over_wide_label_truncates_instead_of_wrapping():
    row = Spinner("a very long label").render(6)[0]
    assert row.width == 6  # fit, not wrapped
    assert row.text.endswith("\u2026")


# --- StatusBar -----------------------------------------------------------------


def test_priority_order_and_lowest_dropped_first():
    bar = StatusBar(segments=[StatusSegment("aaa", 1), StatusSegment("bbb", 0)])
    assert [row.text for row in bar.render(7)] == ["aaa bbb"]
    assert [row.text for row in bar.render(6)] == ["aaa"]  # " bbb" no longer fits
    # Priority beats insertion order in both directions.
    flipped = StatusBar(segments=[StatusSegment("bbb", 0), StatusSegment("aaa", 1)])
    assert [row.text for row in flipped.render(6)] == ["aaa"]


def test_empty_bar_renders_one_blank_row():
    assert StatusBar().render(20) == [Line()]


def test_priority_ties_keep_insertion_order():
    bar = StatusBar(segments=[StatusSegment("one", 0), StatusSegment("two", 0)])
    assert [row.text for row in bar.render(20)] == ["one two"]


def test_segment_method_appends_cells():
    bar = StatusBar()
    bar.segment("left", 1)
    bar.segment("right", 0)
    assert [row.text for row in bar.render(20)] == ["left right"]


def test_narrow_width_truncates_the_survivor():
    row = StatusBar(segments=[StatusSegment("abcdef", 0)]).render(3)[0]
    assert row.text == "ab\u2026"
    assert row.width == 3


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
    assert tabs.activate(1) is (active != 1)  # already active: nothing changed
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


def test_narrow_widths_never_overflow():
    for width in (0, 1, 2, 3, 4, 5):
        assert _row(ProgressBar(0.5), width=width).width <= width
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
