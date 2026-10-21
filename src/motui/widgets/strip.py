"""Strip internals: the clamped cursor and the one-row label strip.

The module is private to the widget package.  :class:`ClampedCursor` is the
selection half of a label strip -- ``index`` / ``select`` / ``move`` over a
label sequence and a disabled-index set -- and :class:`LabelStrip` adds the
one-row rendering skeleton: the span table of the last render, the hit walk
and the hover marking.  The public components are
:class:`~motui.widgets.tabs.Tabs` and
:class:`~motui.widgets.menubar.MenuBar`; nothing here is re-exported from
:mod:`motui.widgets`.
"""

from __future__ import annotations

from typing import Sequence

from ..kernel.cursor import Cursor
from ..kernel.lines import Line
from ..kernel.text import visible_width
from ..kernel.theme import Themed

__all__ = ["ClampedCursor", "LabelStrip"]


class ClampedCursor:
    """A clamped, non-wrapping cursor over a disabled-aware label sequence.

    The mixin owns no storage: subclasses keep the ``_index``,
    ``_disabled_items`` and ``disabled`` slots and implement
    :attr:`_entries`.  :meth:`select` clamps into ``0..len-1`` and refuses a
    disabled index (or a disabled control); :meth:`move` steps over disabled
    indices, clamps at the ends and never wraps.  ``revision()`` stays with
    each component: the value it snapshots is the component's own.
    """

    __slots__ = ()

    _index: int
    _disabled_items: frozenset[int]
    disabled: bool

    @property
    def _entries(self) -> Sequence[str]:
        """The label sequence every cursor verb measures; subclasses implement."""
        raise NotImplementedError

    @property
    def index(self) -> int:
        """The selected index, always inside the entry range.

        Read-only: :meth:`select` and :meth:`move` are the moving doors.
        """
        return self._index

    def _cursor(self) -> Cursor:
        """The cursor value over the entries and the disabled set."""
        return Cursor(
            len(self._entries),
            index=self._index,
            disabled=self._disabled_items,
        )

    def select(self, index: int) -> bool:
        """Select ``index``, clamped into range; True when it changed.

        A ``disabled`` index is refused outright -- ``False``, nothing
        moved -- a disabled control refuses every selection, and an empty
        sequence answers ``False`` always.
        """
        if self.disabled or not self._entries:
            return False
        cursor = self._cursor()
        changed = cursor.select(index)
        self._index = cursor.index
        return changed

    def move(self, delta: int) -> bool:
        """Move the selection ``delta`` labels, clamped and never wrapping.

        Disabled indices are **stepped over**: a positive step from index 1
        with 2 disabled lands on 3, and a step whose direction holds no
        enabled index left stays where it was (``False``).  A disabled
        control moves nowhere.  The answer is whether the selection changed.
        """
        if self.disabled or not self._entries or delta == 0:
            return False
        before = self._index
        cursor = self._cursor()
        cursor.move(delta)
        # A stale cursor (a host replaced the entries in place) is clamped
        # like any other request, and the clamping itself is a move.
        cursor.index = cursor.clamp(cursor.index)
        self._index = cursor.index
        return cursor.index != before


class LabelStrip(ClampedCursor, Themed):
    """The one-row label strip shared by ``Tabs`` and ``MenuBar``.

    The class is a skeleton, not a component: subclasses provide
    :attr:`_entries` (their label sequence) and :meth:`_layout` (the fitted
    row plus its span table), keep their own styles and ``revision()``, and
    set the storage documented below.  The shared half is the cursor, the
    hit geometry of the last render -- the span table
    ``(start, stop, index)`` per label, so ``click``/``hover_at`` never
    re-render -- and the one-row :meth:`render`.

    ``_last_width`` is the width the last :meth:`render` painted at -- the
    geometry :meth:`click` maps a column against; until the first paint it
    is 80, the same convention as ``TextBuffer.last_width``.  ``_spans`` is
    the last render's span table (``None`` until the first paint, when a hit
    builds it once without calling ``render``).  The marking starts
    ``None``, so an un-hovered strip renders exactly the bytes it always
    did.  A hit resolves only on row 0: the leading and trailing padding,
    every divider gap, a cell past the last label and a truncating ``fit``
    all answer no label.
    """

    __slots__ = (
        "_disabled_items",
        "_hover_index",
        "_index",
        "_last_width",
        "_spans",
        "disabled",
        "focused",
        "glyphs",
        "hover",
        "theme",
    )

    def click(self, row: int, col: int) -> bool:
        """Select the label cell ``(row, col)`` covers; True on a hit.

        The cell resolves through :meth:`_hit`, the walk over this
        component's own last render: the column of the strip's one row, or
        no label -- the leading and trailing padding, every divider gap, a
        cell past the last label and a truncating ``fit`` all answer no
        label, and so does any row but the first.  A hit on a **disabled**
        label (or on a disabled strip) answers ``False`` and changes
        nothing; a hit on an enabled one selects it -- even when it already
        was active -- and answers ``True``.
        """
        if self.disabled:
            return False
        index = self._hit(row, col)
        if index is None or index in self._disabled_items:
            return False
        self.select(index)
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the label under a cell; ``True`` when the marking changed.

        The cell resolves through :meth:`_hit`, the same walk :meth:`click`
        consumes, so the two can never disagree about which label a cell
        covers -- a cell no label covers, and a negative ``row`` (the
        pointer left), answer "no label" and clear the marking.  Disabled
        labels are marked like any other (the band is the pointer's echo,
        not a selection).  The answer is whether the marked label changed.
        """
        target = None if row < 0 else self._hit(row, col)
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def _hit(self, row: int, col: int) -> int | None:
        """The label index a cell covers on the strip's one row, or ``None``."""
        if row != 0:
            return None
        return self._label_at(col)

    def _label_at(self, col: int) -> int | None:
        """The label index a column of the last render covers, or ``None``.

        The hit reads the **span table** the last :meth:`render` recorded --
        ``(start, stop, index)`` tuples in paint order, measured on the
        fitted row, so the leading and trailing padding, every divider gap
        and a truncating ``fit`` marker pass by exactly as they did when the
        table was walked per hit.  Before the first paint the table is built
        once at the default width (the old ``_last_width`` convention);
        after it, no render runs from a hit (the P0).
        """
        if not self._entries:
            return None
        spans = self._spans
        if spans is None:
            _, spans = self._layout(self._last_width)
            self._spans = spans
        for start, stop, index in spans:
            if start <= col < stop:
                return index
        return None

    def _spans_of(self, line: Line) -> tuple[tuple[int, int, int], ...]:
        """The label spans of a fitted row, by the render's own segment walk.

        A label segment is recognized by its text matching the entry's
        label, so padding, dividers and a truncating ellipsis (which changes
        the segment's text) carry no span -- the walk the old per-hit table
        ran, now recorded once per render.
        """
        spans: list[tuple[int, int, int]] = []
        names = self._entries
        x, seen = 0, 0
        for segment in line.segments:
            span = visible_width(segment.text)
            if seen < len(names) and segment.text == names[seen]:
                spans.append((x, x + span, seen))
                seen += 1
            x += span
        return tuple(spans)

    def render(self, width: int) -> list[Line]:
        """The strip's one row (or one empty row for an empty strip), ``fit``.

        The subclass's :meth:`_layout` supplies the row and its span table;
        the render records both for the hits.  ``_last_width`` is the
        geometry :meth:`click` maps a column against.
        """
        self._last_width = width  # the geometry ``click`` maps a column against
        line, spans = self._layout(width)
        self._spans = spans
        return [line]

    def _layout(self, width: int) -> tuple[Line, tuple[tuple[int, int, int], ...]]:
        """The strip's fitted row and the label span table, in one build."""
        raise NotImplementedError
