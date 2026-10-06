"""The headless replay: the event script the piped run feeds the session.

``script()`` returns the whole piped session as a list of
:class:`~mocode_tui.core.events.Key` / :class:`~mocode_tui.core.events.MouseEvent`
/ :class:`~mocode_tui.core.events.Paste` events: every page is visited, a
couple are played with by key and by click, the focus ring's tab is cycled,
a pane opens and closes, a range is dragged to the clipboard, a multi-line
paste is replayed, a question is asked -- so
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

    for name in ("overview", "data", "structure", "lists", "fields", "feedback",
                 "styles", "features", "markdown"):
        command(f"/{name}")
    # Play the lists page by the focus ring: the ring starts on the menu, the
    # arrows wrap its cursor (the counter follows), enter activates the pick.
    command("/lists")
    for _ in range(4):
        events.append(Key("down"))
    events.append(Key("enter"))
    # Play the structure page with the ring: tab moves the focus off the tab
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
    events.append(Key("c-c"))
    return events
