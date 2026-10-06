"""Choice components: :class:`Option`, :class:`Select` and :class:`Confirm`.

``Select`` is the toolkit's menu: one :class:`Option` per row, one cursor,
one scroll window.  A row reads ``"\u2192 label"`` under the cursor and
``"  label"`` elsewhere -- the cursor row in the theme's ``accent``, the
others plain -- and every option's ``description`` sits in one column to the
right, measured over the whole option list so the column never jumps while
the cursor scrolls or a filter narrows the rows.  A menu longer than
``max_rows`` renders a scrolling window (the cursor row is always visible) and
a ``(i/n)`` counter row beneath it; :meth:`Select.move` wraps around the ends
by default (``wrap=False`` clamps instead).

``Confirm`` is the Yes/No specialization for destructive confirmations.  Only
the kernel is imported; no key is read here -- the editing entry points are
plain methods a host routes to.  Styles resolve once, at construction, as
explicit > theme field (``accent`` / ``dim`` / ``error``) > ``DEFAULT_THEME``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import visible_width
from ..core.theme import Theme, Themed

__all__ = ["Confirm", "Option", "Select"]

#: The cursor row's leading arrow (the classic menu pointer).
MARKER = "\u2192"

#: Columns between the widest label and its description's column.
GAP = 2


@dataclass(frozen=True)
class Option:
    """One selectable entry: a label, a payload, and an optional description."""

    label: str
    value: object = None
    description: str = ""


class Select(Themed):
    """A vertical :class:`Option` list with a cursor, a window and a counter.

    ``index`` is the cursor's row: reading it is always a row of the current
    rows, and assigning clamps into range (an empty list keeps ``0``).
    :meth:`_rows` is the one subclass seam -- the rows the cursor walks and
    the window renders; :class:`~mocode_tui.widgets.autocomplete.Autocomplete`
    overrides it with its filtered matches, everything else is shared.

    ``max_rows`` caps the rendered window (``None`` renders every row; a
    non-positive cap renders none).  While the cursor sits inside the first
    ``max_rows`` rows the window hangs at the top, then scrolls one row per
    step with the cursor row as its last -- the selected row is always on
    screen.  ``wrap`` makes :meth:`move` step from the last row to the first
    (and back) instead of stopping at the ends.  ``marker`` leads the cursor
    row; the other rows are indented by its width.  A counter row ``(i/n)``
    (the cursor's 1-based row over the row count) is rendered only while the
    window actually scrolls, so short menus stay clean.
    """

    __slots__ = (
        "_description_style",
        "_index",
        "_label_style",
        "_selected_style",
        "_title_style",
        "max_rows",
        "marker",
        "options",
        "theme",
        "title",
        "wrap",
    )

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        title: str = "",
        max_rows: int | None = 8,
        wrap: bool = True,
        marker: str = MARKER,
        label_style: Style | None = None,
        selected_style: Style | None = None,
        description_style: Style | None = None,
        title_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.options = list(options)
        self.title = title
        self.max_rows = max_rows
        self.wrap = wrap
        self.marker = marker
        # The cursor starts on the first row; ``_index`` is written directly
        # because the setter reads ``_rows()``, which a subclass may not have
        # armed yet at this point.
        self._index = 0
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._label_style = label_style if label_style is not None else NONE
        self._selected_style = self._pick(selected_style, "accent")
        self._description_style = self._pick(description_style, "dim")
        self._title_style = title_style if title_style is not None else NONE

    # -- the cursor -------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor's row of :meth:`_rows` (``0`` for an empty list)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        count = len(self._rows())
        self._index = min(max(value, 0), count - 1) if count else 0

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` rows; ``True`` when it moved.

        Wrapping (the default) steps off the last row onto the first, and off
        the first onto the last; ``wrap=False`` clamps at the ends instead.
        An empty list moves nowhere.
        """
        count = len(self._rows())
        if count <= 0:
            return False
        if self.wrap:
            target = (self._index + delta) % count
        else:
            target = min(max(self._index + delta, 0), count - 1)
        moved = target != self._index
        self._index = target
        return moved

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the rendered row ``row``; ``True`` on a hit.

        ``row`` is a 0-based row of this component's own render -- what
        :meth:`~mocode_tui.app.TUI.hit_test` reports -- so the title row
        (when there is one) is row 0, the window's rows follow, and the
        counter row (when there is one) is never an option.  ``col`` is
        ignored: every menu row owns the whole width, so the column never
        narrows a hit.
        """
        index = row - (1 if self.title else 0)
        if index < 0:
            return False
        start, stop = self._visible_range()
        target = start + index
        if not start <= target < stop:
            return False
        self._index = target
        return True

    @property
    def selected(self) -> Option | None:
        """The option under the cursor, or ``None`` for an empty list."""
        rows = self._rows()
        if not rows:
            return None
        return rows[self._index]

    # -- the rows ---------------------------------------------------------------

    def _rows(self) -> Sequence[Option]:
        """The rows the cursor walks and the window renders."""
        return self.options

    def _visible_range(self) -> tuple[int, int]:
        """The ``[start, stop)`` slice of rows rendered, at most ``max_rows``.

        The window hangs at the top while the cursor sits inside the first
        ``max_rows`` rows, then scrolls one row per step with the cursor as
        its last row -- the selected row is always on screen.
        """
        count = len(self._rows())
        cap = self.max_rows
        if cap is None or count <= cap:
            return 0, count
        if cap <= 0:
            return 0, 0
        if self._index < cap:
            return 0, cap
        return self._index - cap + 1, self._index + 1

    def _description_column(self) -> int:
        """The column every description starts at (0 when none is set).

        Measured over **every** option -- not the window or the current
        matches -- so the column holds still while the cursor scrolls and a
        filter narrows the rows.
        """
        if not any(option.description for option in self.options):
            return 0
        widest = max(visible_width(option.label) for option in self.options)
        return visible_width(self.marker) + 1 + widest + GAP

    def _row(self, option: Option, current: bool, column: int) -> Line:
        """One menu row: the marker, the label, and the description column."""
        lead = visible_width(self.marker) + 1
        style = self._selected_style if current else self._label_style
        segments = [
            Segment(f"{self.marker} " if current else " " * lead, style),
            Segment(option.label, style),
        ]
        if option.description and column:
            pad = column - lead - visible_width(option.label)
            if pad > 0:
                segments.append(Segment(" " * pad))
            segments.append(Segment(option.description, self._description_style))
        return Line(tuple(segments))

    def _counter(self) -> str:
        """The ``(i/n)`` row while the window scrolls; empty when it does not."""
        count = len(self._rows())
        cap = self.max_rows
        if cap is None or cap <= 0 or count <= cap:
            return ""
        return f"({self._index + 1}/{count})"

    def render(self, width: int) -> list[Line]:
        rows = self._rows()
        start, stop = self._visible_range()
        column = self._description_column()
        out: list[Line] = []
        if self.title:
            out.append(Line.from_text(self.title, self._title_style).fit(width))
        for i in range(start, stop):
            out.append(self._row(rows[i], i == self._index, column).fit(width))
        counter = self._counter()
        if counter:
            out.append(Line.from_text(counter, self._description_style).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Select({self.options!r}, index={self._index})"


class Confirm(Themed):
    """A Yes/No :class:`Select` specialization for confirmations.

    The options are ``Option("Yes", True)`` and ``Option("No", False)``; with
    ``danger=True`` the message renders as the title in the theme's ``error``
    style.  ``index``/``selected``/``move``/``click`` forward to the inner
    select.
    """

    __slots__ = ("_select", "danger", "message", "theme")

    def __init__(self, message: str, *, danger: bool = False, theme: Theme | None = None) -> None:
        super().__init__(theme)
        self.message = message
        self.danger = danger
        self.theme = theme
        self._select = Select(
            [Option("Yes", True), Option("No", False)],
            title=message,
            title_style=self._theme.error if danger else None,
            theme=theme,
        )

    @property
    def index(self) -> int:
        return self._select.index

    @property
    def selected(self) -> Option | None:
        return self._select.selected

    def move(self, delta: int) -> bool:
        """Move between Yes/No (wrapping, like the inner :class:`Select`)."""
        return self._select.move(delta)

    def click(self, row: int, col: int) -> bool:
        """Select Yes/No at block row ``row``; the message row is not an option.

        ``col`` is ignored -- like the inner :class:`Select`, a Yes/No row
        owns the whole width.
        """
        return self._select.click(row, col)

    def render(self, width: int) -> list[Line]:
        return self._select.render(width)

    def __repr__(self) -> str:
        return f"Confirm({self.message!r}, danger={self.danger})"
