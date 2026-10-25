"""Text: the plain-text component, verbatim text wrapped into rows.

The simplest component: its wrap is :func:`motui.kernel.text.wrap_text` and
each wrapped row becomes a :class:`~motui.kernel.cell.Line`.  Measurement
stays in :mod:`motui.kernel.text`; the row model stays in
:mod:`motui.kernel.cell`; this module only binds them into a component.
"""

from __future__ import annotations

from ..kernel.cell import Line, Surface, action_at
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from .base import Widget

__all__ = ["Text"]


class Text(Widget):
    """A block of plain text rendered verbatim, line by line.

    ``text`` is a mutable attribute (streaming text assigns to it).  Each
    logical line (``split("\\n")``) is word-wrapped with
    :meth:`motui.kernel.cell.Line.reflow` (``WrapMode.WORD``) into rows of at
    most ``width`` columns, so blank lines survive as blank rows.  Every row
    carries ``style``; the wrap itself is the final width guard.

    ``style`` defaults to ``None``, which renders as the unstyled default
    (``NONE``).  ``theme`` is read for exactly one thing: the ``hover`` band
    a hovered inline span merges (:meth:`on_hover`); verbatim text has no
    other theme-able style of its own.

    **Caching.**  Wrapping a long text is the most expensive render the
    toolkit has, and a host re-renders the same component frame after frame
    (every mouse move repaints).  The cache lives in **one** place:
    :meth:`motui.kernel.document.Section.rows`, which remembers a sealed (or
    revisioned) section's rows by width and :meth:`revision`.  ``render``
    itself is pure -- every standalone call re-wraps -- so a component
    handed straight to a caller never serves a stale row; behind a section,
    the section's cache answers the repeats.  The hit table :attr:`_rows`
    keeps its "last render" meaning and is geometry, not a cache.

    **Inline actions.**  ``Text`` is :class:`Hoverable` and
    :class:`Clickable` (and, in 2.0 terms, ``clickable`` / ``hoverable``):
    the row table of its last render lives in ``self._rows``, and a click or
    a hover resolves the cell against it through
    :func:`motui.kernel.cell.action_at`.  ``on_click(pos)`` leaves the
    segment's ``action`` payload pending -- the host reads it once through
    :meth:`take`, which clears it -- and answers ``True`` only when a payload
    was hit; a miss declines, so the host's own policies still get their
    turn.  ``on_hover(pos)`` remembers the span under the pointer and answers
    whether the render changed; the span merges the theme's ``hover`` band
    over that segment **on a copy**, so the row's own text and payloads are
    never rewritten.  The 1.x ``click(row, col)`` / ``hover_at(row, col)``
    verbs are thin aliases until W3b3 deletes them.
    The component-level :attr:`hover` flag is the protocol's peer of
    ``focused`` and changes nothing by itself: this component's visual is
    the span, so a whole-row band would be wrong (``Pointer`` sets the flag
    and calls ``hover_at`` on the same move).

    The default rows carry no payloads -- a plain row is verbatim text --
    so a subclass that wants spans renders its own ``Line`` values through
    :meth:`_rows_for` and inherits the hit testing, the hover transform and
    the one-shot result unchanged.
    """

    __slots__ = (
        "_hover_span",
        "_hover_style",
        "_pending",
        "_rows",
        "style",
        "text",
    )

    #: A plain text block takes pointer clicks (inline ``action`` payloads)
    #: and pointer hovers (the span band); it has no focus or activation.
    clickable = True
    hoverable = True

    def __init__(
        self,
        text: str = "",
        *,
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.text = text
        self.style = style
        #: The pending pick: ``on_click`` lands a hit segment's action here
        #: and the host reads it once through :meth:`take`.
        self._pending: str | None = None
        # The one themed style: the pointer-hover band, resolved once (there
        # is no explicit hover_style= parameter to win over it).
        self._hover_style = self.group("surfaces").hover
        #: The row table of the last render; geometry for on_click/on_hover.
        self._rows: list[Line] = []
        #: The span under the pointer: ``(row, start, end)`` or ``None``.
        self._hover_span: tuple[int, int, int] | None = None

    def _rows_for(self, width: int) -> list[Line]:
        """The rows ``text`` renders to: the subclass seam for inline spans.

        The default is verbatim text: one ``Line`` per wrapped piece.  A
        subclass that wants clickable/hoverable spans returns ``Line`` values
        whose segments carry ``link`` / ``action`` payloads instead -- the
        inherited ``render`` keeps the table it returns for ``on_click`` and
        ``on_hover``, with no further wiring.
        """
        out: list[Line] = []
        for row in self.text.split("\n"):
            out.extend(Line.from_text(row, self.style).reflow(WrapMode.WORD, width))
        return out

    def _revision(self) -> object:
        """The value snapshot of everything the rows are made of.

        The default answers ``(text, style, hover span, hover style)`` --
        all four are row inputs: the text wraps, the style lands on every
        segment, and the span (with the band it merges) is what a hovered
        render answers.  This is the **overridable seam** for subclasses
        (the same tier as :meth:`_rows_for`): a subclass whose rows depend
        on more state adds that state to the tuple, and one whose state
        cannot be snapshotted cheaply returns ``None``, which switches block
        caching off rather than risking a stale hit.  The snapshot must be a
        value (no live mutable fields) and must cost far less than the
        wrap it guards.
        """
        return (self.text, self.style, self._hover_span, self._hover_style)

    def revision(self) -> object:
        """The :class:`~motui.kernel.document.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a section holding this
        component keys its own row cache on the same value, so a streamed
        ``text =`` assignment or a moved hover span invalidates the
        section's copy in one move.  The component keeps no row cache of its
        own.
        """
        return self._revision()

    def render(self, c: Constraints) -> Surface:
        """Wrap ``text`` to the constraints and return a clipped surface.

        A ``max_height`` budget
        truncates the wrapped rows (a text block never grows past the height
        it was offered).  The surface is :meth:`Surface.clipped`, not padded:
        short rows keep their natural width, so the bytes a layout paints are
        the same ones the 1.x list answer produced.

        The render is pure: every call runs :meth:`_rows_for`, and the one
        row cache in the stack is :meth:`motui.kernel.document.Section.rows`
        (which keys on this component's :meth:`revision`).  The hover
        transform follows on a copy, so the last-render table never carries
        the band.

        The row table is also kept on ``self`` (``_rows``), because the
        hit testing of ``on_click`` / ``on_hover`` reads the geometry of the
        **last render**: with no hovered span that table is the hover-free
        rows, byte-for-byte what this component always rendered, and a
        hovered span answers that row rebuilt with the theme's ``hover``
        merged onto the span -- a copy, so the last-render row itself stays
        hover-free.
        """
        rows = self._rows_for(c.width)
        if c.max_height is not None:
            rows = rows[: c.max_height]
        self._rows = rows
        span = self._hover_span
        if span is None:
            return Surface.clipped(rows, c.width)
        index, start, end = span
        out = list(rows)
        if 0 <= index < len(out):
            out[index] = out[index].merge_span(start, end, self._hover_style)
        return Surface.clipped(out, c.width)

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the cell under the pointer; answer whether the render changed.

        ``None`` (the pointer left) clears the mark.  The cell resolves
        against the last render's row table through
        :func:`motui.kernel.cell.action_at`: a column inside a segment with
        an ``action`` remembers ``(row, start, end)``, anything else -- a
        plain run, a column past the row -- clears it.  The answer is whether
        that span differs from the one remembered, which is exactly whether
        the frame repaints.
        """
        span: tuple[int, int, int] | None = None
        if pos is not None and 0 <= pos.y < len(self._rows):
            hit = action_at(self._rows[pos.y], pos.x)
            if hit is not None:
                span = (pos.y, hit[1], hit[2])
        changed = span != self._hover_span
        self._hover_span = span
        return changed

    def hover_at(self, row: int, col: int) -> bool:
        """The 1.x cell spelling of :meth:`on_hover` (``row < 0`` leaves)."""
        return self.on_hover(Pos(y=row, x=col) if row >= 0 else None)

    def on_click(self, pos: Pos) -> bool:
        """Take the action under ``pos`` as the pending result; hit?

        The hit is :func:`motui.kernel.cell.action_at` against the last
        render's row table, so the column must land inside a segment that
        carries an ``action``.  A hit leaves that payload pending -- read
        once through :meth:`take`, which clears it -- and answers ``True``;
        a miss -- a plain run, a column outside the row -- answers ``False``
        and consumes nothing, leaving the cell to whatever the host does
        next.
        """
        if 0 <= pos.y < len(self._rows):
            hit = action_at(self._rows[pos.y], pos.x)
            if hit is not None:
                self._pending = hit[0]
                return True
        return False

    def click(self, row: int, col: int) -> bool:
        """The 1.x cell spelling of :meth:`on_click`."""
        return self.on_click(Pos(y=row, x=col))

    def take(self) -> str | None:
        """Read the pending action payload once and clear it."""
        value = self._pending
        self._pending = None
        return value

    def take_result(self) -> str | None:
        """The 1.x alias of :meth:`take`."""
        return self.take()

    def __repr__(self) -> str:
        return f"Text({self.text!r})"
