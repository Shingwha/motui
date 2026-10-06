"""The component pages: the widget library, one category per page.

Every page answers the same three questions with the exhibit grammar's
helpers: :func:`~showcase.page.header` says *what it is*, a
:func:`~showcase.page.try_line` says *what you do here*, and
:func:`~showcase.page.api_note` names the line of the library behind each
part -- with :func:`~showcase.page.section` separating the parts in between.
A page mounts anything a click should reach as its **own block**, so a hit
test resolves to the widget it landed on.  A page that can be played with
returns a :class:`~mocode_tui.focus.FocusRing`: ``tab`` cycles the focus, the
arrows and ``enter`` drive the focused widget, and a click runs the ring's
click policy -- and every widget that answers ``click(row, col)`` still takes
a mouse hit on its own.

An activation's outcome comes back through the ``chosen`` the host reads
once: the toast is the host's own, and a page that wants to echo the last
pick in a line of its own sets
:attr:`~showcase.page.PageBody.note` -- the page-level hook
:attr:`~showcase.page.PageBody.tick` is for live widgets.
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
from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["feedback", "fields", "lists", "markdown", "structure", "text"]

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


def text(session: Showcase) -> PageBody:
    """Text, Markdown, Table, Divider -- the primitives that carry content.

    The exhibit-grammar template: a ``TRY`` line saying what to do, the
    exhibit itself, and an ``API`` note per part saying which line of the
    library it is.  The table keeps its row cursor and its one-target ring.
    """
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
        try_line("click any table row; \u2191\u2193 moves the cursor; enter takes it", theme),
        table,
        api_note("Table.index / Table.chosen -- the host reads the pick once", theme),
        section("Markdown -- one sample of everything", theme),
        Markdown(MARKDOWN_SAMPLE, theme=theme),
        api_note("Markdown(text)", theme),
        section("Text -- one paragraph, wrapped to the pane", theme),
        Text(PARAGRAPH, style=DIM),
        api_note("Text(text, style=\u2026)", theme),
        section("Divider -- three ways", theme),
        Divider(theme=theme),
        Divider(theme=theme, label="a labelled rule"),
        Divider(theme=theme, char="\u00b7", max_width=40),
        api_note("Divider(label=\u2026, char=\u2026, max_width=\u2026)", theme),
    ], focus=FocusRing([table]), hint="table")


def structure(session: Showcase) -> PageBody:
    """Panels, rows and columns, insets -- plus a tab strip and a tree.

    The exhibit grammar in full: the ``TRY`` line says what to click, the
    boxes keep their "boxes and columns" story, and one ``API`` row names
    the three verbs the page runs on.  The dim line beside the two playable
    widgets points at the focus model's visible half: a widget that loses
    the focus keeps its cursor -- that row just dims.
    """
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
                "Boxes and columns, insets -- and a tab strip and a tree you can play with.",
                theme),
        try_line("click any tab in the strip, or any row in the tree; tab moves the focus on "
                 "-- the widget left behind dims its cursor; enter folds a node", theme),
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
        section("Tabs -- click a tab; tab moves the focus between the strip and the tree", theme),
        tabs,
        Text("when the focus moves on, the cursor row dims -- theme.dim merged over "
             "the selected style", style=theme.dim),
        section("Tree -- \u2191\u2193 move, enter or a click folds", theme),
        tree,
        api_note("Tabs.click(row, col) / Tree.activate() / FocusRing.handle(event)", theme),
    ], focus=FocusRing([tabs, tree]), hint="tabs, tree")


def lists(session: Showcase) -> PageBody:
    """The menu kernel the palette runs on: Select, Confirm, Autocomplete.

    The first page with an echo of its own: the pick a menu takes is read by
    the host exactly once (the toast) and handed back through the page's
    ``note`` hook, so the last pick stays on screen in the page's own line.
    Every row carries its payload in the option's ``value`` -- that payload
    is what a host acts on, which is why the echo can print it.
    """
    theme = session.theme
    menu = Select(
        [Option(f"option {i:02d}", value=f"option {i:02d}",
                description=f"the description of row {i}")
         for i in range(1, 21)],
        max_rows=6,
        theme=theme,
    )
    menu.index = 11  # mid-list: the window and its (12/20) counter both show
    danger = Confirm("delete the project?", danger=True, theme=theme)
    plain = Confirm("and a plain confirmation?", theme=theme)
    filtered = Autocomplete(
        options=[Option("/help", value="/help", description="the command list"),
                 Option("/components", value="/components", description="the widget catalogue"),
                 Option("/clear", value="/clear", description="empty the transcript"),
                 Option("/quit", value="/quit", description="leave the demo")],
        theme=theme,
    )
    filtered.set_query("/c")

    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """Write one reported activation onto the echo line (the last one only).

        The host reports ``chosen: <repr of the value>``; the echo keeps the
        value half, so the line reads the same shape for every menu here.
        """
        echo.text = f"last pick: {text.removeprefix('chosen: ')}"

    return PageBody([
        *header("lists & menus",
                "The kernel the palette itself runs on: a windowed Select, Confirm, a filter.",
                theme),
        try_line("click a row to move the cursor there; enter activates it -- watch the toast "
                 "and the echo line below", theme),
        echo,
        section("Select -- 20 rows, 6 visible, the counter under the window", theme),
        menu,
        api_note("Select.chosen -- the host reads the pick once, then resets it", theme),
        section("Confirm -- a dangerous one and a plain one", theme),
        danger,
        plain,
        api_note("Confirm -- a Yes/No pair of Option(\"Yes\", True) / Option(\"No\", False)", theme),
        section("Autocomplete -- the same rows, narrowed by a query", theme),
        filtered,
        api_note("Autocomplete -- enter takes the matching row into chosen", theme),
    ], focus=FocusRing([menu, danger, plain, filtered]), hint="menus, confirms", note=note)


def fields(session: Showcase) -> PageBody:
    """The text fields: Input and Editor, in their states.

    The landing exhibit for the interaction model's ``place``: the two
    blocks of text at the bottom take a click anywhere inside them and dock
    the block cursor on the very cell the hit test resolved -- the field
    answers the click itself, so there is no callback in the way.  The dim
    line closes with the paste rule the fields implement.
    """
    theme = session.theme
    hint_only = Input(placeholder="an empty focused Input: the hint, no cursor block", theme=theme)
    plain = Input(prompt="$ ", theme=theme, focused=False)
    plain.insert("focused=False renders the text plainly, without a cursor")
    editor = Editor(text="the Editor\ncarries a block cursor\nand wraps long lines at the pane edge",
                    theme=theme)
    windowed = Editor(text="\n".join(f"row {i:02d}" for i in range(1, 13)), max_rows=5, theme=theme)

    return PageBody([
        *header("fields",
                "The text fields -- and the two blocks at the bottom take a click anywhere "
                "in their text.", theme),
        try_line("click any cell in the two blocks of text at the bottom -- the block cursor "
                 "lands there; a click on the prompt lands at the row's start", theme),
        section("Input -- empty (focused) and plain", theme),
        hint_only,
        plain,
        api_note("Input(placeholder=\u2026) / Input(prompt=\u2026, focused=False)", theme),
        section("Editor -- \u2191\u2193 move the block cursor, enter breaks a line, "
                "click where you want it", theme),
        editor,
        api_note("TextBuffer.place(row, col) -- a click docks the cursor on the cell it hit", theme),
        section("Editor -- a max_rows window over a twelve-row buffer, click any row", theme),
        windowed,
        api_note("field.click(row, col) -- the cell of its own render, window rows included", theme),
        Text("a multi-line paste is one event and never submits; a single-line Input "
             "folds its newlines", style=theme.dim),
    ], focus=FocusRing([editor, windowed]), hint="editor, window")


def feedback(session: Showcase) -> PageBody:
    """Determinate bars, the spinner's frames, the notice levels -- and a toast.

    The activation exhibit of the feedback family: the level selector is the
    page's one ``Activable``, and every row carries the sentence it raises in
    its ``value`` -- so the host's read-once report (``chosen`` ->
    ``Toasts.show``) is exactly the toast you see.  The bars and the spinner
    keep the page's ``tick``; the notices show the three levels standing
    still, which is the half a toast cannot show.
    """
    theme = session.theme
    levels = Select(
        [Option(level, value=f"{level}: a {level} notice from the feedback exhibit")
         for level in ("info", "warn", "error")],
        theme=theme,
    )
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
                "Determinate bars, a spinner, the three notice levels -- and a selector "
                "that raises a toast.", theme),
        try_line("activate the level selector below -- it raises a toast at the level "
                 "you picked", theme),
        levels,
        api_note("Toasts.show(text) -- the row's value is the sentence the host shows", theme),
        section("ProgressBar -- three fractions and one live bar", theme),
        Row([ProgressBar(0.25, label="25%", width_chars=16, theme=theme),
             ProgressBar(0.5, label="50%", width_chars=16, theme=theme),
             ProgressBar(1.0, label="done", width_chars=16, theme=theme)]),
        live,
        api_note("ProgressBar.fraction -- set it and the bar repaints", theme),
        section("Spinner -- every frame, then one live", theme),
        Text("  ".join(Spinner("").frames), style=theme.accent),
        frame,
        api_note("Spinner.advance() -- the page's tick steps the frame above", theme),
        section("Notice -- info, warn, error", theme),
        Notice("an info Notice: nothing to worry about", level="info", theme=theme),
        Notice("a warn Notice: mind the gap", level="warn", theme=theme),
        Notice("an error Notice: something broke", level="error", theme=theme),
        api_note("Notice(text, level=\"info\" | \"warn\" | \"error\")", theme),
    ], focus=FocusRing([levels]), hint="levels", tick=tick)


def markdown(session: Showcase) -> PageBody:
    """The rendering fixture: every Markdown construct, one page long."""
    theme = session.theme
    return PageBody([
        *header("the Markdown fixture",
                f"{FIXTURE.name} -- every construct the engine renders, one page long.", theme),
        Markdown(FIXTURE.read_text(encoding="utf-8"), theme=theme),
    ])
