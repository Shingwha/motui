"""Choice components: :class:`Option`, :class:`Select` and :class:`Confirm`.

``Select`` is the toolkit's menu: one :class:`Option` per row, one cursor,
one scroll window.  A row reads ``"\u2192 label"`` under the cursor and
``"  label"`` elsewhere -- the cursor row in the theme's ``accent``, the
others plain -- and every option's ``description`` sits in one column to the
right, measured over the whole option list so the column never jumps while
the cursor scrolls or a filter narrows the rows.  A menu longer than
``max_rows`` renders a scrolling window (the cursor row is always visible) and
a ``(i/n)`` counter row beneath it; :meth:`Select.move` wraps around the ends
by default (``wrap=False`` clamps instead).  :meth:`Select.activate` is the
menu's activation -- it takes the option under the cursor into
:attr:`Select.chosen`, which the host reads once; moving the cursor or
re-filtering clears it.

``Confirm`` is the Yes/No specialization for destructive confirmations.  Only
the kernel is imported; no key is read here -- the editing entry points are
plain methods a host routes to.  Styles resolve once, at construction, as
explicit > theme field (``accent`` / ``dim`` / ``error``) > ``DEFAULT_THEME``.
``focused`` is the focus flag the focus tier sets (an unfocused cursor row
renders ``selected_style.merge(theme.dim)``), and ``hover_at`` is the
pointer tier's row marking (the marked row merges the theme's ``hover``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..kernel.lines import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed

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
    the window renders; :class:`~motui.widgets.autocomplete.Autocomplete`
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

    :meth:`activate` is the menu's activation: it takes the option under
    the cursor into :attr:`chosen` and answers whether there was one to
    take.  A host calls it on the return key, reads ``chosen`` once, then
    resets it to ``None``; :meth:`move` and
    :meth:`~motui.widgets.autocomplete.Autocomplete.set_query` clear
    it, so a stale pick never survives the next keystroke.

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.block.Focusable`): while it is ``True`` the
    cursor row renders in ``selected_style``; while it is ``False`` that
    style is merged with the theme's ``dim`` -- the cursor stays legible
    but loses weight, and nothing else on the row changes (the
    description column keeps its own ``dim``).

    ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.block.Hoverable`);
    :meth:`hover_at` marks the option row under the pointer -- resolved
    through the same arithmetic :meth:`click` uses -- and the marked row
    renders its existing style merged with the theme's ``hover``.  The
    marking lives in one private row index that starts ``None``, so an
    un-hovered menu renders byte-for-byte what it always did.
    """

    __slots__ = (
        "_description_style",
        "_dim",
        "_hover_row",
        "_hover_style",
        "_index",
        "_label_style",
        "_selected_style",
        "_title_style",
        "chosen",
        "focused",
        "hover",
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
        focused: bool = True,
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
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`hover_at`).
        self.hover = False
        # The cursor starts on the first row; ``_index`` is written directly
        # because the setter reads ``_rows()``, which a subclass may not have
        # armed yet at this point.
        self._index = 0
        # The option row the pointer is on (its data-row index), or ``None``;
        # written by ``hover_at``, read by ``render``.  ``None`` renders
        # byte-for-byte what the menu always did.
        self._hover_row: int | None = None
        # The pending activation: written by ``activate``, read once by the
        # host, cleared by ``move`` and by a re-filter.
        self.chosen: Option | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._label_style = label_style if label_style is not None else NONE
        self._selected_style = self._pick(selected_style, "accent")
        self._description_style = self._pick(description_style, "dim")
        self._title_style = title_style if title_style is not None else NONE
        self._dim = self._pick(None, "dim")
        self._hover_style = self._pick(None, "hover")

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
        An empty list moves nowhere.  Stepping clears the pending
        :attr:`chosen` activation: a stale pick never survives the next
        keystroke.
        """
        self.chosen = None
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
        :meth:`~motui.app.TUI.hit_test` reports -- so the title row
        (when there is one) is row 0, the window's rows follow, and the
        counter row (when there is one) is never an option.  ``col`` is
        ignored: every menu row owns the whole width, so the column never
        narrows a hit.
        """
        target = self._option_at(row)
        if target is None:
            return False
        self._index = target
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the option row under a cell; ``True`` when the marking changed.

        The pointer tier's row-level half (D3): ``row`` is a 0-based row of
        this component's own render, resolved through the very arithmetic
        :meth:`click` uses (:meth:`_option_at`) -- the title row above the
        window and the counter row below it carry no option, and a marking
        on them is cleared -- and ``col`` is ignored like ``click``'s.  A
        negative ``row`` clears the marking: the pointer left.  The answer
        is whether the marked row actually changed, so a motion inside one
        row answers ``False`` (nothing to repaint), and
        :meth:`render` merges the theme's ``hover`` over the marked row's
        own style.
        """
        target = None if row < 0 else self._option_at(row)
        changed = target != self._hover_row
        self._hover_row = target
        return changed

    @property
    def selected(self) -> Option | None:
        """The option under the cursor, or ``None`` for an empty list."""
        rows = self._rows()
        if not rows:
            return None
        return rows[self._index]

    def activate(self) -> bool:
        """Take the option under the cursor into :attr:`chosen`.

        The menu's :class:`~motui.kernel.block.Activable` verb: a host
        routes the return key here, then reads ``chosen`` once -- the
        option that was taken -- and resets it to ``None``.  Answers
        whether there was something to take (``False``, and ``chosen``
        stays ``None``, for an empty list).
        """
        self.chosen = self.selected
        return self.chosen is not None

    # -- the rows ---------------------------------------------------------------

    def _rows(self) -> Sequence[Option]:
        """The rows the cursor walks and the window renders."""
        return self.options

    def _option_at(self, row: int) -> int | None:
        """The data-row index a rendered row carries, or ``None``.

        The one row arithmetic :meth:`click` and :meth:`hover_at` share: the
        title row (``row 0`` when there is one) sits above the window, the
        counter row below it, and neither carries an option -- as does
        every cell past the window.  Negative rows answer ``None`` too.
        """
        index = row - (1 if self.title else 0)
        if index < 0:
            return None
        start, stop = self._visible_range()
        target = start + index
        return target if start <= target < stop else None

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

    def _row(self, option: Option, current: bool, column: int, hovered: bool = False) -> Line:
        """One menu row: the marker, the label, and the description column.

        The cursor row's style is the focus rule in one line: unfocused, the
        marker and the label render in ``selected_style.merge(dim)`` (the
        description keeps its own ``dim``).  A hovered row merges the theme's
        ``hover`` on top of whatever its own style resolved to (the cursor
        row's included) -- marker and label only, the description column
        keeping its own style exactly as the focus rule leaves it.
        """
        lead = visible_width(self.marker) + 1
        style = self._selected_style if current else self._label_style
        if current and not self.focused:
            style = style.merge(self._dim)  # unfocused: keep the hue, lose the weight
        if hovered:
            style = style.merge(self._hover_style)
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

    def _revision(self) -> object:
        """The value snapshot of everything the menu's rows are made of.

        The rows themselves (``tuple(_rows())`` -- the subclass seam, so an
        ``Autocomplete`` snapshots its current matches), the whole option
        universe (the description column is measured over *it*, never the
        window or the filter), the title, the marker, the window cap, the
        cursor, the pointer's mark, the focus flag and the six resolved
        styles -- all plain values, so the tuple is a copy by construction.
        A pending :attr:`chosen` is deliberately out: no row reads it.
        """
        return (
            tuple(self._rows()),
            tuple(self.options),
            self.title,
            self.marker,
            self.max_rows,
            self._index,
            self._hover_row,
            self.focused,
            self._label_style,
            self._selected_style,
            self._description_style,
            self._title_style,
            self._dim,
            self._hover_style,
        )

    def revision(self) -> object:
        """The :class:`~motui.kernel.block.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a block holding this menu
        keys its own row cache on the same value, so a moved cursor, a
        re-filter or a hover invalidates the block's copy -- and a
        **sealed** menu's cursor band finally reaches the screen (D4).
        """
        return self._revision()

    def render(self, width: int) -> list[Line]:
        rows = self._rows()
        start, stop = self._visible_range()
        column = self._description_column()
        out: list[Line] = []
        if self.title:
            out.append(Line.from_text(self.title, self._title_style).fit(width))
        for i in range(start, stop):
            out.append(
                self._row(
                    rows[i], i == self._index, column, i == self._hover_row
                ).fit(width)
            )
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
    style.  ``index``/``selected``/``chosen``/``focused``/``hover``/``move``/
    ``activate``/``click``/``hover_at`` forward to the inner select.
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

    @property
    def chosen(self) -> Option | None:
        """The option the last :meth:`activate` took; the host reads it once."""
        return self._select.chosen

    @chosen.setter
    def chosen(self, value: Option | None) -> None:
        self._select.chosen = value

    @property
    def focused(self) -> bool:
        """The focus flag of the inner select (see :class:`Select`)."""
        return self._select.focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._select.focused = value

    @property
    def hover(self) -> bool:
        """The hover flag of the inner select (see :class:`Select`)."""
        return self._select.hover

    @hover.setter
    def hover(self, value: bool) -> None:
        self._select.hover = value

    def move(self, delta: int) -> bool:
        """Move between Yes/No (wrapping, like the inner :class:`Select`)."""
        return self._select.move(delta)

    def activate(self) -> bool:
        """Take Yes/No into :attr:`chosen`: ``Option("Yes", True)`` or ``Option("No", False)``."""
        return self._select.activate()

    def click(self, row: int, col: int) -> bool:
        """Select Yes/No at block row ``row``; the message row is not an option.

        ``col`` is ignored -- like the inner :class:`Select`, a Yes/No row
        owns the whole width.
        """
        return self._select.click(row, col)

    def hover_at(self, row: int, col: int) -> bool:
        """Mark Yes/No under a cell; forwards to the inner :class:`Select`."""
        return self._select.hover_at(row, col)

    def revision(self) -> object:
        """The inner select's snapshot, forwarded -- a Confirm renders its rows.

        :meth:`render` is the inner :class:`Select`'s, so the component's
        rows are a pure function of the same value the select answers; the
        forward is what lets a **sealed** confirmation's cursor band reach
        the screen, exactly as it does for the bare menu.
        """
        return self._select.revision()

    def render(self, width: int) -> list[Line]:
        return self._select.render(width)

    def __repr__(self) -> str:
        return f"Confirm({self.message!r}, danger={self.danger})"
