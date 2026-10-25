"""Test helpers: a headless TUI and a structured document snapshot.

``headless_tui`` wires a :class:`~motui.core.screen.HeadlessScreen` (live by
construction, every byte recorded) to a
:class:`~motui.testing.ScriptedEvents` source with ``interactive`` forced
off, so a test drives a real :class:`~motui.app.TUI` without touching a
terminal.  ``snapshot`` renders the document as structured plain text for
assertions that do not care about escape bytes.

The helpers sit above the kernel: they import the driver, the screens and the
event model, which is exactly what a test needs to drive a real session.

``Emulator`` lives beside them in :mod:`motui.testing.emulator`: it consumes
the bytes a :class:`~motui.core.painter.Painter` writes and rebuilds the cell
grid, so a test can assert on what a terminal would actually show rather than
on escape-string spellings.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..app import TUI
from ..core.events import Event, EventSource
from ..core.screen import HeadlessScreen
from .emulator import Emulator

__all__ = ["Emulator", "ScriptedEvents", "headless_tui", "snapshot"]


class ScriptedEvents:
    """An event source that replays a fixed sequence, then EOFs.

    Handy for tests and demos: hand it events and every ``read()`` returns
    the next item in order, until the sequence is exhausted -- after which
    ``read()`` returns ``None`` forever.  A ``None`` item inside the sequence
    is delivered as a one-shot end-of-stream signal, exactly like a real
    source reporting EOF before more input arrives.
    """

    def __init__(self, events: Iterable[Event | None] = ()) -> None:
        self._events = list(events)
        self._index = 0

    async def read(self) -> Event | None:
        if self._index >= len(self._events):
            return None
        event = self._events[self._index]
        self._index += 1
        return event


def headless_tui(
    width: int = 80,
    height: int = 24,
    *,
    script: Iterable[Event | None] | None = None,
    keys: EventSource | None = None,
) -> TUI:
    """A TUI wired for tests: recording screen, scripted events, no terminal.

    ``script`` is a sequence of events replayed by
    :class:`~motui.testing.ScriptedEvents`; ``keys`` overrides it with any
    :class:`~motui.core.events.EventSource`.  The screen is a
    :class:`~motui.core.screen.HeadlessScreen` whose every written byte is
    readable from ``tui.screen.output``.
    """
    source = keys if keys is not None else ScriptedEvents(script or ())
    return TUI(screen=HeadlessScreen(width, height), keys=source, interactive=False)


def snapshot(tui: TUI) -> str:
    """A structured plain-text view of the document: one stanza per block.

    Each block renders as a ``[id]`` header -- ``[id | top]`` / ``[id |
    bottom]`` for a block in the matching fixed region -- followed by its
    rendered rows, each prefixed with ``  |``.  Rows are rendered at the
    screen width, so the snapshot shows exactly what the viewport would lay
    out.
    """
    width = tui.screen.width
    out: list[str] = []
    for block in tui.document.blocks():
        if block.pin is None:
            out.append(f"[{block.id}]")
        else:
            out.append(f"[{block.id} | {block.pin}]")
        out.extend("  |" + row.text for row in block.render(width))
    return "\n".join(out)
