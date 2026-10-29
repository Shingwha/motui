"""CommandPalette: a query row over the filtered list, in a modal.

A modal controller: the panel is private to this module, and the modal
owns the scrim, placement and routing. Opening resets the query, the list
and the pending pick."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..kernel.cell import Surface
from ..kernel.events import Event, KeyEvent, PasteEvent
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints
from ..kernel.theme import Theme
from ..widgets.autocomplete import Autocomplete
from ..widgets.textfield import Input
from .focus import FocusManager
from .modal import Modal

if TYPE_CHECKING:
    from .runtime import Runtime

__all__ = ["CommandPalette"]

#: "No decision yet" inside the panel: ``None`` is a legal decision (an
#: ``enter`` that matched nothing, an ``escape``), so absence needs its own
#: value.
_NO_RESULT = object()

#: The panel's anchor cell.  No frame is a million rows tall, so the modal's
#: clamp parks the panel against the frame's **bottom** edge (``rect.bottom
#: - h``) whatever the screen's height: the palette's habit -- a query row
#: at the foot of the screen, its left edge at the frame's own.
_BOTTOM = (1 << 20, 0)


class _CommandPalettePanel:
    """The palette's panel: the query row over the list, the modal's dialog;
    the one-shot result is what the modal watches."""

    __slots__ = ("_pending", "input", "list")

    def __init__(
        self,
        commands: list[object],
        *,
        max_rows: int = 8,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
    ) -> None:
        self.input = Input(glyphs=glyphs, theme=theme)
        self.list = Autocomplete(
            list(commands), max_rows=max_rows, glyphs=glyphs, theme=theme
        )
        #: The pending decision, in the modal's one-shot protocol: the value
        #: :meth:`handle` leaves when it takes one, else ``_NO_RESULT``.
        self._pending: object = _NO_RESULT

    def reset(self) -> None:
        """A fresh visit: the query row empties, the list shows everything and the
        pending decision goes."""
        self.input.clear()
        self.list.set_query("")
        self._pending = _NO_RESULT

    def render(self, c: Constraints) -> Surface:
        """The query row followed by the list's rows, as a clipped surface."""
        inner = Constraints(width=c.width)
        rows = [*self.input.render(inner), *self.list.render(inner)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def on_click(self, pos: Pos) -> bool:
        """No click gesture: the palette is keyboard-driven, so every cell declines."""
        return False

    def on_key(self, event: KeyEvent) -> bool:
        """The palette's keys: up/down move, enter takes the option's value, escape
        cancels; anything else filters through the query row."""
        if event.key == "up":
            self.list.move(-1)
            return True
        if event.key == "down":
            self.list.move(1)
            return True
        if event.key == "enter":
            self.list.on_action("activate")
            self._pending = self.list.take()
            return True
        if event.key == "escape":
            self._pending = None
            return True
        if self.input.on_key(event):
            self.list.set_query(self.input.text)
            return True
        return False

    def on_paste(self, event: PasteEvent) -> bool:
        """Feed one paste to the query row; a consumed paste re-filters."""
        if self.input.on_paste(event):
            self.list.set_query(self.input.text)
            return True
        return False

    def take(self) -> object | None:
        """Read the pending decision once and clear it."""
        value = self._pending
        self._pending = _NO_RESULT
        return None if value is _NO_RESULT else value

    def _take_decision(self) -> tuple[bool, object]:
        """Read the routing's decision as ``(made, value)`` and clear it."""
        value = self._pending
        self._pending = _NO_RESULT
        return (False, None) if value is _NO_RESULT else (True, value)


class CommandPalette:
    """A command palette: an input row over a filtered command list, in a modal.

    It starts closed and renders zero rows; ``detach`` is the one final
    unmount. ``take`` reads the pending pick once."""

    __slots__ = ("_modal", "_panel", "commands", "input", "list")

    def __init__(
        self,
        tui: Runtime,
        commands: list[object],
        *,
        theme: Theme | None = None,
        max_rows: int = 8,
        glyphs: Glyphs = GLYPHS,
        focus: FocusManager | None = None,
    ) -> None:
        self.commands = list(commands)
        self._panel = _CommandPalettePanel(
            self.commands, max_rows=max_rows, glyphs=glyphs, theme=theme
        )
        self.input = self._panel.input
        self.list = self._panel.list
        self._modal = Modal(tui, self._panel, anchor=_BOTTOM, focus=focus)

    def take(self) -> object | None:
        """Read the pending pick once and clear it (the modal's result)."""
        return self._modal.take()

    @property
    def is_open(self) -> bool:
        """Whether the palette is showing (and therefore consuming keys)."""
        return self._modal.is_open

    def open(self) -> None:
        """Show the panel with a fresh query (nothing pending, full list)."""
        self._panel.reset()
        self._modal.open()

    def close(self) -> None:
        """Hide the palette; it stops consuming keys immediately."""
        self._modal.close()

    def detach(self) -> None:
        """Unmount the palette: unregister its modal overlay and close it; final
        and idempotent."""
        self._modal.detach()

    def set_theme(self, theme: Theme) -> None:
        """Re-skin the query row, the list and the modal's scrim in place."""
        self.input.theme = theme
        self.list.theme = theme
        self._modal.set_theme(theme)

    def handle(self, event: Event) -> bool:
        """Consume an event while open (the modal's routing with the panel behind
        it); a closed palette consumes nothing."""
        return self._modal.handle(event)

    def render(self, c: Constraints) -> Surface:
        """The query row followed by the list's rows; zero rows while closed."""
        if not self._modal.is_open:
            return Surface(width=c.width, rows=())
        return self._panel.render(c)

    def __repr__(self) -> str:
        return (
            f"CommandPalette({self.commands!r}, open={self.is_open}, "
            f"query={self.input.text!r})"
        )
