"""Layout values: constraints, the scrolling window and the scroll geometry.

``Constraints`` is the input a component renders against.  ``ScreenLayout`` is
one screen's worth of rows -- the fixed regions plus the scrolling window --
with the row-ownership table that lets an overlay resolve a screen row back
to its document address.  :class:`Viewport` renders a document against a size
and remembers where the user has scrolled to; its private body index keeps
per-block heights and prefix sums so a layout locates the window by bisect
and materializes only the rows the window covers.

``ScrollState`` is the mutable geometry every scrolling surface shares (the
viewport, the scroll view, the pane): the furthest legal offset, the clamp
after a layout, the minimal move that reveals a row and the scrollbar thumb
are formulas that live here once.  :class:`Scrollable` is the narrow
read/write face the scrollbar and the wheel route go through.

``ScrollAxis``/``Scroll`` are the 2.0 immutable two-axis values.  The thumb
formula they carry is copied verbatim from ``ScrollState`` (including the
builtin ``round`` half-to-even rule).  The 1.x clamp remembers the previous
extent so a tail-following window can pin to a bottom that moved; this wave
does not carry that bookkeeping -- the ``sticky`` branch compares the offset
against this value's own extent, which is the equivalent test the W0a work
order asks for.  W2.6 restores the previous-extent behavior when
``ScrollState`` is retired.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from .cell import Line
from .document import Document, Placement, Section, Sizing

__all__ = [
    "Constraints",
    "ScreenLayout",
    "Scroll",
    "ScrollAxis",
    "ScrollState",
    "Scrollable",
    "Viewport",
    "as_constraints",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class Constraints:
    """What a component is asked to render into.

    ``width`` is required and non-negative; ``max_height`` is ``None`` for a
    natural height or a non-negative row budget for a filled one.
    """

    width: int = 0
    max_height: int | None = None

    def __post_init__(self) -> None:
        if self.width < 0:
            raise ValueError(f"constraints width must not be negative, got {self.width}")
        if self.max_height is not None and self.max_height < 0:
            raise ValueError(
                f"constraints max_height must not be negative, got {self.max_height}"
            )


def as_constraints(value: Constraints | int) -> Constraints:
    """Normalize a render argument: an ``int`` width becomes constraints.

    The 2.0 component signature takes :class:`Constraints`; the 1.x tests and
    call sites still pass a bare width.  Accepting both at the seam keeps the
    old spelling working while a component migrates, without each component
    re-spelling the conversion.  A negative width is rejected by
    ``Constraints`` itself, so both spellings fail with the same
    ``ValueError``.
    """
    if isinstance(value, Constraints):
        return value
    if isinstance(value, int):
        return Constraints(width=value)
    raise TypeError(f"expected Constraints or int, got {type(value).__name__}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ScrollAxis:
    """One axis of a scrolling window: offset, content, viewport and follow.

    Every verb returns a new value; the receiver is never mutated.  ``sticky``
    marks the value as tail-following (the vertical axis of :class:`Scroll`
    starts sticky), so a clamp lands on the bottom rather than keeping a
    detached offset.
    """

    offset: int = 0
    content: int = 0
    viewport: int = 0
    sticky: bool = False

    @property
    def max_offset(self) -> int:
        """The furthest legal window start: the content past the window."""
        return max(0, self.content - self.viewport)

    def clamp(self) -> ScrollAxis:
        """Re-derive the offset for this extent.

        A sticky axis whose offset stood at the extent pins to the bottom;
        every other axis clamps into ``[0, max_offset]``.  With no previous
        extent stored on the value, ``max_offset`` is the equivalent test
        (see the module docstring), so the two branches coincide until W2.6.
        """
        limit = self.max_offset
        if self.sticky and self.offset >= limit:
            return replace(self, offset=limit)
        return replace(self, offset=max(0, min(self.offset, limit)))

    def reveal(self, row: int) -> ScrollAxis:
        """Bring ``row`` into the window, moving as little as possible.

        The row is clamped into the content; an already visible row (or an
        empty content or viewport) moves nothing, and the returned offset is
        clamped into the legal range.  ``sticky`` is carried through
        unchanged: revealing is an explicit move, not a tail follow.
        """
        if self.content <= 0:
            return self
        target = max(0, min(int(row), self.content - 1))
        if self.viewport <= 0:
            return self
        if target < self.offset:
            return replace(self, offset=max(0, min(target, self.max_offset)))
        if target >= self.offset + self.viewport:
            return replace(
                self,
                offset=max(0, min(target - self.viewport + 1, self.max_offset)),
            )
        return self

    def thumb(self, track: int, min_length: int = 1) -> tuple[int, int] | None:
        """The thumb's ``(start, length)`` over ``track`` cells.

        ``None`` when there is nothing to map -- the content fits the window
        (an empty document included) or ``min_length`` shaved the thumb away.
        The formula is the 1.x one, including the builtin ``round`` (half to
        even), so the geometry is reproducible rather than approximate.
        """
        if track <= 0 or self.content <= self.viewport:
            return None
        length = min(
            track,
            max(
                min_length,
                round(self.viewport * track / self.content),
            ),
        )
        if length <= 0:
            return None
        travel = max(1, track - length)
        span = max(1, self.content - self.viewport)
        start = min(travel, max(0, round(self.offset * travel / span)))
        return start, length


@dataclass(frozen=True, slots=True, kw_only=True)
class Scroll:
    """A two-axis scroll state; the vertical axis follows the tail by default."""

    x: ScrollAxis = ScrollAxis()
    y: ScrollAxis = field(default_factory=lambda: ScrollAxis(sticky=True))

    def with_x(self, axis: ScrollAxis) -> Scroll:
        """A copy of this scroll with its horizontal axis replaced."""
        return replace(self, x=axis)

    def with_y(self, axis: ScrollAxis) -> Scroll:
        """A copy of this scroll with its vertical axis replaced."""
        return replace(self, y=axis)


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
    borrow (:meth:`~motui.kernel.document.Section.rows_view`), never owned here --
    so the entry is only a height token the geometry recomputes from: the
    rows themselves are taken from the block's own cache at the moment the
    window materializes them.  ``revision`` is the snapshot the block
    answered when ``count`` was measured; ``None`` marks a block without a
    usable snapshot, which is re-measured on every :meth:`_BodyIndex.ensure`
    (a block whose memory is off cannot prove itself unchanged).
    """

    __slots__ = ("block", "count", "revision")

    def __init__(self, block: Section, revision: object, count: int) -> None:
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

    Freshness is a two-level check.  The key ``(Document.mutation, c)``
    catches structural change and any change to the constraints (width or
    height budget) -- either one rebuilds every entry (``row_count`` renders
    a first layout's blocks exactly as the per-frame walk always did).  Within
    a key, every ``ensure`` sweeps the entries and probes each block's
    ``revision()``: an equal value means the block's height stands (one cheap
    value comparison -- the snapshot is a value, so equality is the block's
    own promise that its rows are unchanged), a moved value re-measures the
    block through :meth:`~motui.kernel.document.Section.row_count` (which
    re-renders and refills the block's own cache) and re-runs the prefix sums
    **from that entry on** -- the naive suffix recompute, because a moved
    block in an append-mostly document is almost always at the tail.  A
    ``None`` snapshot (no protocol, or memory switched off) is always dirty:
    the entry is re-measured every frame, which re-renders that block every
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
        # ``(mutation, constraints)`` the entries were built for; ``None``
        # until the first ``ensure``.
        self._key: tuple[int, Constraints] | None = None
        self._entries: list[_BodyEntry] = []
        self._cum: list[int] = [0]
        self._total = 0
        self._top: list[Section] = []
        self._bottom: list[Section] = []
        self._order: tuple[str, ...] = ()
        self._order_mutation: int = -1  # no document starts at -1 mutations
        # Rows rendered by this frame's measurement pass, for the blocks
        # that render per call and so must not be asked twice in one frame;
        # emptied by every ``ensure`` -- nothing survives the frame.
        self._frame_rows: dict[Section, Sequence[Line]] = {}

    def ensure(self, c: Constraints) -> None:
        """Bring the index up to date for ``c``; the one entry door.

        After it answers, the geometry properties (pinned blocks, entries,
        prefix sums, body total, block order) describe the document at these
        constraints as of the blocks' current snapshots.  Cheap when nothing
        changed: one key comparison plus one ``revision()`` probe per body
        block.
        """
        self._frame_rows = {}
        mutation = self._document.mutation
        if self._key is not None and self._key == (mutation, c):
            self._sweep(c)
            return
        self._rebuild(mutation, c)

    # -- geometry read by the layout -------------------------------------------------

    @property
    def top_blocks(self) -> list[Section]:
        """The ``pin="top"`` blocks in document order."""
        return self._top

    @property
    def bottom_blocks(self) -> list[Section]:
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

    def window_spans(self, start: int, end: int) -> list[tuple[Section, int, int]]:
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
        spans: list[tuple[Section, int, int]] = []
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

    def entry_rows(self, block: Section, c: Constraints) -> Sequence[Line]:
        """The rows a windowed body block lends this frame.

        The measurement pass already rendered every block without a usable
        snapshot (they render per call by contract, so asking them again
        here would render them twice in one frame); their rows are kept in
        ``_frame_rows`` for this frame and handed back, so the slice the
        window takes answers the very rows the entry's count was measured
        from.  Every other block answers its own cache through
        :meth:`~motui.kernel.document.Section.rows_view` -- a hit, the sweep has
        kept it warm.
        """
        rows = self._frame_rows.get(block)
        if rows is None:
            return block.rows_view(c)
        return rows

    # -- maintenance ------------------------------------------------------------------

    def _sweep(self, c: Constraints) -> None:
        """Probe every entry's snapshot and re-measure the ones that moved."""
        entries = self._entries
        dirty_from = -1
        for i, entry in enumerate(entries):
            revision = entry.block.revision()
            if revision is None:
                # No snapshot, no memory: render per call, and keep the rows
                # for the window so this frame renders the block only once.
                rows = entry.block.rows_view(c)
                self._frame_rows[entry.block] = rows
                if len(rows) != entry.count:
                    entry.count = len(rows)
                    if dirty_from < 0:
                        dirty_from = i
            elif revision != entry.revision:
                entry.revision = revision
                count = entry.block.row_count(c)
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

    def _rebuild(self, mutation: int, c: Constraints) -> None:
        """Build every entry from the document (a key change: structure or constraints).

        The walk is the one per-document pass: pinned blocks are filed by
        region, each body block is measured through ``row_count`` (which
        renders a first-seen block exactly once, as the per-frame rows walk
        always did), and the ids collected in the same pass become the
        ``block_order`` tuple -- rebuilt only when the document actually
        mutated, so a constraints-only change reuses the ids of the same
        structure.
        """
        blocks = self._document.blocks()
        entries: list[_BodyEntry] = []
        cum: list[int] = [0]
        top: list[Section] = []
        bottom: list[Section] = []
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
                    rows = block.rows_view(c)
                    self._frame_rows[block] = rows
                    count = len(rows)
                else:
                    count = block.row_count(c)
                entries.append(_BodyEntry(block, revision, count))
                cum.append(total + count)
                total += count
        self._entries = entries
        self._cum = cum
        self._total = total
        self._top = top
        self._bottom = bottom
        self._key = (mutation, c)
        if mutation != self._order_mutation:
            self._order = tuple(block.id for block in blocks)
            self._order_mutation = mutation


class Viewport:
    """Scroll state over a document: window offset, row ownership.

    One window over one document: the offset (with its stick-to-bottom
    rule) and the row-ownership table each layout rebuilds.  The rows
    themselves are the blocks' -- every walk here goes through the block's
    own cache (the read-only doors :meth:`~motui.kernel.document.Section.rows_view`
    and :meth:`~motui.kernel.document.Section.row_count`), borrowed, never copied.
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

        A document with a ``FILL`` section takes
        :meth:`_layout_with_fill` instead: the natural flow keeps its own
        window and the fill takes the residual height.
        """
        fill = self._document.fill()
        if fill is not None:
            return self._layout_with_fill(fill, width, height)
        index = self._index
        c = Constraints(width=width)
        index.ensure(c)

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
            rendered = block.rows_view(c)
            top_rows.extend(rendered)
            top_owners.extend((block.id, i) for i in range(len(rendered)))
        for block in index.bottom_blocks:
            rendered = block.rows_view(c)
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
            rendered = index.entry_rows(block, c)
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

    def _layout_with_fill(self, fill: Section, width: int, height: int) -> ScreenLayout:
        """Lay out a document whose last flow section fills the remainder.

        The index is deliberately not consulted: a fill section would enter
        it as an ordinary body block (its natural height is meaningless)
        and pollute the prefix sums every later layout would bisect.  This
        path walks the sections directly instead -- the flow is exactly the
        natural content above the fill, so it is materialized here anyway.

        Pinned regions keep the normal priority (bottom first, then top,
        each clamped to the screen).  The flow is windowed against the
        space left, with the same :class:`ScrollState` clamp the indexed
        path uses, so scrolling and tail-follow behave identically; the
        fill then renders under a ``max_height`` of the residual rows and
        is blank-padded to it (a surface that answers fewer rows leaves the
        rest unowned).  ``total_rows`` counts the natural flow only: the
        fill never scrolls.
        """
        blocks = self._document.blocks()
        c = Constraints(width=width)
        top_rows: list[Line] = []
        top_owners: list[tuple[str, int]] = []
        bottom_rows: list[Line] = []
        bottom_owners: list[tuple[str, int]] = []
        flow_rows: list[Line] = []
        flow_owners: list[tuple[str, int]] = []
        for block in blocks:
            if block is fill:
                continue
            rendered = block.rows_view(c)
            if block.placement is Placement.TOP:
                top_rows.extend(rendered)
                top_owners.extend((block.id, i) for i in range(len(rendered)))
            elif block.placement is Placement.BOTTOM:
                bottom_rows.extend(rendered)
                bottom_owners.extend((block.id, i) for i in range(len(rendered)))
            else:
                flow_rows.extend(rendered)
                flow_owners.extend((block.id, i) for i in range(len(rendered)))

        bottom_kept = bottom_rows[:height]
        top_kept = top_rows[: max(0, height - len(bottom_kept))]
        available = max(0, height - len(top_kept) - len(bottom_kept))
        flow_natural = len(flow_rows)
        flow_visible = min(available, flow_natural)

        state = self._state
        state.content_height = flow_natural
        state.viewport_height = flow_visible
        state.clamp()
        start = state.offset
        visible = flow_rows[start : start + flow_visible]
        visible_owners = flow_owners[start : start + flow_visible]

        fill_budget = available - flow_visible
        fill_rows: list[Line] = []
        fill_owners: list[tuple[str, int] | None] = []
        if fill_budget > 0:
            rendered = list(
                fill.rows_view(Constraints(width=width, max_height=fill_budget))
            )[:fill_budget]
            fill_rows = rendered + [Line() for _ in range(fill_budget - len(rendered))]
            fill_owners = [(fill.id, i) for i in range(len(rendered))]
            fill_owners += [None] * (fill_budget - len(rendered))

        body_rows = visible + fill_rows
        rows = top_kept + body_rows + bottom_kept
        row_blocks = [
            *top_owners[: len(top_kept)],
            *visible_owners,
            *fill_owners,
            *bottom_owners[: len(bottom_kept)],
        ]
        return ScreenLayout(
            rows=tuple(rows),
            body_rows=tuple(body_rows),
            row_blocks=tuple(row_blocks),
            block_order=tuple(block.id for block in blocks),
            offset=state.offset,
            total_rows=flow_natural,
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
        :meth:`~motui.kernel.document.Section.row_count` (a cached block answers
        the length of its cache; nothing here materializes rows).  A band
        laid out at exactly this height holds its whole content and no
        blank fill, so it hugs the edge it is reserved against.

        A ``FILL`` block has no natural height (it takes what is left), so
        a document that holds one is measured as pinned rows plus natural
        flow rows -- never through the body index, which would count the
        fill's own render at the constraint height and make the band grow
        to fill itself.
        """
        blocks = self._document.blocks()
        if self._document.fill() is not None:
            c = Constraints(width=width)
            return sum(
                block.row_count(c)
                for block in blocks
                if block.sizing is not Sizing.FILL
            )
        index = self._index
        c = Constraints(width=width)
        index.ensure(c)
        pinned = (*index.top_blocks, *index.bottom_blocks)
        return index.body_total + sum(block.row_count(c) for block in pinned)

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


@dataclass
class ScrollState:
    """One scrolling window's geometry: offset, content and viewport rows.

    The value is mutable -- a scrolling surface owns one and moves it in
    place -- and every verb clamps into the window's own extent, so a caller
    can never park the offset outside ``[0, max_offset()]`` through this
    API.  ``stick_to_bottom`` switches the tail-follow rule on: a
    :meth:`clamp` pins to the bottom while the offset stood at the previous
    extent, which is what makes a fresh viewport show a streaming document's
    tail and a detached one stay put.
    """

    offset: int = 0
    content_height: int = 0
    viewport_height: int = 0
    stick_to_bottom: bool = False
    #: The extent the last :meth:`clamp` derived, ``None`` before one: the
    #: "old max" a stick-to-bottom clamp compares the offset against.  It is
    #: bookkeeping, not part of the value's identity.
    _extent: int | None = field(default=None, repr=False, compare=False)

    def max_offset(self) -> int:
        """The furthest legal window start: the content past the window."""
        return max(0, self.content_height - self.viewport_height)

    def clamp(self) -> bool:
        """Re-derive the offset after a layout; ``True`` when it moved.

        A stick-to-bottom state pins to the new bottom when the offset stood
        at the previous layout's extent -- or when no layout has run yet --
        so content that grew under a followed window carries it along and a
        window the user detached stays where it was.  Every other state
        clamps into ``[0, max_offset()]``.  Either way the current extent is
        remembered for the next comparison.
        """
        previous = self.offset
        limit = self.max_offset()
        at_previous_bottom = self._extent is None or previous >= self._extent
        if self.stick_to_bottom and at_previous_bottom:
            self.offset = limit
        else:
            self.offset = max(0, min(previous, limit))
        self._extent = limit
        return self.offset != previous

    def scroll_to(self, offset: int) -> bool:
        """Move the window's top to ``offset`` (clamped); ``True`` on a move.

        Landing on the bottom edge re-attaches a tail-following state; a
        target above it detaches one, exactly the driver-visible rule that
        scrolling to the tail resumes auto-follow.
        """
        target = max(0, min(int(offset), self.max_offset()))
        moved = target != self.offset
        self.offset = target
        if target >= self.max_offset():
            self.stick_to_bottom = True
        elif self.stick_to_bottom:
            self.stick_to_bottom = False
        return moved

    def scroll_by(self, delta: int) -> bool:
        """Step the window ``delta`` rows (clamped); ``True`` on a move.

        A downward step that lands on the bottom edge re-attaches the tail;
        any upward step detaches it, even when the window was already at the
        top -- the same rule the viewport's :meth:`scroll_up` follows.
        """
        if delta == 0:
            return False
        moved = self.scroll_to(self.offset + delta)
        if delta < 0:
            self.stick_to_bottom = False
        return moved

    def reveal(self, row: int) -> bool:
        """Bring ``row`` into the window, moving as little as possible.

        The row is clamped into the content; a target already visible (or a
        window showing everything) moves nothing, and an empty content or an
        empty window answers ``False``.  A target above the window parks it
        at the target; one below parks it so the target is the last visible
        row.
        """
        if self.content_height <= 0:
            return False
        target = max(0, min(int(row), self.content_height - 1))
        if self.viewport_height <= 0:
            return False
        if target < self.offset:
            return self.scroll_to(target)
        if target >= self.offset + self.viewport_height:
            return self.scroll_to(target - self.viewport_height + 1)
        return False

    def thumb(self, track_height: int, min_length: int = 1) -> tuple[int, int] | None:
        """The thumb's ``(start, length)`` over ``track_height`` cells.

        ``None`` when there is nothing to map -- the content fits the window
        (an empty document included) or ``min_length`` shaved the thumb away
        -- which a scrollbar paints as its plain track.  Otherwise::

            length = min(track, max(min_length, round(viewport * track / content)))
            travel = max(1, track - length)
            span   = max(1, content - viewport)
            start  = min(travel, max(0, round(offset * travel / span)))

        ``round`` is the builtin, so a half goes to the even integer and the
        geometry is reproducible rather than merely approximate.  This is the
        only thumb formula: the pane scrollbar and the scroll view's bar both
        call it.
        """
        if track_height <= 0 or self.content_height <= self.viewport_height:
            return None
        length = min(
            track_height,
            max(min_length, round(self.viewport_height * track_height / self.content_height)),
        )
        if length <= 0:
            return None
        travel = max(1, track_height - length)
        span = max(1, self.content_height - self.viewport_height)
        start = min(travel, max(0, round(self.offset * travel / span)))
        return start, length


@runtime_checkable
class Scrollable(Protocol):
    """Anything a scrollbar or a wheel route can read and move.

    The narrow face the interaction tier needs: the geometry to paint a
    thumb from and the two verbs to move the window.  :class:`Viewport`,
    ``ScrollPanel`` and ``Pane`` (delegating its viewport) answer it without
    sharing a base class.
    """

    @property
    def scroll_state(self) -> ScrollState: ...

    def scroll_to(self, offset: int) -> bool: ...

    def scroll_by(self, delta: int) -> bool: ...
