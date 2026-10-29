"""Tabs: the horizontal content strip -- one row, one underline indicator.

One fitted row of labels joined by `` " │ " ``; the active label carries
accent plus underline and the focus overlay, inactive labels faint, hover
wins.  The cursor clamps, skips disabled items and never wraps; activation
emits the active label.  The host routes keys and cells.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..kernel.cell import Line, Segment
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP
from .strip import Keymap, LabelStrip

__all__ = ["Tabs"]

#: The horizontal indicator's shape: the active label underlines its own
#: cells (D2).  It is composed onto the label whatever the colors say, so
#: "active" reads with the terminal's colors off.
UNDERLINE = Style(underline=True)


class Tabs(LabelStrip):
    """A horizontal content strip: one row, a clamped, non-wrapping selection.

    ``index`` is the selected label (assignment clamps); disabled items
    render with the disabled overlay and are stepped over.  Styles resolve
    at render time: accent+underline for active, faint for others, muted
    dividers, hover merged.  Hits read the last render's span table.
    """

    __slots__ = ("items",)

    #: A tab strip activates its active label (the host reads it once).
    activatable = True

    #: The family's cursor table (a per-instance copy backs ``self.keymap``).
    keymap = Keymap(CURSOR_KEYMAP)

    def __init__(
        self,
        items: list[str],
        *,
        index: int = 0,
        glyphs: Glyphs = GLYPHS,
        disabled_items: Iterable[int] = (),
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.items = list(items)
        self.glyphs = glyphs
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        #: The pointer tier's flag; the label-level emphasis lives in
        #: ``_hover_index`` (:meth:`on_hover`).
        self.hover = False
        #: The whole strip refuses every selection gesture when disabled.
        self.disabled = disabled
        # The label the pointer is on, or ``None``; written by ``on_hover``,
        # read by ``render``.  ``None`` renders byte-for-byte what the strip
        # always did.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable; a frozenset so
        # ``click``/``select``/``move`` are one membership test apiece.
        self._disabled_items = frozenset(disabled_items)
        # The width ``click`` maps against before the first paint (same 80 as
        # ``TextBuffer.last_width``); every render refreshes it.
        self._last_width = 80
        # The label spans of the last render -- ``(start, stop, index)`` per
        # label, in paint order -- so a hit reads the table instead of
        # re-rendering the strip (the P0).  ``None`` until the first paint:
        # the fallback builds the geometry once, without calling ``render``.
        self._spans: tuple[tuple[int, int, int], ...] | None = None
        # The constructor's explicit index is clamped **without** the
        # disabled refusal: an explicit request an item rule will refuse is
        # kept, exactly as the verbs have always behaved.
        self._sync_cursor()
        self._cursor.index = self._cursor.clamp(index)

    @property
    def _entries(self) -> list[str]:
        """The tab labels every cursor verb and the span walk measure."""
        return self.items

    # -- the activation verb ----------------------------------------------------

    def activate(self) -> bool:
        """Leave the active label pending; disabled/empty strips refuse."""
        if self.disabled or not self.items:
            return False
        index = self.index
        if index in self._disabled_items:
            return False
        self._emit(self.items[index])
        return True

    def _layout(self, width: int) -> tuple[Line, tuple[tuple[int, int, int], ...]]:
        """The strip's fitted row and the label span table, in one build."""
        if not self.items:
            return Line(), ()
        index = self.index
        controls = self.group("controls")
        active_style = (
            self.group("content")
            .accent.merge(UNDERLINE)
            .merge(controls.overlay(focused=self.focused))
        )
        inactive_style = self.group("text").faint
        disabled_style = self.group("text").faint.merge(
            controls.overlay(disabled=True)
        )
        hover_style = self.group("surfaces").hover
        divider_style = self.group("text").muted

        def style_of(row: int) -> Style:
            if row in self._disabled_items:
                style = disabled_style
            else:
                style = active_style if row == index else inactive_style
            return style.merge(hover_style) if row == self._hover_index else style

        segments: list[Segment] = [Segment(" ")]
        for i, name in enumerate(self.items):
            if i:
                segments.append(
                    Segment(f" {self.glyphs.vertical_rule} ", divider_style)
                )
            segments.append(Segment(name, style_of(i)))
        segments.append(Segment(" "))
        line = Line(segments).clip(WrapMode.ELLIPSIS, width)
        return line, self._spans_of(line)

    def __repr__(self) -> str:
        return f"Tabs({self.items!r}, index={self.index})"
