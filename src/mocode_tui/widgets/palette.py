"""Palette: a self-contained command palette -- its own query row over a list.

:class:`Palette` packages the whole slash menu: a query
:class:`~mocode_tui.widgets.input.Input` row on top, an
:class:`~mocode_tui.widgets.autocomplete.Autocomplete` filtered by that row's
text below.  It is **self-contained** -- the palette owns the keyboard while
it is open, so a host needs no pinned editor to feed it a query.  That is the
one difference from the retired host-fed slash menu, which owned navigation
and dismissal only and read the host editor's text as its query; the host
contract around :attr:`chosen` is unchanged.

Opening resets everything: the query row empties, the list shows every
command again and a stale pick cannot leak in.  While open, :meth:`handle`
consumes ``up``/``down`` (moving the list cursor, clearing any pending
:attr:`chosen`), ``enter`` (activating the cursor's option, mapping its
``value`` into :attr:`chosen` -- ``None`` when the query matches nothing --
clearing the kernel's own ``chosen`` and closing) and ``escape`` (closing
with nothing chosen).  Every other event -- a printable, an editing key, a
:class:`~mocode_tui.core.events.Paste` -- routes through the palette's own
input row; when the row consumes it the list re-filters on the row's text.
A closed palette consumes nothing and renders zero rows, so a host can pin
it in a constant-height slot and hand it the keyboard only while open.

The host reads :attr:`chosen` once after a consuming ``handle`` and resets
the attribute to ``None``; navigation clears it itself, so a stale selection
never survives a later keystroke.  Filtering is the kernel's: case-sensitive,
prefix matches first, then substrings (the command labels are the rows, so a
label's own leading slash is what prefix matching keys on).
"""

from __future__ import annotations

from ..core.events import Key, Paste
from ..core.lines import Line
from ..core.theme import Theme, Themed
from .autocomplete import Autocomplete
from .choice import Option
from .input import Input

__all__ = ["Palette"]


class Palette(Themed):
    """A command palette: an input row over a filtered command list.

    ``commands`` are the selectable :class:`Option` values (a label like
    ``"/help"``, the payload in ``value``); ``max_rows`` caps the list's
    rendered window (the kernel scrolls it to keep the cursor visible) at the
    palette's default ``8``.  The palette starts closed.  :attr:`input` and
    :attr:`list` are the composed widgets (a host may restyle the row's
    prompt or read the query from ``palette.input.text``);
    :attr:`chosen` is the pending selection: the value of the command the
    last ``enter`` picked, read and cleared by the host.
    """

    __slots__ = ("_open", "chosen", "commands", "input", "list")

    def __init__(
        self,
        commands: list[Option],
        *,
        theme: Theme | None = None,
        max_rows: int = 8,
    ) -> None:
        super().__init__(theme)
        self.commands = list(commands)
        self.input = Input(theme=theme)
        self.list = Autocomplete(options=self.commands, max_rows=max_rows, theme=theme)
        self.chosen: str | None = None
        self._open = False

    @property
    def is_open(self) -> bool:
        """Whether the palette is showing (and therefore consuming keys)."""
        return self._open

    def open(self) -> None:
        """Show the full command list with an empty query row (nothing chosen).

        The host calls this on a freshly typed leading slash.  Both the query
        row and the list reset, so an open palette never inherits a stale
        query or a stale :attr:`chosen` selection from an earlier visit.
        """
        self.input.clear()
        # set_query("") restores the full list and clears the kernel's own
        # chosen: a fresh visit inherits nothing from the last one.
        self.list.set_query("")
        self.chosen = None
        self._open = True

    def close(self) -> None:
        """Hide the palette; it stops consuming keys immediately."""
        self._open = False

    def handle(self, event: Key | Paste) -> bool:
        """Consume an event; see the module docstring for the contract.

        A closed palette consumes nothing.  ``up``/``down`` move the list
        cursor (wrapping around the list's ends, like every menu) and are
        consumed, clearing any pending :attr:`chosen`; ``enter`` is consumed
        and delegates: the kernel's activation takes the highlighted option,
        the palette maps its value into :attr:`chosen` (``None`` when the
        query matches nothing), clears the kernel's pick and closes;
        ``escape`` closes it, consumed, with nothing chosen.  Everything
        else is the query row's: when the row consumes the event the list
        re-filters on its text and the palette answers ``True``.
        """
        if not self._open:
            return False
        if isinstance(event, Key):
            if event.name == "up":
                self.chosen = None
                self.list.move(-1)
                return True
            if event.name == "down":
                self.chosen = None
                self.list.move(1)
                return True
            if event.name == "enter":
                self.list.activate()
                option = self.list.chosen
                self.chosen = None if option is None else option.value
                self.list.chosen = None
                self.close()
                return True
            if event.name == "escape":
                self.chosen = None
                self.close()
                return True
        if self.input.handle(event):
            self.list.set_query(self.input.text)
            return True
        return False

    def render(self, width: int) -> list[Line]:
        """The query row followed by the list's rows; zero rows while closed."""
        if not self._open:
            return []
        return self.input.render(width) + self.list.render(width)

    def __repr__(self) -> str:
        return (
            f"Palette({self.commands!r}, open={self._open}, "
            f"query={self.input.text!r})"
        )
