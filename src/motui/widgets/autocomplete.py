"""Autocomplete: a query-filtered :class:`~motui.widgets.choice.Select`.

``Autocomplete`` is the filter layer of the menu family: the host feeds it a
query string with :meth:`Autocomplete.set_query` and it keeps the matching
options -- prefix matches first, then substring matches, each group in the
original order -- as the rows its inherited cursor, window, counter and row
rendering work on.  Everything else (the ``"\\u2192 "`` cursor row, the
description column, ``move`` wrapping, ``click``, the ``(i/n)`` counter) is
:class:`~motui.widgets.choice.Select`'s, shared unmodified; this module
only answers *which* rows are current.

The component is pure: it reads no keys and mounts nowhere -- keyboard
routing belongs to the host (:class:`~motui.app.command_palette.CommandPalette`
is its consumer).
"""

from __future__ import annotations

from typing import Sequence

from ..kernel.events import KeyEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Surface
from ..kernel.layout import Constraints
from ..kernel.theme import Styles, Theme
from .choice import Option, Select

__all__ = ["Autocomplete"]


class Autocomplete(Select):
    """A ``Select`` whose rows are the matches of :attr:`query`.

    ``options`` is the universe of :class:`Option` values, passed
    positionally like ``Select``'s (keyword form keeps working); ``query``
    (mutated only through :meth:`set_query`) filters it.  An **empty query
    matches every option** in the original order -- the component starts as
    a plain list.  Otherwise prefix matches rank before substring matches,
    both groups keep the option order, and an option appears at most once.
    Matching is **case-insensitive**: the query and the labels are compared
    through ``casefold()`` while the rendered label keeps its own case.

    The description column is measured over ``options`` -- the whole
    universe, not the current matches -- so it holds still while the query
    narrows the rows.
    """

    __slots__ = ("_matches", "query")

    #: The menu family's capability set (the same flags :class:`Select`
    #: publishes): the list takes the focus ring, pointer clicks and the
    #: activation verb.
    focusable = True
    clickable = True
    activatable = True

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        max_rows: int | None = 8,
        wrap: bool = True,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(
            options,
            max_rows=max_rows,
            wrap=wrap,
            glyphs=glyphs,
            theme=theme,
            styles=styles,
        )
        self.query = ""
        self._matches = list(self.options)

    def set_query(self, query: str) -> None:
        """Filter ``options`` by ``query`` and reset the cursor to the top.

        An empty query keeps every option; otherwise prefix matches come
        first, then substring matches, both compared case-insensitively.
        The cursor resets to ``0`` because the match list it indexes has just
        been replaced; the pointer's row mark is cleared (the row numbering
        it named no longer exists -- the P0 this method fixes) and the
        pending result is cleared, so a re-filter never leaks an earlier
        pick.
        """
        self._pending = None
        self._hover_row = None
        self.query = query
        if not query:
            self._matches = list(self.options)
        else:
            needle = query.casefold()
            prefix: list[Option] = []
            substring: list[Option] = []
            for option in self.options:
                label = option.label.casefold()
                if label.startswith(needle):
                    prefix.append(option)
                elif needle in label:
                    substring.append(option)
            self._matches = prefix + substring
        self.index = 0

    def _rows(self) -> Sequence[Option]:
        """The current matches -- the rows the inherited cursor walks."""
        return self._matches

    def on_key(self, e: KeyEvent) -> bool:
        """Forward one key to the inherited menu routing.

        The filter layer adds no keys of its own: :class:`Select` owns the
        cursor walk and activation, so this hook only keeps the typed door
        available on the subclass (a Select that predates the hooks routes
        through ``Widget.on_key`` -> ``handle`` unchanged).
        """
        return super().on_key(e)

    def render(self, c: Constraints) -> Surface:
        """The inherited ``Select`` row trunk, under the render constraints.

        The window, cursor row, description column and ``(i/n)`` counter all
        stay :class:`~motui.widgets.choice.Select`'s; this layer forwards the
        constraints, truncates by ``max_height`` and answers a clipped (never
        padded) surface, so the painted bytes are unchanged.
        """
        rows = list(super().render(c))
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    @property
    def is_empty(self) -> bool:
        """True when the current query matches no option."""
        return not self._matches

    def __repr__(self) -> str:
        return (
            f"Autocomplete({self.options!r}, query={self.query!r}, "
            f"index={self.index})"
        )
