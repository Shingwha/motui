"""The mouse-gesture policy tier of document-space selection.

Press anchors, motion extends, release finalizes; a zero-width click
clears and never fires ``on_end``. Auto-scroll rides the pump, and the
head moves by the offset the viewport actually travelled."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..kernel.cell import Line
from ..kernel.events import Event, MouseEvent
from ..kernel.frame import Pane
from ..kernel.hit import Hit
from ..kernel.layout import Constraints
from ..kernel.selection import Selection, SelectionAnchor, extract
from ..kernel.text import visible_width

if TYPE_CHECKING:
    from .runtime import Runtime, Timer

__all__ = ["SelectionGesture", "copy_on_select"]

#: The ``on_end`` hook: the gesture's selection-end action.  It receives the
#: driver and the finished :class:`~motui.kernel.selection.Selection`; its
#: return value is ignored.  ``None`` disables the effect.
_OnEnd = Callable[["Runtime", Selection], object] | None


def copy_on_select(tui: Runtime, selection: Selection) -> bool:
    """The shipped ``on_end``: extract the range at the pane's laid-out width
    and OSC 52 it (best effort)."""
    pane = tui.selection_pane
    if pane is None:
        pane = tui.frame.focused_pane
    region = tui.frame.region(pane.id) if pane is not None else None
    document = pane.document if pane is not None else tui.document
    width = region.width if region is not None else tui.screen.width
    return tui.copy_to_clipboard(extract(document, selection, width=width))


class SelectionGesture:
    """Mouse selection policy: anchor, drag, end.

    The gesture owns document-space anchors and mirrors the drag into the
    driver. A drag stays in one document (block ids repeat per pane), held by
    pane id. Click counting (click, word, line, click) lives here with its
    timestamps."""

    __slots__ = (
        "_anchor",
        "_dir",
        "_double_click_seconds",
        "_handle",
        "_head",
        "_last_press",
        "_on_end",
        "_pane_id",
        "_scroll_rows",
        "_scroll_tick",
        "_tui",
    )

    def __init__(
        self,
        tui: Runtime,
        *,
        on_end: _OnEnd = copy_on_select,
        scroll_rows: int = 2,
        scroll_tick: float = 0.05,
        double_click_seconds: float = 0.35,
    ) -> None:
        self._tui = tui
        self._on_end = on_end
        self._scroll_rows = scroll_rows
        self._scroll_tick = scroll_tick
        self._double_click_seconds = double_click_seconds
        self._anchor: SelectionAnchor | None = None
        self._head: SelectionAnchor | None = None
        self._handle: Timer | None = None
        self._dir = 0
        self._last_press: tuple[int, int, float] | None = None
        self._pane_id: str | None = None

    # -- the event contract -------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Advance the gesture; ``True`` when consumed. The left button, and a wheel
        during a drag, are the gesture's."""
        if not isinstance(event, MouseEvent):
            return False
        if event.kind == "wheel" and self._anchor is not None:
            if event.button == "wheel_down":
                rows = self._scroll_rows
            elif event.button == "wheel_up":
                rows = -self._scroll_rows
            else:
                rows = 0
            if rows:
                # A wheel during a drag shifts the content under a still
                # pointer: the head co-extends by the same signed rows (D4).
                self._scroll_and_extend(rows)
                return True
        if event.kind == "press":
            if event.button != "left":
                return False
            self._press(event)
            return True
        if event.kind == "release":
            if event.button != "left":
                return False
            self._release()
            return True
        if event.kind == "motion":
            if self._anchor is None:
                return False  # no drag in flight: the pointer belongs to the host
            self._motion(event)
            return True
        return False

    def detach(self) -> None:
        """Cancel the edge ticker and drop the in-flight drag; the stored selection
        stays as the last frame painted it."""
        self._cancel_autoscroll()
        self._anchor = None
        self._head = None
        self._last_press = None
        self._pane_id = None

    def __repr__(self) -> str:
        return f"SelectionGesture(dragging={self._anchor is not None})"

    # -- gesture internals -----------------------------------------------------

    def _press(self, event: MouseEvent) -> None:
        """Count the press and route to click, word or line selection."""
        self._cancel_autoscroll()
        now = self._tui.clock()
        last = self._last_press
        count = 1
        if (
            last is not None
            and (last[0], last[1]) == (event.x, event.y)
            and now - last[2] <= self._double_click_seconds
        ):
            count = last[3] + 1
            if count > 3:
                count = 1  # the fourth press starts the count over
        self._last_press = (event.x, event.y, now, count)
        if count == 2:
            self._word_select(event)
        elif count == 3:
            self._line_select(event)
        else:
            self._plain_press(event)

    def _plain_press(self, event: MouseEvent) -> None:
        """Anchor at the pressed cell; a press retires the previous highlight, and an
        edge press arms auto-scroll."""
        hit = self._tui.hit(event.x, event.y)
        if hit is None:
            # No block owns the cell (blank fill, out of range, removed since
            # the last layout): there is nothing to anchor, and the click
            # still retires the previous highlight.
            self._anchor = None
            self._head = None
            self._tui.set_selection(None)
            return
        self._anchor = (hit.block.id, hit.row, hit.col)
        self._head = self._anchor
        self._pane_id = hit.pane_id  # the drag's document, held for every later step
        # A zero-width range paints nothing (the kernel's lazy clamp), so the
        # previous highlight yields to this press (D8 lifecycle) while the
        # drag is still a single address.
        self._tui.set_selection(
            Selection.between(self._anchor, self._head), pane=self._pane_id
        )
        # A press that lands on the viewport's edge row arms the ticker too:
        # the pointer can reach the edge *before* the button goes down, and
        # a stationary press there emits no motion to arm it otherwise.
        bounds = self._visible_range()
        if bounds is not None:
            if event.y == bounds.last:
                self._start_autoscroll(1)
            elif event.y == bounds.first:
                self._start_autoscroll(-1)

    def _word_select(self, event: MouseEvent) -> None:
        """Select the maximal non-whitespace run around the pressed cell; a cell on
        whitespace degrades to a plain press."""
        hit = self._tui.hit(event.x, event.y)
        run = self._word_run(hit) if hit is not None else None
        if hit is None or run is None:
            self._plain_press(event)
            return
        self._select_span(hit, *run)

    def _line_select(self, event: MouseEvent) -> None:
        """Select the pressed row's whole visible line (the third press)."""
        hit = self._tui.hit(event.x, event.y)
        span = self._line_run(hit) if hit is not None else None
        if hit is None or span is None:
            self._plain_press(event)
            return
        self._select_span(hit, *span)

    def _select_span(self, hit: Hit, start: int, end: int) -> None:
        """Complete a non-drag span and fire ``on_end`` once, at the press."""
        self._anchor = None  # not a drag: the release must neither extend nor clear
        self._head = None
        self._pane_id = hit.pane_id
        selection = Selection.between(
            (hit.block.id, hit.row, start), (hit.block.id, hit.row, end)
        )
        self._tui.set_selection(selection, pane=self._pane_id)
        if self._on_end is not None:
            self._on_end(self._tui, selection)

    def _display_row(self, hit: Hit) -> Line | None:
        """``hit``'s row as the block renders it now, or ``None`` when it moved."""
        pane = self._tui.frame.pane(hit.pane_id)
        width = self._pane_width(pane) if pane is not None else self._tui.screen.width
        rows = hit.block.rows_view(Constraints(width=width))
        if not 0 <= hit.row < len(rows):
            return None  # the document moved since the layout: nothing to select
        return rows[hit.row]

    def _line_run(self, hit: Hit) -> tuple[int, int] | None:
        """The ``(0, width)`` span of the row at ``hit``, or ``None`` for an empty
        row."""
        row = self._display_row(hit)
        if row is None or row.width <= 0:
            return None
        return (0, row.width)

    def _word_run(self, hit: Hit) -> tuple[int, int] | None:
        """The display-column span of the maximal non-whitespace run at ``hit``;
        wide characters contribute their whole width."""
        row = self._display_row(hit)
        if row is None or row.width <= 0:
            return None
        probe = max(0, min(hit.col, row.width - 1))
        text = row.text
        spans: list[tuple[int, int]] = []  # one (start, end) column span per character
        col = 0
        for char in text:
            width_ = visible_width(char)
            spans.append((col, col + width_))
            col += width_
        index = next(
            (i for i, (start, end) in enumerate(spans) if start <= probe < end), None
        )
        if index is None or text[index].isspace():
            return None  # the cell is on a separator: no run to select
        first = index
        while first > 0 and not text[first - 1].isspace():
            first -= 1
        last = index
        while last + 1 < len(text) and not text[last + 1].isspace():
            last += 1
        return (spans[first][0], spans[last][1])

    def _motion(self, event: MouseEvent) -> None:
        """Extend the head to the hit cell, staying in the anchored pane, and arm or
        disarm the edge ticker."""
        anchor, head = self._anchor, self._head
        if self._tui.selection is None:
            self._cancel_autoscroll()
            self._anchor = None
            self._head = None
            return
        hit = self._tui.hit(event.x, event.y)
        if hit is None:
            self._cancel_autoscroll()  # off the content: no edge to hold either
            return
        if hit.pane_id != self._pane_id:
            self._cancel_autoscroll()  # across the divider: one document per drag
            return
        head = (hit.block.id, hit.row, hit.col)
        self._head = head
        self._tui.set_selection(Selection.between(anchor, head), pane=self._pane_id)
        bounds = self._visible_range()
        if bounds is None:
            self._cancel_autoscroll()  # no viewport region: nothing can scroll
        elif event.y == bounds.last:
            self._start_autoscroll(1)  # the bottom edge: scroll forward
        elif event.y == bounds.first:
            self._start_autoscroll(-1)  # the top edge: scroll back
        else:
            self._cancel_autoscroll()  # edge-exit

    def _release(self) -> None:
        """Finalize: clear a click (no ``on_end``), end a drag (one ``on_end``)."""
        self._cancel_autoscroll()
        anchor, head = self._anchor, self._head
        self._anchor = None
        self._head = None
        if anchor is None:
            return  # a press that hit nothing: already retired the highlight
        if anchor == head:
            self._tui.set_selection(None)  # a click clears; the clipboard is never touched
            return
        selection = Selection.between(anchor, head)
        self._tui.set_selection(selection, pane=self._pane_id)
        if self._on_end is not None:
            self._on_end(self._tui, selection)

    # -- the anchored pane ---------------------------------------------------------

    def _pane(self) -> Pane | None:
        """The pane the drag lives in, or ``None`` when it left the frame."""
        return None if self._pane_id is None else self._tui.frame.pane(self._pane_id)

    def _pane_width(self, pane: Pane) -> int:
        """The width ``pane``'s rows were laid out at (chrome subtracted)."""
        region = self._tui.frame.region(pane.id)
        return region.width if region is not None else self._tui.screen.width

    # -- edge auto-scroll ------------------------------------------------------

    def _visible_range(self):
        """The drag's pane window as screen rows, so fixed regions and docks stay
        out of the edge zone."""
        return self._tui.visible_range(self._pane_id)

    def _start_autoscroll(self, direction: int) -> None:
        """Arm the edge ticker for ``direction`` (``1`` down, ``-1`` up)."""
        if self._handle is not None:
            if self._dir == direction:
                return  # already scrolling this way: one handle, one direction
            self._handle.cancel()
        self._dir = direction
        self._handle = self._tui.every(self._scroll_tick, self._tick_scroll)

    def _cancel_autoscroll(self) -> None:
        """Cancel the edge ticker (a no-op when none is armed)."""
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
            self._dir = 0

    def _tick_scroll(self) -> None:
        """One edge tick: scroll and extend, or stand down when the drag ended or
        the document end froze the content."""
        if self._anchor is None or self._tui.selection is None or self._pane() is None:
            self._cancel_autoscroll()
            return
        before = self._pane().viewport.offset
        self._scroll_and_extend(self._dir * self._scroll_rows)
        after = self._pane()
        if after is None or after.viewport.offset == before:
            self._cancel_autoscroll()  # pinned at the document's end

    def _scroll_and_extend(self, rows: int) -> None:
        """Scroll the drag's pane and move the head by the rows the viewport
        actually travelled -- the one walk the ticker and the wheel share."""
        pane = self._pane()
        if self._head is None or rows == 0 or pane is None:
            return
        before = pane.viewport.offset
        pane.scroll_by(rows)
        moved = pane.viewport.offset - before
        if moved == 0:
            return  # pinned at the document end: nothing moved under the pointer
        self._head = self._advance_head(self._head, moved, pane)
        self._tui.set_selection(
            Selection.between(self._anchor, self._head), pane=pane
        )

    def _advance_head(
        self, anchor: SelectionAnchor, rows: int, pane: Pane
    ) -> SelectionAnchor:
        """Move a document address ``rows`` rows through the pane's blocks, crossing
        block boundaries and clamping at the document ends."""
        blocks = pane.document.blocks()
        positions = {block.id: index for index, block in enumerate(blocks)}
        index = positions.get(anchor[0])
        if index is None:
            return anchor
        _, row, col = anchor
        width = self._pane_width(pane)
        if rows > 0:
            remaining = rows
            while True:
                count = blocks[index].row_count(Constraints(width=width))
                if row + remaining < count:
                    return (blocks[index].id, row + remaining, col)
                remaining -= count - row  # the rest of this block is consumed
                if index + 1 >= len(blocks):
                    return (blocks[index].id, max(0, count - 1), col)
                index += 1
                row = 0
        remaining = -rows
        while True:
            if row - remaining >= 0:
                return (blocks[index].id, row - remaining, col)
            remaining -= row + 1  # the head of this block is consumed
            if index == 0:
                return (blocks[index].id, 0, col)
            index -= 1
            row = blocks[index].row_count(Constraints(width=width)) - 1
