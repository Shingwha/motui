"""Document model: addressable blocks rendered by components.

The toolkit's unit of content is a :class:`Section`: a stable id, a
:class:`Component` that knows how to render itself at a given width, and a
row cache that follows the component's own revision snapshot.  There is no
lifecycle flag: a block caches exactly when its component can prove the rows
are unchanged (:class:`Revisioned` answering a snapshot), and re-renders
otherwise.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from .cell import Line, Surface

if TYPE_CHECKING:  # the protocol names the layout model; no runtime import needed
    from .layout import Constraints

__all__ = [
    "Component",
    "Document",
    "Fill",
    "Placement",
    "Revisioned",
    "Section",
    "Sizing",
    "descend",
    "descend_chain",
]


class Placement(Enum):
    """Where a section sits: the scrolling body or a fixed region.

    ``FLOW`` is the document body a viewport scrolls; ``TOP``/``BOTTOM`` are
    the fixed bands that never scroll away.
    """

    FLOW = "flow"
    TOP = "top"
    BOTTOM = "bottom"


class Sizing(Enum):
    """How a section consumes height: its content or the pane's remainder.

    ``NATURAL`` sections contribute their rendered rows.  At most one
    ``FILL`` section -- the last flow section -- takes whatever height the
    natural content leaves, which is the slot a game canvas or a dashboard
    fills.
    """

    NATURAL = "natural"
    FILL = "fill"


@dataclass(frozen=True, slots=True)
class Fill:
    """A component that owns a pane's whole remaining height.

    This wave keeps ``Fill`` as the public value behind
    ``Document.add(..., sizing=Sizing.FILL)``; the W4 ``PaneContent`` union
    (a document *or* a fill) is not introduced yet.  Frozen: the widget is
    the value's identity.
    """

    widget: Component



@runtime_checkable
class Component(Protocol):
    """Anything that renders itself into a surface: ``render(c) -> Surface``.

    The one protocol the document model knows: a component is handed the
    constraints available to it (the width, and an optional height budget)
    and answers with the rows it wants painted there.  Nothing else about its
    host is promised, and nothing about its own state is assumed.
    """

    def render(self, c: Constraints) -> Surface:
        ...


@runtime_checkable
class Revisioned(Protocol):
    """A component whose rows are a pure function of a value snapshot.

    ``revision()`` answers *everything the component's rows depend on*, as a
    value: while two calls answer **equal** snapshots the component promises
    that ``render(c)`` answers equal rows at any one width -- so a cache
    keyed on the pair ``(width, revision())`` may hand the older rows back.
    The row cache on :meth:`Section.rows` is exactly that cache, and the
    promise is what makes it safe to keep a block's rows between frames: a
    hover that moves, a streamed assignment, a toggled mark changes the
    snapshot, so the next ``rows()`` misses and re-renders.

    Two rules make the promise hold.

    The snapshot must be **value semantics**: every mutable field the rows
    read goes in copied, not by reference.  ``Table.rows`` is the canonical
    trap -- ``rows == cached`` is trivially true when "cached" holds the very
    same list, so an in-place edit would never be seen -- and a tuple built
    over a snapshot (``tuple(map(tuple, self.rows))``) is the shape that
    catches it.  Reference identity is not value identity, and a component
    that hands its live state out is worse than one without a revision at
    all: it would freeze under a cache instead of merely being re-rendered.

    The snapshot must **cost much less than the render it guards** -- the
    design bound is at most a few percent of one ``render(c)``, because
    every cached frame pays the snapshot again while only a miss pays the
    render; a snapshot that re-wraps the text it guards has moved the cost,
    not removed it.

    ``None`` is the off switch, not a snapshot: :meth:`Section.rows` never
    caches a block whose revision answers ``None`` (no snapshot, no
    invalidation), and ``Text._revision`` returning ``None`` closes that
    component's own row memory the same way.  A block whose component does
    not implement this protocol at all also re-renders every layout.
    Optional: hosts and blocks check ``isinstance(component,
    Revisioned)``.
    """

    def revision(self) -> object:
        ...


#: How many container levels :func:`descend` walks before stopping.
#:
#: A safety rail, not a layout rule: a well-formed tree is a handful of
#: levels deep, and a malformed container that answers ``child_at`` with
#: itself would otherwise loop forever.  Past the limit ``descend`` stops
#: and hands back the layer it is on -- it never raises.
_DESCEND_LIMIT = 64


def descend_chain(
    component: Component, row: int, col: int
) -> tuple[tuple[Component, int, int], ...]:
    """Every component owning a cell, outermost first, with its own coords.

    Walks ``child_at`` from ``component`` down, recording each
    component it lands on beside the cell in that component's own
    coordinate space.  The first entry is always ``(component, row, col)``;
    the last is the deepest component the cell descends to, which is what
    :func:`descend` answers.  Pure, allocation-light (one tuple per level)
    and depth-guarded like :func:`descend` (``_DESCEND_LIMIT``).

    The chain is the value a host routes with: a wheel finds the nearest
    :class:`~motui.kernel.scroll.Scrollable` by walking it backwards, and a
    click can address any ancestor without a second hit test.
    """
    chain: list[tuple[Component, int, int]] = [(component, row, col)]
    for _ in range(_DESCEND_LIMIT):
        child_at = getattr(component, "child_at", None)
        if child_at is None:
            break
        cell = child_at(row, col)
        if cell is None:
            break
        component, row, col = cell
        chain.append((component, row, col))
    return tuple(chain)


def descend(component: Component, row: int, col: int) -> tuple[Component, int, int]:
    """The deepest component owning a cell, with that component's own coords.

    Walks ``child_at`` until a component has no coordinate door or declines
    the cell; then returns it unchanged.  Pure, allocation-light
    and depth-guarded (a malformed container that returns itself cannot
    loop forever).  The kernel's one coordinate-descend primitive, shared by
    the pointer tier and the focus ring's click policy; it is the tail of
    :func:`descend_chain`.
    """
    return descend_chain(component, row, col)[-1]


class Section:
    """One addressable row-producing unit inside a :class:`Document`.

    Besides the id and the widget, a block owns its own **row cache**
    (:meth:`rows`): the rows a widget answered at one width are the
    block's rows, so the cache belongs with the identity they hang on rather
    than in whatever object happened to lay them out last.  A cache on the
    layout side had to be pruned by id every frame -- a per-frame walk of the
    whole document to catch a removed block or an id reused by a new one; a
    cache on the block dies with the block and nothing reuses it.  The cache
    is keyed ``(width, max_height, revision)``, and only a widget that
    implements :class:`Revisioned` and answers a non-``None`` snapshot is
    cached: an unrevisioned widget re-renders on every call, because the
    block has no way to see that its content changed.
    """

    __slots__ = (
        "_cacheable",
        "_id",
        "_placement",
        "_rows_cache",
        "_rows_max_height",
        "_rows_revision",
        "_rows_width",
        "_sizing",
        "_widget",
    )

    def __init__(
        self,
        id: str,
        widget: Component,
        *,
        placement: Placement = Placement.FLOW,
        sizing: Sizing = Sizing.NATURAL,
    ) -> None:
        if not isinstance(placement, Placement):
            raise ValueError(f"placement must be a Placement, got {placement!r}")
        if not isinstance(sizing, Sizing):
            raise ValueError(f"sizing must be a Sizing, got {sizing!r}")
        if sizing is Sizing.FILL and placement is not Placement.FLOW:
            raise ValueError("a FILL section must be placed in the flow")
        self._id = id
        self._widget = widget
        self._placement = placement
        self._sizing = sizing
        # The widget's protocol membership never changes (it is fixed by
        # the type), so it is decided once here: a per-frame isinstance on
        # every block would cost more than the cache saves.
        self._cacheable = isinstance(widget, Revisioned)
        # The cache slot: the last rows rendered at ``_rows_width`` whose
        # widget answered ``_rows_revision``.  ``None`` rows mean "nothing
        # cached yet" -- a revision of ``None`` (a widget without the
        # protocol, or one with its memory switched off) is a legitimate key,
        # so it cannot double as the empty marker.
        self._rows_cache: list[Line] | None = None
        self._rows_width: int | None = None
        self._rows_max_height: int | None = None
        self._rows_revision: object = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def widget(self) -> Component:
        """The component this section renders."""
        return self._widget

    @property
    def placement(self) -> Placement:
        """Where the block sits: the body or a fixed top/bottom region."""
        return self._placement

    @property
    def sizing(self) -> Sizing:
        """Whether the block takes its natural height or the remaining one."""
        return self._sizing

    def revision(self) -> object:
        """The widget's snapshot for the rows it renders, or ``None``.

        Forwards to a :class:`Revisioned` widget and answers ``None``
        for anything else -- "no snapshot", the answer that leaves the row
        cache off.
        """
        if self._cacheable:
            return cast("Revisioned", self._widget).revision()
        return None

    def render(self, c: Constraints) -> list[Line]:
        """Forward rendering to the block's component: the *fresh-rows* door.

        Deliberately uncached: this is "render it again, now".  The cached
        door every layout-side caller wants is :meth:`rows`.  The answer
        stays ``list[Line]`` for the existing callers, though the component
        protocol answers a Surface.
        """
        return self.rows(c)

    def rows(self, c: Constraints) -> list[Line]:
        """The block's rows under ``c``, cached when the component allows it.

        The one door for "a list of this block's rows the caller owns" --
        the door to reach for whenever the rows (or the list holding them)
        might be kept or changed -- and the cache it answers from is the
        block's own, keyed ``(width, max_height, revision())``.  The caching
        rule is one line:

        * a component that implements :class:`Revisioned` **and** answers a
          snapshot is cached until the width or the snapshot moves;
        * anything else -- no protocol, or a ``None`` snapshot ("memory
          off") -- re-renders per call, because the block cannot see a
          change it would have to invalidate on.

        The returned list is a fresh copy the caller owns (the cache keeps
        its own); the :class:`Line` values inside it are immutable and may
        be shared, so a hit is one list copy, not a row rebuild.  A read-only
        walker that never keeps nor changes the list pays that copy for
        nothing and takes :meth:`rows_view` or :meth:`row_count` instead.
        Cache entries die with the block: nothing is pruned anywhere, and a
        removed block's id reused by a new block starts with a fresh slot.
        """
        return list(self._refresh(c))

    def rows_view(self, c: Constraints) -> Sequence[Line]:
        """The block's rows under ``c``, borrowed from the cache: read-only.

        The door for "read the rows, keep nothing, change nothing" -- the
        layout walk, a row count, a search or a gesture reading one row.  A
        cacheable block whose cache answers hands back **the cache list
        itself**: no copy, but also no ownership -- the caller must not
        mutate it.  A later miss swaps the cache for a freshly rendered
        list (the borrowed one is replaced, never edited in place), so the
        borrowed list keeps whatever it held, but a subsequent call may
        hand back a different list: the answer is good for this call only,
        and nothing may depend on reading it across calls.  This is safe
        to share because the :class:`Line` values inside are immutable; a
        caller that wants a list it may change or keep takes :meth:`rows`.
        A block whose component is not cacheable answers a fresh
        ``render(c)`` list -- there is no cache to protect, and the
        caller owns that one.
        """
        return self._refresh(c)

    def row_count(self, c: Constraints) -> int:
        """How many rows the block occupies under ``c``.

        The door for callers that need the count alone -- height walks,
        prefix sums, an "is this row in range" check.  It follows the same
        cache rule as :meth:`rows`: a hit answers ``len`` of the cache, a
        miss renders once and fills the block's own cache first (a first
        layout pays the render either way), and a component without a
        usable snapshot is rendered per call and measured.  ``row_count(c)
        == len(rows(c))`` always.
        """
        return len(self._refresh(c))

    def _refresh(self, c: Constraints) -> list[Line]:
        """The one hit-or-miss decision every rows door shares.

        Answers the block's rows under ``c``, rendering and filling the
        cache on a miss; the caching rule is the one :meth:`rows`
        documents.  The answer is either **the cache list itself** (a
        cacheable block: borrowed, the caller must not mutate it) or a
        fresh render (a component without a usable snapshot: never cached,
        the caller owns it).  Doors that hand the list out copy it
        (:meth:`rows`); doors that only read take it as is.

        The cache key is ``(width, max_height, revision)``: a height budget
        changes the rows a component answers, so it must miss exactly like a
        width change does.
        """
        if not self._cacheable:
            return self._render(c)  # no snapshot
        revision = cast("Revisioned", self._widget).revision()
        if revision is None:
            # A component with the protocol switched its memory off (``None``
            # is "no snapshot"): the block must not cache what it cannot
            # invalidate.
            return self._render(c)
        if (
            self._rows_cache is not None
            and self._rows_width == c.width
            and self._rows_max_height == c.max_height
            and self._rows_revision == revision
        ):
            return self._rows_cache
        rows = self._render(c)
        self._rows_cache = rows
        self._rows_width = c.width
        self._rows_max_height = c.max_height
        self._rows_revision = revision
        return rows

    def _render(self, c: Constraints) -> list[Line]:
        """Render the component once and enforce the row contract.

        The component answers a :class:`Surface`; its rows are copied out
        (the cache owns its list) and the section remains the final guard:
        an over-wide row is clipped to ``c.width`` and a row past
        ``c.max_height`` is dropped.  A well-behaved component already
        satisfies both, so the clipping pass normally hands every row back
        unchanged.
        """
        surface = self._widget.render(c)
        rows = list(surface.rows)
        if c.max_height is not None and len(rows) > c.max_height:
            rows = rows[: c.max_height]
        if any(row.width > c.width for row in rows):
            rows = list(Surface.clipped(rows, c.width).rows)
        return rows

    def __repr__(self) -> str:
        return f"Section(id={self._id!r}, placement={self._placement!r})"


class Document:
    """An ordered collection of blocks, addressable by id."""

    def __init__(self) -> None:
        self._blocks: list[Section] = []
        self._by_id: dict[str, Section] = {}
        self._auto_index = -1  # first generated id is "b0"
        # Monotone count of content mutations: ``add``/``remove`` each bump
        # it and nothing ever resets it, so an equal count proves the block
        # list is unchanged.  Caches of the block list (``blocks``)'s
        # snapshot, a layout-side index) key on it instead of diffing.
        self._mutation = 0
        # The last snapshot ``blocks`` handed out, keyed by the mutation
        # count it was taken at; ``None`` means "none taken yet".
        self._blocks_cache: tuple[int, tuple[Section, ...]] | None = None

    def _next_auto_id(self) -> str:
        """The first ``b{n}`` id past the last one handed out that is free.

        The candidate is derived from the cursor and advanced past every id
        the document already holds -- an explicit ``b0`` pushes the first
        auto id to ``b1`` -- so a generated id never collides with one a
        caller claimed; the cursor lands on the id handed out.
        """
        index = self._auto_index + 1
        while f"b{index}" in self._by_id:
            index += 1
        self._auto_index = index
        return f"b{index}"

    def add(
        self,
        component: Component,
        *,
        id: str | None = None,
        placement: Placement = Placement.FLOW,
        sizing: Sizing = Sizing.NATURAL,
    ) -> Section:
        """Append a block; auto id ``b{n}`` when ``id`` is None.

        ``placement`` is the body (``FLOW``, the default) or a fixed
        ``TOP``/``BOTTOM`` band.  Duplicate ids raise ``ValueError``.

        The fill rules are checked here, at the one door a block enters the
        document through: at most one ``FILL`` section, it takes only the flow
        placement, and no flow section may follow it (a fill owns the remainder
        below every natural row, so content appended after it could never be
        laid out).  Fixed-region sections are natural-height by definition and
        therefore reject ``FILL``.
        """
        if not isinstance(placement, Placement):
            raise ValueError(f"placement must be a Placement, got {placement!r}")
        if not isinstance(sizing, Sizing):
            raise ValueError(f"sizing must be a Sizing, got {sizing!r}")
        if sizing is Sizing.FILL:
            if placement is not Placement.FLOW:
                raise ValueError("a FILL section must be placed in the flow")
            if any(block.sizing is Sizing.FILL for block in self._blocks):
                raise ValueError("a document holds at most one FILL section")
        elif placement is Placement.FLOW and any(
            block.sizing is Sizing.FILL for block in self._blocks
        ):
            raise ValueError("a flow section cannot follow a FILL section")
        if id is None:
            id = self._next_auto_id()
        elif id in self._by_id:
            raise ValueError(f"duplicate block id: {id!r}")
        block = Section(id, component, placement=placement, sizing=sizing)
        self._blocks.append(block)
        self._by_id[id] = block
        self._mutation += 1
        return block

    def fills(self) -> tuple[Section, ...]:
        """Every ``FILL`` section in document order (zero or one by contract)."""
        return tuple(block for block in self._blocks if block.sizing is Sizing.FILL)

    def fill(self) -> Section | None:
        """The document's ``FILL`` section, or ``None``.

        The one-lookup form the viewport's fill path takes; the invariant
        ``add`` enforces means there is never more than one.
        """
        for block in self._blocks:
            if block.sizing is Sizing.FILL:
                return block
        return None


    @property
    def mutation(self) -> int:
        """How many ``add``/``remove`` calls the document has taken, ever.

        A monotone count and nothing more: it never resets, and an equal
        value between two reads proves the block list has not changed in
        between.  Caches of the block list -- the snapshot
        :meth:`blocks` hands out, any layout-side index -- key on it, so
        "unchanged" costs one integer comparison instead of a diff.
        """
        return self._mutation

    def get(self, id: str) -> Section:
        """The block with ``id``; missing id raises KeyError with a message."""
        try:
            return self._by_id[id]
        except KeyError:
            raise KeyError(f"no block with id {id!r}") from None

    def remove(self, id: str) -> Section:
        """Detach the block with ``id`` and return it; missing id raises KeyError."""
        block = self.get(id)
        self._blocks.remove(block)
        del self._by_id[id]
        self._mutation += 1
        return block

    def blocks(self) -> tuple[Section, ...]:
        """Snapshot of the blocks in document order (immune to later mutation).

        The tuple is cached against :attr:`mutation`: calls between two
        mutations share one tuple object instead of rebuilding one per
        call, and a mutation makes the next call build a fresh tuple.  The
        snapshot semantics are unchanged -- a tuple already handed out is
        never touched again (the cache is replaced, not edited), so it
        reads exactly what the document held when it was taken, before or
        after any later mutation.
        """
        cached = self._blocks_cache
        if cached is not None and cached[0] == self._mutation:
            return cached[1]
        snapshot = tuple(self._blocks)
        self._blocks_cache = (self._mutation, snapshot)
        return snapshot

    def __len__(self) -> int:
        return len(self._blocks)

    def __repr__(self) -> str:
        return f"Document({len(self._blocks)} blocks)"
