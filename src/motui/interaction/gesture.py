"""gesture: the mouse-gesture policy tier of document-space selection.

This module is the assembly tier (D3) -- the peer of :mod:`motui.app`
and :mod:`motui.testing`: it imports kernel and app, and it is where every
selection *behavior* lands.  Above it sit the mechanisms it drives, none of
which it may extend downward: the kernel
(:mod:`motui.kernel.selection`) stays pure, timeless and side-effect-free
(the :class:`~motui.kernel.selection.Selection` model, the
:func:`~motui.kernel.selection.highlight` overlay, the
:func:`~motui.kernel.selection.extract` text), and the driver
(:class:`~motui.app.TUI`) exposes the minimal imperative surface the
gesture needs: :attr:`~motui.app.TUI.selection` (read),
:meth:`~motui.app.TUI.set_selection` (write + invalidate), the
:meth:`~motui.app.TUI.hit` cell resolution, the
:meth:`~motui.app.TUI.visible_range` edge zone, the scroll facades
and the pump's :meth:`~motui.app.TUI.every` handles.

:class:`SelectionGesture` turns mouse reports into that state.  A host opts
in with one explicit line -- ``TUI`` never attaches a gesture itself, the
same explicit-mounting rule the other controllers follow -- and dispatches
every event through it::

    gesture = SelectionGesture(tui)       # copy_on_select is the default
    event = await tui.read_event()
    if not gesture.handle(event):
        ...                               # the host's own dispatch

``handle`` follows the established consume-a-key contract
(:meth:`~motui.widgets.textfield.Input.handle` /
:meth:`~motui.widgets.textfield.Editor.handle`): it returns ``True`` when the
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
``extract`` + :meth:`Screen.copy <motui.kernel.screen.Screen.copy>` -- the
smallness is the proof that the mechanism/policy split held (D3/D6).

The two time-driven behaviors ride the pump instead of adding any mechanism
of their own.  Drag-to-edge auto-scroll (D4/D5): a motion that lands on the
first or last row of the *viewport region* -- the scrolling window, never the
pinned rows -- arms a
:meth:`~motui.app.TUI.every` ticker that scrolls ``scroll_rows`` rows per
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

The click-count rule is the last policy here, and it stays a controller
concern: the gesture tracks the last press's cell, its ``clock()`` reading and
how many presses in a row landed there (``double_click_seconds`` apart).  A
second press selects the maximal non-whitespace run around it on that row
(the word), a third the row's whole visible line, and a fourth starts the
count over -- click, word, line, click.  Timestamps live in the controller --
the event model stays timeless -- and both spans are display columns through
the same measure the kernel cuts by, so a CJK character is selected whole.
A press at a cell *not* seen before, or later than the window, is a plain
press: a double-click between words behaves like a click.
"""

from __future__ import annotations

from collections.abc import Callable

from ..kernel.host import EveryHandle, Hit, Host
from ..kernel.events import Event, MouseEvent
from ..kernel.frame import Pane
from ..kernel.lines import Line
from ..kernel.selection import Selection, SelectionAnchor, extract
from ..kernel.text import visible_width

__all__ = ["SelectionGesture", "copy_on_select"]

#: The ``on_end`` hook: the gesture's selection-end action.  It receives the
#: driver and the finished :class:`~motui.kernel.selection.Selection`; its
#: return value is ignored.  ``None`` disables the effect.
_OnEnd = Callable[[Host, Selection], object] | None


def copy_on_select(tui: Host, selection: Selection) -> bool:
    """The shipped ``on_end`` default: extract the range and OSC 52 it (D6).

    Still three lines -- every mechanism (the range walk of
    :func:`~motui.kernel.selection.extract`, the clipboard primitive
    :meth:`Screen.copy <motui.kernel.screen.Screen.copy>`) lives in the
    kernel, and the whole policy is "which text, which screen, once".  The
    text comes from the pane the selection lives in (:attr:`TUI.selection_pane`
    -- D7: selection is single-document, and block ids are numbered per
    document), read at the pane's own laid-out width -- the width its rows
    were wrapped at, chrome budget and split half included -- because a
    selection's row numbers address that wrapping.  The write is
    best-effort (a non-live screen returns ``False`` without touching the
    stream); a host with stronger needs passes its own ``on_end``.
    """
    pane = tui.selection_pane
    if pane is None:
        pane = tui.frame.focused_pane
    region = tui.frame.region(pane.id) if pane is not None else None
    document = pane.document if pane is not None else tui.document
    width = region.width if region is not None else tui.screen.width
    return tui.copy_to_clipboard(extract(document, selection, width=width))


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
    ``double_click_seconds`` is the click-count window: the last press's cell
    is remembered for that long, and a press at it again selects the word
    around that cell on its row -- a third press, the row's whole line --
    while a fourth restarts the count at one.

    The gesture owns its own anchor and head addresses (document space, D1)
    and mirrors the drag into the driver through
    :meth:`~motui.app.TUI.set_selection`; it keeps no copy of the text,
    the rows, or the layout.  It is single-pointer by construction: the left
    button anchors and extends, and a second press while a drag is in flight
    re-anchors from the new cell.

    A drag is **one document wide** (the frame group's D7).  The press anchors
    it in the pane the hit test names, and every later step -- the motion that
    extends the head, the edge auto-scroll, the head walk, the extraction --
    runs through that pane's viewport and document.  Block ids are numbered
    per document, so a split's second child holds a ``b0`` exactly as the
    first does: a drag that let its head wander into a neighbour's pane would
    build a range of two documents' addresses, and the overlay would then
    mark the anchored pane's own ``b0`` at rows the user never selected.  A
    pointer that crosses the divider simply stops extending.  The pane is
    held by id and re-resolved through the frame, so an in-place retile rides
    along, a collapse keeps the survivor's id, and a pane that actually leaves
    the tiling ends the drag.
    """

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
        tui: Host,
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
        self._pane_id: str | None = None

    # -- the event contract -------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Advance the gesture with ``event``; ``True`` when it was consumed.

        The consume-a-key contract (:meth:`~motui.widgets.textfield.Input.handle`
        / :meth:`~motui.widgets.textfield.Editor.handle`): the host's dispatch is
        ``if not gesture.handle(event): ...``.  The left button -- press,
        motion while dragging, release -- is consumed; a wheel report during a
        drag is consumed and co-extends the head; every other event is passed
        through untouched.
        """
        if not isinstance(event, MouseEvent):
            return False
        if event.kind == "wheel" and self._anchor is not None:
            rows = self._tui.scroll_keys.get(event.button)
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
        """End the gesture cleanly (the ``EveryHandle`` convention).

        Cancels the edge ticker -- the one thing the pump may still be holding
        -- and drops the in-flight drag so a later release cannot finalize it.
        The stored selection is the driver's overlay, not the gesture's state,
        and stays as the last frame painted it.
        """
        self._cancel_autoscroll()
        self._anchor = None
        self._head = None
        self._last_press = None
        self._pane_id = None

    def __repr__(self) -> str:
        return f"SelectionGesture(dragging={self._anchor is not None})"

    # -- gesture internals -----------------------------------------------------

    def _press(self, event: MouseEvent) -> None:
        """Count the press, then anchor, select the word or select the line.

        The timestamps live here, in the controller: the last press's cell is
        remembered with its ``clock()`` reading and the count of presses that
        landed there in a row, and the event model stays timeless.  A press at
        that same cell, within ``double_click_seconds``, is a word select on
        the second and a line select on the third (D7's vocabulary: one
        gesture family, its own mechanism); the fourth restarts the count, so
        the cycle is click, word, line, click.
        """
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
        """Anchor at the pressed cell; a press ends the previous highlight."""
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
        """Select the maximal non-whitespace run around the pressed cell.

        A completed selection, so it fires ``on_end`` exactly once -- at the
        press, like a drag fires it at the release -- and the release that
        follows finalizes nothing: no drag was ever anchored, so the word
        stays selected until the next press.  A cell the word rule cannot
        resolve (whitespace, an empty or vanished row) degrades to a plain
        press, which is what a double-click between words should do.
        """
        hit = self._tui.hit(event.x, event.y)
        run = self._word_run(hit) if hit is not None else None
        if hit is None or run is None:
            self._plain_press(event)
            return
        self._select_span(hit, *run)

    def _line_select(self, event: MouseEvent) -> None:
        """Select the pressed row's whole visible line (the third press).

        The word rule's completed-selection shape, one row wide: ``on_end``
        fires at the press and the release finalizes nothing.  The line is the
        hit block's own display row at the width the pane laid it out at --
        address and span are the same block's, so it never runs past the
        block into its neighbour (block ids are numbered per document).  A row
        with no cells (an empty block, a document that moved since the layout)
        degrades to a plain press, exactly as the word rule's whitespace does.
        """
        hit = self._tui.hit(event.x, event.y)
        span = self._line_run(hit) if hit is not None else None
        if hit is None or span is None:
            self._plain_press(event)
            return
        self._select_span(hit, *span)

    def _select_span(self, hit: Hit, start: int, end: int) -> None:
        """Complete a non-drag span on ``hit``'s row and fire ``on_end`` once.

        The word rule's and the line rule's shared tail: no anchor is left
        behind (the release that follows must neither extend the head nor
        clear the highlight), the pane is recorded for the host's extraction,
        and the end hook fires here, at the press.
        """
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
        """``hit``'s row as the blocks render it now, or ``None`` when it moved.

        Measured at the pane's own width -- the width its rows were laid out
        at -- and read back from the block's own rows
        (:meth:`~motui.kernel.block.Block.rows`, the cache a layout just
        filled), so a document edited since the layout resolves to nothing
        rather than to a stale row and an unchanged one costs a list copy.
        """
        pane = self._tui.frame.pane(hit.pane_id)
        width = self._pane_width(pane) if pane is not None else self._tui.screen.width
        rows = hit.block.rows(width)
        if not 0 <= hit.row < len(rows):
            return None  # the document moved since the layout: nothing to select
        return rows[hit.row]

    def _line_run(self, hit: Hit) -> tuple[int, int] | None:
        """The ``(0, width)`` display-column span of the row at ``hit``.

        The line rule's measure, on the same row :meth:`_word_run` reads: the
        hit block's own display row, its whole width -- a row with no cells
        has no line to select.
        """
        row = self._display_row(hit)
        if row is None or row.width <= 0:
            return None
        return (0, row.width)

    def _word_run(self, hit: Hit) -> tuple[int, int] | None:
        """The ``(start, end)`` display columns of the word run at ``hit``.

        The row's text is measured once in display columns -- the same measure
        :func:`~motui.kernel.lines.cut_line` cuts by -- into one span per
        character; the cell's character is the one whose span contains the
        probed column, and the run grows from it in *both* directions across
        every neighbouring non-whitespace character.  CJK needs no special
        case: a wide character is an ordinary non-whitespace character
        contributing its whole width, so a double-click on one selects it
        whole.  A cell on whitespace has no run; a cell past the row's text
        probes its last column, exactly where the kernel clamps (D8).  The
        columns are the pane's own, at the width its rows were laid out at.
        """
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
        """Extend the head to the cell under the pointer, or end the drag.

        Called only while dragging.  A cleared overlay underneath the drag
        (a reflow, D8, or a host write) ends the drag cleanly rather than
        dragging addresses that no longer point at the same glyphs.  A hit in
        another pane is not a cell this drag can extend into -- block ids are
        numbered per document, so a neighbour's ``b0`` is a different block
        wearing the same name -- and the head holds where it was until the
        pointer comes back.  Landing on the viewport region's edge row arms
        the auto-scroll ticker; every other cell disarms it (D4/D5).
        """
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
        """The pane the drag lives in, or ``None`` when it left the frame.

        Held by id and re-resolved through the frame, because that is the
        identity the frame itself honours: an in-place retile rewrites
        rectangles under the same ids, a collapse keeps the survivor's id on
        the parent that took its window, and only a pane that actually leaves
        the tiling stops resolving -- which ends the drag rather than letting
        it walk a document the frame no longer shows.
        """
        return None if self._pane_id is None else self._tui.frame.pane(self._pane_id)

    def _pane_width(self, pane: Pane) -> int:
        """The width ``pane``'s rows were laid out at (chrome subtracted)."""
        region = self._tui.frame.region(pane.id)
        return region.width if region is not None else self._tui.screen.width

    # -- edge auto-scroll ------------------------------------------------------

    def _visible_range(self):
        """The drag's pane window as screen rows (D5).

        The rows that pane's window occupies in the *frame* -- chrome
        subtracted and the top-pin offset included -- as
        :meth:`~motui.app.TUI.visible_range` reports them.  Asking the
        driver rather than walking the ownership table keeps every fixed
        region out of the edge zone: the pinned rows a host still pins in
        its document, and the frame's docks (pinned footers), which live
        outside the pane area -- dragging into a dock must not scroll the
        document.
        """
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
        """One edge tick (pump callback): scroll and extend, or stand down.

        The two stop conditions that live inside the tick: the drag ended
        underneath it (a reflow cleared the overlay, a press/detach dropped
        the anchor, or the pane it lives in left the frame), and the document
        end -- a scroll that could not move the viewport means the content
        under the pointer is frozen too, so the tick stands down instead of
        dragging the head past the range.
        """
        if self._anchor is None or self._tui.selection is None or self._pane() is None:
            self._cancel_autoscroll()
            return
        before = self._pane().viewport.offset
        self._scroll_and_extend(self._dir * self._scroll_rows)
        after = self._pane()
        if after is None or after.viewport.offset == before:
            self._cancel_autoscroll()  # pinned at the document's end

    def _scroll_and_extend(self, rows: int) -> None:
        """Scroll the drag's pane ``rows`` rows (signed) and move the head with it.

        The one walk the ticker and the wheel share (D4): the viewport moves
        ``rows`` rows, the content under a fixed screen row moves by exactly
        that many document rows, and the head -- which sits at a fixed screen
        row -- follows.  So the head is extended by the offset the viewport
        *actually* travelled, which is what folds the document-end clamp and
        the block-boundary crossing into a single arithmetic walk.

        The pane is the drag's own, not the frame's focused one: a drag in an
        unfocused pane (a host may focus nothing) must still scroll and extend
        in the document it started in.
        """
        pane = self._pane()
        if self._head is None or rows == 0 or pane is None:
            return
        before = pane.viewport.offset
        if rows > 0:
            pane.viewport.scroll_down(rows)
        else:
            pane.viewport.scroll_up(-rows)
        moved = pane.viewport.offset - before
        if moved == 0:
            return  # pinned at the document end: nothing moved under the pointer
        self._head = self._walk(self._head, moved, pane)
        self._tui.set_selection(
            Selection.between(self._anchor, self._head), pane=pane
        )

    def _walk(
        self, anchor: SelectionAnchor, rows: int, pane: Pane
    ) -> SelectionAnchor:
        """Move ``anchor`` ``rows`` rows through ``pane``'s document (signed).

        The document-space half of the identity: a document row lives inside
        some block, so the walk consumes rows block by block -- crossing a
        boundary by entering the next block's row 0 (or the previous block's
        last row) -- and clamps at the document's first and last row.  An
        address whose block left the document resolves to itself (D8:
        defensive, never an error).  The rows are measured at the width the
        pane laid its rows out at, the same width the overlay marked and the
        extract reads, and they come from each block's own cache
        (:meth:`~motui.kernel.block.Block.rows`): a drag across a long
        document reads what the layout already filled instead of
        re-wrapping every block it crosses.
        """
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
                count = len(blocks[index].rows(width))
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
            row = len(blocks[index].rows(width)) - 1
