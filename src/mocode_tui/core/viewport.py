"""Viewport layout: the scrolling window over the document plus fixed regions.

A :class:`Viewport` renders a :class:`~mocode_tui.core.block.Document` against a
screen size and remembers where the user has scrolled to.  Sealed blocks are
rendered once per width and cached (the cache lives on the viewport and is
invalidated whenever the width changes); open blocks re-render on every
layout.  A layout slices the window out of the blocks that overlap it, so a
long document costs the window plus a walk of its blocks rather than the
materialization of every row.  Scrolling is stick-to-bottom by default: a
fresh viewport shows the tail of the document, scrolling up detaches it, and
the view re-attaches when it reaches the bottom edge again or
:meth:`Viewport.scroll_to_bottom` is called.

Blocks may sit in a fixed region that never scrolls away: ``pin="top"``
rows paint above the window, ``pin="bottom"`` rows below it, and the
unpinned blocks form the scrollable body between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .block import Block, BlockState, Document
from .lines import Line
from .style import MUTED

__all__ = ["MORE_BELOW", "ScreenLayout", "Viewport"]

#: Marker row shown as the viewport's last row when content waits below it.
MORE_BELOW = Line.from_text("─ more below ─", MUTED)


@dataclass(frozen=True)
class ScreenLayout:
    """One screen's worth of rows.

    ``rows`` is the full painting target: exactly ``height`` rows -- the
    top fixed region first, then the viewport region, the bottom fixed
    region last.  ``viewport_rows`` is the viewport region alone: exactly
    ``viewport_height`` rows, blank-padded below the content so the fixed
    regions always sit at their screen edges.

    ``row_blocks`` is the row-ownership table of this exact layout, one
    entry per screen row in painting order: ``(block id, row within that
    block)`` or ``None`` for a row no block owns -- the same table the
    :attr:`Viewport.row_blocks` property hands out, travelling with the
    layout so overlays (text selection) resolve a row back to its document
    address without reaching into the viewport.  ``block_order`` lists the
    block ids in document order -- every block the document holds, whether
    or not any of its rows are on screen -- so an overlay can order two
    document addresses (a selection's anchor and head live in different
    blocks) without the ids themselves carrying order.  Both fields default
    to "nothing known", which leaves every row unowned: a layout built by
    hand is painted as-is and highlights nothing.

    ``offset`` / ``total_rows`` carry the window's scroll state as it was
    laid out: the body-row index the window starts at, and the body rows
    the document holds (fixed-region rows excluded) -- what a scrollbar
    maps its thumb onto.  They are populated by :meth:`Viewport.layout` and
    default to "nothing known" (0), so chrome renders from the layout alone
    and never reaches into live viewport attributes.
    """

    rows: list[Line]
    viewport_rows: list[Line]
    row_blocks: list[tuple[str, int] | None] = field(default_factory=list)
    block_order: tuple[str, ...] = ()
    offset: int = 0
    total_rows: int = 0


class Viewport:
    """Scroll state over a document: window offset, sealed-row cache, ownership."""

    def __init__(self, document: Document) -> None:
        self._document = document
        self._offset = 0
        self._at_bottom = True
        # id -> (block, rows): the block reference guards against a removed
        # block's id being reused by a different block later.
        self._cache: dict[str, tuple[Block, list[Line]]] = {}
        self._cache_width: int | None = None
        self._total_rows = 0
        self._viewport_height = 0
        # Screen row -> (block id, row within that block), or None for a row
        # no block owns; rebuilt by every layout (see the row_blocks property).
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
        and pinned to the maximum while sticking to the bottom.  When
        scrolled away with content left below the window, the viewport's
        last row becomes the "more below" marker.  The window is sliced
        out of the blocks that overlap ``[offset, offset + vh)`` -- a
        sealed block's cached rows are sliced, never copied whole -- so a
        long document costs the window plus one walk of its blocks, not
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
        if self._cache_width != width:
            self._cache.clear()
            self._cache_width = width
        blocks = self._document.blocks()
        # The cache only ever holds sealed blocks, and sealing is one-way
        # (no sealed block returns to open), so an entry goes stale exactly
        # when its block leaves the document -- the sealed ids catch that at
        # the width the cache itself is keyed on, without a set over every
        # block.  A later block reusing a removed block's id is covered by
        # the identity check in _block_rows.
        live_ids = {b.id for b in blocks if b.state is BlockState.SEALED}
        if self._cache.keys() != live_ids:
            # Drop rows of blocks that left the document (a later block may
            # reuse the id; the identity check below covers that case).
            self._cache = {k: v for k, v in self._cache.items() if k in live_ids}

        top_rows: list[Line] = []
        bottom_rows: list[Line] = []
        # Row owners alongside the rows: (block id, row within that block).
        top_owners: list[tuple[str, int]] = []
        bottom_owners: list[tuple[str, int]] = []
        # The body as per-block geometry, never one concatenated list: each
        # unpinned block contributes ``(id, row count, rows)``.  The count
        # comes from the sealed cache's length -- a cached count, keyed on
        # width and block identity exactly where the cache is -- or from the
        # fresh render of an open block, whose content can change between
        # layouts with no mutation the viewport can see.  ``rows`` is the
        # cached list itself (sliced below, never copied whole) or the open
        # block's fresh one, so ``total`` is a sum of counts rather than a
        # ``len`` of materialized rows.
        body: list[tuple[str, int, list[Line]]] = []
        # Every block id in document order, for ScreenLayout.block_order:
        # collected on the one walk instead of a second pass over the blocks.
        block_order: list[str] = []
        total = 0
        for block in blocks:
            rendered = self._block_rows(block, width)
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
        viewport_rows: list[Line] = []
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
            viewport_rows.extend(rendered[start:stop])
            visible.extend((block_id, i) for i in range(start, stop))
            pos = block_end
        if not self._at_bottom and vh >= 1 and self._offset + vh < total:
            viewport_rows[-1] = MORE_BELOW
        if len(viewport_rows) < vh:
            viewport_rows.extend(Line() for _ in range(vh - len(viewport_rows)))

        rows = top_kept + viewport_rows + bottom_kept
        self._row_blocks = [
            *top_owners[: len(top_kept)],
            *visible,
            *([None] * (vh - len(visible))),  # blank fill below the content
            *bottom_owners[: len(bottom_kept)],
        ]
        return ScreenLayout(
            rows=rows,
            viewport_rows=viewport_rows,
            row_blocks=list(self._row_blocks),
            block_order=tuple(block_order),
            offset=self._offset,
            total_rows=self._total_rows,
        )

    def natural_height(self, width: int) -> int:
        """The rows this document occupies at ``width``: every block's rows.

        What a region whose height is its *content* -- the frame's bottom
        band, a pinned footer -- needs before it can be laid out: the
        fixed regions' rows plus the body's, measured by rendering each
        block once.  A band laid out at exactly this height holds its whole
        content and no blank fill, so it hugs the edge it is reserved
        against.
        """
        return sum(
            len(self._block_rows(block, width)) for block in self._document.blocks()
        )

    def _block_rows(self, block: Block, width: int) -> list[Line]:
        """Cached rows for a sealed block; freshly rendered rows for an open one.

        The cache is keyed by block id and validated by block identity: a
        sealed block keeps its frozen rows even if its component is swapped
        afterwards, while a new block reusing a removed block's id renders
        fresh.  Returned lists are owned by the caller; treat cached ones as
        read-only.
        """
        if block.state is BlockState.SEALED:
            entry = self._cache.get(block.id)
            if entry is not None and entry[0] is block:
                return entry[1]
            rows = list(block.render(width))
            self._cache[block.id] = (block, rows)
            return rows
        return list(block.render(width))

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
    def total_rows(self) -> int:
        """Body rows in the last layout (fixed-region rows excluded)."""
        return self._total_rows

    @property
    def viewport_height(self) -> int:
        """Window rows available in the last layout (height minus the fixed regions)."""
        return self._viewport_height

    @property
    def row_blocks(self) -> list[tuple[str, int] | None]:
        """Screen row to ``(block id, row within the block)``, or ``None``.

        Rebuilt by every :meth:`layout`, one entry per screen row in
        painting order (top fixed region, viewport window, bottom fixed
        region): the ownership a mouse hit test resolves through.  Rows no
        block owns -- the blank fill below short content -- are ``None``.
        The "more below" marker keeps the ownership of the body row it
        covers, so a click there still resolves to that block.  The
        returned list is a copy; the same table also travels on the layout
        as :attr:`ScreenLayout.row_blocks`.
        """
        return list(self._row_blocks)

    @property
    def at_bottom(self) -> bool:
        """Whether the window sticks to the bottom of the document."""
        return self._at_bottom
