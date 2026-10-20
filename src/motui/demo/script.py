"""The headless replay: welcome, every section, a palette jump, a theme, quit.

``script()`` returns the whole piped session as events.  The tour starts on
the welcome topic, clicks the header's **Components** label (the real
``MenuBar`` road), walks one topic per section with the section chords,
clicks a catalog row, plays the focused Select, opens the global palette
with ``c-k`` and jumps through it, cycles the theme with ``c-t``, returns to
``overview`` and quits with ``q``.

**The mouse cells are symbolic.**  :class:`Anchors` mounts its own headless
session at the replay's geometry and resolves a label by scanning the live
frame -- the header dock for a section, the catalog region for a topic --
so a label that moves moves its cell with it, and a label that disappears
fails with :class:`AnchorError` instead of clicking a neighbour.
"""

from __future__ import annotations

from motui import KeyEvent, MouseEvent, TUI
from motui.kernel import HeadlessScreen

from .registry import BY_KEY, SECTION_BY_KEY, TOPICS
from .session import Session

#: Headless replay geometry: the live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 110, 70

__all__ = ["HEADLESS_H", "HEADLESS_W", "AnchorError", "Anchors", "script"]


class AnchorError(LookupError):
    """A label the replay anchors on is no longer on screen."""


class Anchors:
    """The replay's symbolic label anchors, resolved against a live frame."""

    def __init__(self, width: int = HEADLESS_W, height: int = HEADLESS_H) -> None:
        self.tui = TUI(screen=HeadlessScreen(width, height), interactive=False)
        self.session = Session(self.tui)
        self._topic: str | None = None

    def showing(self, key: str) -> Session:
        if key not in BY_KEY:
            raise AnchorError(f"no topic named {key!r}")
        if self._topic != key:
            self.session.show_topic(key, toast=False)
            self.tui.paint()
            self._topic = key
        return self.session

    def catalog_cell(self, key: str) -> tuple[int, int]:
        """The cell of the catalog row whose label is ``key``'s title."""
        topic = BY_KEY[key]
        session = self.showing(key)
        region = self.tui.frame.region(session.catalog_pane.id)
        if region is None:
            raise AnchorError(f"{key}: the catalog has no region")
        for y in range(region.y, region.bottom):
            row = self.tui.rows[y].text
            col = row.find(topic.title, region.x, region.right)
            if col >= 0:
                return (col + 1, y)
        raise AnchorError(f"{key}: the catalog does not paint {topic.title!r}")

    def menu_cell(self, section: str) -> tuple[int, int]:
        """The cell of the header label for ``section``."""
        section_value = SECTION_BY_KEY.get(section)
        if section_value is None:
            raise AnchorError(f"no section named {section!r}")
        self.tui.paint()
        top = self.tui.dock_region("top")
        if top is None:
            raise AnchorError(f"{section}: the frame has no top dock")
        for y in range(top.y, top.bottom):
            row = self.tui.rows[y].text
            col = row.find(section_value.title, top.x, top.right)
            if col >= 0:
                return (col + 1, y)
        raise AnchorError(f"{section}: the header does not paint {section_value.title!r}")

    def stage_cell(self, needle: str) -> tuple[int, int]:
        """The first stage cell whose painted row contains ``needle``."""
        session = self.showing(self._topic or TOPICS[0].key)
        region = self.tui.frame.region(session.stage.id)
        if region is None:
            raise AnchorError(f"{needle!r}: the stage has no region")
        for y in range(region.y, region.bottom):
            row = self.tui.rows[y].text
            col = row.find(needle, region.x, region.right)
            if col >= 0:
                return (col, y)
        raise AnchorError(f"{needle!r}: the stage does not paint it")

    def corner(self) -> tuple[int, int]:
        """The toast stack's corner cell: the frame's top-right, two cells in."""
        rect = self.tui.frame.rect
        if rect is None or rect.width < 4:
            raise AnchorError("the frame has no room for the toast stack")
        return (rect.right - 2, rect.y)


def _mouse(button: str, cell: tuple[int, int], kind: str = "press") -> MouseEvent:
    return MouseEvent(button, x=cell[0], y=cell[1], kind=kind)


def script() -> list:
    """The whole piped tour, in event order."""
    events: list = []
    layout = Anchors()

    def click(cell: tuple[int, int]) -> None:
        events.append(_mouse("left", cell))
        events.append(_mouse("left", cell, "release"))

    def type_text(text: str) -> None:
        events.extend(KeyEvent(char, char) for char in text)

    # Welcome: the header menu is a real MenuBar; clicking Components lands there.
    click(layout.menu_cell("components"))
    events.append(KeyEvent("c-n"))  # text -> markdown

    # One topic per remaining section, with c-n and a catalog click.
    events.append(KeyEvent("c-3"))  # interactions/focus
    events.append(KeyEvent("c-n"))  # -> pointer
    click(layout.catalog_cell("selection"))
    events.append(KeyEvent("c-4"))  # styling/theme-tokens
    events.append(KeyEvent("c-t"))  # amber
    events.append(KeyEvent("c-5"))  # patterns/streaming-markdown
    events.append(KeyEvent("c-6"))  # reference/api-layers

    # Back to components through a catalog row, play the Select, then palette-jump.
    events.append(KeyEvent("c-2"))  # components/text
    click(layout.catalog_cell("select"))
    events.extend((KeyEvent("down"), KeyEvent("enter")))
    events.append(KeyEvent("c-k"))
    type_text("select")
    events.append(KeyEvent("enter"))
    events.append(KeyEvent("c-t"))  # violet

    # End where the dump wants to be: the welcome topic.
    events.append(KeyEvent("c-1"))
    for _ in range(3):
        click(layout.corner())  # dismiss the toast stack
    events.append(KeyEvent("q"))
    events.append(KeyEvent("c-c"))  # the unread second quit gesture
    return events
