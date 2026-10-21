"""Interaction topics: the seven tiers, each with a small live sandbox."""

from __future__ import annotations

from motui import Button, Checkbox, Dialog, Link, Markdown, Modal, Text
from motui.widgets import ButtonSpec, Column, Notice, ScrollView, Table

from ..stage import topic

_DISPATCH_ROWS = [
    ["1", "stats", "counts every event, consumes none"],
    ["2", "palette", "the global command palette while open"],
    ["3", "modal", "the topic's blocking panel while open"],
    ["4", "find", "the search row while open"],
    ["5", "scrollbar", "the pane's thumb and track"],
    ["6", "toasts", "clicks on the notification stack"],
    ["7", "gesture", "press/drag/release selection"],
    ["8", "pointer", "hover and stationary clicks (watches beside)"],
    ["9", "focus", "the focused leaf: arrows, enter, handled keys"],
    ["10", "host", "navigation, theme, palette, find, quit"],
]

_FIND_TEXT = """\
# Find

Find searches the focused pane's document, case-insensitively, and
reveals the current match. Type a query, then press enter to step to the
next match. The row at the bottom carries an (i/n) counter.

- find the word find in this paragraph
- the markdown heading above is a match too
- escape closes the row and keeps the document
"""


def _focus(b) -> None:
    first = Button("First", theme=b.theme)
    first.hint = "the first ring target"
    second = Checkbox("Second", theme=b.theme)
    second.hint = "the ring's second target"
    third = Link("Third", theme=b.theme)
    third.hint = "the ring's last target"
    b.preview(first, second, third)
    b.focus(first, second, third)
    echo = b.echo("result")

    def note(report) -> None:
        if report.source in (first, second, third):
            echo.set(report.value)

    b.note(note)


def _pointer(b) -> None:
    button = Button("Hover or click me", theme=b.theme)
    button.hint = "hover flips this leaf's hint band"
    link = Link("a link under the pointer", theme=b.theme)
    link.hint = "the pointer tracks the deepest leaf"
    b.preview(button, link)
    b.focus(button, link)


def _selection(b) -> None:
    text = Text(
        "\n".join(
            f"line {index:02d}: drag across these rows and release to copy"
            for index in range(1, 16)
        ),
        theme=b.theme,
    )
    b.preview(text)


def _find(b) -> None:
    document = Markdown(_FIND_TEXT, theme=b.theme)
    b.preview(document)


def _scrollbar(b) -> None:
    content = Column(
        [Text(f"line {index:02d}: the scrollbar maps this document") for index in range(1, 41)]
    )
    view = ScrollView(content, height=8, bar=True, theme=b.theme)
    b.preview(view)
    b.focus(view)


def _modal_stack(b) -> None:
    first_dialog = Dialog(
        "First panel",
        Text("Its decision opens the second panel."),
        ["Cancel", ButtonSpec("Next", "next")],
        theme=b.theme,
    )
    second_dialog = Dialog(
        "Second panel",
        Text("Closing the top panel returns to the one below."),
        [ButtonSpec("Done", "done")],
        theme=b.theme,
    )
    first = Modal(b.session.tui, first_dialog, theme=b.theme)
    second = Modal(b.session.tui, second_dialog, theme=b.theme)
    opener = Button("Open first panel", theme=b.theme)
    opener.hint = "the first of two stacked modals"
    b.preview(opener)
    b.modal(first)
    b.controller(second)
    b.focus(opener)
    echo = b.echo("result")

    def note(report) -> None:
        if report.source is opener:
            first.open()
        elif report.source is first:
            echo.set(report.value)
            body = b.session.body
            if body is not None and report.value == "next":
                second.open()
                body.modal = second
        elif report.source is second:
            echo.set(report.value, "done")

    b.note(note)


def _dispatch(b) -> None:
    order = Table(["#", "tier", "owns"], _DISPATCH_ROWS, theme=b.theme)
    b.preview(order, Notice("The focus ring sees a key only after every panel above it declined.", theme=b.theme))


TOPICS = (
    topic(
        key="focus",
        title="Focus",
        summary="FocusManager owns the cycle, the key routing and the click policy.",
        group="Focus & input",
        section="interactions",
        try_line="tab cycles the targets; arrows drive; enter activates; esc to catalog",
        api_line="FocusManager([...]) \u00b7 focus_next/focus_previous \u00b7 handle(event) \u00b7 click(hit)",
        components=("FocusManager", "Button", "Checkbox", "Link"),
        build=_focus,
    ),
    topic(
        key="pointer",
        title="Pointer",
        summary="Hover tracking and stationary clicks, mounted beside the selection gesture.",
        group="Focus & input",
        section="interactions",
        try_line="move the pointer over a row; press and release on one cell to click it",
        api_line="Pointer(tui, ring=focus) \u00b7 handle(event) \u2192 repaint cue \u00b7 hovered/position",
        components=("Pointer", "Button", "Link"),
        build=_pointer,
    ),
    topic(
        key="selection",
        title="Selection",
        summary="Drag selection in document space; release copies through the clipboard.",
        group="Focus & input",
        section="interactions",
        try_line="drag across the rows; release copies them and raises a toast",
        api_line="SelectionGesture(tui, on_end=...) \u00b7 ScreenClipboard(screen)/MemoryClipboard()",
        components=("SelectionGesture", "Text"),
        build=_selection,
    ),
    topic(
        key="find",
        title="Find",
        summary="Incremental search over the focused pane's document with match reveal.",
        group="Search & chrome",
        section="interactions",
        try_line="c-f opens the row; type to match; enter/up step; escape closes",
        api_line="Find(tui, *, theme) \u00b7 open() \u00b7 handle(event) \u00b7 matches/index \u00b7 close()",
        components=("Find", "Markdown"),
        build=_find,
    ),
    topic(
        key="scrollbar",
        title="Scrollbar",
        summary="A pane-chrome strip whose thumb maps the viewport's position.",
        group="Search & chrome",
        section="interactions",
        try_line="up/down scroll the view; page keys move a window; drag the thumb",
        api_line="Scrollbar(tui, *, pane=stage.id, size, glyphs, track, thumb, theme) \u00b7 handle(event)",
        components=("Scrollbar", "ScrollView"),
        build=_scrollbar,
    ),
    topic(
        key="modal-stack",
        title="Modal stack",
        summary="Two modals nest: closing the top one restores the layer below.",
        group="Panels",
        section="interactions",
        try_line="open the first panel, choose Next, then Done; escape cancels each layer",
        api_line="Modal(tui, dialog) \u00b7 FocusManager.push_trap/pop_trap nests per modal",
        components=("Modal", "Dialog", "Button"),
        build=_modal_stack,
    ),
    topic(
        key="dispatch",
        title="Dispatch",
        summary="The host loop's fixed order: panels, chrome, gestures, pointer, focus, host keys.",
        group="Panels",
        section="interactions",
        try_line="press c-g to watch the stats counter, or c-f to see a lower tier take the keys",
        api_line="read_event() \u2192 tiers in order \u2192 focus ring \u2192 host keys \u2192 refresh()",
        components=("Table", "Notice"),
        build=_dispatch,
    ),
)
