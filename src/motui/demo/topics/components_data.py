"""Data topics: List, Table, Tree, Tabs, NavList, ProgressBar and Spinner."""

from __future__ import annotations

from dataclasses import replace

from motui import List, Table, Tree
from motui.kernel.glyphs import GLYPHS
from motui.widgets import NavList, ProgressBar, Spinner, Tabs, TreeNode

from ..stage import topic

_ITEMS = [f"item {index:02d}" for index in range(1, 31)]

_TREE_ROWS = [
    TreeNode(
        "motui",
        [
            TreeNode("kernel", [TreeNode("lines"), TreeNode("frame")], expanded=True),
            TreeNode("widgets", [TreeNode("choice"), TreeNode("table")]),
            TreeNode("interaction", [TreeNode("focus"), TreeNode("modal")]),
        ],
        expanded=True,
    ),
    TreeNode("docs", [TreeNode("DESIGN.md"), TreeNode("CONTRACT.md")], expanded=True),
]


def _list(b) -> None:
    main = List(_ITEMS, window=6, theme=b.theme)
    marked = List(_ITEMS[:8], window=5, theme=b.theme)
    marked.index = 2
    marked.toggle()
    marked.take()  # the variant mounts without a stale pick
    disabled = List(_ITEMS[:8], window=5, disabled_items=[2], theme=b.theme)
    b.preview(main)
    b.variants(("marks", marked), ("disabled row", disabled))
    b.focus(main, marked, disabled)
    echo = b.echo("picked")

    def note(report) -> None:
        if report.source in (main, marked, disabled):
            echo.set(report.value)

    b.note(note)


def _table(b) -> None:
    headers = ["id", "name", "state"]
    rows = [
        ["01", "kernel", "stable"],
        ["02", "widgets", "stable"],
        ["03", "interaction", "stable"],
        ["04", "demo", "live"],
    ]
    table = Table(headers, rows, theme=b.theme)
    table.index = 0
    marked = Table(headers, rows, theme=b.theme)
    marked.index = 1
    marked.toggle()
    marked.take()
    aligned = Table(headers, rows, aligns=["right", "left", "right"], theme=b.theme)
    b.preview(table)
    b.variants(("marked row", marked), ("aligned columns", aligned))
    b.focus(table, marked, aligned)
    echo = b.echo("row")

    def note(report) -> None:
        if report.source in (table, marked, aligned):
            echo.set(report.value)

    b.note(note)


def _tree(b) -> None:
    tree = Tree(_TREE_ROWS, theme=b.theme)
    filtered = Tree(_TREE_ROWS, theme=b.theme)
    filtered.filter("kernel")
    disabled = Tree(
        [TreeNode("root", [TreeNode("locked", disabled=True), TreeNode("open")], expanded=True)],
        theme=b.theme,
    )
    b.preview(tree)
    b.variants(("filter('kernel')", filtered), ("disabled node", disabled))
    b.focus(tree)


def _tabs(b) -> None:
    tabs = Tabs(["Overview", "Components", "Interactions"], theme=b.theme)
    unfocused = Tabs(["One", "Two"], theme=b.theme)
    unfocused.focused = False
    b.preview(tabs)
    b.variants(
        ("disabled item", Tabs(["One", "Two", "Three"], disabled_items=[1], theme=b.theme)),
        ("unfocused strip", unfocused),
    )
    b.focus(tabs)


def _navlist(b) -> None:
    nav = NavList(
        ["Text", "Forms", "Data", "Layout"],
        groups=((0, "TEXT"), (2, "DATA")),
        theme=b.theme,
    )
    plain = NavList(
        ["Text", "Forms", "Data"], glyphs=replace(GLYPHS, rail=""), theme=b.theme
    )
    b.preview(nav)
    b.variants(("groups", nav), ("rail='' (no indicator)", plain))
    b.focus(nav)


def _progress(b) -> None:
    build = ProgressBar(0.35, label="build", theme=b.theme)
    tests = ProgressBar(0.75, label="tests", width_chars=20, theme=b.theme)
    b.preview(build, tests)
    b.variants(
        ("empty", ProgressBar(0.0, label="queued", theme=b.theme)),
        ("done", ProgressBar(1.0, label="done", theme=b.theme)),
    )

    def tick() -> None:
        build.fraction = 0.0 if build.fraction >= 1.0 else build.fraction + 0.01
        tests.fraction = 0.0 if tests.fraction >= 1.0 else tests.fraction + 0.02

    b.tick(tick)


def _spinner(b) -> None:
    working = Spinner("working", theme=b.theme)
    waiting = Spinner("waiting", theme=b.theme)
    b.preview(working, waiting)
    b.variants(
        ("custom frames", Spinner("custom", frames=("|", "/", "-", "\\"), theme=b.theme)),
        ("text only", Spinner("text only", theme=b.theme)),
    )

    def tick() -> None:
        working.advance()
        waiting.advance()

    b.tick(tick)


TOPICS = (
    topic(
        key="list",
        title="List",
        summary="A cursor over a long sequence, rendered as a sliding window with counters.",
        group="Data",
        section="components",
        try_line="up/down move; home/end jump; enter takes a row; space marks the cursor row",
        api_line="List(items, *, window, glyphs, disabled_items, bands) · move/activate/toggle",
        components=("List",),
        build=_list,
    ),
    topic(
        key="table",
        title="Table",
        summary="A box-drawing grid with a row cursor, marks, alignment and column budgets.",
        group="Data",
        section="components",
        try_line="up/down move; enter takes the row index; space marks; sort_by reorders records",
        api_line="Table(headers, rows, *, aligns, index, glyphs, grid) · move/sort_by/toggle",
        components=("Table",),
        build=_table,
    ),
    topic(
        key="tree",
        title="Tree",
        summary="An indented, collapsible node list with a cursor and a filter.",
        group="Data",
        section="components",
        try_line="up/down move; enter folds the node; the variant shows filter('kernel')",
        api_line="Tree(root_nodes, *, indent, glyphs) · TreeNode(label, children)",
        components=("Tree", "TreeNode"),
        build=_tree,
    ),
    topic(
        key="tabs",
        title="Tabs",
        summary="A one-row content strip with an underline indicator and disabled slots.",
        group="Data",
        section="components",
        try_line="left/right move; click a label; enter is the host's (no result)",
        api_line="Tabs(tabs, *, index, disabled_items, focused, theme) \u00b7 move/select/click",
        components=("Tabs",),
        build=_tabs,
    ),
    topic(
        key="navlist",
        title="NavList",
        summary="The vertical navigation rail: one row per item, a bar indicator, group rows.",
        group="Data",
        section="components",
        try_line="up/down move; click a row; group rows are chrome and never select",
        api_line="NavList(items, *, groups, index, glyphs, disabled_items, theme) \u00b7 select/click",
        components=("NavList",),
        build=_navlist,
    ),
    topic(
        key="progress",
        title="Progress",
        summary="A determinate bar: label, filled fraction and an empty track.",
        group="Data",
        section="components",
        try_line="watch the interactive beat move the fraction; the variants pin 0 and 1",
        api_line="ProgressBar(fraction, *, label, width_chars, done_style, todo_style, theme)",
        components=("ProgressBar",),
        build=_progress,
    ),
    topic(
        key="spinner",
        title="Spinner",
        summary="An activity indicator: a frame cycle plus a label, advanced by the host.",
        group="Data",
        section="components",
        try_line="watch the interactive beat advance the frame; advance() is the host's verb",
        api_line="Spinner(text='', *, frames, style, theme) \u00b7 advance() \u00b7 render(width)",
        components=("Spinner",),
        build=_spinner,
    ),
)
