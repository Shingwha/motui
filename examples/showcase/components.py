"""The component pages: the widget library, one category per page.

Every page opens with :func:`~showcase.page.header`, separates its parts with
:func:`~showcase.page.section`, and mounts anything a click should reach as
its **own block**.  A page that can be played with returns a
:class:`~mocode_tui.focus.FocusRing`: ``tab`` cycles the focus, the arrows and
``enter`` drive the focused widget, and a click runs the ring's click policy
-- and every widget that answers ``click(row, col)`` still takes a mouse hit
on its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import (
    ACCENT,
    Autocomplete,
    Confirm,
    DIM,
    Divider,
    Editor,
    FocusRing,
    Input,
    Markdown,
    Notice,
    Option,
    Padding,
    Panel,
    ProgressBar,
    Row,
    Select,
    Spinner,
    SUCCESS,
    Table,
    Tabs,
    Text,
    Tree,
    TreeNode,
    WARNING,
)

from .content import FIXTURE
from .page import PageBody, header, section

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["data", "feedback", "fields", "lists", "markdown", "structure"]

#: The data page's Markdown sample: one of every construct the engine renders.
MARKDOWN_SAMPLE = """\
### A Markdown block

Prose with **bold**, *italic*, `inline code` and a [link](https://example.invalid)
-- wrapped to the pane, never past it.

1. numbered items
2. a second one

> A quote, for the record.

```python
def hello(name: str) -> str:
    return f"hello {name}"
```

| column | meaning |
|:-------|--------:|
| rows   | 2       |
"""

#: The wrapping showcase: one long paragraph, broken on the pane's edge.
PARAGRAPH = (
    "Plain Text is the kernel's simplest component: one logical line per "
    "\\n, each word-wrapped to the width its parent hands it, every row fit "
    "back to that width. The pane you are reading is a Viewport window over "
    "one document; the row count above the fold is what its scrollbar shows."
)


def data(session: Showcase) -> PageBody:
    """Text, Markdown, Table, Divider -- the primitives that carry content."""
    theme = session.theme
    table = Table(
        ["component", "what it does", "state"],
        [
            ["Text", "verbatim rows, word-wrapped", ("streams", SUCCESS)],
            ["Markdown", "headings, lists, code, tables", ("live", SUCCESS)],
            ["Table", "shrinks to fit, never stretches", ("you are here", ACCENT)],
            ["Divider", "a full-width rule, labelled or not", ("below", WARNING)],
        ],
        aligns=["left", "left", "right"],
        theme=theme,
    )
    return PageBody([
        *header("text & data",
                "Text, Markdown, Table and Divider -- the primitives that carry content, "
                "and a table you can steer.", theme),
        section("Table -- natural widths, styled cells, a row cursor (\u2191\u2193 or a click)", theme),
        table,
        section("Markdown -- one sample of everything", theme),
        Markdown(MARKDOWN_SAMPLE, theme=theme),
        section("Text -- one paragraph, wrapped to the pane", theme),
        Text(PARAGRAPH, style=DIM),
        section("Divider -- three ways", theme),
        Divider(theme=theme),
        Divider(theme=theme, label="a labelled rule"),
        Divider(theme=theme, char="\u00b7", max_width=40),
    ], focus=FocusRing([table]), hint="table")


def structure(session: Showcase) -> PageBody:
    """Panels, rows and columns, insets -- plus a tab strip and a tree."""
    theme = session.theme
    tabs = Tabs(["overview", "components", "keys"], active=1, theme=theme)
    tree = Tree(
        [TreeNode("mocode_tui", [
            TreeNode("core", [TreeNode("lines"), TreeNode("painter")], expanded=True),
            TreeNode("widgets", [TreeNode("choice"), TreeNode("tree"), TreeNode("layout")]),
            TreeNode("chat", [TreeNode("composer"), TreeNode("transcript")]),
        ], expanded=True)],
        theme=theme,
    )

    return PageBody([
        *header("structure & layout",
                "Boxes and columns, insets -- and a tab strip and a tree you can click.", theme),
        section("Panel -- a child in a single-line box", theme),
        Row(
            [Panel(Text("a Panel around Text", style=DIM), title="Panel", theme=theme),
             Panel(Panel(Text("a Panel around a Panel", style=DIM), title="inner", theme=theme),
                   title="outer", theme=theme)],
            widths=[40, None],
        ),
        section("Row / Column -- fixed and flexible widths, gaps", theme),
        Row(
            [Panel(Text("fixed at 24", style=DIM), theme=theme),
             Panel(Text("the rest of the row", style=DIM), theme=theme),
             Panel(Text("and 20 more", style=DIM), theme=theme)],
            widths=[24, None, 20],
        ),
        section("Padding -- a child inset over a filled band", theme),
        Padding(Text("Padding: inset text over a filled band"), left=2, top=1,
                fill_style=theme.user_bg),
        section("Tabs -- click a tab", theme),
        tabs,
        section("Tree -- \u2191\u2193 move, enter or a click folds", theme),
        tree,
    ], focus=FocusRing([tabs, tree]), hint="tabs, tree")


def lists(session: Showcase) -> PageBody:
    """The menu kernel the palette runs on: Select, Confirm, Autocomplete."""
    theme = session.theme
    menu = Select(
        [Option(f"option {i:02d}", description=f"the description of row {i}")
         for i in range(1, 21)],
        max_rows=6,
        theme=theme,
    )
    menu.index = 11  # mid-list: the window and its (12/20) counter both show
    danger = Confirm("delete the project?", danger=True, theme=theme)
    plain = Confirm("and a plain confirmation?", theme=theme)
    filtered = Autocomplete(
        options=[Option("/help", description="the command list"),
                 Option("/components", description="the widget catalogue"),
                 Option("/clear", description="empty the transcript"),
                 Option("/quit", description="leave the demo")],
        theme=theme,
    )
    filtered.set_query("/c")

    return PageBody([
        *header("lists & menus",
                "The kernel the palette itself runs on: a windowed Select, Confirm, a filter.", theme),
        section("Select -- 20 rows, 6 visible, the counter under the window", theme),
        menu,
        section("Confirm -- a dangerous one and a plain one", theme),
        danger,
        plain,
        section("Autocomplete -- the same rows, narrowed by a query", theme),
        filtered,
    ], focus=FocusRing([menu, danger, plain, filtered]), hint="menus, confirms")


def fields(session: Showcase) -> PageBody:
    """The text fields: Input and Editor, in their states."""
    theme = session.theme
    hint_only = Input(placeholder="an empty focused Input: the hint, no cursor block", theme=theme)
    plain = Input(prompt="$ ", theme=theme, focused=False)
    plain.insert("focused=False renders the text plainly, without a cursor")
    editor = Editor(text="the Editor\ncarries a block cursor\nand wraps long lines at the pane edge",
                    theme=theme)
    windowed = Editor(text="\n".join(f"row {i:02d}" for i in range(1, 13)), max_rows=5, theme=theme)

    return PageBody([
        *header("fields",
                "The text fields. The one you can type in is the composer at the bottom.", theme),
        section("Input -- empty (focused) and plain", theme),
        hint_only,
        plain,
        section("Editor -- \u2191\u2193 move the block cursor, enter breaks a line, click where you want it",
                theme),
        editor,
        section("Editor -- a max_rows window over a twelve-row buffer, click any row", theme),
        windowed,
    ], focus=FocusRing([editor, windowed]), hint="editor, window")


def feedback(session: Showcase) -> PageBody:
    """Determinate bars, the spinner's frames, and the notice levels."""
    theme = session.theme
    live = ProgressBar(0.0, label="live", width_chars=20, theme=theme)
    spinner = Spinner("live")
    frame = Text("", style=theme.accent)

    def tick() -> None:
        spinner.advance()
        live.fraction = (live.fraction + 0.02) % 1.0
        frame.text = f"{spinner.frame} {spinner.text}"

    tick()
    return PageBody([
        *header("progress & feedback",
                "Determinate bars, a spinner, and the three notice levels.", theme),
        section("ProgressBar -- three fractions and one live bar", theme),
        Row([ProgressBar(0.25, label="25%", width_chars=16, theme=theme),
             ProgressBar(0.5, label="50%", width_chars=16, theme=theme),
             ProgressBar(1.0, label="done", width_chars=16, theme=theme)]),
        live,
        section("Spinner -- every frame, then one live", theme),
        Text("  ".join(Spinner("").frames), style=theme.accent),
        frame,
        section("Notice -- info, warn, error", theme),
        Notice("an info Notice: nothing to worry about", level="info", theme=theme),
        Notice("a warn Notice: mind the gap", level="warn", theme=theme),
        Notice("an error Notice: something broke", level="error", theme=theme),
    ], tick=tick)


def markdown(session: Showcase) -> PageBody:
    """The rendering fixture: every Markdown construct, one page long."""
    theme = session.theme
    return PageBody([
        *header("the Markdown fixture",
                f"{FIXTURE.name} -- every construct the engine renders, one page long.", theme),
        Markdown(FIXTURE.read_text(encoding="utf-8"), theme=theme),
    ])
