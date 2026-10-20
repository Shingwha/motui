"""The headless replay: the event script the piped run feeds the demo.

``script()`` returns the whole piped session as a list of
:class:`~motui.kernel.events.KeyEvent` /
:class:`~motui.kernel.events.MouseEvent` /
:class:`~motui.kernel.events.PasteEvent` events.  It is deliberately thin: the
bulk of the tour is the rail's own click road plus ``c-n`` stepping around
the page cycle (:func:`script`'s own ``goto``), so every page is built and
mounted by the road a user takes and a page that fails to build fails the
run.  The keys drive the rest (``tab``/arrows/``enter`` on the focused
widget, ``c-t`` filters the tree, ``c-f`` searches, ``c-g`` toggles the
stats box, ``c-o`` walks onto the page's own pane, ``space`` marks the
focused view's cursor row).

**The mouse reports are symbolic.**  No cell is hand-computed: an anchor is
the page, the name of one of its exhibits (:data:`SLOTS`) and a cell inside
that exhibit's own rows, and :class:`Anchors` resolves it against a live
layout at the replay's own geometry -- the frame's ownership table, the very
addresses :meth:`~motui.app.TUI.hit` resolves a report through.  A page
that moves an exhibit moves its anchors with it, and an anchor that no
longer resolves raises :class:`AnchorError` naming it instead of clicking a
neighbour; ``tests/test_demo_protocol.py`` resolves the same helper, so the
replay and the test cannot drift apart.

The script ends on the ``actions`` page and quits with ``q`` while that
page's ring holds the focus -- the host's keys never reach a focused widget
-- with ``c-c`` as the unread second gesture.
"""

from __future__ import annotations

from typing import Callable, Sequence

from motui import Button, KeyEvent, Markdown, MouseEvent, PasteEvent, Select, Table, TUI
from motui.kernel import HeadlessScreen
from motui.kernel.block import Component
from motui.widgets import Editor

from .registry import BY_NAME, GROUPS, PAGES
from .session import Session

#: Headless replay geometry: the live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 110, 70

__all__ = [
    "HEADLESS_H",
    "HEADLESS_W",
    "AnchorError",
    "Anchors",
    "SLOTS",
    "rail_cell",
    "script",
]


def rail_cell(name: str) -> tuple[int, int]:
    """The cell of the rail's label for page ``name``: one rendered row per
    item *and group row*, the first under the header band, the column the
    label's middle -- behind the two-cell seat (``bar`` + ``bar_space``)
    every ``NavList`` row opens with."""
    for index, page in enumerate(PAGES):
        if page.name == name:
            # A group at position p renders above item p, so it shifts every
            # later item one row down -- the row math `NavList` itself does.
            groups_above = sum(1 for position, _ in GROUPS if position <= index)
            return 2 + len(page.name) // 2, 1 + index + groups_above
    raise KeyError(name)


def _of(kind: type, predicate: Callable[[Component], bool], what: str):
    """A slot selector: the page's exhibit of ``kind`` the predicate answers."""
    def select(blocks: Sequence[Component]) -> Component:
        for block in blocks:
            if isinstance(block, kind) and predicate(block):
                return block
        raise LookupError(f"no {kind.__name__} exhibit ({what})")
    return select


#: The exhibits the replay's anchors name, by page: each selector answers the
#: exhibit (the component the page mounts) the anchor sits in.  The names are
#: the replay's own vocabulary -- a page's exhibit by its meaning, not by a
#: cell it happens to occupy.
SLOTS: dict[str, dict[str, Callable[[Sequence[Component]], Component]]] = {
    "overview": {
        # The index table: one row per page, the "text" row's own road.
        "index": _of(Table, lambda b: True, "the index table"),
    },
    "text": {
        # The Markdown sample: every construct, the task boxes' own rows.
        "sample": _of(Markdown, lambda b: "example.invalid" in b.text, "the fixture sample"),
    },
    "modals": {
        # The Palette exhibit's "open the palette" row.
        "palette": _of(Select, lambda b: b.options and b.options[0].value == "open the palette",
                       "the palette row"),
    },
    "shell": {
        # The hit-test probe's first leaf.
        "probe": _of(Button, lambda b: b.label == "probe one -- a Button", "the probe row"),
    },
    "forms": {
        # The max_rows window over the twelve-row buffer.
        "windowed": _of(Editor, lambda b: b.max_rows == 5, "the windowed editor"),
        # The ComboBox exhibit's "open the composer" row.
        "composer": _of(Select, lambda b: b.options and b.options[0].value == "open the composer",
                        "the composer row"),
    },
    "actions": {
        # The page's first exhibit: the "Ship" Button.
        "button": _of(Button, lambda b: True, "the first Button"),
    },
}


class AnchorError(LookupError):
    """An anchor that no longer resolves: the replay's own, named failure.

    :class:`Anchors` raises it with the anchor's page, slot and cell, so a
    stale script -- a page that dropped an exhibit, a row the window no
    longer paints -- fails the run naming what it lost, never with a
    silently different cell.
    """


class Anchors:
    """The replay's symbolic anchors, resolved against one live layout.

    The helper builds its own headless ``Session`` at the replay's geometry
    and shows a page on demand; :meth:`cell` then answers the screen cell of
    an exhibit by walking the frame's ownership table (the pane, the block
    and the row inside it) and round-trips the answer through
    :meth:`~motui.app.TUI.hit`, so a resolved cell is one the run's own
    click road resolves back to the same exhibit and the same cell.
    """

    def __init__(self, width: int = HEADLESS_W, height: int = HEADLESS_H) -> None:
        self.tui = TUI(screen=HeadlessScreen(width, height), interactive=False)
        self.session = Session(self.tui)
        self._page: str | None = None

    def showing(self, page: str, anchor: str) -> Session:
        """Show ``page`` on the probe layout (once) and answer its session."""
        if page not in BY_NAME:
            raise AnchorError(f"{anchor}: no page named {page!r}")
        if self._page != page:
            self.session.show(BY_NAME[page])
            self.tui.paint()  # the frame's table is what resolves a cell
            self._page = page
        return self.session

    def cell(self, page: str, slot: str, row: int = 0, col: int | None = None) -> tuple[int, int]:
        """The screen cell of ``page``'s exhibit ``slot``, its own ``row``/``col``.

        ``col=None`` is the exhibit's first column.  The row must be one the
        pane paints and the cell must resolve back to the exhibit itself,
        at that same row and column; anything else raises
        :class:`AnchorError` naming the anchor.
        """
        col = 0 if col is None else col
        anchor = f"{page}/{slot}[{row},{col}]"
        select = SLOTS.get(page, {}).get(slot)
        if select is None:
            raise AnchorError(f"{anchor}: no such exhibit on this page")
        session = self.showing(page, anchor)
        try:
            component = select(session.body.blocks)
        except LookupError as lost:
            raise AnchorError(f"{anchor}: {lost}") from None
        block = next(
            (b for b in session.main.document.blocks() if b.component is component), None
        )
        if block is None:
            raise AnchorError(f"{anchor}: the exhibit is not a mounted block")
        if not 0 <= row < len(block.rows(self.tui.frame.region(session.main.id).width)):
            raise AnchorError(f"{anchor}: the exhibit does not paint that row")
        y = self._row_of(session, block.id, row, anchor)
        x = self.tui.frame.region(session.main.id).x + col
        hit = self.tui.hit(x, y)
        if hit is None or hit.block.component is not component or (hit.row, hit.col) != (row, col):
            raise AnchorError(f"{anchor}: the cell does not resolve back to the exhibit")
        return (x, y)

    def aside(self, page: str, row: int = 0, col: int | None = None) -> tuple[int, int]:
        """A cell on the right pane ``page``'s own ``enter`` hook opens.

        ``col=None`` is the pane's middle, over its own rows -- all a wheel
        report needs, since the wheel scrolls the pane under the pointer.
        """
        anchor = f"{page}/aside[{row}]"
        session = self.showing(page, anchor)
        pane = session.aside
        rect = None if pane is None else self.tui.frame.region(pane.id)
        if rect is None or not 0 <= row < rect.height:
            raise AnchorError(f"{anchor}: the page opens no right pane at that row")
        x = rect.x + (rect.width // 2 if col is None else col)
        y = rect.y + row
        hit = self.tui.hit(x, y)
        if hit is None or hit.pane_id != pane.id:
            raise AnchorError(f"{anchor}: the cell is not inside the page's own pane")
        return (x, y)

    def corner(self) -> tuple[int, int]:
        """The toast stack's own corner cell: the frame's top-right, two cells in."""
        rect = self.tui.frame.rect
        if rect is None or rect.width < 4:
            raise AnchorError("corner: the frame has no room for the toast stack")
        return (rect.right - 2, rect.y)

    def _row_of(self, session: Session, block_id: str, row: int, anchor: str) -> int:
        """The screen row the page's pane paints ``row`` of block ``block_id`` at."""
        table = self.tui.frame.table
        for y, spans in enumerate(() if table is None else table.rows):
            for span in spans:
                if (
                    span.pane_id == session.main.id
                    and span.block_id == block_id
                    and span.row_in_block == row
                ):
                    return y
        raise AnchorError(f"{anchor}: the pane does not paint that row")


def script() -> list:
    """The rail click, every page, a handful of plays, then quit."""
    events: list = []
    layout = Anchors()  # the anchors resolve against a live layout (see module)
    position = PAGES.index(next(page for page in PAGES if page.name == "views"))

    def type_text(text: str) -> None:
        events.extend(KeyEvent(ch, ch) for ch in text)

    def mouse(button: str, x: int, y: int, kind: str = "press") -> None:
        events.append(MouseEvent(button, x=x, y=y, kind=kind))

    def click(cell: tuple[int, int]) -> None:
        mouse("left", *cell)
        mouse("left", *cell, "release")

    def goto(name: str) -> None:
        """Walk forward with c-n to ``name`` -- the way a reader reaches it."""
        nonlocal position
        target = PAGES.index(next(page for page in PAGES if page.name == name))
        while position != target:
            events.append(KeyEvent("c-n"))
            position = (position + 1) % len(PAGES)

    # The rail's own road: a motion marks the label, a stationary click selects it -- the host follows NavList.index and opens the page.  Then the walk presses c-n around the cycle, building every page once.
    mouse("none", *rail_cell("views"), kind="motion")
    click(rail_cell("views"))
    goto("text")  # nine steps: views -> ... -> overview -> text

    # The views page: the table's arrows and pick plus a mark (space flips the focused view's cursor-row mark), then tab on -- list (down, enter), sorter (down to "state", enter runs Table.sort_by), tree (down, enter folds); c-t cycles the tree filter.
    goto("views")
    events.extend((KeyEvent("down"), KeyEvent("down"), KeyEvent("enter"), KeyEvent("space", " ")))
    events.extend((KeyEvent("tab"), KeyEvent("right"), KeyEvent("enter")))
    events.extend((KeyEvent("tab"), KeyEvent("down"), KeyEvent("down"), KeyEvent("enter")))
    events.extend((KeyEvent("tab"), KeyEvent("down"), KeyEvent("down"), KeyEvent("enter")))
    events.extend((KeyEvent("tab"), KeyEvent("down"), KeyEvent("enter")))
    events.extend((KeyEvent("c-t"), KeyEvent("c-t")))

    # The forms page's menu family: tab on past the fields to the menu (a step, then the row), the RadioGroup (a step lands the pick), the CheckboxGroup (enter flips the cursor row's mark) and the commit select (the cursor is the choice, one step writes it).
    goto("forms")
    events.extend((KeyEvent("tab"),) * 4)  # editor -> windowed -> autocomplete -> composer -> the menu
    events.extend((KeyEvent("down"), KeyEvent("enter")))
    events.extend((KeyEvent("tab"), KeyEvent("down"), KeyEvent("enter")))
    events.extend((KeyEvent("tab"), KeyEvent("enter")))
    events.extend((KeyEvent("tab"), KeyEvent("down")))

    # The layout page: enter folds the Collapsible away (the state is the pick).
    goto("layout")
    events.append(KeyEvent("enter"))

    # The modals page: the Palette exhibit -- two clicks focus then activate its row, a typed query narrows it, enter takes the row for the echo.
    goto("modals")
    palette = layout.cell("modals", "palette", row=1, col=2)
    click(palette)
    click(palette)
    type_text("say")
    events.append(KeyEvent("enter"))

    # The themes page: down to amber, enter re-skins the shell; up, enter puts the default skin back for the rest of the tour.
    goto("themes")
    events.extend((KeyEvent("down"), KeyEvent("enter"), KeyEvent("up"), KeyEvent("enter")))

    # The streaming page: the control bar pauses, steps, plays the step; then c-f searches the 346-line document (enter walks the matches, escape closes).
    goto("streaming")
    events.extend((KeyEvent("enter"), KeyEvent("down"), KeyEvent("enter")))
    events.append(KeyEvent("c-f"))
    type_text("markdown")
    for _ in range(5):
        events.append(KeyEvent("enter"))
    events.append(KeyEvent("escape"))

    # The overview's index: a click lands the cursor on the "text" row, enter lands the pick and the host opens the page it names.
    goto("overview")
    click(layout.cell("overview", "index", row=5, col=2))  # the "text" data row
    events.append(KeyEvent("enter"))
    position = PAGES.index(next(page for page in PAGES if page.name == "text"))

    # The text page: a drag copies the range (both ends are rows of the sample); the task box runs the pick loop and flips its own source.
    mouse("left", *layout.cell("text", "sample", row=7, col=4))
    mouse("left", *layout.cell("text", "sample", row=10, col=48), kind="motion")
    mouse("left", *layout.cell("text", "sample", row=10, col=48), kind="release")
    click(layout.cell("text", "sample", row=20, col=0))  # the first task box
    # A multi-line paste: no editor is mounted, so nothing consumes it.
    events.append(PasteEvent("a paste with\nthree lines"))

    # The shell page: enter raises the toast selector's row (the sentence is the pick); then c-o onto the page's own pane, the wheel over it and two c-o back out; a hover for the hit-test row; c-g mounts and unmounts the stats box.
    goto("shell")
    events.append(KeyEvent("enter"))
    events.extend((KeyEvent("c-o"), KeyEvent("c-o"), KeyEvent("c-o")))
    wheel = layout.aside("shell", row=6)  # the pane's first own row
    mouse("wheel_down", wheel[0], wheel[1], kind="wheel")
    mouse("wheel_down", wheel[0], wheel[1] + 2, kind="wheel")
    mouse("none", *layout.cell("shell", "probe", row=0, col=1), kind="motion")
    events.extend((KeyEvent("c-g"), KeyEvent("c-g")))

    # The forms page: a click docks the Editor's cursor on "row 05", tab + enter take the Autocomplete's match; then the ComboBox exhibit -- the row opens the dropdown over its Modal, typing narrows it, enter takes the label into the field.
    goto("forms")
    click(layout.cell("forms", "windowed", row=4, col=0))  # the row "05" of the window
    events.extend((KeyEvent("tab"), KeyEvent("enter")))
    composer = layout.cell("forms", "composer", row=1, col=2)
    click(composer)
    click(composer)
    type_text("log")
    events.append(KeyEvent("enter"))

    # The actions page -- the finale: the pointer over the Button, a click activates it, then tab + enter flip the Checkbox and tab + enter confirm the Slider's value.
    goto("actions")
    ship = layout.cell("actions", "button", row=0, col=2)
    mouse("none", *ship, kind="motion")
    click(ship)
    events.extend((KeyEvent("tab"), KeyEvent("enter"), KeyEvent("tab"), KeyEvent("enter")))

    # Dismiss the toasts (three presses on the stack's corner), then quit with the ring still holding the focus; c-c is the unread second gesture.
    for _ in range(3):
        click(layout.corner())
    events.append(KeyEvent("q"))
    events.append(KeyEvent("c-c"))
    return events
