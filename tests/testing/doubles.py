"""Component and screen doubles: the smallest fakes a test needs."""

from __future__ import annotations

from motui.core.block import Document
from motui.core.lines import Line

__all__ = ["RecordingScreen", "Rows", "document", "many"]


class Rows:
    """Component double rendering one row per given text."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(t) for t in self.texts]


class RecordingScreen:
    """Screen double: records every write, counts the session bracket.

    ``entered`` / ``left`` count the buffer switches a session brackets itself
    with; the double writes no bytes for them (a test that cares about the
    alt-screen bytes uses a :class:`~motui.core.screen.TerminalScreen` on a
    stream it holds).
    """

    def __init__(self, width: int = 80, height: int = 24, *, live: bool = True) -> None:
        self.width = width
        self.height = height
        self.live = live
        self.writes: list[str] = []
        self.flushes = 0
        self.entered = 0
        self.left = 0
        self.mark = 0

    def write(self, s: str) -> None:
        self.writes.append(s)

    def flush(self) -> None:
        self.flushes += 1

    def refresh_size(self) -> None:
        pass

    def enter(self) -> None:
        self.entered += 1

    def leave(self) -> None:
        self.left += 1

    @property
    def output(self) -> str:
        return "".join(self.writes)

    def delta(self) -> str:
        """Everything written since the last delta() call."""
        fresh = "".join(self.writes[self.mark :])
        self.mark = len(self.writes)
        return fresh


def many(n: int) -> list[str]:
    """``n`` distinct row texts: ``"r0"`` .. ``"r{n-1}"``."""
    return [f"r{i}" for i in range(n)]


def document(*texts: str) -> Document:
    """A one-block document whose rows are exactly ``texts``."""
    doc = Document()
    doc.add(Rows(*texts))
    return doc
