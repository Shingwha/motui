"""Autocomplete: a query-filtered :class:`~mocode_tui.widgets.choice.Option` list.

``Autocomplete`` is the query-driven sibling of
:class:`~mocode_tui.widgets.choice.Select`: the host feeds it a query string
with :meth:`Autocomplete.set_query` and the component keeps the matching
options -- prefix matches first, then substring matches, each group in the
original order -- with a clamped, non-wrapping cursor over them.  Rendering
yields at most ``max_rows`` rows, the selected row carrying the ``"\\u276e "``
marker inside one continuous ``selected_style`` band exactly like a ``Select``
row, hints trailing in ``hint_style``; an empty result renders zero rows.

The component is pure: it reads no keys and mounts nowhere -- keyboard
routing belongs to the host (the W6 ``SlashPalette`` is its consumer).  Only
the kernel plus :class:`Option` is imported.  ``label_style`` defaults to
``NONE``; ``selected_style``/``hint_style`` fall back to the theme's
``selection``/``dim``, matching ``Select``.
"""

from __future__ import annotations

from ..core.lines import Line
from ..core.style import NONE, Style
from ..core.theme import Theme, Themed
from .choice import Option, clamped_move, option_row

__all__ = ["Autocomplete"]


class Autocomplete(Themed):
    """A filtered ``Option`` list with a cursor, capped at ``max_rows`` rows.

    ``options`` is any iterable of :class:`Option`; ``query`` (mutated only
    through :meth:`set_query`) filters it.  An **empty query matches every
    option** in the original order -- the component starts as a plain list.
    Otherwise prefix matches rank before substring matches, both groups keep
    the option order, and an option appears at most once.  Matching is
    case-sensitive.

    ``move`` clamps inside the filtered matches (never wraps) and
    :meth:`selected` is the match under the cursor (``None`` when nothing
    matches).  When the matches outnumber ``max_rows`` the rendered window
    follows the cursor, so the selected row is always visible.  Row styles
    resolve once, at construction, as explicit > theme > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "_hint_style",
        "_label_style",
        "_matches",
        "_selected_style",
        "index",
        "max_rows",
        "options",
        "query",
        "theme",
    )

    def __init__(
        self,
        *,
        options=(),
        max_rows: int = 8,
        label_style: Style | None = None,
        hint_style: Style | None = None,
        selected_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.options = list(options)
        self.max_rows = max_rows
        self.query = ""
        self.index = 0
        self._matches = list(self.options)
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._label_style = label_style if label_style is not None else NONE
        self._selected_style = self._pick(selected_style, "selection")
        self._hint_style = self._pick(hint_style, "dim")

    def set_query(self, query: str) -> None:
        """Filter ``options`` by ``query`` and reset the cursor to the top.

        An empty query keeps every option; otherwise prefix matches come
        first, then substring matches.  The cursor resets to ``0`` because
        the match list it indexes has just been replaced.
        """
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

    def move(self, delta: int) -> bool:
        """Move the cursor by ``delta`` rows, clamped; True when it moved."""
        self.index, moved = clamped_move(self.index, len(self._matches), delta)
        return moved

    @property
    def is_empty(self) -> bool:
        """True when the current query matches no option."""
        return not self._matches

    @property
    def selected(self) -> Option | None:
        """The matched option under the cursor, or ``None`` for no match."""
        if not self._matches:
            return None
        return self._matches[self.index]

    def render(self, width: int) -> list[Line]:
        if self.is_empty or self.max_rows <= 0:
            return []
        start, stop = self._visible_range()
        out: list[Line] = []
        for i in range(start, stop):
            option = self._matches[i]
            row = option_row(
                option, i == self.index, self._label_style, self._selected_style, self._hint_style
            )
            out.append(row.fit(width))
        return out

    def _visible_range(self) -> tuple[int, int]:
        """The ``[start, stop)`` slice of matches rendered, ``max_rows`` long.

        The window hangs at the top while the cursor sits inside the first
        ``max_rows`` matches, then scrolls one row per step with the cursor
        as its last row -- the selected row is always on screen.
        """
        count = len(self._matches)
        if count <= self.max_rows:
            return 0, count
        if self.index < self.max_rows:
            return 0, self.max_rows
        return self.index - self.max_rows + 1, self.index + 1

    def __repr__(self) -> str:
        return (
            f"Autocomplete({self.options!r}, query={self.query!r}, "
            f"index={self.index})"
        )
