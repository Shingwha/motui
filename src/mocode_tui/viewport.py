"""Viewport layout: the scrolling window over the document plus fixed regions.

A :class:`Viewport` renders a :class:`~mocode_tui.block.Document` against a
screen size and remembers where the user has scrolled to.  Sealed blocks are
rendered once per width and cached (the cache lives on the viewport and is
invalidated whenever the width changes); open blocks re-render on every
layout.  Scrolling is stick-to-bottom by default: a fresh viewport shows the
tail of the document, scrolling up detaches it, and the view re-attaches when
it reaches the bottom edge again or :meth:`Viewport.scroll_to_bottom` is
called.

Blocks may sit in a fixed region that never scrolls away: ``pin="top"``
rows paint above the window, ``pin="bottom"`` rows below it, and the
unpinned blocks form the scrollable body between them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .block import Block, BlockState, Document
from .lines import Line
from .style import MUTED

__all__ = ["ScreenLayout", "Viewport"]

#: Marker row shown as the viewport's last row when content waits below it.
_MORE_BELOW = Line.from_text("─ more below ─", MUTED)


@dataclass(frozen=True)
class ScreenLayout:
    """One screen's worth of rows.

    ``rows`` is the full painting target: exactly ``height`` rows -- the
    top fixed region first, then the viewport region, the bottom fixed
    region last.  ``viewport_rows`` is the viewport region alone: exactly
    ``viewport_height`` rows, blank-padded below the content so the fixed
    regions always sit at their screen edges.
    """

    rows: list[Line]
    viewport_rows: list[Line]


class Viewport:
    """Scroll state over a document: window offset plus the sealed-row cache."""

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
        last row becomes the "more below" marker.  Rows come back as
        exactly ``height`` entries: top region, viewport region, bottom
        region.
        """
        if self._cache_width != width:
            self._cache.clear()
            self._cache_width = width
        blocks = self._document.blocks()
        live_ids = {block.id for block in blocks}
        if self._cache.keys() != live_ids:
            # Drop rows of blocks that left the document (a later block may
            # reuse the id; the identity check below covers that case).
            self._cache = {k: v for k, v in self._cache.items() if k in live_ids}

        top_rows: list[Line] = []
        bottom_rows: list[Line] = []
        body_rows: list[Line] = []
        for block in blocks:
            if block.pin == "top":
                top_rows.extend(self._block_rows(block, width))
            elif block.pin == "bottom":
                bottom_rows.extend(self._block_rows(block, width))
            else:
                body_rows.extend(self._block_rows(block, width))

        # The bottom region wins the space it needs (status bar / input box
        # are never lost to the top region); the top region keeps the
        # leading rows that still fit; the viewport may end up empty.
        bottom_kept = bottom_rows[:height]
        top_kept = top_rows[: max(0, height - len(bottom_kept))]
        vh = max(0, height - len(top_kept) - len(bottom_kept))

        total = len(body_rows)
        self._total_rows = total
        self._viewport_height = vh
        max_offset = self._max_offset()
        self._offset = max_offset if self._at_bottom else min(self._offset, max_offset)

        viewport_rows = body_rows[self._offset : self._offset + vh]
        if not self._at_bottom and vh >= 1 and self._offset + vh < total:
            viewport_rows[-1] = _MORE_BELOW
        if len(viewport_rows) < vh:
            viewport_rows.extend(Line() for _ in range(vh - len(viewport_rows)))

        rows = top_kept + viewport_rows + bottom_kept
        return ScreenLayout(rows=rows, viewport_rows=viewport_rows)

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
    def total_rows(self) -> int:
        """Body rows in the last layout (fixed-region rows excluded)."""
        return self._total_rows

    @property
    def viewport_height(self) -> int:
        """Window rows available in the last layout (height minus the fixed regions)."""
        return self._viewport_height

    @property
    def at_bottom(self) -> bool:
        """Whether the window sticks to the bottom of the document."""
        return self._at_bottom
