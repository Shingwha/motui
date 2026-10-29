"""Menus: the horizontal :class:`MenuBar` and the :class:`ContextMenu` preset.

``MenuBar`` is a one-row label strip: the active label wears accent plus
underline, hover merges ``surfaces.hover`` and the cursor clamps.  Activation
emits the active label.  ``ContextMenu`` is a vertical ``Select`` preset.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..kernel.cell import Line, Segment
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP
from .choice import Option, Select
from .strip import Keymap, LabelStrip

__all__ = ["ContextMenu", "MenuBar"]

#: The active label's mark: the bar underlines it whatever the colors say.
UNDERLINE = Style(underline=True)


class MenuBar(LabelStrip):
    """A horizontal menu bar: one row, one active label, a clamped cursor.

    ``index`` is the active label; movement clamps and skips disabled
    items.  The active label is accent+underline, inactive labels faint,
    dividers muted, and hover wins (unless disabled).  ``disabled`` refuses
    every gesture; activation emits the active label.  Click/hover resolve
    against the last render's span table.
    """

    __slots__ = ("items",)

    #: A bar activates its active label.
    activatable = True

    #: The cursor family's default table (a per-instance copy backs
    #: ``self.keymap``).
    keymap = Keymap(CURSOR_KEYMAP)

    def __init__(
        self,
        items: Sequence[str],
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
        #: The whole bar refuses every gesture when disabled.
        self.disabled = disabled
        # The label the pointer is on, or ``None``; written by ``on_hover``,
        # read by ``render``.  ``None`` renders byte-for-byte what the bar
        # always did.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable.
        self._disabled_items = frozenset(disabled_items)
        # The width ``click`` maps against before the first paint (the same
        # 80 as ``Tabs``/``TextBuffer.last_width``); every render refreshes it.
        self._last_width = 80
        # The label spans of the last render -- ``(start, stop, index)`` per
        # label, in paint order -- so a hit reads the table instead of
        # re-rendering the bar.
        self._spans: tuple[tuple[int, int, int], ...] | None = None
        # The constructor's explicit index is clamped **without** the
        # disabled refusal: an explicit request an item rule will refuse is
        # kept, exactly as the verbs have always behaved.
        self._sync_cursor()
        self._cursor.index = self._cursor.clamp(index)

    @property
    def _entries(self) -> list[str]:
        """The menu labels every cursor verb and the span walk measure."""
        return self.items

    # -- the activation verb ----------------------------------------------------

    def activate(self) -> bool:
        """Leave the active label pending; disabled/empty bars refuse."""
        if self.disabled or not self.items:
            return False
        index = self.index
        if index in self._disabled_items:
            return False
        self._emit(self.items[index])
        return True

    def _style_of(self, index: int) -> Style:
        """The style one label renders with (the stricter state wins)."""
        controls = self.group("controls")
        if index in self._disabled_items:
            style = self.group("text").faint.merge(controls.overlay(disabled=True))
        elif index == self.index:
            style = (
                self.group("content")
                .accent.merge(UNDERLINE)
                .merge(controls.overlay(focused=self.focused))
            )
        else:
            style = self.group("text").faint
        if index == self._hover_index:
            style = style.merge(self.group("surfaces").hover)
        return style

    def _layout(self, width: int) -> tuple[Line, tuple[tuple[int, int, int], ...]]:
        """The bar's fitted row and the label span table, in one build."""
        if not self.items:
            return Line(), ()
        divider_style = self.group("text").muted
        segments: list[Segment] = [Segment(" ")]
        for i, label in enumerate(self.items):
            if i:
                segments.append(
                    Segment(f" {self.glyphs.vertical_rule} ", divider_style)
                )
            segments.append(Segment(label, self._style_of(i)))
        segments.append(Segment(" "))
        line = Line(segments).clip(WrapMode.ELLIPSIS, width)
        return line, self._spans_of(line)

    def __repr__(self) -> str:
        return f"MenuBar({self.items!r}, index={self.index})"


class ContextMenu(Select):
    """A :class:`Select` preset for a desktop context menu.

    ``wrap=True``, ``window=False``; options/title pass through.  The host
    mounts it over the click with a modal and reads ``take()``.
    """

    __slots__ = ()

    def __init__(
        self,
        options: Sequence[Option] = (),
        *,
        title: str = "",
        max_rows: int = 8,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(
            options,
            title=title,
            max_rows=max_rows,
            glyphs=glyphs,
            window=False,
            theme=theme,
            styles=styles,
        )
