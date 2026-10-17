"""The features page: what the toolkit does beyond drawing rows.

The page's subject is the **shell**, so it is a layout rather than a list of
rows: its ``enter`` hook opens a right pane of its own -- the very pane a
host builds by hand, here mounted through :meth:`~motui.demo.session.Gallery.open_aside`,
which runs the one ``tui.split("vertical", ratios=(2, 1))`` -- fills it with
the pane's half of the story, and its ``leave`` hook closes the pane again on
the way out.  The pane's content is plain text and enough rows to scroll:
the wheel scrolls the pane under the pointer, a drag across the rows selects
them (release copies through OSC 52), and ``c-o`` or a click moves the pane
focus between the two columns.

**Search** is the shell's own tier (``Find``, ``c-f``): a query row over the
page's document, the host routing it ahead of the gestures while it is open,
and the current match revealed -- centered -- through ``tui.reveal``.

**Hover** is the one capability with a page of its own -- ``/action`` -- and
this page says what the other page shows: the pointer tier flips the ``hover``
flag of the leaf under the pointer, which is why the gallery opens the
screen with ``TUI(hover=True)``, and a leaf's own ``hint`` rises beside the
pointer as a one-line tooltip band.  A *drag* moves none of that any more:
the pointer tells the two apart by the motion's name -- a button-named motion
is the gesture's drag -- so pulling a selection across a page leaves the
hover (and the hint) where they were.  **IME**: the terminal cursor anchor went
with the retired composer; a host that wants a caret parks the terminal
cursor on a field's own ``cursor`` readout -- the gallery keeps no input box
to anchor.
"""

from __future__ import annotations

from motui import Text
from motui.kernel import DIM
from motui.widgets import Column, Divider

from ..page import PageBody, api_note, header, section, try_line

#: The capability list: ``(name, the action that shows it)``.  Every row is
#: something a reader can do on this very screen.
CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("panes",
     "press c-o, or click the right pane: the focus moves between the two columns"),
    ("scrollback",
     "roll the wheel over either pane: each scrolls on its own, the scrollbar follows "
     "the pointer"),
    ("search",
     "press c-f, type a word: every match on the page is marked, enter/arrows walk "
     "them and the window follows to the current one, Esc closes"),
    ("selection",
     "drag across any rows and release: the range is copied through OSC 52 and a toast answers"),
    ("hover",
     "pass the pointer over a row on /action: the leaf takes the hover band and its own "
     "hint rises beside the pointer -- and a drag no longer drags the hover along "
     "(TUI(hover=True) opened DECSET 1003)"),
    ("IME",
     "a host parks the terminal cursor on a field's own cursor readout -- the gallery keeps "
     "no input box to anchor"),
)

#: The three commands that need no terminal -- and what each one is for.
NO_TERMINAL: tuple[tuple[str, str], ...] = (
    ("uv run python examples/demo.py < /dev/null",
     "replays the session headless, dumps the screen"),
    ("uv run python examples/demo.py --pages",
     "prints every page as plain text"),
    ("uv run pytest -q \u00b7 uv run python tools/framebench.py",
     "the gates: the suite, and the render hash"),
)

#: The right pane's own copy: the pane half, then filler rows for the wheel.
PANE_TEXT: tuple[str, ...] = (
    "This pane is the page's own.",
    "session.show called the page's enter hook, and the hook opened this pane with "
    "tui.split(\"vertical\", ratios=(2, 1)) -- the left child kept the gallery's document.",
    "c-o cycles the focus; a press focuses the pane it lands in.",
    "The wheel scrolls the pane under the pointer, not the focused one.",
    "The scrollbar on the left tracks this page's document; this pane keeps its own.",
)


def page(gallery) -> PageBody:
    """The capability lines, the pane the page opens, and the no-terminal three."""
    theme = gallery.theme

    def enter(g) -> None:
        """The page's own resource: a right pane, filled and parked at its top."""
        pane = g.open_aside()
        pane.document.add(Column([
            Text("a pane of this page's own", style=theme.accent),
            Divider(theme=theme),
            *(Text(line, style=DIM) for line in PANE_TEXT),
            Divider(theme=theme),
            *(Text(f"pane row {i:02d} -- roll the wheel over me", style=DIM)
              for i in range(1, 25)),
        ]))
        pane.viewport.scroll_up(1 << 20)  # a fresh pane opens at its first row

    def leave(g) -> None:
        """Give the pane's cells back: the un-split the next page expects."""
        g.close_aside()

    return PageBody([
        *header("features",
                "What the toolkit does beyond drawing rows -- every row below is an action "
                "you can take right here.", theme),
        try_line("press c-o (or click the right pane) and roll the wheel over either column; "
                 "drag across any rows and release to copy them", theme),
        section("capabilities -- press it and watch", theme),
        *(Text(f"{name:<10} {how}", style=DIM) for name, how in CAPABILITIES),
        api_note('tui.split("vertical", ratios=(2, 1)) -- the left pane keeps the document',
                 theme),
        api_note("SelectionGesture(tui, on_end=...) -- release hands the range to the host",
                 theme),
        api_note("Pointer(tui, ring=...) + TUI(hover=True) -- hover and stationary clicks",
                 theme),
        api_note("Tooltip(tui, pointer) -- the hovered leaf's own hint, beside the pointer",
                 theme),
        api_note("Find(tui) -- c-f: matches + the reveal, the row owns the keyboard while open",
                 theme),
        section("the page's own pane -- enter and leave mount it", theme),
        api_note("PageBody.enter(gallery) / PageBody.leave(gallery) -- the page's resources",
                 theme),
        Text("The right pane is this page's, not the shell's: the gallery opens it when the "
             "page arrives and closes it when the page is left, so /split toasts here instead "
             "of stacking a third pane.",
             style=theme.dim),
        section("no terminal needed -- three commands", theme),
        *(Text(f"{command:<46} {what}", style=DIM) for command, what in NO_TERMINAL),
        Text("The piped run and the dump are the gallery's own smoke test: the replay drives "
             "every page through the same host loop a terminal does, so a page that fails to "
             "build fails the run.",
             style=theme.dim),
    ], enter=enter, leave=leave)
