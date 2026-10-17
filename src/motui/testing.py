"""Test helpers: a headless TUI and a structured document snapshot.

``headless_tui`` wires a :class:`~motui.core.screen.HeadlessScreen` (live by
construction, every byte recorded) to a
:class:`~motui.core.events.ScriptedKeys` source with ``interactive`` forced
off, so a test drives a real :class:`~motui.app.TUI` without touching a
terminal.  ``snapshot`` renders the document as structured plain text for
assertions that do not care about escape bytes.

The helpers sit above the kernel: they import the driver, the screens and the
event model, which is exactly what a test needs to drive a real session.
"""

from __future__ import annotations

from collections.abc import Iterable

from .app import TUI
from .core.events import Key, KeySource, Paste, ScriptedKeys
from .core.screen import HeadlessScreen

__all__ = ["headless_tui", "snapshot"]


def headless_tui(
    width: int = 80,
    height: int = 24,
    *,
    script: Iterable[Key | Paste | None] | None = None,
    keys: KeySource | None = None,
) -> TUI:
    """A TUI wired for tests: recording screen, scripted keys, no terminal.

    ``script`` is a sequence of ``Key``/``Paste`` events replayed by
    :class:`~motui.core.events.ScriptedKeys`; ``keys`` overrides it with any
    :class:`~motui.core.events.KeySource`.  The screen is a
    :class:`~motui.core.screen.HeadlessScreen` whose every written byte is
    readable from ``tui.screen.output``.
    """
    source = keys if keys is not None else ScriptedKeys(script or ())
    return TUI(screen=HeadlessScreen(width, height), keys=source, interactive=False)


def snapshot(tui: TUI) -> str:
    """A structured plain-text view of the document: one stanza per block.

    Each block renders as a ``[id | state]`` header -- ``state`` gains a
    ``,top`` / ``,bottom`` suffix for a block in the matching fixed region --
    followed by its rendered rows, each prefixed with ``  |``.  Rows are
    rendered at the screen width, so the snapshot shows exactly what the
    viewport would lay out.
    """
    width = tui.screen.width
    out: list[str] = []
    for block in tui.document.blocks():
        state = block.state.value
        if block.pin is not None:
            state += f",{block.pin}"
        out.append(f"[{block.id} | {state}]")
        out.extend("  |" + row.text for row in block.render(width))
    return "\n".join(out)
