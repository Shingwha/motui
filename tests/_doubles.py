"""Shared test doubles: the components, screens, and shorthands used.

``Rows`` renders one row per given text, ``RecordingScreen`` records every
write (``delta()`` returns what changed), plus the ``texts``/``many``/``key``.
"""

from __future__ import annotations

from motui.core.block import Component
from motui.core.events import Key
from motui.core.lines import Line

__all__ = ["RecordingScreen", "Rows", "key", "many", "texts"]


class Rows:
    """Component double rendering one row per given text."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(t) for t in self.texts]


class RecordingScreen:
    """Screen double: records every write, settable size, switchable liveness."""

    def __init__(self, width: int = 80, height: int = 24, *, live: bool = True) -> None:
        self.width = width
        self.height = height
        self.live = live
        self.writes: list[str] = []
        self.flushes = 0
        self._mark = 0  # the first delta() captures everything written so far

    def write(self, s: str) -> None:
        self.writes.append(s)

    def flush(self) -> None:
        self.flushes += 1

    def refresh_size(self) -> None:
        pass  # the size only changes when a test moves it

    @property
    def output(self) -> str:
        return "".join(self.writes)

    def delta(self) -> str:
        """Everything written since the last delta() call."""
        fresh = "".join(self.writes[self._mark :])
        self._mark = len(self.writes)
        return fresh


def texts(component: Component, width: int) -> list[str]:
    """The plain-text rows ``component`` renders at ``width``."""
    return [row.text for row in component.render(width)]


def many(n: int) -> list[str]:
    """``n`` distinct row texts: ``"r0"`` .. ``"r{n-1}"``."""
    return [f"r{i}" for i in range(n)]


def key(name: str, char: str = "") -> Key:
    """One key press: its routable ``name`` plus the printable ``char``."""
    return Key(name, char)
