"""Text: the plain-text component, verbatim text wrapped into rows.

The simplest component: its wrap is :func:`motui.kernel.text.wrap_text` and
each wrapped row becomes a :class:`~motui.kernel.cell.Line`.  Measurement
stays in :mod:`motui.kernel.text`; the row model stays in
:mod:`motui.kernel.cell`; this module only binds them into a component.
"""

from __future__ import annotations

from ..kernel.cell import Line, action_at
from ..kernel.style import Style
from ..kernel.text import wrap_text
from ..kernel.theme import Theme, Themed

__all__ = ["Text"]


class Text(Themed):
    """A block of plain text rendered verbatim, line by line.

    ``text`` is a mutable attribute (streaming text assigns to it).  Each
    logical line (``split("\\n")``) is word-wrapped with
    :func:`motui.kernel.text.wrap_text` into rows of at most ``width``
    columns, so blank lines survive as blank rows.  Every row carries
    ``style`` and is ``fit`` to ``width`` as a final guard.

    ``style`` defaults to ``None``, which renders as the unstyled default
    (``NONE``).  ``theme`` is read for exactly one thing: the ``hover`` band
    a hovered inline span merges (:meth:`hover_at`); verbatim text has no
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
    :class:`Clickable`: the row table of its last render lives in
    ``self._rows``, and a click or a hover resolves the cell against it
    through :func:`motui.kernel.cell.action_at`.  ``click(row, col)`` leaves
    the segment's ``action`` payload pending -- the host reads it once through
    :meth:`take_result`, which clears it -- and answers ``True`` only when
    a payload was hit; a miss declines, so the host's own policies still
    get their turn.  ``hover_at(row, col)``
    remembers the span under the pointer and answers whether the render
    changed; the span merges the theme's ``hover`` band over that segment
    **on a copy**, so the row's own text and payloads are never rewritten.
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
        "hover",
        "style",
        "text",
    )

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
        #: The pointer tier's flag: written by ``Pointer``, never read here
        #: (see the class docstring: this component's visual is the span).
        self.hover = False
        #: The pending pick: ``click`` lands a hit segment's action here and
        #: the host reads it once through :meth:`take_result`.
        self._pending: str | None = None
        # The one themed style: the pointer-hover band, resolved once (there
        # is no explicit hover_style= parameter to win over it).
        self._hover_style = self.pick(None, self._theme.surfaces.hover)
        #: The row table of the last render; geometry for click/hover_at.
        self._rows: list[Line] = []
        #: The span under the pointer: ``(row, start, end)`` or ``None``.
        self._hover_span: tuple[int, int, int] | None = None

    def _rows_for(self, width: int) -> list[Line]:
        """The rows ``text`` renders to: the subclass seam for inline spans.

        The default is verbatim text: one ``Line`` per wrapped piece.  A
        subclass that wants clickable/hoverable spans returns ``Line`` values
        whose segments carry ``link`` / ``action`` payloads instead -- the
        inherited ``render`` keeps the table it returns for ``click`` and
        ``hover_at``, with no further wiring.
        """
        out: list[Line] = []
        for row in self.text.split("\n"):
            for piece in wrap_text(row, width):
                out.append(Line.from_text(piece, self.style).fit(width))
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

    def render(self, width: int) -> list[Line]:
        """Wrap ``text`` to ``width`` and return the rows (always a fresh list).

        The render is pure: every call runs :meth:`_rows_for`, and the one
        row cache in the stack is :meth:`motui.kernel.document.Section.rows`
        (which keys on this component's :meth:`revision`).  The hover
        transform follows on a copy, so the last-render table never carries
        the band.

        The row table is also kept on ``self`` (``_rows``), because the
        hit testing of ``click`` / ``hover_at`` reads the geometry of the
        **last render**: with no hovered span that table is the hover-free
        rows, byte-for-byte what this component always rendered, and a
        hovered span answers that row rebuilt with the theme's ``hover``
        merged onto the span -- a copy, so the last-render row itself stays
        hover-free.
        """
        rows = self._rows_for(width)
        self._rows = rows
        span = self._hover_span
        if span is None:
            return list(rows)
        index, start, end = span
        out = list(rows)
        if 0 <= index < len(out):
            out[index] = out[index].merge_span(start, end, self._hover_style)
        return out

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the cell under the pointer; answer whether the render changed.

        ``row < 0`` (the pointer left) clears the mark.  The cell resolves
        against the last render's row table through
        :func:`motui.kernel.cell.action_at`: a column inside a segment with
        an ``action`` remembers ``(row, start, end)``, anything else -- a
        plain run, a column past the row -- clears it.  The answer is whether
        that span differs from the one remembered, which is exactly whether
        the frame repaints.
        """
        span: tuple[int, int, int] | None = None
        if row >= 0 and row < len(self._rows):
            hit = action_at(self._rows[row], col)
            if hit is not None:
                span = (row, hit[1], hit[2])
        changed = span != self._hover_span
        self._hover_span = span
        return changed

    def click(self, row: int, col: int) -> bool:
        """Take the action under ``(row, col)`` as the pending result; hit?

        The hit is :func:`motui.kernel.cell.action_at` against the last
        render's row table, so the column must land inside a segment that
        carries an ``action``.  A hit leaves that payload pending -- read
        once through :meth:`take_result`, which clears it -- and answers
        ``True``; a miss -- a plain run, a column outside the row -- answers
        ``False`` and consumes nothing, leaving the cell to whatever the host
        does next.
        """
        if 0 <= row < len(self._rows):
            hit = action_at(self._rows[row], col)
            if hit is not None:
                self._pending = hit[0]
                return True
        return False

    def take_result(self) -> str | None:
        """Read the pending action payload once and clear it."""
        value = self._pending
        self._pending = None
        return value

    def __repr__(self) -> str:
        return f"Text({self.text!r})"
