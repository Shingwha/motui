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
routing belongs to the host (:class:`~motui.widgets.palette.Palette`
is its consumer).
"""

from __future__ import annotations

from typing import Sequence

from ..kernel.style import Style
from ..kernel.theme import Theme
from .choice import Option, Select

__all__ = ["Autocomplete"]


class Autocomplete(Select):
    """A ``Select`` whose rows are the matches of :attr:`query`.

    ``options`` is the universe of :class:`Option` values; ``query`` (mutated
    only through :meth:`set_query`) filters it.  An **empty query matches
    every option** in the original order -- the component starts as a plain
    list.  Otherwise prefix matches rank before substring matches, both groups
    keep the option order, and an option appears at most once.  Matching is
    case-sensitive.

    The description column is measured over ``options`` -- the whole
    universe, not the current matches -- so it holds still while the query
    narrows the rows.
    """

    __slots__ = ("_matches", "query")

    def __init__(
        self,
        *,
        options: Sequence[Option] = (),
        max_rows: int | None = 8,
        wrap: bool = True,
        label_style: Style | None = None,
        selected_style: Style | None = None,
        description_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(
            options,
            max_rows=max_rows,
            wrap=wrap,
            label_style=label_style,
            selected_style=selected_style,
            description_style=description_style,
            theme=theme,
        )
        self.query = ""
        self._matches = list(self.options)

    def set_query(self, query: str) -> None:
        """Filter ``options`` by ``query`` and reset the cursor to the top.

        An empty query keeps every option; otherwise prefix matches come
        first, then substring matches.  The cursor resets to ``0`` because
        the match list it indexes has just been replaced; the pending
        :attr:`~motui.widgets.choice.Select.chosen` activation is
        cleared, so a re-filter never leaks an earlier pick.
        """
        self.chosen = None
        self.query = query
        if not query:
            self._matches = list(self.options)
        else:
            prefix: list[Option] = []
            substring: list[Option] = []
            for option in self.options:
                if option.label.startswith(query):
                    prefix.append(option)
                elif query in option.label:
                    substring.append(option)
            self._matches = prefix + substring
        self.index = 0

    def _rows(self) -> Sequence[Option]:
        """The current matches -- the rows the inherited cursor walks."""
        return self._matches

    @property
    def is_empty(self) -> bool:
        """True when the current query matches no option."""
        return not self._matches

    def __repr__(self) -> str:
        return (
            f"Autocomplete({self.options!r}, query={self.query!r}, "
            f"index={self.index})"
        )
