"""Strip internals: the keymap seam and the one-row label strip.

The module is private to the widget package.  :class:`Keymap` lives in
:mod:`motui.widgets.base` now and is re-exported here for the views that
still import it from this module: reading it on the class answers the
family's default table, reading it on an instance answers that instance's
own copy, so ``lst.keymap["j"] = "next"`` rebinds one widget and never
writes through to the class.  :class:`LabelStrip` is the one-row rendering
skeleton behind :class:`~motui.widgets.tabs.Tabs` and
:class:`~motui.widgets.menubar.MenuBar` -- the clamped selection over a
label sequence, the span table of the last render, the hit walk and the
hover marking.  Nothing here is re-exported from :mod:`motui.widgets`.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..kernel.cell import Line, Surface
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.text import visible_width
from ..widgets.base import Keymap, Widget
from ..widgets.cursor import Cursor

__all__ = ["Keymap", "LabelStrip"]


class LabelStrip(Widget):
    """The one-row label strip shared by ``Tabs`` and ``MenuBar``.

    The class is a skeleton, not a component: subclasses provide
    :attr:`_entries` (their label sequence) and :meth:`_layout` (the fitted
    row plus its span table), keep their own state, and set the storage
    documented below.  Every state change touches the widget, so a block's
    row cache follows a moved selection or a hovered label.  Styles are read
    through :meth:`Widget.group` at
    layout time and stored nowhere; the base supplies ``theme``, ``styles``,
    ``focused`` and ``hover``.  The shared half is the cursor, the
    hit geometry of the last render -- the span table
    ``(start, stop, index)`` per label, so ``on_click``/``on_hover`` never
    re-render -- and the one-row :meth:`render`.

    ``_last_width`` is the width the last :meth:`render` painted at -- the
    geometry :meth:`on_click` maps a column against; until the first paint it
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
        "glyphs",
    )

    #: A strip takes the keyboard through its subclass keymap, clicks on its
    #: labels and the pointer's marking; it has no activation verb (selecting
    #: is not activating).
    focusable = True
    clickable = True
    hoverable = True
    activatable = False

    def __init__(self, theme=None, styles=None) -> None:
        super().__init__(theme, styles)

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
        if changed:
            self.touch()
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
        moved = cursor.index != before
        self._index = cursor.index
        if moved:
            self.touch()
        return moved

    def on_click(self, pos: Pos) -> bool:
        """Select the label cell ``(pos.y, pos.x)`` covers; True on a hit.

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
        index = self._hit(pos.y, pos.x)
        if index is None or index in self._disabled_items:
            return False
        self.select(index)
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the label under the pointer; ``True`` when the marking changed.

        The cell resolves through :meth:`_hit`, the same walk
        :meth:`on_click` consumes, so the two can never disagree about which
        label a cell covers -- a cell no label covers, and ``None`` (the
        pointer left), answer "no label" and clear the marking.  Disabled
        labels are marked like any other (the band is the pointer's echo,
        not a selection).  The answer is whether the marked label changed.
        """
        target = None if pos is None else self._hit(pos.y, pos.x)
        changed = target != self._hover_index
        if changed:
            self._hover_index = target
            self.touch()
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

    def render(self, c: Constraints) -> Surface:
        """The strip's one row (or one empty row for an empty strip), ``fit``.

        The subclass's :meth:`_layout` supplies the row and its span table,
        and the render
        records both for the hits.  A ``max_height`` of zero paints no row
        at all (the strip's height budget is its one row), while
        ``_last_width`` still records the width the cells were measured
        against.  The surface is :meth:`Surface.clipped`, not padded.
        """
        self._last_width = c.width  # the geometry ``click`` maps a column against
        line, spans = self._layout(c.width)
        self._spans = spans
        rows = [line]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def _layout(self, width: int) -> tuple[Line, tuple[tuple[int, int, int], ...]]:
        """The strip's fitted row and the label span table, in one build."""
        raise NotImplementedError
