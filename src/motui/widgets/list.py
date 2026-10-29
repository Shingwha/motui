"""List component: a cursor over a long sequence, rendered as a window.

``List`` renders at most ``window`` item rows centred on the cursor, with
``↑ N more``/``↓ N more`` counters for items outside it.  Movement clamps;
activation emits; marks are sticky.  Only the kernel is imported and
``render`` is a pure function of the list and width.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, pair_seat, seat, seat_width
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP, CursorWidget
from ..widgets.mark import MarkSet
from .strip import Keymap

__all__ = ["List"]

#: Private row-plan tokens for the two counter rows.  The token cannot be
#: the glyph itself: a host may pass the same string for ``more_up`` and
#: ``more_down`` (or any string), and the plan must still tell the rows
#: apart from each other and from an item index.
_ABOVE = object()
_BELOW = object()


class List(CursorWidget):
    """A cursor over ``items``, rendered as a ``window``-row view.

    ``index`` clamps into the items; the window centres on the cursor with
    ``↑/↓ N more`` counters outside it.  ``window`` must be >= 1.
    ``prefix_jump`` arms printable type-ahead.  ``glyphs`` seats the cursor
    and marks; empty glyphs collapse their seats.  The cursor row rides
    ``rows.active`` (``rows.inactive`` unfocused), hover wins (D3), disabled
    rows paint faint.  ``marked`` is sticky; ``toggle`` flips the cursor
    item's mark without emitting.
    """

    __slots__ = (
        "_hover_row",
        "disabled",
        "disabled_items",
        "glyphs",
        "items",
        "marked",
        "prefix_jump",
        "window",
    )

    #: The list owns the keyboard, clicks, the pointer's row and activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    #: The family table plus the marking key.
    keymap = Keymap({**CURSOR_KEYMAP, "space": "toggle"})

    def __init__(
        self,
        items: Sequence[str] = (),
        *,
        window: int = 8,
        prefix_jump: bool = True,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.items = list(items)
        if window < 1:
            raise ValueError(f"window must be at least 1 row, got {window}")
        self.window = window
        self.prefix_jump = prefix_jump
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = False
        self.glyphs = glyphs
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`on_hover`).
        self.hover = False
        #: The marked items (:class:`~motui.widgets.mark.MarkSet`, raw item
        #: indices): :meth:`toggle` flips the cursor row's mark, and while
        #: the set is non-empty every item row leads with its
        #: ``[x] ``/``[ ] `` prefix.  The set is the host's to read, clear
        #: and fill.
        self.marked = MarkSet()
        # The item row the pointer is on, or ``None``; written by
        # ``on_hover``, read by ``render``.  ``None`` renders byte-for-byte
        # what the list always did.
        self._hover_row: int | None = None
        #: The whole control refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The item rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        return self.group("rows").band(
            active=current, hovered=hovered, focused=self.focused, disabled=disabled
        )

    # -- the cursor -------------------------------------------------------------

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self.items)

    def _entry_at(self, index: int) -> object | None:
        return self.items[index]

    def _cursor_disabled(self) -> Iterable[int]:
        return self.disabled_items

    def _cursor_wraps(self) -> bool:
        """A data view clamps at its ends (D10); it never wraps."""
        return False

    def _cursor_enabled(self) -> bool:
        return not self.disabled

    def _page_size(self, size: int) -> int:
        """A page is the visible window, capped by the item count."""
        return min(size, self.window)

    def _is_disabled(self, index: int) -> bool:
        return self.disabled or index in self.disabled_items

    # -- the verbs ---------------------------------------------------------------

    def activate(self) -> bool:
        """Leave the cursor item pending; ``False`` on no enabled item."""
        if self.selected is None or self._is_disabled(self.index):
            return False
        self._emit(self.selected)
        return True

    def toggle(self) -> bool:
        """Flip the cursor item's mark; ``True`` when one flipped.

        Never emits.  Empty lists, disabled controls and disabled rows
        refuse.
        """
        if self.selected is None or self._is_disabled(self.index):
            return False
        self.marked.toggle(self.index)
        self.touch()
        return True

    def on_click(self, pos: Pos) -> bool:
        """Land the item rendered at row ``pos.y``; ``True`` on a hit.

        Counter rows and rows past the view carry no item; ``pos.x`` is
        ignored.  A hit moves the cursor without emitting; disabled rows
        refuse.
        """
        if self.disabled:
            return False
        layout = self._layout()
        if not 0 <= pos.y < len(layout):
            return False
        entry = layout[pos.y]
        if not isinstance(entry, int):  # a counter row: no item to land on
            return False
        if self._is_disabled(entry):
            return False
        self.select(entry)
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the item row under the pointer; True when the marking changed.

        Resolved like :meth:`on_click` without the move; ``None`` clears it.
        """
        target: int | None = None
        if pos is not None:
            row = pos.y
            layout = self._layout()
            if 0 <= row < len(layout):
                entry = layout[row]
                if isinstance(entry, int):
                    target = entry
        changed = target != self._hover_row
        if changed:
            self._hover_row = target
            self.touch()
        return changed

    # -- the keyboard -----------------------------------------------------------

    def on_key(self, event: KeyEvent) -> bool:
        """Consume a key: keymap action first, then printable prefix-jump.

        With ``prefix_jump``, a printable key is consumed whether or not it
        matches.  Everything else, and a disabled list, declines.
        """
        if self.disabled or not isinstance(event, KeyEvent):
            return False
        name = event.key
        if name in self.keymap:
            return super().on_key(event)
        if self.prefix_jump and len(name) == 1 and name.isprintable():
            self._jump(name)
            return True
        return False

    def _jump(self, char: str) -> bool:
        """Move to the first enabled item starting with ``char``; True when it moved.

        Case-insensitive and always scanned from the top; a miss changes
        nothing.
        """
        needle = char.lower()
        for index, item in enumerate(self.items):
            if not self._is_disabled(index) and item.lower().startswith(needle):
                moved = index != self.index
                if moved:
                    self.select(index)
                return moved
        return False

    # -- the window -------------------------------------------------------------

    def _visible_range(self) -> tuple[int, int]:
        """The ``[start, stop)`` item rows: a centred window clamped at the ends."""
        self._sync_cursor()
        return self._cursor.window(self.window, anchor="center")

    def _layout(self) -> list[int | object]:
        """What each rendered row carries: an item index or a counter token.

        The one row arithmetic render and hit mapping share.  The private
        counter tokens cannot collide with a host's glyph strings.
        """
        count = len(self.items)
        if count == 0:
            return []
        start, stop = self._visible_range()
        layout: list[int | object] = []
        if start > 0:
            layout.append(_ABOVE)
        layout.extend(range(start, stop))
        if stop < count:
            layout.append(_BELOW)
        return layout

    def _row(self, index: int, disabled: bool = False) -> Line:
        """One item row: the marker seat, the optional mark, the item text.

        Text styles only; the band is applied by the caller.  The mark pair
        shares the pair's wider seat so marked and unmarked rows align.
        """
        style = self.group("text").faint if disabled else self.group("text").base
        if index == self.index:
            lead = seat(self.glyphs.cursor)
        else:
            lead = " " * seat_width(self.glyphs.cursor)
        segments = [Segment(lead, style)]
        if len(self.marked):
            marked = index in self.marked
            first, second = self.glyphs.check_on, self.glyphs.check_off
            glyph, other = (first, second) if marked else (second, first)
            segments.append(Segment(pair_seat(glyph, other), style))
        segments.append(Segment(self.items[index], style))
        return Line(tuple(segments))

    def render(self, c: Constraints) -> Surface:
        """The window's item rows and counter rows, banded and clipped to width."""
        count = len(self.items)
        if count == 0:
            return Surface.clipped([], c.width)
        start, stop = self._visible_range()
        cursor_index = self.index
        rows: list[Line] = []
        for entry in self._layout():
            if isinstance(entry, int):
                item_disabled = self._is_disabled(entry)
                rows.append(
                    rest(
                        self._row(entry, item_disabled),
                        c.width,
                        self._band(
                            entry == cursor_index,
                            entry == self._hover_row,
                            item_disabled,
                        ),
                    )
                )
            elif entry is _ABOVE:  # the items before the window
                rows.append(
                    rest(
                        Line.from_text(
                            f"{seat(self.glyphs.more_up)}{start} more",
                            self.group("text").muted,
                        ),
                        c.width,
                        self._band(False, False),
                    )
                )
            else:  # _BELOW: the items past the window's last row
                rows.append(
                    rest(
                        Line.from_text(
                            f"{seat(self.glyphs.more_down)}{count - stop} more",
                            self.group("text").muted,
                        ),
                        c.width,
                        self._band(False, False),
                    )
                )
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"List({len(self.items)} items, index={self.index}, window={self.window})"
