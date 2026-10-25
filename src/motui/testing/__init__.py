"""Test helpers: a headless harness and a structured document snapshot.

``headless_tui`` wires a :class:`~motui.terminal.screen.HeadlessScreen` (live by
construction, every byte recorded) to a
:class:`~motui.testing.ScriptedEvents` source with ``interactive`` forced
off, so a test drives a real :class:`~motui.app.runtime.Runtime` and its
:class:`~motui.app.workspace.Workspace` without touching a terminal.  It
returns a :class:`Harness`.  ``snapshot`` renders the document as structured
plain text for assertions that do not care about escape bytes.

The harness is the **flat test driver**: content members (``add``, ``get``,
``frame``, ``hit``, ``split``, ``dock`` ...) resolve to the workspace and
session members (``paint``, ``refresh``, ``every``, ``screen`` ...) to the
runtime.  Production code never imports it -- it exists so a test can write
``tui.add(...)`` and ``tui._clock = ...`` against one object while the real
split stays intact.

``Emulator`` lives beside them in :mod:`motui.testing.emulator`: it consumes
the bytes a :class:`~motui.terminal.paint.Painter` writes and rebuilds the cell
grid, so a test can assert on what a terminal would actually show rather than
on escape-string spellings.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..app import Runtime, Workspace
from ..kernel.document import Placement
from ..kernel.events import Event, EventSource
from ..kernel.layout import Constraints
from ..terminal.screen import HeadlessScreen, TerminalOptions
from ..terminal.terminal import Terminal
from .emulator import Emulator

__all__ = ["Emulator", "Harness", "ScriptedEvents", "headless_tui", "snapshot"]


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


class Harness:
    """One flat test driver over a runtime and its workspace.

    ``__getattr__`` resolves the workspace first and the runtime second, so
    ``tui.add`` is the workspace's and ``tui.paint`` the runtime's.
    ``__setattr__`` sends private names (``_clock`` and the other session
    seams) to the runtime and public names to the workspace, matching the
    order ``__getattr__`` uses.  Dunder lookups are never proxied.
    """

    __slots__ = ("runtime", "terminal", "workspace")

    def __init__(
        self,
        runtime: Runtime,
        workspace: Workspace | None = None,
        terminal: Terminal | None = None,
    ) -> None:
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "workspace", runtime.workspace if workspace is None else workspace)
        object.__setattr__(self, "terminal", runtime.terminal if terminal is None else terminal)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        try:
            return getattr(self.workspace, name)
        except AttributeError:
            return getattr(self.runtime, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("runtime", "workspace", "terminal"):
            object.__setattr__(self, name, value)
        elif name.startswith("_"):
            setattr(self.runtime, name, value)
        else:
            setattr(self.workspace, name, value)

    def __repr__(self) -> str:
        return f"Harness(runtime={self.runtime!r})"


def headless_tui(
    width: int = 80,
    height: int = 24,
    *,
    script: Iterable[Event | None] | None = None,
    keys: EventSource | None = None,
) -> Harness:
    """A harness wired for tests: recording screen, scripted events, no terminal.

    ``script`` is a sequence of events replayed by
    :class:`~motui.testing.ScriptedEvents`; ``keys`` overrides it with any
    :class:`~motui.kernel.events.EventSource`.  The screen is a
    :class:`~motui.terminal.screen.HeadlessScreen` whose every written byte is
    readable from ``tui.screen.output``.
    """
    source = keys if keys is not None else ScriptedEvents(script or ())
    terminal = Terminal(
        TerminalOptions(screen=HeadlessScreen(width, height), input=source)
    )
    runtime = Runtime(terminal, interactive=False)
    return Harness(runtime, runtime.workspace, terminal)


def snapshot(tui: Harness) -> str:
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
        if block.placement is Placement.FLOW:
            out.append(f"[{block.id}]")
        else:
            out.append(f"[{block.id} | {block.placement.value}]")
        out.extend("  |" + row.text for row in block.render(Constraints(width=width)))
    return "\n".join(out)
