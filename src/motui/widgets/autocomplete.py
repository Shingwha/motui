"""Autocomplete: a query-filtered :class:`Select`.

``set_query`` keeps prefix matches first, then substring matches, each in
original order (case-insensitive).  Cursor, window, rendering and verbs are
the inherited ``Select`` ones; the component reads no keys itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..kernel.cell import Surface
from ..kernel.events import KeyEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints
from ..kernel.theme import Styles, Theme
from .choice import Option, Select

__all__ = ["Autocomplete"]


class Autocomplete(Select):
    """A ``Select`` whose rows are the matches of :attr:`query`.

    An empty query matches every option.  Otherwise prefix matches rank
    before substring matches, both in original order, compared with
    ``casefold()``.  The description column measures all ``options``.
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
        """Filter ``options`` by ``query`` and reset cursor, hover and result.

        Prefix matches first, then substrings, case-insensitively.  The
        reset prevents a stale row mark or pending pick after re-filtering.
        """
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
        """Forward a key to the inherited menu routing; the filter adds no keys."""
        return super().on_key(e)

    def render(self, c: Constraints) -> Surface:
        """The inherited Select trunk, clipped to the constraints."""
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
