"""Test helpers: a headless harness and a structured document snapshot.

``headless_tui`` wires a recording ``HeadlessScreen`` to scripted events with
``interactive`` off, returning a flat ``Harness`` over the workspace and
runtime.  ``snapshot`` renders the document as stanza text; ``Emulator``
rebuilds the cell grid from painter bytes.  Production never imports this.
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

    A ``None`` item is a one-shot end-of-stream signal; afterwards ``read``
    returns ``None`` forever.
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

    Attribute reads resolve the workspace first, then the runtime; writes
    send private names to the runtime and public names to the workspace.
    Dunder lookups are never proxied.
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

    ``script`` replays through ``ScriptedEvents``; ``keys`` overrides it with
    any ``EventSource``.  Written bytes are readable from
    ``tui.screen.output``.
    """
    source = keys if keys is not None else ScriptedEvents(script or ())
    terminal = Terminal(
        TerminalOptions(screen=HeadlessScreen(width, height), input=source)
    )
    runtime = Runtime(terminal, interactive=False)
    return Harness(runtime, runtime.workspace, terminal)


def snapshot(tui: Harness) -> str:
    """A structured plain-text view: one stanza per block.

    Each block is a ``[id]`` (or ``[id | placement]``) header followed by
    ``  |``-prefixed rows rendered at the screen width.
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
