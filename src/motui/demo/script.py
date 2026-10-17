"""The headless replay: the event script the piped run feeds the demo.

``script()`` returns the whole piped session as a list of
:class:`~motui.kernel.events.Key` /
:class:`~motui.kernel.events.MouseEvent` /
:class:`~motui.kernel.events.Paste` events.  It is deliberately thin: the
bulk of the tour is the rail's own click road plus ``c-n`` stepping around
the page cycle (:func:`script`'s own ``goto``), so every page is built and
mounted by the road a user takes and a page that fails to build fails the
run.  The keys drive the rest (``tab``/arrows/``enter`` on the focused
widget, ``c-t`` filters the tree, ``c-f`` searches,
``c-g`` toggles the stats box, ``c-o`` walks onto the page's own pane,
``space`` marks the focused view's cursor row).
Coordinates are the exception: the few mouse reports are this module's
constants, and ``tests/test_demo_protocol.py`` resolves every one of them
off a live frame, so a page that moves an anchor fails a test, not the
replay.  The script ends on the ``action`` page and quits with ``q`` while
that page's ring holds the focus -- the host's keys never reach a focused
widget -- with ``c-c`` as the unread second gesture.
"""

from __future__ import annotations

from motui import Key, MouseEvent, Paste

from .registry import PAGES

#: Headless replay geometry: the live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 110, 70

#: The content pane's first column at the headless geometry (the rail takes ``ratios=(1, 4)`` of 110 columns); every page anchor includes this offset.
CONTENT_X = 22

#: The action page's Button row: the hover, the click and the tooltip band.
BUTTON_ROW = 8

#: The text page's first task box: a click there lands ``"todo:0"``.
TASK_BOX = (CONTENT_X, 28)

#: A drag across the text page's Markdown sample (press, motion, release).
DRAG_FROM, DRAG_TO = (26, 15), (70, 18)

#: The chrome page's own pane: the wheel report's cell, and the press focus.
ASIDE_CELL = (105, 6)

#: The modal page's "open the palette" row (focused, then activated).
PALETTE_CELL = (CONTENT_X + 2, 19)

#: The chrome page's first probe row: the hover its hit-test row resolves.
PROBE_CELL = (CONTENT_X + 1, 48)

#: The input page's windowed Editor: a click docks the cursor on "row 05".
EDITOR_CELL = (CONTENT_X, 31)

#: The input page's ComboBox exhibit: its "open the composer" row (focused, then
#: activated), whose pick raises the dropdown over its Modal.
COMBO_CELL = (CONTENT_X + 2, 17)

#: The toast stack's corner cells: presses here dismiss the raised toasts.
TOAST_CORNER = (HEADLESS_W - 2, 0)

__all__ = ["HEADLESS_H", "HEADLESS_W", "script", "rail_cell"]


def rail_cell(name: str) -> tuple[int, int]:
    """The cell of the rail's label for page ``name``: one row per label, the
    first under the header band, the column the label's middle."""
    for index, page in enumerate(PAGES):
        if page.name == name:
            return len(page.name) // 2, 1 + index
    raise KeyError(name)


def script() -> list:
    """The rail click, every page, a handful of plays, then quit."""
    events: list = []
    position = PAGES.index(next(page for page in PAGES if page.name == "data"))

    def type_text(text: str) -> None:
        events.extend(Key(ch, ch) for ch in text)

    def mouse(name: str, x: int, y: int, kind: str = "press", button: int = 0) -> None:
        events.append(MouseEvent(name, button=button, x=x, y=y, kind=kind))

    def click(x: int, y: int) -> None:
        mouse("left", x, y)
        mouse("left", x, y, "release")

    def wheel(y: int) -> None:
        mouse("wheel_down", ASIDE_CELL[0], y)

    def goto(name: str) -> None:
        """Walk forward with c-n to ``name`` -- the way a reader reaches it."""
        nonlocal position
        target = PAGES.index(next(page for page in PAGES if page.name == name))
        while position != target:
            events.append(Key("c-n"))
            position = (position + 1) % len(PAGES)

    # The rail's own road: a motion marks the label, a stationary click selects it -- the host follows Tabs.active and opens the page.  Then the walk presses c-n around the cycle, building every page once.
    mouse("motion", *rail_cell("data"), kind="motion")
    click(*rail_cell("data"))
    goto("text")  # ten steps: data -> ... -> overview -> text

    # The data page: the table's arrows and pick plus a mark (space flips the focused view's cursor-row mark), then tab on -- list (down, enter), sorter (down to "state", enter runs Table.sort_by), tree (down, enter folds); c-t cycles the tree filter.
    goto("data")
    events.extend((Key("down"), Key("down"), Key("enter"), Key("space", " ")))
    events.extend((Key("tab"), Key("right"), Key("enter")))
    events.extend((Key("tab"), Key("down"), Key("down"), Key("enter")))
    events.extend((Key("tab"), Key("down"), Key("down"), Key("enter")))
    events.extend((Key("tab"), Key("down"), Key("enter")))
    events.extend((Key("c-t"), Key("c-t")))

    # The choice body -- the merged forms page's menu family: tab on past the fields to the menu (a step, then the row), the Radio (a step lands the pick), the CheckGroup (enter flips the cursor row's mark) and the commit select (the cursor is the choice, one step writes it).
    goto("choice")
    events.extend((Key("tab"),) * 4)  # editor -> windowed -> autocomplete -> composer -> the menu
    events.extend((Key("down"), Key("enter")))
    events.extend((Key("tab"), Key("down"), Key("enter")))
    events.extend((Key("tab"), Key("enter")))
    events.extend((Key("tab"), Key("down")))

    # The layout page: enter folds the Collapsible away (the state is the pick).
    goto("layout")
    events.append(Key("enter"))

    # The modal page: the Palette exhibit, moved in from the chrome page -- two clicks focus then activate its row, a typed query narrows it, enter takes the row for the echo.
    goto("modal")
    click(*PALETTE_CELL)
    click(*PALETTE_CELL)
    type_text("say")
    events.append(Key("enter"))

    # The styles page: down to amber, enter re-skins the shell; up, enter puts the default skin back for the rest of the tour.
    goto("styles")
    events.extend((Key("down"), Key("enter"), Key("up"), Key("enter")))

    # The streaming page: the control bar pauses, steps, plays the step; then c-f searches the 346-line document (enter walks the matches, escape closes).
    goto("streaming")
    events.extend((Key("enter"), Key("down"), Key("enter")))
    events.append(Key("c-f"))
    type_text("markdown")
    for _ in range(5):
        events.append(Key("enter"))
    events.append(Key("escape"))

    # The overview's index: down walks onto "text", enter lands the pick and the host opens the page it names.
    goto("overview")
    events.extend((Key("down"), Key("enter")))
    position = PAGES.index(next(page for page in PAGES if page.name == "text"))

    # The text page: a drag copies the range; the task box runs the pick loop.
    mouse("left", *DRAG_FROM)
    mouse("left", *DRAG_TO, kind="motion", button=1)
    mouse("left", *DRAG_TO, kind="release")
    click(*TASK_BOX)
    # A multi-line paste: no editor is mounted, so nothing consumes it.
    events.append(Paste("a paste with\nthree lines"))

    # The chrome page: enter raises the toast selector's row (the sentence is the pick); then c-o onto the page's own pane, the wheel over it and two c-o back out; a hover for the hit-test row; c-g mounts and unmounts the stats box.
    goto("chrome")
    events.append(Key("enter"))
    events.extend((Key("c-o"), Key("c-o"), Key("c-o")))
    wheel(ASIDE_CELL[1])
    wheel(ASIDE_CELL[1] + 2)
    mouse("motion", *PROBE_CELL, kind="motion")
    events.extend((Key("c-g"), Key("c-g")))

    # The input page: a click docks the Editor's cursor, tab + enter take the Autocomplete's match; then the ComboBox exhibit -- the row opens the dropdown over its Modal, typing narrows it, enter takes the label into the field.
    goto("input")
    click(*EDITOR_CELL)
    events.extend((Key("tab"), Key("enter")))
    click(*COMBO_CELL)
    click(*COMBO_CELL)
    type_text("log")
    events.append(Key("enter"))

    # The action page -- the finale: the pointer over the Button, a click activates it, then tab + enter flip the Checkbox and tab + enter confirm the Slider's value.
    goto("action")
    mouse("motion", CONTENT_X + 2, BUTTON_ROW, kind="motion")
    click(CONTENT_X + 2, BUTTON_ROW)
    events.extend((Key("tab"), Key("enter"), Key("tab"), Key("enter")))

    # Dismiss the toasts (three presses on the stack's corner), then quit with the ring still holding the focus; c-c is the unread second gesture.
    for _ in range(3):
        click(*TOAST_CORNER)
    events.append(Key("q"))
    events.append(Key("c-c"))
    return events
