"""NavList: the vertical navigation list -- one row per item, a bar indicator.

Each row is a one-cell indicator seat, a separator and a label; the active
row fills the seat with ``glyphs.rail``.  ``groups`` inserts unselectable
title rows between items.  The rail clamps (never wraps) and is a pure
component: the host routes keys and cells.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, seat_width
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP, CursorWidget
from .strip import Keymap

__all__ = ["NavList"]


class NavList(CursorWidget):
    """A vertical navigation list: a bar indicator, a clamped selection.

    ``index`` is an item index, clamped by the verbs (the constructor keeps
    an explicit request).  ``disabled_items`` render faint and refuse
    clicks/selection; ``disabled`` refuses everything.  ``groups`` inserts
    unselectable title rows at item positions.  All rows share one bar
    column and separator, so labels align.  The active row keeps its accent
    label and rides ``rows.active``; hover wins over it (D3).  An empty list
    renders no rows.
    """

    __slots__ = (
        "_bar_seat",
        "_bar_space",
        "_disabled_items",
        "_groups",
        "_hover_index",
        "_separator",
        "disabled",
        "glyphs",
        "items",
    )

    #: The rail owns the keyboard, clicks, the pointer's row and activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    #: The cursor family's default table (a per-instance copy backs
    #: ``self.keymap``).
    keymap = Keymap(CURSOR_KEYMAP)

    def __init__(
        self,
        items: list[str],
        *,
        groups: Sequence[tuple[int, str]] = (),
        index: int = 0,
        disabled_items: Iterable[int] = (),
        disabled: bool = False,
        glyphs: Glyphs = GLYPHS,
        bar_space: str | None = None,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.items = list(items)
        self.glyphs = glyphs
        bar = glyphs.rail
        # The bar column is as wide as the glyph; the blank rows leave that
        # column empty.  ``bar_space`` is the separator after it -- one space
        # by default while the bar is on, none when it is off -- and the
        # seat the blank rows wear (``_bar_seat``) plus that separator is the
        # full gutter stored as ``_bar_space``: ``" " * seat_width(bar)`` for
        # the default bar, and ``""`` when the bar is off.  A wide bar widens
        # its own column, so both states put the label at one column; an
        # explicit ``bar_space`` sets the separator's width.  Read-only: the
        # gutter is derived state (the P0 -- a host edit used to desync the
        # rendered seat from the snapshot).
        self._bar_seat = " " * (seat_width(bar) - (1 if bar else 0))
        separator_width = (
            visible_width(bar_space) if bar_space is not None else (1 if bar else 0)
        )
        self._separator = " " * separator_width
        self._bar_space = self._bar_seat + self._separator
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_index`` (:meth:`on_hover`).
        self.hover = False
        #: The whole rail refuses every selection gesture when disabled.
        self.disabled = disabled
        # The item row the pointer is on, or ``None``; written by
        # ``on_hover``, read by ``render``.  ``None`` renders byte-for-byte
        # what the list always did, and a group row never marks.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable; a frozenset so
        # ``click``/``select``/``move`` are one membership test apiece.
        self._disabled_items = frozenset(disabled_items)
        # The group title rows, latched at construction: each ``(position,
        # label)`` sits before that **item** index (clamped into
        # ``0..len(items)``, sorted stably so one position keeps its order).
        self._groups: tuple[tuple[int, str], ...] = tuple(
            sorted(
                ((min(max(position, 0), len(self.items)), label)
                 for position, label in groups),
                key=lambda pair: pair[0],
            )
        )
        # Styles resolve at render time from the theme (or ``styles=``);
        # only the derived gutter is latched here.
        # The constructor's explicit index is clamped **without** the
        # disabled refusal: an explicit request an item rule will refuse is
        # kept, exactly as the verbs have always behaved.
        self._sync_cursor()
        self._cursor.index = self._cursor.clamp(index)

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        """The rail's row band: disabled > hover > active > base; active never dims."""
        rows = self.group("rows")
        if disabled:
            return rows.disabled
        if hovered:
            return rows.hover
        if current:
            return rows.active
        return rows.base

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self.items)

    def _entry_at(self, index: int) -> object | None:
        return self.items[index]

    def _cursor_disabled(self) -> Iterable[int]:
        return self._disabled_items

    def _cursor_wraps(self) -> bool:
        """The rail clamps at its ends; it never wraps."""
        return False

    def _cursor_enabled(self) -> bool:
        return not self.disabled

    # -- the activation verb ----------------------------------------------------

    def activate(self) -> bool:
        """Leave the active item's label pending; disabled or empty rails refuse."""
        if self.disabled or not self.items:
            return False
        index = self.index
        if index in self._disabled_items:
            return False
        self._emit(self.items[index])
        return True

    @property
    def bar_space(self) -> str:
        """The derived gutter (blank bar column plus separator); read-only."""
        return self._bar_space

    def on_click(self, pos: Pos) -> bool:
        """Select the item the rendered row ``pos.y`` covers; ``True`` on a hit.

        ``pos.x`` is ignored.  Group rows, disabled items, out-of-range rows
        and a disabled rail decline.
        """
        if self.disabled:
            return False
        index = self._item_at(pos.y)
        if index is None or index in self._disabled_items:
            return False
        self.select(index)
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the item the rendered row ``pos.y`` covers; True when it changed.

        Group rows and cells past the list carry no item; disabled items
        still mark (hover is the pointer's echo, not a selection).
        """
        target = None if pos is None else self._item_at(pos.y)
        changed = target != self._hover_index
        if changed:
            self._hover_index = target
            self.touch()
        return changed

    def render(self, c: Constraints) -> Surface:
        """One banded row per item and group title; an empty list renders none.

        Item rows share the bar column/separator shape; group rows are muted
        chrome on the ground.  An unfocused rail mutes the active bar but
        never dims the label.  ``max_height`` truncates.
        """
        if not self.items:
            return Surface.clipped([], c.width)
        cursor_index = self.index
        # The roles resolve once per render; the focus rule drops the active
        # bar from accent to muted -- the label is never dimmed (D3).
        text = self.group("text")
        active_label = self.group("content").accent
        bar_active = active_label
        if not self.focused:
            bar_active = bar_active.merge(text.muted)
        rows: list[Line] = []
        for kind, payload in self._plan():
            if kind == "group":
                rows.append(
                    rest(
                        Line((
                            Segment(self._bar_seat, text.muted),
                            Segment(f"{self._separator}{payload}", text.muted),
                        )),
                        c.width,
                        self._band(False, False),
                    )
                )
                continue
            index = payload
            if index in self._disabled_items:
                label_style, bar_style = text.faint, text.muted
            elif index == cursor_index:
                label_style, bar_style = active_label, bar_active
            else:
                label_style, bar_style = text.faint, text.muted
            seat = (
                self.glyphs.rail
                if index == cursor_index and self.glyphs.rail
                else self._bar_seat
            )
            rows.append(
                rest(
                    Line((
                        Segment(seat, bar_style),
                        Segment(
                            f"{self._separator}{self.items[index]}", label_style
                        ),
                    )),
                    c.width,
                    self._band(index == cursor_index, index == self._hover_index),
                )
            )
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    # -- the row plan ------------------------------------------------------------

    def _plan(self) -> list[tuple[str, object]]:
        """The rendered rows: ``("group", label)`` or ``("item", index)``, top to bottom."""
        plan: list[tuple[str, object]] = []
        remaining = list(self._groups)
        for position in range(len(self.items) + 1):
            while remaining and remaining[0][0] == position:
                plan.append(("group", remaining.pop(0)[1]))
            if position < len(self.items):
                plan.append(("item", position))
        return plan

    def _item_at(self, row: int) -> int | None:
        """The item index the rendered ``row`` covers, or ``None`` (group/outside)."""
        plan = self._plan()
        if 0 <= row < len(plan) and plan[row][0] == "item":
            return plan[row][1]  # type: ignore[return-value]
        return None

    def __repr__(self) -> str:
        return f"NavList({self.items!r}, index={self.index})"
