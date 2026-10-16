"""The headless replay: the event script the piped run feeds the gallery.

``script()`` returns the whole piped session as a list of
:class:`~mocode_tui.core.events.Key` /
:class:`~mocode_tui.core.events.MouseEvent` /
:class:`~mocode_tui.core.events.Paste` events, and it is deliberately thin:
the bulk of the tour is the ``/page`` palette command -- one command per
page, fourteen of them -- so a page that fails to build fails the run, and the
keys drive the rest (``tab`` cycles a page's ring, ``\u2191\u2193`` and
``enter`` play the focused widget, ``c-n``/``c-p`` step between pages,
``c-o`` moves the pane focus, ``c-f`` searches the streaming page's document,
``c-g`` mounts and unmounts the dev stats overlay,
``/split`` opens and closes the preview pane).  The widgets-basic wave's
keys ride the same road: the palette's query row takes two typed
characters, ``c-z``/``c-y`` and ``c-a`` (its undo history and selection),
the data page's Slider and the choice page's Radio step under the ring,
and the structure page's Collapsible folds on ``enter``.  The
widgets-advanced wave adds the ``diff`` page to the walk and the List's own
two steps on the data page (the ring's ``tab`` reaches it after the
Slider).  The widgets-deepening wave rides the same road: the data page's
sorter is the ring's fourth target (``enter`` on a column runs the page's
``Table.sort_by``), the navigation page's ``c-t`` cycles the tree's filter
through the shell's own key, and the content page's task box is a mouse
click whose pick the page turns into a rewritten task marker (``c-y``
copies the page's first fence on the way past).
Coordinates are the exception, not the rule: the few mouse reports the
replay needs are the top of this module's constants and one helper that
derives a tab label's column from the registry's own arithmetic -- the
selection drag, the pointer's hover and click on the action page's Button,
the content page's task box, and the wheel over the preview pane.

The script ends on the ``action`` page -- the wave's own primitives, each
with a hover -- and quits with ``q`` while that page's ring holds the focus,
so the run covers the rule that the host's own keys are never routed to a
focused widget; ``c-c`` follows as the second quit gesture (unread once the
first one lands).
"""

from __future__ import annotations

from mocode_tui import Key, MouseEvent, Paste

from .registry import PAGES

#: Headless replay geometry.  The live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 110, 70

#: The action page's Button row at the headless geometry: the one page-row
#: anchor the replay uses (the hover, the click, and the row the try line
#: announces).  The page mounts the Button as its own block, right below the
#: section rule that introduces it.
BUTTON_ROW = 11

#: The content page's first task box at the headless geometry: the wave's
#: task-list loop, walked by the mouse.  A stationary click on that cell
#: lands ``"todo:0"`` in ``Markdown.chosen``, the host reads it once and the
#: page's ``note`` rewrites the sample's own text -- the next frame draws
#: the checked box.  Like ``BUTTON_ROW`` this is an anchor pinned to the
#: page's layout; ``test_gallery_protocol`` resolves the cell off the live
#: frame, so a page that moves the box fails a test, not a replay.
TASK_BOX = (0, 31)

#: A drag across the content page's Markdown sample: press, a motion away
#: from the anchor, release -- the gesture's on_end copies through OSC 52 and
#: a toast answers.
DRAG_FROM, DRAG_TO = (6, 11), (44, 14)

#: The preview pane's anchor cell: a wheel report there scrolls the pane
#: under the pointer (``read_key`` maps the report through the frame), and a
#: press focuses it.
PREVIEW_CELL = (HEADLESS_W - 8, 6)

#: The top-right corner: the toast stack's own cells, presses here dismiss
#: the toasts the tour raised so the dump ends on the page itself.
TOAST_CORNER = (HEADLESS_W - 2, 0)

__all__ = ["HEADLESS_H", "HEADLESS_W", "script"]


def tab_column(name: str) -> int:
    """The column the header's label for page ``name`` covers, mid-label.

    The strip's own arithmetic, read off the registry: one leading space,
    the labels joined by ``" | "``.  Deriving the column beats hard-coding
    one, and it is the same walk :meth:`~mocode_tui.widgets.tabs.Tabs.click`
    runs against its last render.
    """
    x = 1
    for page in PAGES:
        if page.name == name:
            return x + len(page.nav) // 2
        x += len(page.nav) + 3  # " | " between neighbours
    return 1


def script() -> list:
    """Every page through the palette, a handful of plays, then quit."""
    events: list = []

    def type_text(text: str) -> None:
        events.extend(Key(ch, ch) for ch in text)

    def command(name: str) -> None:
        """One palette command: ``/`` opens the modal panel, the name filters it,
        enter takes the top row."""
        events.append(Key("/", "/"))
        type_text(name)
        events.append(Key("enter"))

    def mouse(name: str, x: int, y: int, kind: str = "press", button: int = 0) -> None:
        events.append(MouseEvent(name, button=button, x=x, y=y, kind=kind))

    def click(x: int, y: int) -> None:
        mouse("left", x, y)
        mouse("left", x, y, "release")

    def wheel(y: int, x: int = PREVIEW_CELL[0]) -> None:
        mouse("wheel_down", x, y)

    # Every page, through the palette: the command table is what the tour
    # walks, so each page is built and mounted by the same road a user takes.
    for name in ("overview", "content", "data", "diff", "structure", "input", "choice",
                 "navigation", "action", "feedback", "styles", "streaming", "features",
                 "devtools"):
        command(name)

    # The palette's query row is a real Input, so the wave's editing work
    # rides here too: two typed characters merge into one undo step, c-z/c-y
    # walk the history, c-a selects the whole query and typing replaces the
    # selection -- then enter runs the command the query names (this lands on
    # the data page, the next stanza's own page).
    events.append(Key("/", "/"))
    type_text("da")
    events.extend((Key("c-z"), Key("c-y"), Key("c-a")))
    type_text("data")
    events.append(Key("enter"))

    # On the data page the table's ring owns the arrows: down walks the rows,
    # enter lands the pick (the toast and the echo line report it).  tab then
    # steps onto the Slider -- right walks its value and enter confirms it --
    # and onto the List, where the arrows walk the windowed cursor and enter
    # lands the item under it.  The sorter is the ring's fourth target: tab
    # once more, walk to the state column and enter -- the page's note calls
    # Table.sort_by, so the table above re-orders (the cursor's record moves
    # with it) and the echo reads the pick.
    command("/data")
    events.extend((Key("down"), Key("down"), Key("enter")))
    events.extend((Key("tab"), Key("right"), Key("enter")))
    events.extend((Key("tab"), Key("down"), Key("down"), Key("enter")))
    events.extend((Key("tab"), Key("down"), Key("down"), Key("enter")))

    # The choice page: tab steps off the menu onto the Radio, where a down
    # arrow already lands the new selection as the pick; tab again steps onto
    # the first Confirm and enter takes its Yes/No option.
    command("/choice")
    events.extend((Key("tab"), Key("down"), Key("enter"), Key("tab"), Key("enter")))

    # The structure page: its one ring target is the Collapsible, focused on
    # arrival -- enter folds the section away (the new state is the pick).
    command("/structure")
    events.append(Key("enter"))

    # The navigation page: tab moves onto the tree, down walks it, enter folds
    # the node under the cursor -- an activation with no pick at all.  The
    # shell's own c-t then cycles the tree's filter (the wave's second
    # exhibit): each press prunes to the next canned query of TREE_FILTERS,
    # the page's echo line names it, and the prune shows on the page.
    command("/navigation")
    events.extend((Key("tab"), Key("down"), Key("enter")))
    events.extend((Key("c-t"), Key("c-t")))

    # The feedback page: enter on the level selector raises the row's own
    # sentence as a real toast.
    command("/feedback")
    events.append(Key("enter"))

    # The styles page: down moves the picker onto amber, enter re-skins the
    # shell (header, status row, palette and the page all rebuild).
    command("/styles")
    events.extend((Key("down"), Key("enter")))

    # The content page and a drag: press, a motion away from the anchor, then
    # release -- the gesture's on_end copies the range and a toast answers.
    command("/content")
    mouse("left", *DRAG_FROM)
    mouse("left", *DRAG_TO, kind="motion", button=1)
    mouse("left", *DRAG_TO, kind="release")
    # The task box: a stationary click on the sample's first box lands
    # "todo:0" in chosen; the page's note flips the marker in its own text
    # and the next frame draws the checked box.  c-y is the shell's copy key
    # for the page's first fence (Markdown.fences() -> screen.copy; headless
    # records the OSC 52 bytes) and the toast names what landed.
    click(*TASK_BOX)
    events.append(Key("c-y"))
    # A multi-line paste arrives as one Paste event: no editor is mounted, and
    # the gallery routes no printable to a page widget, so nothing consumes it
    # and nothing submits.
    events.append(Paste("a paste with\nthree lines"))

    # A second pane: /split opens the live preview, the wheel over it scrolls
    # the pane under the pointer, c-o moves the pane focus and c-o again
    # brings it back, then /split closes the pane.
    command("/split")
    wheel(PREVIEW_CELL[1])
    events.extend((Key("c-o"), Key("c-o")))
    wheel(PREVIEW_CELL[1] + 2)
    command("/split")

    # The streaming page: its control bar owns the ring, so the arrows walk it
    # and enter takes the row under the cursor.  This path is dump-safe -- the
    # stream is complete before the page is built -- so the picks are answered
    # without moving the document, and the run still covers the whole road
    # (activate -> chosen -> the page's note hook -> the stream).
    command("/streaming")
    events.extend((Key("enter"), Key("down"), Key("enter"), Key("down"), Key("enter")))

    # The search tier over the 346-line document: c-f opens the query row,
    # the typed word is searched case-insensitively, enter walks to the next
    # match -- walking far enough reaches one the window has to move for, so
    # the reveal road runs here too -- and escape closes.  The page switch
    # below opens the next page at its top, so the view the search moved
    # leaves no trace in the dump.
    events.append(Key("c-f"))
    type_text("markdown")
    for _ in range(5):
        events.append(Key("enter"))
    events.append(Key("escape"))

    # The devtools page, and the stats overlay's own road: c-g mounts the box
    # in the frame's corner (it counts this very replay's events and paints a
    # frame of its own), and a second c-g unmounts it -- no probe box rides
    # the pages after this one.
    command("/devtools")
    events.append(Key("c-g"))
    events.append(Key("c-g"))

    # The features page opens a pane of its own through the page's enter hook;
    # c-o steps the focus into it and back, and a click on the right column is
    # the mouse's road to the same focus move.
    command("/features")
    events.append(Key("c-o"))
    click(*PREVIEW_CELL)
    events.append(Key("c-o"))

    # c-p / c-n step between pages (the ends wrap).
    events.append(Key("c-p"))
    events.append(Key("c-n"))

    # The finale: the action page -- the new primitives, each with a hover.
    command("/action")
    # The header's own strip first: a motion marks the "action" label, a click
    # on it opens the page the ordinary way (if the hover left nothing).
    mouse("motion", tab_column("action"), 1, kind="motion")
    # The pointer over the Button: the hover band follows the leaf, then a
    # press and release on the same cell is a stationary click, which the
    # ring's policy dispatches and -- the Button holds the focus -- activates.
    mouse("motion", 3, BUTTON_ROW, kind="motion")
    click(3, BUTTON_ROW)
    # tab moves the focus to the Checkbox; enter flips it and lands the new
    # state in chosen.
    events.extend((Key("tab"), Key("enter")))

    # Dismiss the toasts the tour raised -- three presses on the stack's own
    # corner cells -- so the dump ends on the page itself.
    for _ in range(3):
        click(*TOAST_CORNER)

    # Quit with the ring still holding the focus: `q` is the host's key and
    # never reaches the focused widget; c-c is the second gesture, unread.
    events.append(Key("q"))
    events.append(Key("c-c"))
    return events
