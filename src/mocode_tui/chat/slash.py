"""SlashPalette: the command palette a leading slash opens.

The pi-style slash menu, packaged: a list of :class:`Option` commands the
host narrows with the editor's current text.  :class:`SlashPalette` owns
**navigation and dismissal only** -- exactly the demo's rule that the
palette and the input stay decoupled and the menu never eats the
keyboard.  Every key that is not up/down/enter/escape answers ``False``
and falls through to the editor, so typing inside the palette's query
keeps working while it is open.

Host contract: open the palette when a leading slash is *typed* (the
palette never opens itself from a query -- a dismissed palette stays
dismissed while the user keeps editing, which is what the demo does), and
feed the editor's current value to :meth:`sync_query` after each edit.
:meth:`sync_query` closes the palette as soon as the text stops starting
with ``"/"`` and otherwise filters the commands through the
:class:`~mocode_tui.widgets.autocomplete.Autocomplete` kernel -- the
editor value is the query verbatim, so a command label's own leading
slash is what prefix matching keys on (``"/mod"`` matches ``/model``,
``"/"`` matches everything).  Matching is the kernel's: case-sensitive.

:meth:`handle_key` answers one of three things:

``False``
    the event is not the palette's -- the host routes it to the editor;
``None``
    the event was consumed but selected nothing (a navigation step, or a
    dismissal);
a ``str``
    ``enter`` selected a command: its :attr:`Option.value`, with the
    palette closed.

Rendering yields zero rows while closed, so the palette slot a host pins
below its input box keeps a constant height at rest.  The row styles are
the kernel's (the theme's ``selection`` for the selected row); the demo
painted its selection in reverse video, a demo-specific choice the
library leaves to a custom theme instead.
"""

from __future__ import annotations

from ..core.lines import Line
from ..core.theme import Theme
from ..keys.events import Key, Paste
from ..widgets.autocomplete import Autocomplete
from ..widgets.choice import Option

__all__ = ["SlashPalette"]


class SlashPalette:
    """A query-filtered command list that consumes only navigation keys.

    ``commands`` are the selectable :class:`Option` values (a label like
    ``"/help"``, the payload in ``value``); ``max_rows`` caps the rendered
    window (the kernel scrolls it to keep the cursor visible).  The
    palette starts closed.
    """

    __slots__ = ("_auto", "_open", "commands", "max_rows", "theme")

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

    @property
    def is_open(self) -> bool:
        """Whether the palette is showing (and therefore consuming keys)."""
        return self._open

    def open(self) -> None:
        """Show the full command list (the query resets; nothing selected).

        The host calls this on a freshly typed leading slash.  The list is
        unfiltered until the next :meth:`sync_query`, so an open palette
        never inherits a stale query from an earlier visit.
        """
        self._auto.set_query("")
        self._open = True

    def close(self) -> None:
        """Hide the palette; it stops consuming keys immediately."""
        self._open = False

    def sync_query(self, text: str) -> None:
        """Filter by the editor's current value; lose the slash, close.

        A text not starting with ``"/"`` closes the palette -- the leading
        slash owns it, exactly as in the demo.  Otherwise the text is the
        query verbatim (the leading slash included, so labels match on
        their own prefix), case-sensitive like the kernel.
        """
        if not text.startswith("/"):
            self.close()
            return
        self._auto.set_query(text)

    def handle_key(self, key: Key | Paste) -> str | None | False:
        """Route one event; see the module docstring for the three answers.

        ``up``/``down`` move the (clamped, non-wrapping) cursor and are
        consumed; ``enter`` answers the selected command's value and
        closes -- ``None`` when the query matches nothing; ``escape``
        closes and answers ``None``.  Everything else, a
        :class:`~mocode_tui.keys.events.Paste` included, is not the
        palette's business and answers ``False``.
        """
        if not self._open or not isinstance(key, Key):
            return False
        if key.name == "up":
            self._auto.move(-1)
            return None
        if key.name == "down":
            self._auto.move(1)
            return None
        if key.name == "enter":
            selected = self._auto.selected
            value = None if selected is None else selected.value
            self.close()
            return value
        if key.name == "escape":
            self.close()
            return None
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
