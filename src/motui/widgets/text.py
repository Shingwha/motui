"""Text: the plain-text component, verbatim text wrapped into rows.

The wrap is the kernel's word wrap; each wrapped row becomes a ``Line``.
The module only binds measurement and the row model into a component.
"""

from __future__ import annotations

from ..kernel.cell import Line, Surface, action_at
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from .base import ResultWidget

__all__ = ["Text"]


class Text(ResultWidget):
    """A block of plain text rendered verbatim, line by line.

    Each logical line word-wraps to ``width``; blank lines survive.  Every
    row carries ``style`` (``None`` = unstyled).  ``render`` is pure; the
    one row cache is the section's.  Inline ``action`` spans are clickable
    and hoverable: ``on_click`` leaves the payload pending, ``on_hover``
    marks the span (merged on a copy).  Subclasses can render spans through
    :meth:`_rows_for`.
    """

    __slots__ = (
        "_hover_span",
        "_hover_style",
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
        # The one themed style: the pointer-hover band, resolved once (there
        # is no explicit hover_style= parameter to win over it).
        self._hover_style = self.group("surfaces").hover
        #: The row table of the last render; geometry for on_click/on_hover.
        self._rows: list[Line] = []
        #: The span under the pointer: ``(row, start, end)`` or ``None``.
        self._hover_span: tuple[int, int, int] | None = None

    def _rows_for(self, width: int) -> list[Line]:
        """The rows ``text`` renders to: the subclass seam for inline spans."""
        out: list[Line] = []
        for row in self.text.split("\n"):
            out.extend(Line.from_text(row, self.style).reflow(WrapMode.WORD, width))
        return out

    def render(self, c: Constraints) -> Surface:
        """Wrap ``text`` to the constraints and return a clipped surface.

        The last-render row table is kept for hit testing; a hovered span
        is merged on a copy, so the table itself stays hover-free.
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
        """Mark the action span under the pointer; True when the render changed.

        Resolved against the last render's rows; ``None`` clears it.
        """
        span: tuple[int, int, int] | None = None
        if pos is not None and 0 <= pos.y < len(self._rows):
            hit = action_at(self._rows[pos.y], pos.x)
            if hit is not None:
                span = (pos.y, hit[1], hit[2])
        changed = span != self._hover_span
        if changed:
            self._hover_span = span
            self.touch()
        return changed

    def on_click(self, pos: Pos) -> bool:
        """Leave the action under ``pos`` pending; ``False`` off every span."""
        if 0 <= pos.y < len(self._rows):
            hit = action_at(self._rows[pos.y], pos.x)
            if hit is not None:
                self._emit(hit[0])
                return True
        return False

    def __repr__(self) -> str:
        return f"Text({self.text!r})"
