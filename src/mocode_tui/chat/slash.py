"""SlashPalette: the command palette a leading slash opens.

The slash menu, packaged: a list of :class:`Option` commands the host
narrows with the editor's current text.  :class:`SlashPalette` owns
**navigation and dismissal only** -- the palette and the input stay
decoupled and the menu never eats the keyboard.  :meth:`handle` consumes
only up/down/enter/escape and answers ``False`` for everything else, so
typing inside the palette's query keeps working while it is open.

Host contract: open the palette when a leading slash is *typed* (the
palette never opens itself from a query -- a dismissed palette stays
dismissed while the user keeps editing), and feed the editor's current
text to :meth:`set_query` after each edit.  :meth:`set_query` closes the
palette as soon as the text stops starting with ``"/"`` and otherwise
filters the commands through the
:class:`~mocode_tui.widgets.autocomplete.Autocomplete` kernel -- the
editor text is the query verbatim, so a command label's own leading slash
is what prefix matching keys on (``"/mod"`` matches ``/model``, ``"/"``
matches everything).  Matching is the kernel's: case-sensitive.

:meth:`handle` answers whether the palette consumed the event (``False``:
not the palette's -- the host routes it to the editor) and records a
selection in :attr:`chosen`: ``enter`` selects the highlighted command and
stores its :attr:`Option.value` there (``None`` when the query matches
nothing) and closes the palette; ``escape`` closes it with nothing
chosen.  A host reads :attr:`chosen` after a consuming ``handle`` and
resets the attribute to ``None``; navigation steps clear it themselves,
so a stale selection never survives a later keystroke.

Rendering yields zero rows while closed, so the palette slot a host pins
below its input box keeps a constant height at rest.  The row styles are
the kernel's (the theme's ``accent`` for the cursor row, ``dim`` for the
descriptions and the ``(i/n)`` counter); a host wanting a reverse-video band
passes ``theme.selection`` as the kernel's ``selected_style``.
"""

from __future__ import annotations

from ..core.events import Key, Paste
from ..core.lines import Line
from ..core.theme import Theme
from ..widgets.autocomplete import Autocomplete
from ..widgets.choice import Option

__all__ = ["SlashPalette"]


class SlashPalette:
    """A query-filtered command list that consumes only navigation keys.

    ``commands`` are the selectable :class:`Option` values (a label like
    ``"/help"``, the payload in ``value``); ``max_rows`` caps the rendered
    window (the kernel scrolls it to keep the cursor visible).  The
    palette starts closed.  :attr:`chosen` is the pending selection: the
    value of the command the last ``enter`` picked, read and cleared by
    the host.
    """

    __slots__ = ("_auto", "_open", "chosen", "commands", "max_rows", "theme")

    def __init__(
        self,
        commands: list[Option],
        *,
        theme: Theme | None = None,
        max_rows: int = 8,
    ) -> None:
        self.commands = list(commands)
        self.theme = theme
        self.max_rows = max_rows
        self._auto = Autocomplete(options=self.commands, max_rows=max_rows, theme=theme)
        self._open = False
        self.chosen: str | None = None

    @property
    def is_open(self) -> bool:
        """Whether the palette is showing (and therefore consuming keys)."""
        return self._open

    def open(self) -> None:
        """Show the full command list (the query resets; nothing selected).

        The host calls this on a freshly typed leading slash.  The list is
        unfiltered until the next :meth:`set_query`, so an open palette
        never inherits a stale query from an earlier visit -- or a stale
        :attr:`chosen` selection from one.
        """
        self._auto.set_query("")
        self.chosen = None
        self._open = True

    def close(self) -> None:
        """Hide the palette; it stops consuming keys immediately."""
        self._open = False

    def set_query(self, text: str) -> None:
        """Filter by the editor's current value; lose the slash, close.

        A text not starting with ``"/"`` closes the palette -- the leading
        slash owns it.  Otherwise the text is the
        query verbatim (the leading slash included, so labels match on
        their own prefix), case-sensitive like the kernel.
        """
        if not text.startswith("/"):
            self.close()
            return
        self._auto.set_query(text)

    def handle(self, event: Key | Paste) -> bool:
        """Consume an event; see the module docstring for the contract.

        A closed palette consumes nothing.  ``up``/``down`` move the cursor
        (wrapping around the list's ends, like every menu) and are consumed,
        clearing any pending :attr:`chosen`; ``enter`` is consumed and selects: the
        highlighted command's value lands in :attr:`chosen` (``None`` when
        the query matches nothing) and the palette closes; ``escape``
        closes it, consumed, with nothing chosen.  Everything else -- a
        :class:`~mocode_tui.core.events.Paste` included -- is not the
        palette's business and answers ``False``.
        """
        if not self._open or not isinstance(event, Key):
            return False
        if event.name == "up":
            self.chosen = None
            self._auto.move(-1)
            return True
        if event.name == "down":
            self.chosen = None
            self._auto.move(1)
            return True
        if event.name == "enter":
            selected = self._auto.selected
            self.chosen = None if selected is None else selected.value
            self.close()
            return True
        if event.name == "escape":
            self.chosen = None
            self.close()
            return True
        return False

    def render(self, width: int) -> list[Line]:
        """The filtered command rows; zero rows while closed."""
        if not self._open:
            return []
        return self._auto.render(width)

    def __repr__(self) -> str:
        return (
            f"SlashPalette({self.commands!r}, open={self._open}, "
            f"query={self._auto.query!r})"
        )
