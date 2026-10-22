"""Viewport layout: the scrolling window over the document plus fixed regions.

A :class:`Viewport` renders a :class:`~motui.core.block.Document` against a
screen size and remembers where the user has scrolled to.  The rows come
from the block's borrow gate :meth:`~motui.core.block.Block.rows_view` --
each block's own cache, keyed
on width and the component's revision snapshot, handed over uncopied
because this walk only reads -- so the viewport keeps **no
row cache of its own**: a sealed (or revisioned) block answers its cached
rows, an unrevisioned open one re-renders per layout, and a cache dies with
its block instead of being pruned by id on every frame.  What the viewport
*does* keep is the private :class:`_BodyIndex`: per-block heights and
prefix sums it maintains incrementally, so a layout locates the window by
bisect and materializes only the rows the window covers -- a long document
costs the cheapest probe per block (one snapshot comparison), the re-render
of what changed, and the window itself.  Scrolling is stick-to-bottom by
default: a fresh viewport shows the tail of the document, scrolling up
detaches it, and the view re-attaches
when it reaches the bottom edge again or :meth:`Viewport.scroll_to_bottom`
is called.  An absolute jump lands through :meth:`Viewport.scroll_to`,
clamped to the same extent -- a landing on the bottom edge re-attaches the
view, exactly as a scroll down that reached it.

Blocks may sit in a fixed region that never scrolls away: ``pin="top"``
rows paint above the window, ``pin="bottom"`` rows below it, and the
unpinned blocks form the scrollable body between them.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Sequence

from .block import Block, Document
from .lines import Line
from .scroll import ScrollState

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
    so a hand-built layout may pass lists too; an input that already is a
    tuple is taken as is -- the normalization serves hand-built layouts,
    and a tuple has nothing left to normalize.

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
        """Normalize the row containers to tuples (a frozen value's arrays).

        The normalization serves hand-built layouts, whose fields may be
        lists; an input that already is a tuple is taken as is, so a
        layout built by :meth:`Viewport.layout` -- which constructs tuples
        -- pays no second pass over the rows it just built.
        """
        if type(self.rows) is not tuple:
            object.__setattr__(self, "rows", tuple(self.rows))
        if type(self.body_rows) is not tuple:
            object.__setattr__(self, "body_rows", tuple(self.body_rows))
        if type(self.row_blocks) is not tuple:
            object.__setattr__(self, "row_blocks", tuple(self.row_blocks))
        if type(self.block_order) is not tuple:
            object.__setattr__(self, "block_order", tuple(self.block_order))


class _BodyEntry:
    """One body block's indexed shape: the block, its snapshot, its height.

    The index deliberately stores **no rows** -- a block's cached list is a
    borrow (:meth:`~motui.core.block.Block.rows_view`), never owned here --
    so the entry is only a height token the geometry recomputes from: the
    rows themselves are taken from the block's own cache at the moment the
    window materializes them.  ``revision`` is the snapshot the block
    answered when ``count`` was measured; ``None`` marks a block without a
    usable snapshot, which is re-measured on every :meth:`_BodyIndex.ensure`
    (a block whose memory is off cannot prove itself unchanged).
    """

    __slots__ = ("block", "count", "revision")

    def __init__(self, block: Block, revision: object, count: int) -> None:
        self.block = block
        self.revision = revision
        self.count = count


class _BodyIndex:
    """The viewport's private body index: who is in the body, how tall.

    The per-frame geometry facts of one document, kept between layouts so a
    frame pays for what changed instead of for the document: body entries in
    document order (``block, revision, count``), the cumulative heights
    (``_cum[i]`` is the body row the *i*-th entry starts at, so the window
    is located by bisect), the body total, the pinned blocks in document
    order, and the ``block_order`` tuple (rebuilt only when the document
    mutates, handed to every layout as the same object).

    Freshness is a two-level check.  The key ``(Document.mutation, width)``
    catches structural change and width change -- either one rebuilds every
    entry (``row_count`` renders a first layout's blocks exactly as the
    per-frame walk always did).  Within a key, every ``ensure`` sweeps the
    entries and probes each block's ``revision()``: an equal value means the
    block's height stands (one cheap value comparison -- the snapshot is a
    value, so equality is the block's own promise that its rows are
    unchanged), a moved value re-measures the block through
    :meth:`~motui.core.block.Block.row_count` (which re-renders and refills
    the block's own cache) and re-runs the prefix sums **from that entry
    on** -- the naive suffix recompute, because a moved block in an
    append-mostly document is almost always at the tail.  A ``None``
    snapshot (no protocol, or memory switched off) is always dirty: the
    entry is re-measured every frame, which re-renders that block every
    frame -- exactly once, the same single render the per-frame rows walk
    paid, because the rows that render produced are carried to the window
    on ``_frame_rows`` (a frame-scoped hold, the exact lifetime the walk's
    ``body`` list had; the index keeps no rows across frames).
    """

    __slots__ = (
        "_bottom",
        "_cum",
        "_document",
        "_entries",
        "_frame_rows",
        "_key",
        "_order",
        "_order_mutation",
        "_top",
        "_total",
    )

    def __init__(self, document: Document) -> None:
        self._document = document
        # ``(mutation, width)`` the entries were built for; ``None`` until
        # the first ``ensure``.
        self._key: tuple[int, int] | None = None
        self._entries: list[_BodyEntry] = []
        self._cum: list[int] = [0]
        self._total = 0
        self._top: list[Block] = []
        self._bottom: list[Block] = []
        self._order: tuple[str, ...] = ()
        self._order_mutation: int = -1  # no document starts at -1 mutations
        # Rows rendered by this frame's measurement pass, for the blocks
        # that render per call and so must not be asked twice in one frame;
        # emptied by every ``ensure`` -- nothing survives the frame.
        self._frame_rows: dict[Block, Sequence[Line]] = {}

    def ensure(self, width: int) -> None:
        """Bring the index up to date for ``width``; the one entry door.

        After it answers, the geometry properties (pinned blocks, entries,
        prefix sums, body total, block order) describe the document at this
        width as of the blocks' current snapshots.  Cheap when nothing
        changed: one key comparison plus one ``revision()`` probe per body
        block.
        """
        self._frame_rows = {}
        mutation = self._document.mutation
        if self._key is not None and self._key == (mutation, width):
            self._sweep(width)
            return
        self._rebuild(mutation, width)

    # -- geometry read by the layout -------------------------------------------------

    @property
    def top_blocks(self) -> list[Block]:
        """The ``pin="top"`` blocks in document order."""
        return self._top

    @property
    def bottom_blocks(self) -> list[Block]:
        """The ``pin="bottom"`` blocks in document order."""
        return self._bottom

    @property
    def body_total(self) -> int:
        """The body rows the document holds (fixed regions excluded)."""
        return self._total

    @property
    def block_order(self) -> tuple[str, ...]:
        """Every block id in document order (the same tuple until a mutation)."""
        return self._order

    def window_spans(self, start: int, end: int) -> list[tuple[Block, int, int]]:
        """The body entries overlapping ``[start, end)`` as slice requests.

        Each answer is ``(block, slice start, slice stop)``: the rows to
        take from that block's own cache, addressing exactly the body rows
        the window covers.  The window is located by bisecting the prefix
        sums (``_cum``), so finding the first overlapping block costs
        ``log n`` regardless of how far down the document it sits; a
        zero-height entry at the boundary is skipped, exactly as the
        per-frame walk skipped it.
        """
        entries = self._entries
        cum = self._cum
        spans: list[tuple[Block, int, int]] = []
        for i in range(bisect_right(cum, start) - 1, len(entries)):
            pos = cum[i]
            if pos >= end:  # entirely below: no later block overlaps
                break
            count = entries[i].count
            if pos + count <= start:  # entirely above
                continue
            spans.append(
                (
                    entries[i].block,
                    start - pos if start > pos else 0,
                    min(count, end - pos),
                )
            )
        return spans

    def entry_rows(self, block: Block, width: int) -> Sequence[Line]:
        """The rows a windowed body block lends this frame.

        The measurement pass already rendered every block without a usable
        snapshot (they render per call by contract, so asking them again
        here would render them twice in one frame); their rows are kept in
        ``_frame_rows`` for this frame and handed back, so the slice the
        window takes answers the very rows the entry's count was measured
        from.  Every other block answers its own cache through
        :meth:`~motui.core.block.Block.rows_view` -- a hit, the sweep has
        kept it warm.
        """
        rows = self._frame_rows.get(block)
        if rows is None:
            return block.rows_view(width)
        return rows

    # -- maintenance ------------------------------------------------------------------

    def _sweep(self, width: int) -> None:
        """Probe every entry's snapshot and re-measure the ones that moved."""
        entries = self._entries
        dirty_from = -1
        for i, entry in enumerate(entries):
            revision = entry.block.revision()
            if revision is None:
                # No snapshot, no memory: render per call, and keep the rows
                # for the window so this frame renders the block only once.
                rows = entry.block.rows_view(width)
                self._frame_rows[entry.block] = rows
                if len(rows) != entry.count:
                    entry.count = len(rows)
                    if dirty_from < 0:
                        dirty_from = i
            elif revision != entry.revision:
                entry.revision = revision
                count = entry.block.row_count(width)
                if count != entry.count:
                    entry.count = count
                    if dirty_from < 0:
                        dirty_from = i
        if dirty_from >= 0:
            self._recompute_prefix(dirty_from)

    def _recompute_prefix(self, from_index: int) -> None:
        """Re-run the prefix sums from ``from_index`` on (naive suffix, P6).

        Entries before ``from_index`` are untouched, so their accumulated
        height is still true; everything after shifts by whatever the dirty
        entries gained or lost.
        """
        entries = self._entries
        cum = self._cum
        running = cum[from_index]
        for i in range(from_index, len(entries)):
            running += entries[i].count
            cum[i + 1] = running
        self._total = running

    def _rebuild(self, mutation: int, width: int) -> None:
        """Build every entry from the document (a key change: structure or width).

        The walk is the one per-document pass: pinned blocks are filed by
        region, each body block is measured through ``row_count`` (which
        renders a first-seen block exactly once, as the per-frame rows walk
        always did), and the ids collected in the same pass become the
        ``block_order`` tuple -- rebuilt only when the document actually
        mutated, so width-only changes reuse the ids of the same structure.
        """
        blocks = self._document.blocks()
        entries: list[_BodyEntry] = []
        cum: list[int] = [0]
        top: list[Block] = []
        bottom: list[Block] = []
        total = 0
        for block in blocks:
            if block.pin == "top":
                top.append(block)
            elif block.pin == "bottom":
                bottom.append(block)
            else:
                revision = block.revision()
                if revision is None:
                    # No snapshot, no memory: render per call, and keep the
                    # rows for the window (one render per frame, as always).
                    rows = block.rows_view(width)
                    self._frame_rows[block] = rows
                    count = len(rows)
                else:
                    count = block.row_count(width)
                entries.append(_BodyEntry(block, revision, count))
                cum.append(total + count)
                total += count
        self._entries = entries
        self._cum = cum
        self._total = total
        self._top = top
        self._bottom = bottom
        self._key = (mutation, width)
        if mutation != self._order_mutation:
            self._order = tuple(block.id for block in blocks)
            self._order_mutation = mutation


class Viewport:
    """Scroll state over a document: window offset, row ownership.

    One window over one document: the offset (with its stick-to-bottom
    rule) and the row-ownership table each layout rebuilds.  The rows
    themselves are the blocks' -- every walk here goes through the block's
    own cache (the read-only doors :meth:`~motui.core.block.Block.rows_view`
    and :meth:`~motui.core.block.Block.row_count`), borrowed, never copied.
    The geometry between layouts is the :class:`_BodyIndex`: heights and
    prefix sums kept across frames, keyed ``(Document.mutation, width)``,
    so a stable frame re-probes snapshots instead of re-walking blocks.
    """

    def __init__(self, document: Document) -> None:
        self._document = document
        # The one scroll state: offset, body rows and window height, with
        # the viewport's tail-follow rule switched on from birth.
        self._state = ScrollState(stick_to_bottom=True)
        # Screen row -> (block id, row within that block), or None for a row
        # no block owns; rebuilt by every layout and shipped on its result.
        self._row_blocks: list[tuple[str, int] | None] = []
        # The per-block heights and prefix sums behind every layout; keyed
        # ``(Document.mutation, width)`` and swept per frame (see the class).
        self._index = _BodyIndex(document)

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
        ``[offset, offset + vh)`` -- located on the index's prefix sums by
        bisect, and materialized only for those blocks (a cached block's
        rows are sliced, never copied whole) -- so a long document costs
        one snapshot probe per body block, a re-render of what moved, and
        the window itself, not the materialization of every row.  Rows
        come back as exactly ``height`` entries: top region, viewport
        region, bottom region.  Every layout also rebuilds the
        row-ownership table and ships it on the returned
        :class:`ScreenLayout` (alongside the document order of the block
        ids and the window's offset and total rows), so both the
        full-repaint and the diff path resolve clicks against the very
        same result, an overlay painted at the composition root resolves a
        row back to its document address without reaching into the
        viewport, and chrome renders from the layout alone.
        """
        index = self._index
        index.ensure(width)

        top_rows: list[Line] = []
        bottom_rows: list[Line] = []
        # Row owners alongside the rows: (block id, row within that block).
        top_owners: list[tuple[str, int]] = []
        bottom_owners: list[tuple[str, int]] = []
        # Pinned rows are always on screen, so they are materialized every
        # frame from the block's own cache (a borrow; sliced below).  The
        # body contributes no rows here: the index holds its per-block
        # heights, and the window below pulls exactly the overlapping ones.
        for block in index.top_blocks:
            rendered = block.rows_view(width)
            top_rows.extend(rendered)
            top_owners.extend((block.id, i) for i in range(len(rendered)))
        for block in index.bottom_blocks:
            rendered = block.rows_view(width)
            bottom_rows.extend(rendered)
            bottom_owners.extend((block.id, i) for i in range(len(rendered)))

        # The bottom region wins the space it needs (status bar / input box
        # are never lost to the top region); the top region keeps the
        # leading rows that still fit; the viewport may end up empty.
        bottom_kept = bottom_rows[:height]
        top_kept = top_rows[: max(0, height - len(bottom_kept))]
        vh = max(0, height - len(top_kept) - len(bottom_kept))

        self._state.content_height = index.body_total
        self._state.viewport_height = vh
        self._state.clamp()

        # The window: extend rows and owners only from the blocks that
        # overlap ``[offset, offset + vh)``, each contributing its slice of
        # that range.  The index bisects its prefix sums to find the first
        # overlapping block, so the walk touches the window's blocks only;
        # each span's start is the row's address within its block, exactly
        # as a full materialization's slice would name it.
        window_start, window_end = self._state.offset, self._state.offset + vh
        body_rows: list[Line] = []
        visible: list[tuple[str, int]] = []
        for block, start, stop in index.window_spans(window_start, window_end):
            rendered = index.entry_rows(block, width)
            body_rows.extend(rendered[start:stop])
            visible.extend((block.id, i) for i in range(start, stop))
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
            block_order=index.block_order,
            offset=self._state.offset,
            total_rows=self._state.content_height,
            width=width,
            height=height,
            viewport_start=len(top_kept),
        )

    def natural_height(self, width: int) -> int:
        """The rows this document occupies at ``width``: every block's rows.

        What a region whose height is its *content* -- the frame's bottom
        band, a pinned footer -- needs before it can be laid out: the
        fixed regions' rows plus the body's.  The body's share is the
        index's maintained total (the sweep has already re-measured every
        block whose snapshot moved); the pinned blocks are counted through
        :meth:`~motui.core.block.Block.row_count` (a cached block answers
        the length of its cache; nothing here materializes rows).  A band
        laid out at exactly this height holds its whole content and no
        blank fill, so it hugs the edge it is reserved against.
        """
        index = self._index
        index.ensure(width)
        pinned = (*index.top_blocks, *index.bottom_blocks)
        return index.body_total + sum(block.row_count(width) for block in pinned)

    # -- scrolling -----------------------------------------------------------------

    def scroll_up(self, n: int = 1) -> None:
        """Scroll ``n`` rows toward the top (clamped at 0); leaves stick-to-bottom."""
        if n <= 0:
            return
        self._state.scroll_by(-n)
        self._state.stick_to_bottom = False

    def scroll_down(self, n: int = 1) -> None:
        """Scroll ``n`` rows toward the bottom (clamped at the last window).

        Landing on the bottom edge re-attaches the view: content that arrives
        afterwards moves the window again (pgdn all the way down resumes
        auto-follow).
        """
        if n <= 0:
            return
        self._state.scroll_by(n)
        if self._state.offset >= self._max_offset():
            self._state.stick_to_bottom = True

    def scroll_to(self, offset: int) -> bool:
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
        sticks to the bottom.  ``True`` when the offset moved.
        """
        moved = self._state.scroll_to(offset)
        self._state.stick_to_bottom = self._state.offset >= self._max_offset()
        return moved

    def scroll_by(self, delta: int) -> bool:
        """Step the window ``delta`` rows (clamped); ``True`` when it moved.

        The relative sibling of :meth:`scroll_to`: a downward step follows
        the scroll-down rule (landing on the bottom re-attaches the tail),
        an upward one the scroll-up rule (it detaches, at the top edge
        included), and ``0`` moves nothing.
        """
        if delta > 0:
            moved = self._state.scroll_by(delta)
            if self._state.offset >= self._max_offset():
                self._state.stick_to_bottom = True
            return moved
        if delta < 0:
            moved = self._state.scroll_by(delta)
            self._state.stick_to_bottom = False
            return moved
        return False

    def scroll_to_bottom(self) -> None:
        """Stick to the bottom again; the next layout pins the offset to the tail."""
        self._state.offset = self._max_offset()
        self._state.stick_to_bottom = True

    def _max_offset(self) -> int:
        return self._state.max_offset()

    # -- read-only state -------------------------------------------------------------

    @property
    def scroll_state(self) -> ScrollState:
        """The live scroll geometry this viewport moves and layouts update."""
        return self._state

    @property
    def offset(self) -> int:
        """Row index of the window's top within the body rows."""
        return self._state.offset

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
        return self._state.stick_to_bottom
