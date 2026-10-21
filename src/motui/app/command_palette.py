"""CommandPalette: the command palette -- a query row over the filtered list, in a modal.

:class:`CommandPalette` packages a command palette end to end: a query
:class:`~motui.widgets.textfield.Input` row on top, an
:class:`~motui.widgets.autocomplete.Autocomplete` filtered by that row's text
below, and the list the rows come from.  It is a **modal controller**: the
panel is the palette's own private composition and a
:class:`~motui.app.modal.Modal` paints it over a scrimmed frame,
places it (bottom-anchored), routes the keyboard body-first and dismisses
on a click outside.  The registration, the scrim and the routing are the
modal's; the rows and the query are the palette's -- there is no second
implementation of "open, scrim, route, click outside" hiding here.

The palette is **self-contained**: it owns the keyboard while it is open,
so a host needs no pinned editor to feed it a query, and :meth:`take_result`
is the whole of the host's side.  Opening resets
everything: the query row empties, the list shows every command again and a
stale pick cannot leak in.  While open, ``up``/``down`` move the list cursor
(wrapping the ends), ``enter`` activates the cursor's option and maps its
``value`` into the pending result (``None`` when the query matches nothing), and
``escape`` closes with nothing chosen.  Every other event -- a printable, an
editing key, a :class:`~motui.core.events.PasteEvent` -- routes through the
palette's own input row; when the row consumes it the list re-filters on the
row's text.  A closed palette consumes nothing and renders zero rows, so a
host can pin it in a constant-height slot and hand it the keyboard only
while open.

The host reads :meth:`take_result` once after a consuming ``handle``; a
routed event that decides nothing clears the pending value itself, so a
stale selection never survives a later keystroke.  Filtering is
the kernel's: case-sensitive, prefix matches first, then substrings (the
labels are the rows, so a label's own text is what prefix matching keys on).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.events import Event, KeyEvent
from ..core.glyphs import GLYPHS, Glyphs
from ..core.lines import Line
from ..core.theme import Theme
from ..widgets.autocomplete import Autocomplete
from ..widgets.textfield import Input
from .focus import FocusManager
from .modal import Modal

if TYPE_CHECKING:
    from .driver import TUI

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
    """The palette's panel: the query row over the list, the modal's dialog.

    Private to this module -- :class:`CommandPalette` is its only consumer, so the
    composition lives here instead of the widget layer.  It is the modal's
    structural duck: :meth:`render` is the query row followed by the list's
    rows, :meth:`handle` is the palette's whole keyboard, and the one-shot
    result (:meth:`take_result`; ``None`` for a cancel included) is what the
    modal watches -- a decision closes the modal with it.  There is no
    click gesture: the palette is driven from the keyboard, and a press
    inside the panel is the modal's to consume and nothing else.
    """

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
        """A fresh visit: the query row empties and the list shows everything.

        The one open rule of the old palette: both children reset, so an
        open palette never inherits a stale query or a stale pick
        (``set_query("")`` restores the full list and clears the list's own
        result), and the pending decision goes with them.
        """
        self.input.clear()
        self.list.set_query("")
        self._pending = _NO_RESULT

    def render(self, width: int) -> list[Line]:
        """The query row followed by the list's rows."""
        return self.input.render(width) + self.list.render(width)

    def click(self, row: int, col: int) -> bool:
        """No click gesture: the modal's duck, declining every cell.

        The palette is driven from the keyboard (the widget it grew out of
        had no ``click`` either); a press inside the panel is still the
        modal's to consume, this just decides nothing.
        """
        return False

    def handle(self, event: Event) -> bool:
        """The palette's keyboard: the list's keys first, then the query row's.

        ``up``/``down`` move the list cursor (wrapping around the list's
        ends, like every menu) and are consumed; they decide nothing.
        ``enter`` takes the highlighted option through the kernel's
        activation and leaves its ``value`` pending (``None`` when
        the query matches nothing).  ``escape`` leaves a pending ``None`` --
        the cancel, which the modal reads exactly like a picked value.
        Everything else is the query row's: an event it consumes re-filters
        the list on its text, and the panel answers ``True``.
        """
        if isinstance(event, KeyEvent):
            if event.key == "up":
                self.list.move(-1)
                return True
            if event.key == "down":
                self.list.move(1)
                return True
            if event.key == "enter":
                self.list.activate()
                option = self.list.take_result()
                self._pending = None if option is None else option.value
                return True
            if event.key == "escape":
                self._pending = None
                return True
        if self.input.handle(event):
            self.list.set_query(self.input.text)
            return True
        return False

    def take_result(self) -> object | None:
        """Read the pending decision once and clear it."""
        value = self._pending
        self._pending = _NO_RESULT
        return None if value is _NO_RESULT else value

    def _take_decision(self) -> tuple[bool, object]:
        """Read the routing's decision as ``(made, value)``; clear it."""
        value = self._pending
        self._pending = _NO_RESULT
        return (False, None) if value is _NO_RESULT else (True, value)


class CommandPalette:
    """A command palette: an input row over a filtered command list, in a modal.

    ``tui`` is the driver the palette's modal registers its overlay on and
    invalidates for the scrimmed repaint -- a palette is a modal controller,
    so the driver is not optional.  ``commands`` are the selectable
    ``Option`` values (a label like ``"/help"``, the payload in
    ``value``); ``max_rows`` caps the list's rendered window (the kernel
    scrolls it to keep the cursor visible) at the palette's default ``8``.
    ``theme`` skins the query row and the list (it is forwarded to both --
    :attr:`input` and :attr:`list` are the composed widgets, readable for a
    prompt restyle or ``palette.input.text``).

    The palette starts closed and renders zero rows then; :meth:`open`
    resets the query, the list and the pending pick and shows the panel over
    the scrim, :meth:`close` hides it.  Its modal overlay is mounted at
    construction (the ``Toasts`` lifecycle); :meth:`detach` is the one
    unmount -- final and idempotent, unlike :meth:`close`, which only hides.
    :meth:`take_result` reads the pending selection once and clears it --
    the value the last ``enter`` took (``None`` when nothing matched) or
    ``None`` for ``escape`` and a click outside.  :meth:`is_open` is the
    modal's state, forwarded; :meth:`handle` and :meth:`render` are the same
    forwarding.  ``focus`` optionally mounts the modal's focus trap.
    """

    __slots__ = ("_modal", "_panel", "commands", "input", "list")

    def __init__(
        self,
        tui: TUI,
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

    def take_result(self) -> object | None:
        """Read the pending pick once and clear it (the modal's result)."""
        return self._modal.take_result()

    @property
    def is_open(self) -> bool:
        """Whether the palette is showing (and therefore consuming keys)."""
        return self._modal.is_open

    def open(self) -> None:
        """Show the panel with a fresh query (nothing pending, full list).

        The host calls this when it opens the palette -- a key, a click, a
        pick that names the palette.  The query row and the list reset first
        (the panel's own rule), so an open palette never inherits a stale
        query or a stale pick from an earlier visit, and the modal takes the
        overlay and the scrim from there.
        """
        self._panel.reset()
        self._modal.open()

    def close(self) -> None:
        """Hide the palette; it stops consuming keys immediately."""
        self._modal.close()

    def detach(self) -> None:
        """Unmount the palette: unregister its modal overlay and close it.

        The whole body is the modal's own detach, so the semantics are the
        ``Toasts`` lifecycle's: identity-based, a second call is a no-op, a
        detached palette never re-registers (``open()`` included), and it
        consumes nothing and holds no result.  This is **not**
        :meth:`close`: closing hides the panel but keeps the overlay mounted
        for a later visit; detaching is final.
        """
        self._modal.detach()

    def set_theme(self, theme: Theme) -> None:
        """Re-skin the query row, the list and the modal's scrim in place.

        The widgets take the theme as their own (``styles`` overrides still
        win), and the modal follows through :meth:`Modal.set_theme`; a
        query in progress stays in the input.
        """
        self.input.theme = theme
        self.list.theme = theme
        self._modal.set_theme(theme)

    def handle(self, event: Event) -> bool:
        """Consume an event while open; see the module docstring.

        The modal's routing with the panel behind it: a closed palette
        consumes nothing; open, every event is the palette's -- the panel's
        own keys decide (``enter`` a value, ``escape`` nothing), a press
        outside the panel dismisses, and everything else is consumed and
        dropped rather than falling through to the host's shortcuts.
        """
        return self._modal.handle(event)

    def render(self, width: int) -> list[Line]:
        """The query row followed by the list's rows; zero rows while closed.

        The rows the modal paints in its panel -- and the rows a host may
        still embed in a document (the demo's exhibit does): while closed
        the answer is empty, exactly as the palette always rendered.
        """
        if not self._modal.is_open:
            return []
        return self._panel.render(width)

    def __repr__(self) -> str:
        return (
            f"CommandPalette({self.commands!r}, open={self.is_open}, "
            f"query={self.input.text!r})"
        )
