"""The headless replay: the event script the piped run feeds the session.

``script()`` returns the whole piped session as a list of
:class:`~mocode_tui.core.events.Key` / :class:`~mocode_tui.core.events.MouseEvent`
/ :class:`~mocode_tui.core.events.Paste` events: every page is visited, a
couple are played with by key and by click, the focus ring's tab is cycled,
a pane opens and closes, a range is dragged to the clipboard, a multi-line
paste is replayed, a question is asked, the exhibit keys step, the feedback
page's level selector raises a toast, the overview's live index opens a page,
the streaming control bar plays through, and the run closes on the workspace
exhibit, its inspector switched by click and by arrow -- the ring's focus
moves, an activation that picks and one that folds, a click that docks a
field's cursor, the page's last-action rows reading the session's log, the
control bar's play / pause / step / replay, and then the two-column page the
piped dump ends on -- so
``python examples/demo.py < /dev/null`` exercises the same
:meth:`~showcase.session.Showcase.run` the interactive path does, and a page
that fails to build fails the piped run.
"""

from __future__ import annotations

from mocode_tui import Key, MouseEvent, Paste

#: Headless replay geometry.  The live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 110, 70

__all__ = ["HEADLESS_H", "HEADLESS_W", "script"]


def script() -> list:
    """Every page, a few plays, a drag, a question, then quit."""
    events: list = []

    def type_text(text: str) -> None:
        events.extend(Key(ch, ch) for ch in text)

    def command(name: str) -> None:
        type_text(name)
        events.append(Key("enter"))  # the open palette consumes it and picks

    def mouse(name: str, x: int, y: int, kind: str = "press") -> None:
        events.append(MouseEvent(name, button=0, x=x, y=y, kind=kind))

    def click(x: int, y: int) -> None:
        mouse("left", x, y)
        mouse("left", x, y, "release")

    for name in ("overview", "text", "structure", "lists", "fields", "feedback",
                 "styles", "features", "streaming"):
        command(f"/{name}")
    # Drive the lists page by the focus ring: the ring starts on the menu, the
    # arrows wrap its cursor (the counter follows), enter activates the pick.
    command("/lists")
    for _ in range(4):
        events.append(Key("down"))
    events.append(Key("enter"))
    # Drive the structure page with the ring: tab moves the focus off the tab
    # strip onto the tree, down steps the tree, enter folds the node under it.
    command("/structure")
    events.append(Key("tab"))
    events.append(Key("down"))
    events.append(Key("enter"))
    # The click policy, twice over: the tab-strip click only moves the focus
    # there (the first click on a target focuses); the two tree-row clicks
    # then focus the tree and -- the second one -- activate the node on it.
    click(12, 30)
    click(3, 35)
    click(3, 35)
    # A second pane, its own scroll, then back to one; c-o is the pane focus
    # (tab belongs to the page's focus ring).
    command("/split")
    px, py = HEADLESS_W - 8, 6
    click(px, py)
    events.append(Key("c-o"))
    mouse("wheel_down", px, py)
    command("/split")
    command("/theme")
    command("/fps")  # off
    command("/fps")  # ...and on again
    # A multi-line paste arrives as one Paste event: the composer fills with
    # all three lines and nothing submits.  The separate enter below is the
    # one submit -- the paste itself can never fire the submit gesture.
    events.append(Paste("pasted first\npasted second\npasted third"))
    events.append(Key("enter"))
    type_text("what does this toolkit do?")
    events.append(Key("enter"))  # lands on the chat page and streams an answer
    # A drag over the answer: press, motion, release -- the gesture's on_end
    # copies the range through OSC 52 and the toast answers.
    mouse("left", 6, 30)
    mouse("left", 54, 33, "motion")
    mouse("left", 54, 33, "release")
    # The exhibit keys and the landing page's live index: c-n steps forward
    # (the strip's marker follows), c-p back, and on the overview one down
    # moves the index cursor and enter opens the exhibit it names -- the same
    # activate() -> chosen -> show() road the palette takes.
    events.append(Key("c-n"))  # chat wraps to the overview
    events.append(Key("c-n"))  # ... and on to the text page
    events.append(Key("c-p"))  # back to the overview
    events.append(Key("down"))  # the index cursor: /overview -> /text
    events.append(Key("enter"))  # opens the exhibit under the cursor
    # The feedback exhibit: its one Activable is the level selector -- enter
    # takes the row's payload and the host reports it once, so the piped run
    # covers the toast path (and the page's menu) too.
    command("/feedback")
    events.append(Key("enter"))
    # Close on the keymaps: reading the shell's own keys outside the tables.
    command("/keys")
    # ... then on the interaction exhibit itself: the ring's tab steps the
    # focus through the menu, the tree and the editor, enter on the editor
    # breaks its line (a field owns that key -- it is not an activation), and
    # a click docks the block cursor on the cell it landed on.  The last tab
    # wraps onto the menu, so the two activation shapes follow: the menu
    # picks up the option under its cursor (``chosen: 'row 01'``) and the tree
    # folds -- it carries no ``chosen``, so the log names the act
    # (``activate \u2192 tree``) instead of a value.  The page's last-action rows
    # are the session's log, so the dump ends on the three shapes a report can
    # take: a pick, a fold, a focus move.
    command("/interaction")
    events.append(Key("tab"))
    events.append(Key("tab"))
    events.append(Key("enter"))
    click(3, 41)  # the editor's second row: the block cursor lands on that cell
    events.append(Key("tab"))
    events.append(Key("enter"))
    events.append(Key("tab"))
    events.append(Key("enter"))
    # The streaming exhibit: its control bar is the page's one ring
    # target, so the arrows walk the bar and enter takes the row under the
    # cursor.  On this path the stream is complete before the page is built
    # (no beat runs headless), so the bar opens parked on its pause row --
    # enter takes that pick, down steps onto the other rows, and the visit
    # ends on replay.  Every pick leaves the host's report, so the piped run
    # covers the control bar's whole road (activate -> chosen -> the page's
    # note hook -> the stream), and the non-interactive stream publishes
    # nothing but the whole document.
    command("/streaming")
    events.append(Key("enter"))  # pause: the row the bar opens parked on
    events.append(Key("down"))  # pause -> step
    events.append(Key("enter"))  # step: one block
    events.append(Key("enter"))  # ... and one more
    events.append(Key("down"))  # step -> replay
    events.append(Key("enter"))  # replay: back to the first block
    # Close on the workspace exhibit -- the two-column page the piped dump
    # ends on, visibly two panes side by side.  The page opens its own right
    # pane (no /split), and the inspector's strip is its one ring target.
    # The click lands on the 'edits' label of that strip (its second cell
    # run, at the measured screen columns of the 110-wide replay -- the strip
    # sits on the right pane's row 0); the ring's right then steps the strip
    # on to 'reads'.  Each switch lands in the pane through the page's own
    # sync hook -- one view removed by id, one added, scrolled back to the
    # top -- never through a tick, so the dump reads the last pick exactly.
    command("/workspace")
    click(84, 0)  # the 'edits' label of the right pane's strip
    events.append(Key("tab"))
    events.append(Key("right"))
    # The picks along the way left toasts in the top-right corner; three
    # presses on that corner cell dismiss the stack (the overlay's own
    # press-to-dismiss path, and at most three are held), so the dump's last
    # frame is the page itself.  The cell is past the strip's last label, so
    # a press that finds no toast changes nothing.
    for _ in range(3):
        click(HEADLESS_W - 2, 0)
    events.append(Key("c-c"))
    return events
