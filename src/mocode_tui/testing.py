"""Test helpers: a headless TUI and a structured document snapshot.

``headless_tui`` wires a :class:`~mocode_tui.screen.HeadlessScreen` (live by
construction, every byte recorded) to a
:class:`~mocode_tui.keys.ScriptedKeys` source with ``interactive`` forced
off, so a test drives a real :class:`~mocode_tui.app.TUI` without touching a
terminal.  ``snapshot`` renders the document as structured plain text for
assertions that do not care about escape bytes.
"""

from __future__ import annotations

from .app import TUI
from .keys import Key, KeySource, Paste, ScriptedKeys
from .screen import HeadlessScreen

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
    :class:`~mocode_tui.keys.ScriptedKeys`; ``keys`` overrides it with any
    :class:`~mocode_tui.keys.KeySource`.  The screen is a
    :class:`~mocode_tui.screen.HeadlessScreen` whose every written byte is
    readable from ``tui.screen.output``.
    """
    source = keys if keys is not None else ScriptedKeys(script or ())
    return TUI(screen=HeadlessScreen(width, height), keys=source, interactive=False)


def snapshot(tui: TUI) -> str:
    """A structured plain-text view of the document: one stanza per block.

    Each block renders as a ``[id | state]`` header -- ``state`` gains a
    ``,pinned`` suffix for pinned blocks -- followed by its rendered rows,
    each prefixed with ``  |``.  Rows are rendered at the screen width, so
    the snapshot shows exactly what the viewport would lay out.
    """
    width = tui.screen.width
    out: list[str] = []
    for block in tui.document.blocks():
        state = block.state.value
        if block.pinned:
            state += ",pinned"
        out.append(f"[{block.id} | {state}]")
        out.extend("  |" + row.text for row in block.render(width))
    return "\n".join(out)
