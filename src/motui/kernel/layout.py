"""Layout values: constraints, the scrolling window and the scroll geometry.

``Scroll``/``ScrollAxis`` hold the one thumb and clamp formula; :class:`Viewport`
keeps per-block heights and prefix sums, so a layout bisects to the window
and materializes only its rows."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from .cell import Line, Surface
from .document import Document, Placement, Section, Sizing

__all__ = [
    "Constraints",
    "RowSpan",
    "ScreenLayout",
    "Scroll",
    "ScrollAxis",
    "Scrollable",
    "ScrollableX",
    "Viewport",
]


@dataclass(frozen=True, slots=True)
class RowSpan:
    """A pane's visible body rows as screen rows: ``first`` .. ``last`` inclusive."""

    first: int
    last: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Constraints:
    """What a component is asked to render into: required ``width`` and an
    optional row budget."""

    width: int = 0
    max_height: int | None = None

    def __post_init__(self) -> None:
        if self.width < 0:
            raise ValueError(f"constraints width must not be negative, got {self.width}")
        if self.max_height is not None and self.max_height < 0:
            raise ValueError(
                f"constraints max_height must not be negative, got {self.max_height}"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScrollAxis:
    """One axis of a scrolling window: offset, content, viewport and follow.

    Every verb returns a new value. ``sticky`` follows the tail, so a clamp
    lands on the bottom rather than keeping a detached offset."""

    offset: int = 0
    content: int = 0
    viewport: int = 0
    sticky: bool = False

    @property
    def max_offset(self) -> int:
        """The furthest legal window start: the content past the window."""
        return max(0, self.content - self.viewport)

    def clamp(self, previous_extent: int | None = None) -> ScrollAxis:
        """Re-derive the offset for this extent, given the caller's previous
        ``max_offset``.

        A sticky axis that stood at the previous bottom pins to the new bottom;
        every other axis clamps in place."""
        limit = self.max_offset
        at_previous_bottom = previous_extent is None or self.offset >= previous_extent
        if self.sticky and at_previous_bottom:
            return replace(self, offset=limit)
        return replace(self, offset=max(0, min(self.offset, limit)))

    def reveal(self, row: int) -> ScrollAxis:
        """Bring ``row`` into the window with the smallest move; ``sticky`` is
        carried through because revealing is an explicit move."""
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
        """The thumb's ``(start, length)`` over ``track`` cells, or ``None`` when the
        content fits; the 1.x formula including its half-to-even rounding."""
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
    """One screen's worth of rows plus the row-ownership table.

    ``rows`` holds the top region, the viewport region and the bottom region;
    ``body_rows`` is the viewport alone. ``row_blocks`` maps each screen row to
    ``(block id, row)``, and ``offset``/``total_rows`` carry the scroll state
    so chrome renders from the layout alone."""

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
        """Normalize the row containers to tuples; a tuple input pays no second pass."""
        if type(self.rows) is not tuple:
            object.__setattr__(self, "rows", tuple(self.rows))
        if type(self.body_rows) is not tuple:
            object.__setattr__(self, "body_rows", tuple(self.body_rows))
        if type(self.row_blocks) is not tuple:
            object.__setattr__(self, "row_blocks", tuple(self.row_blocks))
        if type(self.block_order) is not tuple:
            object.__setattr__(self, "block_order", tuple(self.block_order))

    @property
    def surface(self) -> Surface:
        """The layout's rows as a :class:`Surface` at the layout width, clipped (short
        rows stay short, exactly as the painter writes them)."""
        return Surface.clipped(self.rows, self.width)


class _BodyEntry:
    """One body block's indexed shape: the block, its generation and its height.

    The index stores no rows -- a block's cache is borrowed when the window
    materializes."""

    __slots__ = ("block", "count", "generation")

    def __init__(self, block: Section, generation: int | None, count: int) -> None:
        self.block = block
        self.generation = generation
        self.count = count


class _BodyIndex:
    """The viewport's private body index: who is in the body and how tall.

    Freshness is keyed ``(Document.mutation, constraints)``; within a key each
    block's ``generation`` is probed -- an equal value proves the height -- and
    prefix sums re-run only from a moved entry, the naive suffix the append-mostly case wants."""

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
        """Bring the index up to date for ``c``; cheap when only snapshots moved."""
        self._frame_rows = {}
        mutation = self._document.mutation
        if self._key is not None and self._key == (mutation, c):
            self._sweep(c)
            return
        self._rebuild(mutation, c)

    # -- geometry read by the layout -------------------------------------------------

    @property
    def top_blocks(self) -> list[Section]:
        """The ``Placement.TOP`` blocks in document order."""
        return self._top

    @property
    def bottom_blocks(self) -> list[Section]:
        """The ``Placement.BOTTOM`` blocks in document order."""
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
        """The body entries overlapping ``[start, end)`` as ``(block, slice start,
        slice stop)``; the first is located by bisecting the prefix sums."""
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
        """The rows a windowed block lends this frame; per-call blocks are rendered
        once per frame and handed back."""
        rows = self._frame_rows.get(block)
        if rows is None:
            return block.rows_view(c)
        return rows

    # -- maintenance ------------------------------------------------------------------

    def _sweep(self, c: Constraints) -> None:
        """Probe every entry's generation and re-measure the ones that moved."""
        entries = self._entries
        dirty_from = -1
        for i, entry in enumerate(entries):
            generation = entry.block.generation
            if generation is None:
                # No counter, no memory: render per call, and keep the rows
                # for the window so this frame renders the block only once.
                rows = entry.block.rows_view(c)
                self._frame_rows[entry.block] = rows
                if len(rows) != entry.count:
                    entry.count = len(rows)
                    if dirty_from < 0:
                        dirty_from = i
            elif generation != entry.generation:
                entry.generation = generation
                count = entry.block.row_count(c)
                if count != entry.count:
                    entry.count = count
                    if dirty_from < 0:
                        dirty_from = i
        if dirty_from >= 0:
            self._recompute_prefix(dirty_from)

    def _recompute_prefix(self, from_index: int) -> None:
        """Re-run the prefix sums from ``from_index``; entries before it are still
        true."""
        entries = self._entries
        cum = self._cum
        running = cum[from_index]
        for i in range(from_index, len(entries)):
            running += entries[i].count
            cum[i + 1] = running
        self._total = running

    def _rebuild(self, mutation: int, c: Constraints) -> None:
        """Build every entry from the document; ``block_order`` is rebuilt only when
        the document mutated."""
        blocks = self._document.blocks()
        entries: list[_BodyEntry] = []
        cum: list[int] = [0]
        top: list[Section] = []
        bottom: list[Section] = []
        total = 0
        for block in blocks:
            if block.placement is Placement.TOP:
                top.append(block)
            elif block.placement is Placement.BOTTOM:
                bottom.append(block)
            else:
                generation = block.generation
                if generation is None:
                    # No counter, no memory: render per call, and keep the
                    # rows for the window (one render per frame, as always).
                    rows = block.rows_view(c)
                    self._frame_rows[block] = rows
                    count = len(rows)
                else:
                    count = block.row_count(c)
                entries.append(_BodyEntry(block, generation, count))
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
    """Scroll state over a document: window offset and row ownership.

    Rows are borrowed from the blocks' own caches, never copied whole; the
    body index keeps heights and prefix sums keyed ``(mutation, constraints)``,
    so a stable frame re-probes instead of re-walking."""

    def __init__(self, document: Document) -> None:
        self._document = document
        # The one scroll value: x stays at zero (no horizontal movement),
        # y is tail-following from birth.  ``_last_y_extent`` is the extent
        # the previous layout's clamp derived -- the bookkeeping the value
        # itself does not carry -- so growth under a followed tail is
        # handled by the next clamp.
        self._scroll = Scroll()
        self._last_y_extent: int | None = None
        # Screen row -> (block id, row within that block), or None for a row
        # no block owns; rebuilt by every layout and shipped on its result.
        self._row_blocks: list[tuple[str, int] | None] = []
        # The per-block heights and prefix sums behind every layout; keyed
        # ``(Document.mutation, width)`` and swept per frame (see the class).
        self._index = _BodyIndex(document)

    # -- layout -------------------------------------------------------------------

    def layout(self, width: int, height: int) -> ScreenLayout:
        """Render the document against ``width``x``height`` and apply scroll state.

        Top, body and bottom regions in document order; the bottom region wins a
        height squeeze. The window is sliced only from the blocks overlapping it
        -- bisected on cached prefix sums -- and the row-ownership table ships on
        the result."""
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

        self._scroll = self._scroll.with_y(
            replace(
                self._scroll.y, content=index.body_total, viewport=vh
            ).clamp(self._last_y_extent)
        )
        self._last_y_extent = self._scroll.y.max_offset

        # The window: extend rows and owners only from the blocks that
        # overlap ``[offset, offset + vh)``, each contributing its slice of
        # that range.  The index bisects its prefix sums to find the first
        # overlapping block, so the walk touches the window's blocks only;
        # each span's start is the row's address within its block, exactly
        # as a full materialization's slice would name it.
        window_start = self._scroll.y.offset
        window_end = window_start + vh
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
            offset=self._scroll.y.offset,
            total_rows=index.body_total,
            width=width,
            height=height,
            viewport_start=len(top_kept),
        )

    def _layout_with_fill(self, fill: Section, width: int, height: int) -> ScreenLayout:
        """Lay out a document whose ``FILL`` section takes the residual height; the
        fill is excluded from the index so it never pollutes the prefix sums."""
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

        state = self._scroll.y
        state = replace(state, content=flow_natural, viewport=flow_visible)
        state = state.clamp(self._last_y_extent)
        self._scroll = self._scroll.with_y(state)
        self._last_y_extent = state.max_offset
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
        """The rows the document occupies at ``width``: every block's rows, measured
        without materializing them."""
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
        self.scroll_by(-n)

    def scroll_down(self, n: int = 1) -> None:
        """Scroll ``n`` rows toward the bottom; landing on the bottom edge re-attaches
        auto-follow."""
        if n <= 0:
            return
        self.scroll_by(n)

    def scroll_to(self, offset: int) -> bool:
        """Put the window's top at ``offset``, clamped; landing on the bottom
        re-attaches the tail. ``True`` when the offset moved."""
        y = self._scroll.y
        limit = y.max_offset
        target = max(0, min(int(offset), limit))
        moved = target != y.offset
        self._scroll = self._scroll.with_y(
            replace(y, offset=target, sticky=target >= limit)
        )
        return moved

    def scroll_by(self, delta: int) -> bool:
        """Step the window ``delta`` rows; a downward landing re-attaches the tail,
        an upward move detaches. ``True`` when it moved."""
        if delta == 0:
            return False
        moved = self.scroll_to(self._scroll.y.offset + delta)
        if delta < 0 and self._scroll.y.sticky:
            self._scroll = self._scroll.with_y(
                replace(self._scroll.y, sticky=False)
            )
        return moved

    def scroll_to_bottom(self) -> None:
        """Stick to the bottom again; the next layout pins the offset to the tail."""
        self._scroll = self._scroll.with_y(
            replace(self._scroll.y, offset=self._max_offset(), sticky=True)
        )

    def _max_offset(self) -> int:
        return self._scroll.y.max_offset

    # -- read-only state -------------------------------------------------------------

    @property
    def scroll(self) -> Scroll:
        """The immutable scroll value this viewport moves and layouts update."""
        return self._scroll

    @property
    def offset(self) -> int:
        """Row index of the window's top within the body rows."""
        return self._scroll.y.offset

    @property
    def document(self) -> Document:
        """The document this viewport is the window over; a pane's claimed cells
        resolve against it."""
        return self._document

    @property
    def at_bottom(self) -> bool:
        """Whether the window sits at the bottom of the document."""
        return self._scroll.y.offset >= self._scroll.y.max_offset


@runtime_checkable
class Scrollable(Protocol):
    """Anything a scrollbar or wheel route can read and move: the scroll value
    and the two verbs. Viewport, ScrollPanel and Pane all answer it."""

    @property
    def scroll(self) -> Scroll: ...

    def scroll_to(self, offset: int) -> bool: ...

    def scroll_by(self, delta: int) -> bool: ...


@runtime_checkable
class ScrollableX(Protocol):
    """Anything a horizontal wheel can move, in the one method it needs;
    ``app`` therefore never imports the widget library."""

    def scroll_x_by(self, delta: int) -> bool: ...
