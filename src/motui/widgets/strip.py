"""Strip internals: the keymap seam and the one-row label strip.

Private to the widget package: re-exports ``Keymap`` and holds
``LabelStrip``, the cursor/hit/render skeleton behind ``Tabs`` and
``MenuBar``.  Nothing here is re-exported from ``motui.widgets``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..kernel.cell import Line, Surface
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.text import visible_width
from ..widgets.base import CursorWidget, Keymap

__all__ = ["Keymap", "LabelStrip"]


class LabelStrip(CursorWidget):
    """The one-row label strip shared by ``Tabs`` and ``MenuBar``.

    Subclasses provide ``_entries`` and ``_layout`` (row plus span table).
    The base owns the clamped cursor, the last render's span table for hits
    and the one-row render.  Hits resolve only on row 0; padding, dividers
    and truncation carry no label.
    """

    __slots__ = (
        "_disabled_items",
        "_hover_index",
        "_last_width",
        "_spans",
        "disabled",
        "glyphs",
    )

    #: A strip takes the keyboard through its subclass keymap, clicks on its
    #: labels and the pointer's marking; a subclass with an activation verb
    #: publishes ``activatable = True`` itself.
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

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self._entries)

    def _entry_at(self, index: int) -> object | None:
        return self._entries[index]

    def _cursor_disabled(self) -> Iterable[int]:
        return self._disabled_items

    def _cursor_wraps(self) -> bool:
        """A strip clamps at its ends; it never wraps."""
        return False

    def _cursor_enabled(self) -> bool:
        return not self.disabled

    def on_click(self, pos: Pos) -> bool:
        """Select the label cell ``(pos.y, pos.x)`` covers; ``True`` on a hit.

        Only row 0 hits; disabled labels, disabled strips and cells outside
        a label decline.
        """
        if self.disabled:
            return False
        index = self._hit(pos.y, pos.x)
        if index is None or index in self._disabled_items:
            return False
        self.select(index)
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the label under the pointer; True when the marking changed.

        Resolved like :meth:`on_click`; ``None`` clears it and disabled
        labels still mark.
        """
        target = None if pos is None else self._hit(pos.y, pos.x)
        changed = target != self._hover_index
        if changed:
            self._hover_index = target
            self.touch()
        return changed

    def _hit(self, row: int, col: int) -> int | None:
        if row != 0:
            return None
        return self._label_at(col)

    def _label_at(self, col: int) -> int | None:
        """The label index a column covers, from the last render's span table.

        Before the first paint the table is built once at the default
        width; hits never render.
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
        """The label spans of a fitted row, by matching segment text to labels.

        Padding, dividers, ellipsis and truncated labels carry no span.
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
        """The strip's one row, with the span table recorded for hits."""
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
