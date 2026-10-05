"""SelectionGesture: the policy tier of document-space mouse selection.

This module is the assembly tier (D3) -- the peer of :mod:`mocode_tui.app`
and :mod:`mocode_tui.testing`: it imports core and app, and it is where every
selection *behavior* lands.  Above it sit the mechanisms it drives, none of
which it may extend downward: the kernel
(:mod:`mocode_tui.core.selection`) stays pure, timeless and side-effect-free
(the :class:`~mocode_tui.core.selection.Selection` model, the
:func:`~mocode_tui.core.selection.highlight` overlay, the
:func:`~mocode_tui.core.selection.extract` text), and the driver
(:class:`~mocode_tui.app.TUI`) exposes the minimal imperative surface the
gesture needs: :attr:`~mocode_tui.app.TUI.selection` (read),
:meth:`~mocode_tui.app.TUI.set_selection` (write + invalidate), the
:meth:`~mocode_tui.app.TUI.hit_test` cell resolution, the scroll facades and
the pump's :meth:`~mocode_tui.app.TUI.every` handles.

:class:`SelectionGesture` turns mouse reports into that state.  A host opts
in with one explicit line -- ``TUI`` never attaches a gesture itself, the
``Composer.attach`` philosophy -- and dispatches every event through it::

    gesture = SelectionGesture(tui)       # copy_on_select is the default
    event = await tui.read_key()
    if not gesture.handle(event):
        ...                               # the host's own dispatch

``handle`` follows the established consume-a-key contract
(``Input.handle_key`` / ``Editor.handle_key``): it returns ``True`` when the
event advanced the gesture, ``False`` when the host should see it.  The
gesture consumes the left button -- a press anchors the cell the hit test
resolves, motion while dragging extends the head, a release finalizes -- and
passes every other event (and every non-left button) straight through.

The lifecycle rules are policy, and they live here (D8): a zero-width
press-release at one cell *clears* the selection and never fires ``on_end``
(never clobber the clipboard with a click); a completed drag fires
``on_end`` exactly once and the highlight stays until the next press, so the
user can verify what was copied.  ``on_end=None`` selects without any
effect; :func:`copy_on_select` is the shipped default, and its whole body is
``extract`` + :meth:`Screen.copy <mocode_tui.core.screen.Screen.copy>` -- the
smallness is the proof that the mechanism/policy split held (D3/D6).

The two time-driven behaviors ride the pump instead of adding any mechanism
of their own.  Drag-to-edge auto-scroll (D4/D5): a motion that lands on the
first or last row of the *viewport region* -- the scrolling window, never the
pinned rows -- arms a
:meth:`~mocode_tui.app.TUI.every` ticker that scrolls ``scroll_rows`` rows per
``scroll_tick`` and extends the head by the same number of **document** rows.
The head arithmetic is one identity: scrolling ``n`` rows shifts the content
under a fixed screen row by exactly ``n`` document rows, so the ticker moves
the head by the offset the viewport actually travelled -- it never re-hit-tests,
which would read the previous frame's ownership table and form a latency
feedback loop.  The same walk (block boundaries, clamping at the document's
first and last row) serves the wheel: a wheel report during a drag scrolls the
viewport its signed ``scroll_keys`` count and co-extends the head by exactly
that much.  The ticker stands down on edge-exit, release, detach, a reflow
that cleared the overlay underneath it, and the document end.

The double-click rule is the last policy here, and it stays a controller
concern: the gesture tracks the last press's cell and its ``_clock()`` reading
(``double_click_seconds`` apart), and a second press at that same cell selects
the maximal non-whitespace run around it on that row.  Timestamps live in the
controller -- the event model stays timeless -- and the word rule is display
columns through the same measure the kernel cuts by, so a CJK character is
selected whole.  A second press at a cell *not* seen before, or later than the
window, is a plain press: a double-click between words behaves like a click.
"""

from __future__ import annotations

from collections.abc import Callable

from .app import EveryHandle, Hit, TUI
from .core.events import Key, MouseEvent, Paste
from .core.selection import Selection, SelectionAnchor, extract
from .core.text import visible_width

__all__ = ["SelectionGesture", "copy_on_select"]

#: The ``on_end`` hook: the gesture's selection-end action.  It receives the
#: driver and the finished :class:`~mocode_tui.core.selection.Selection`; its
#: return value is ignored.  ``None`` disables the effect.
_OnEnd = Callable[[TUI, Selection], object] | None


def copy_on_select(tui: TUI, selection: Selection) -> None:
    """The shipped ``on_end`` default: extract the range and OSC 52 it (D6).

    Two lines -- that is the point: every mechanism (the range walk of
    :func:`~mocode_tui.core.selection.extract`, the clipboard primitive
    :meth:`Screen.copy <mocode_tui.core.screen.Screen.copy>`) lives in the
    kernel already, and the whole policy is "which text, which screen, once".
    The write is best-effort (a non-live screen returns ``False`` without
    touching the stream); a host with stronger needs passes its own
    ``on_end``.
    """
    tui.screen.copy(extract(tui.document, selection, width=tui.screen.width))


class SelectionGesture:
    """Mouse selection policy over the block document: anchor, drag, end.

    ``tui`` is the driver whose selection surface, hit test, scroll facades
    and pump the gesture drives.  ``on_end`` is the selection-end action
    (:func:`copy_on_select` by default, ``None`` for selection without any
    effect) -- a default *function argument*, never a kernel ``if`` (D3).
    ``scroll_rows`` / ``scroll_tick`` are the edge auto-scroll knobs (D4/D5):
    how many document rows one tick scrolls the viewport -- and extends the
    head -- and how often the ticker runs.  Both are the seam a host retunes
    (an acceleration ramp would grow on top of them; v1 ships the constant).
    ``double_click_seconds`` is the word-select window: the last press's cell
    is remembered for that long, and a second press at it selects the word
    around that cell on its row.

    The gesture owns its own anchor and head addresses (document space, D1)
    and mirrors the drag into the driver through
    :meth:`~mocode_tui.app.TUI.set_selection`; it keeps no copy of the text,
    the rows, or the layout.  It is single-pointer by construction: the left
    button anchors and extends, and a second press while a drag is in flight
    re-anchors from the new cell.
    """

    __slots__ = (
        "_anchor",
        "_dir",
        "_double_click_seconds",
        "_handle",
        "_head",
        "_last_press",
        "_on_end",
        "_scroll_rows",
        "_scroll_tick",
        "_tui",
    )

    def __init__(
        self,
        tui: TUI,
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
        self._handle: EveryHandle | None = None
        self._dir = 0
        self._last_press: tuple[int, int, float] | None = None

    # -- the event contract -------------------------------------------------

    def handle(self, event: Key | Paste | MouseEvent) -> bool:
        """Advance the gesture with ``event``; ``True`` when it was consumed.

        The consume-a-key contract (``Input.handle_key`` /
        ``Editor.handle_key``): the host's dispatch is
        ``if not gesture.handle(event): ...``.  The left button -- press,
        motion while dragging, release -- is consumed; a wheel report during a
        drag is consumed and co-extends the head; every other key, paste,
        button and lone motion is passed through untouched.
        """
        if not isinstance(event, MouseEvent):
            return False
        rows = self._tui.scroll_keys.get(event.name)
        if rows and self._anchor is not None:
            # A wheel during a drag shifts the content under a still pointer:
            # the head co-extends by the same signed rows (D4).
            self._scroll_and_extend(rows)
            return True
        if event.kind == "press":
            if event.name != "left":
                return False
            self._press(event)
            return True
        if event.kind == "release":
            if event.name != "left":
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
        """End the gesture cleanly (the ``EveryHandle``/Composer convention).

        Cancels the edge ticker -- the one thing the pump may still be holding
        -- and drops the in-flight drag so a later release cannot finalize it.
        The stored selection is the driver's overlay, not the gesture's state,
        and stays as the last frame painted it.
        """
        self._cancel_autoscroll()
        self._anchor = None
        self._head = None
        self._last_press = None

    def __repr__(self) -> str:
        return f"SelectionGesture(dragging={self._anchor is not None})"

    # -- gesture internals -----------------------------------------------------

    def _press(self, event: MouseEvent) -> None:
        """Anchor at the pressed cell, or select its word on a second press.

        The timestamps live here, in the controller: the last press's cell is
        remembered with its ``_clock()`` reading, and the event model stays
        timeless.  A second press at that same cell, within
        ``double_click_seconds``, is a word select (D7's vocabulary: one
        gesture family, its own mechanism).
        """
        self._cancel_autoscroll()
        now = self._tui._clock()
        last = self._last_press
        self._last_press = (event.x, event.y, now)
        if (
            last is not None
            and (last[0], last[1]) == (event.x, event.y)
            and now - last[2] <= self._double_click_seconds
        ):
            self._word_select(event)
            return
        self._plain_press(event)

    def _plain_press(self, event: MouseEvent) -> None:
        """Anchor at the pressed cell; a press ends the previous highlight."""
        hit = self._tui.hit_test(event.x, event.y)
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
        # A zero-width range paints nothing (the kernel's lazy clamp), so the
        # previous highlight yields to this press (D8 lifecycle) while the
        # drag is still a single address.
        self._tui.set_selection(Selection.between(self._anchor, self._head))
        # A press that lands on the viewport's edge row arms the ticker too:
        # the pointer can reach the edge *before* the button goes down, and
        # a stationary press there emits no motion to arm it otherwise.
        bounds = self._viewport_rows()
        if bounds is not None:
            if event.y == bounds[1]:
                self._start_autoscroll(1)
            elif event.y == bounds[0]:
                self._start_autoscroll(-1)

    def _word_select(self, event: MouseEvent) -> None:
        """Select the maximal non-whitespace run around the pressed cell.

        A completed selection, so it fires ``on_end`` exactly once -- at the
        press, like a drag fires it at the release -- and the release that
        follows finalizes nothing: no drag was ever anchored, so the word
        stays selected until the next press.  A cell the word rule cannot
        resolve (whitespace, an empty or vanished row) degrades to a plain
        press, which is what a double-click between words should do.
        """
        hit = self._tui.hit_test(event.x, event.y)
        run = self._word_run(hit) if hit is not None else None
        if hit is None or run is None:
            self._plain_press(event)
            return
        start, end = run
        self._anchor = None  # not a drag: the release must neither extend nor clear
        self._head = None
        selection = Selection.between(
            (hit.block.id, hit.row, start), (hit.block.id, hit.row, end)
        )
        self._tui.set_selection(selection)
        if self._on_end is not None:
            self._on_end(self._tui, selection)

    def _word_run(self, hit: Hit) -> tuple[int, int] | None:
        """The ``(start, end)`` display columns of the word run at ``hit``.

        The row's text is measured once in display columns -- the same measure
        :func:`~mocode_tui.core.lines.cut_line` cuts by -- into one span per
        character; the cell's character is the one whose span contains the
        probed column, and the run grows from it in *both* directions across
        every neighbouring non-whitespace character.  CJK needs no special
        case: a wide character is an ordinary non-whitespace character
        contributing its whole width, so a double-click on one selects it
        whole.  A cell on whitespace has no run; a cell past the row's text
        probes its last column, exactly where the kernel clamps (D8).
        """
        rows = hit.block.render(self._tui.screen.width)
        if not 0 <= hit.row < len(rows):
            return None  # the document moved since the layout: nothing to select
        row = rows[hit.row]
        if row.width <= 0:
            return None
        probe = max(0, min(hit.col, row.width - 1))
        text = row.text
        spans: list[tuple[int, int]] = []  # one (start, end) column span per character
        col = 0
        for char in text:
            width = visible_width(char)
            spans.append((col, col + width))
            col += width
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
        """Extend the head to the cell under the pointer, or end the drag.

        Called only while dragging.  A cleared overlay underneath the drag
        (a reflow, D8, or a host write) ends the drag cleanly rather than
        dragging addresses that no longer point at the same glyphs.  Landing
        on the viewport region's edge row arms the auto-scroll ticker; every
        other cell disarms it (D4/D5).
        """
        anchor, head = self._anchor, self._head
        if self._tui.selection is None:
            self._cancel_autoscroll()
            self._anchor = None
            self._head = None
            return
        hit = self._tui.hit_test(event.x, event.y)
        if hit is None:
            self._cancel_autoscroll()  # off the content: no edge to hold either
            return
        head = (hit.block.id, hit.row, hit.col)
        self._head = head
        self._tui.set_selection(Selection.between(anchor, head))
        bounds = self._viewport_rows()
        if bounds is None:
            self._cancel_autoscroll()  # no viewport region: nothing can scroll
        elif event.y == bounds[1]:
            self._start_autoscroll(1)  # the bottom edge: scroll forward
        elif event.y == bounds[0]:
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
        self._tui.set_selection(selection)
        if self._on_end is not None:
            self._on_end(self._tui, selection)

    # -- edge auto-scroll ------------------------------------------------------

    def _viewport_rows(self) -> tuple[int, int] | None:
        """The viewport region's ``(first, last)`` screen rows (D5).

        Read off the state the *last layout* left behind: the window is
        ``viewport.viewport_height`` rows, and it ends just above the bottom
        fixed region, whose size is the trailing run of bottom-pinned rows in
        the ownership table (the layout paints the bottom region last, so its
        kept rows are the table's tail).  Deriving the boundary that way is
        what keeps the pinned rows out of the edge zone -- dragging into the
        composer must not scroll the transcript.

        ``None`` when there is no window to hold (a screen the fixed regions
        fill, or no layout painted yet).
        """
        table = self._tui.viewport.row_blocks
        window = self._tui.viewport.viewport_height
        if not table or window <= 0:
            return None
        pinned = {
            block.id for block in self._tui.document.blocks() if block.pin == "bottom"
        }
        bottom = 0
        for entry in reversed(table):
            if entry is None or entry[0] not in pinned:
                break
            bottom += 1
        first = len(table) - bottom - window
        if first < 0:
            return None  # stale bounds: the screen resized since the layout
        return (first, len(table) - bottom - 1)

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
        """One edge tick (pump callback): scroll and extend, or stand down.

        The two stop conditions that live inside the tick: the drag ended
        underneath it (a reflow cleared the overlay, or a press/detach already
        dropped the anchor), and the document end -- a scroll that could not
        move the viewport means the content under the pointer is frozen too,
        so the tick stands down instead of dragging the head past the range.
        """
        if self._anchor is None or self._tui.selection is None:
            self._cancel_autoscroll()
            return
        before = self._tui.viewport.offset
        self._scroll_and_extend(self._dir * self._scroll_rows)
        if self._tui.viewport.offset == before:
            self._cancel_autoscroll()  # pinned at the document's end

    def _scroll_and_extend(self, rows: int) -> None:
        """Scroll the viewport ``rows`` rows (signed) and move the head with it.

        The one walk the ticker and the wheel share (D4): the viewport moves
        ``rows`` rows, the content under a fixed screen row moves by exactly
        that many document rows, and the head -- which sits at a fixed screen
        row -- follows.  So the head is extended by the offset the viewport
        *actually* travelled, which is what folds the document-end clamp and
        the block-boundary crossing into a single arithmetic walk.
        """
        if self._head is None or rows == 0:
            return
        before = self._tui.viewport.offset
        if rows > 0:
            self._tui.scroll_down(rows)
        else:
            self._tui.scroll_up(-rows)
        moved = self._tui.viewport.offset - before
        if moved == 0:
            return  # pinned at the document end: nothing moved under the pointer
        self._head = self._walk(self._head, moved)
        self._tui.set_selection(Selection.between(self._anchor, self._head))

    def _walk(self, anchor: SelectionAnchor, rows: int) -> SelectionAnchor:
        """Move ``anchor`` ``rows`` rows through the document (signed, clamped).

        The document-space half of the identity: a document row lives inside
        some block, so the walk consumes rows block by block -- crossing a
        boundary by entering the next block's row 0 (or the previous block's
        last row) -- and clamps at the document's first and last row.  An
        address whose block left the document resolves to itself (D8:
        defensive, never an error).
        """
        blocks = self._tui.document.blocks()
        positions = {block.id: index for index, block in enumerate(blocks)}
        index = positions.get(anchor[0])
        if index is None:
            return anchor
        _, row, col = anchor
        width = self._tui.screen.width
        if rows > 0:
            remaining = rows
            while True:
                count = len(blocks[index].render(width))
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
            row = len(blocks[index].render(width)) - 1
