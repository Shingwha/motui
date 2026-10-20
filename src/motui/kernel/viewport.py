"""Viewport layout: the scrolling window over the document plus fixed regions.

A :class:`Viewport` renders a :class:`~motui.kernel.block.Document` against a
screen size and remembers where the user has scrolled to.  The rows come
from :meth:`~motui.kernel.block.Block.rows` -- each block's own cache, keyed
on width and the component's revision snapshot -- so the viewport keeps **no
row cache of its own**: a sealed (or revisioned) block answers its cached
rows, an unrevisioned open one re-renders per layout, and a cache dies with
its block instead of being pruned by id on every frame.  A layout slices the
window out of the blocks that overlap it, so a long document costs the
window plus a walk of its blocks rather than the materialization of every
row.  Scrolling is stick-to-bottom by default: a fresh viewport shows the
tail of the document, scrolling up detaches it, and the view re-attaches
when it reaches the bottom edge again or :meth:`Viewport.scroll_to_bottom`
is called.  An absolute jump lands through :meth:`Viewport.scroll_to`,
clamped to the same extent -- a landing on the bottom edge re-attaches the
view, exactly as a scroll down that reached it.

Blocks may sit in a fixed region that never scrolls away: ``pin="top"``
rows paint above the window, ``pin="bottom"`` rows below it, and the
unpinned blocks form the scrollable body between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .block import Document
from .lines import Line

__all__ = ["ScreenLayout", "Viewport"]


@dataclass(frozen=True)
class ScreenLayout:
    """One screen's worth of rows.

    ``rows`` is the full painting target: exactly ``height`` rows -- the
    top fixed region first, then the viewport region, the bottom fixed
    region last.  ``body_rows`` is the viewport region alone: exactly
    ``viewport_height`` rows, blank-padded below the content so the fixed
    regions always sit at their screen edges.  ``viewport_start`` is the
    body's first row *within* ``rows`` (the top pinned rows above it), so a
    frame-level reader can turn "the first visible body row" into a screen
    row without re-laying anything out.

    ``row_blocks`` is the row-ownership table of this exact layout, one
    entry per screen row in painting order: ``(block id, row within that
    block)`` or ``None`` for a row no block owns -- the table travelling
    with the layout so overlays (text selection) resolve a row back to its
    document address without reaching into the viewport.  ``block_order`` lists the
    block ids in document order -- every block the document holds, whether
    or not any of its rows are on screen -- so an overlay can order two
    document addresses (a selection's anchor and head live in different
    blocks) without the ids themselves carrying order.  Both fields default
    to "nothing known", which leaves every row unowned: a layout built by
    hand is painted as-is and highlights nothing.

    ``rows`` / ``body_rows`` / ``row_blocks`` (and ``block_order``) are
    **tuples**: a layout is one immutable value, and a reader can never
    mutate the rows another reader holds.  The constructor accepts any
    iterable for them and normalizes to a tuple in :meth:`__post_init__`,
    so a hand-built layout may pass lists too.

    ``offset`` / ``total_rows`` carry the window's scroll state as it was
    laid out: the body-row index the window starts at, and the body rows
    the document holds (fixed-region rows excluded) -- what a scrollbar
    maps its thumb onto.  They are populated by :meth:`Viewport.layout` and
    default to "nothing known" (0), so chrome renders from the layout alone
    and never reaches into live viewport attributes.

    ``width`` / ``height`` describe the rectangle the rows were laid out
    in -- a layout names one screen's rows *and* the rectangle they were
    laid out in.  ``width`` is the column count every row is measured and
    wrapped against; ``height`` is the row count ``rows`` holds (the same
    number ``len(rows)`` answers).  They are populated by
    :meth:`Viewport.layout` from its own arguments and default to "nothing
    known" (0) -- the :attr:`row_blocks` precedent -- so a hand-built
    layout stays honest about the geometry it never claimed.
    """

    rows: tuple[Line, ...]
    body_rows: tuple[Line, ...]
    row_blocks: tuple[tuple[str, int] | None, ...] = field(default_factory=tuple)
    block_order: tuple[str, ...] = ()
    offset: int = 0
    total_rows: int = 0
    width: int = 0
    height: int = 0
    viewport_start: int = 0

    def __post_init__(self) -> None:
        """Normalize the row containers to tuples (a frozen value's arrays)."""
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "body_rows", tuple(self.body_rows))
        object.__setattr__(self, "row_blocks", tuple(self.row_blocks))
        object.__setattr__(self, "block_order", tuple(self.block_order))


class Viewport:
    """Scroll state over a document: window offset, row ownership.

    One window over one document: the offset (with its stick-to-bottom
    rule) and the row-ownership table each layout rebuilds.  The rows
    themselves are the blocks' -- every walk here goes through
    :meth:`~motui.kernel.block.Block.rows`, the block's own cache.
    """

    def __init__(self, document: Document) -> None:
        self._document = document
        self._offset = 0
        self._at_bottom = True
        self._total_rows = 0
        self._viewport_height = 0
        # Screen row -> (block id, row within that block), or None for a row
        # no block owns; rebuilt by every layout and shipped on its result.
        self._row_blocks: list[tuple[str, int] | None] = []

    # -- layout -------------------------------------------------------------------

    def layout(self, width: int, height: int) -> ScreenLayout:
        """Render the document against ``width``x``height`` and apply scroll state.

        Fixed-region blocks render first, in document order: ``pin="top"``
        rows above the window, ``pin="bottom"`` rows below it, and the
        unpinned ones form the scrollable body.  The window height is
        ``vh = max(height - top_total - bottom_total, 0)``.  When the fixed
        regions alone would exceed ``height`` the bottom region is
        preserved first (the status bar and input box must not be lost),
        the top region keeps only the leading rows that still fit
        (truncated at its head) and the viewport is left empty.  The
        offset is clamped into ``[0, max(0, total - viewport_height)]``
        and pinned to the maximum while sticking to the bottom.  The
        window holds the content rows themselves, blank-padded below the
        content: it is sliced out of the blocks that overlap
        ``[offset, offset + vh)`` -- a cached block's rows are sliced,
        never copied whole -- so a long document costs the window plus one
        walk of its blocks, not
        the materialization of every row.  Rows come back as exactly
        ``height`` entries: top region, viewport region, bottom region.
        Every layout also rebuilds the row-ownership table and
        ships it on the returned :class:`ScreenLayout` (alongside the
        document order of the block ids and the window's offset and total
        rows), so both the full-repaint and the diff path resolve clicks
        against the very same result, an overlay painted at the composition
        root resolves a row back to its document address without reaching
        into the viewport, and chrome renders from the layout alone.
        """
        blocks = self._document.blocks()

        top_rows: list[Line] = []
        bottom_rows: list[Line] = []
        # Row owners alongside the rows: (block id, row within that block).
        top_owners: list[tuple[str, int]] = []
        bottom_owners: list[tuple[str, int]] = []
        # The body as per-block geometry, never one concatenated list: each
        # unpinned block contributes ``(id, row count, rows)``.  The rows --
        # and with them the count -- come from ``Block.rows``, the block's
        # own cache keyed ``(width, revision)``: a sealed or revisioned
        # block answers a list copy instead of a re-wrap, while an open
        # block without a revision still renders per layout, because its
        # content can change with no mutation the viewport can see.
        # ``rows`` is that list (sliced below, never copied whole), so
        # ``total`` is a sum of counts rather than a ``len`` of materialized
        # rows.
        body: list[tuple[str, int, list[Line]]] = []
        # Every block id in document order, for ScreenLayout.block_order:
        # collected on the one walk instead of a second pass over the blocks.
        block_order: list[str] = []
        total = 0
        for block in blocks:
            rendered = block.rows(width)
            block_order.append(block.id)
            if block.pin == "top":
                top_rows.extend(rendered)
                top_owners.extend((block.id, i) for i in range(len(rendered)))
            elif block.pin == "bottom":
                bottom_rows.extend(rendered)
                bottom_owners.extend((block.id, i) for i in range(len(rendered)))
            else:
                count = len(rendered)
                body.append((block.id, count, rendered))
                total += count

        # The bottom region wins the space it needs (status bar / input box
        # are never lost to the top region); the top region keeps the
        # leading rows that still fit; the viewport may end up empty.
        bottom_kept = bottom_rows[:height]
        top_kept = top_rows[: max(0, height - len(bottom_kept))]
        vh = max(0, height - len(top_kept) - len(bottom_kept))

        self._total_rows = total
        self._viewport_height = vh
        max_offset = self._max_offset()
        self._offset = max_offset if self._at_bottom else min(self._offset, max_offset)

        # The window: extend rows and owners only from the blocks that
        # overlap ``[offset, offset + vh)``, each contributing its slice of
        # that range.  The running body address ``pos`` is the prefix sum of
        # the per-block counts, so an owner keeps the row's address within
        # its block exactly as a full materialization's slice would.
        window_start, window_end = self._offset, self._offset + vh
        body_rows: list[Line] = []
        visible: list[tuple[str, int]] = []
        pos = 0
        for block_id, count, rendered in body:
            block_end = pos + count
            if block_end <= window_start:  # the block sits entirely above
                pos = block_end
                continue
            if pos >= window_end:  # entirely below: no later block overlaps
                break
            start = window_start - pos if window_start > pos else 0
            stop = min(count, window_end - pos)
            body_rows.extend(rendered[start:stop])
            visible.extend((block_id, i) for i in range(start, stop))
            pos = block_end
        if len(body_rows) < vh:
            body_rows.extend(Line() for _ in range(vh - len(body_rows)))

        rows = top_kept + body_rows + bottom_kept
        self._row_blocks = [
            *top_owners[: len(top_kept)],
            *visible,
            *([None] * (vh - len(visible))),  # blank fill below the content
            *bottom_owners[: len(bottom_kept)],
        ]
        return ScreenLayout(
            rows=tuple(rows),
            body_rows=tuple(body_rows),
            row_blocks=tuple(self._row_blocks),
            block_order=tuple(block_order),
            offset=self._offset,
            total_rows=self._total_rows,
            width=width,
            height=height,
            viewport_start=len(top_kept),
        )

    def natural_height(self, width: int) -> int:
        """The rows this document occupies at ``width``: every block's rows.

        What a region whose height is its *content* -- the frame's bottom
        band, a pinned footer -- needs before it can be laid out: the
        fixed regions' rows plus the body's, measured through each block's
        :meth:`~motui.kernel.block.Block.rows` (a cached block answers a
        list copy, not a re-wrap).  A band laid out at exactly this height
        holds its whole content and no blank fill, so it hugs the edge it
        is reserved against.
        """
        blocks = self._document.blocks()
        return sum(len(block.rows(width)) for block in blocks)

    # -- scrolling -----------------------------------------------------------------

    def scroll_up(self, n: int = 1) -> None:
        """Scroll ``n`` rows toward the top (clamped at 0); leaves stick-to-bottom."""
        if n <= 0:
            return
        self._at_bottom = False
        self._offset = max(0, self._offset - n)

    def scroll_down(self, n: int = 1) -> None:
        """Scroll ``n`` rows toward the bottom (clamped at the last window).

        Landing on the bottom edge re-attaches the view: content that arrives
        afterwards moves the window again (pgdn all the way down resumes
        auto-follow).
        """
        if n <= 0:
            return
        self._offset = min(self._max_offset(), self._offset + n)
        if self._offset >= self._max_offset():
            self._at_bottom = True

    def scroll_to(self, offset: int) -> None:
        """Put the window's top at ``offset``, clamped into ``[0, max]``.

        The absolute sibling of :meth:`scroll_up` / :meth:`scroll_down`: the
        target is clamped at the top edge (0) and at the bottom one
        (:meth:`_max_offset`, the extent :meth:`scroll_down` clamps against
        and the layout pins to while sticking), so a target above the
        document shows its first window and one past its end the last window
        -- exactly the rows scrolling there would land on.  A landing on the
        bottom edge re-attaches the view: an absolute jump to the tail
        resumes auto-follow, the same rule :meth:`scroll_down`'s clamp
        follows.  Before the first layout the extent is not known, so every
        ``offset`` clamps to 0 -- which is the tail of a fresh viewport
        already, and the next layout pins it there while the viewport still
        sticks to the bottom.
        """
        self._offset = max(0, min(offset, self._max_offset()))
        self._at_bottom = self._offset >= self._max_offset()

    def scroll_to_bottom(self) -> None:
        """Stick to the bottom again; the next layout pins the offset to the tail."""
        self._at_bottom = True

    def _max_offset(self) -> int:
        return max(0, self._total_rows - self._viewport_height)

    # -- read-only state -------------------------------------------------------------

    @property
    def offset(self) -> int:
        """Row index of the window's top within the body rows."""
        return self._offset

    @property
    def document(self) -> Document:
        """The document this viewport is the window over.

        What a frame's ownership table resolves a claimed cell against: the
        pane owns the address, its document owns the block.
        """
        return self._document

    @property
    def at_bottom(self) -> bool:
        """Whether the window sticks to the bottom of the document."""
        return self._at_bottom
