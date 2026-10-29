"""Document model: addressable blocks rendered by components.

A :class:`Section` caches rows only when its component carries a
``generation`` counter; a pure component re-renders on every read."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .cell import Line, Surface

if TYPE_CHECKING:  # the protocol names the layout model; no runtime import needed
    from .layout import Constraints

__all__ = [
    "Component",
    "Document",
    "Fill",
    "Placement",
    "Section",
    "Sizing",
    "descend",
    "descend_chain",
]


class Placement(Enum):
    """Where a section sits: the scrolling body or a fixed region."""

    FLOW = "flow"
    TOP = "top"
    BOTTOM = "bottom"


class Sizing(Enum):
    """How a section consumes height: its content or the pane's remainder."""

    NATURAL = "natural"
    FILL = "fill"


@dataclass(frozen=True, slots=True)
class Fill:
    """A component that owns a pane's whole remaining height; frozen, because
    the widget is the value's identity."""

    widget: Component



@runtime_checkable
class Component(Protocol):
    """Anything that renders itself into a surface: ``render(c) -> Surface``,
    given the width and an optional height budget."""

    def render(self, c: Constraints) -> Surface:
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
    """Every component owning a cell, outermost first, with its own coordinates;
    pure, allocation-light and depth-guarded."""
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
    """The deepest component owning a cell, with that component's own
    coordinates; the tail of :func:`descend_chain`."""
    return descend_chain(component, row, col)[-1]


class Section:
    """One addressable row-producing unit inside a :class:`Document`.

    The block owns its row cache because a layout-side cache had to be pruned
    by id every frame. It is keyed ``(width, max_height, generation)``, and
    only a component carrying a ``generation`` counter is cached."""

    __slots__ = (
        "_cacheable",
        "_id",
        "_placement",
        "_rows_cache",
        "_rows_generation",
        "_rows_max_height",
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
        # The widget's generation counter is fixed by its type, so protocol
        # membership is decided once here: a per-frame hasattr on every
        # block would cost more than the cache saves.
        self._cacheable = hasattr(widget, "generation")
        # The cache slot: the last rows rendered at ``_rows_width`` whose
        # widget answered ``_rows_generation``.  ``None`` rows mean "nothing
        # cached yet" -- generation ``0`` is a legitimate key, so it cannot
        # double as the empty marker.
        self._rows_cache: list[Line] | None = None
        self._rows_width: int | None = None
        self._rows_max_height: int | None = None
        self._rows_generation: int | None = None

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

    @property
    def generation(self) -> int | None:
        """The widget's change counter, or ``None`` for a pure component; a move
        invalidates the row cache."""
        return getattr(self._widget, "generation", None)

    def render(self, c: Constraints) -> list[Line]:
        """Forward a fresh render to the component; the cached door is
        :meth:`rows`."""
        return self.rows(c)

    def rows(self, c: Constraints) -> list[Line]:
        """The block's rows under ``c``, cached when the component allows it; a
        fresh list the caller owns."""
        return list(self._refresh(c))

    def rows_view(self, c: Constraints) -> Sequence[Line]:
        """The block's rows under ``c``, borrowed read-only from the cache; the
        answer is good for this call only."""
        return self._refresh(c)

    def row_count(self, c: Constraints) -> int:
        """How many rows the block occupies under ``c``, without copying them."""
        return len(self._refresh(c))

    def _refresh(self, c: Constraints) -> list[Line]:
        """The one hit-or-miss decision every rows door shares; the key is
        ``(width, max_height, generation)``."""
        if not self._cacheable:
            return self._render(c)  # no generation counter
        generation = self.generation
        if generation is None:
            # A widget-like component without a counter cannot be
            # invalidated, so it is never cached.
            return self._render(c)
        if (
            self._rows_cache is not None
            and self._rows_width == c.width
            and self._rows_max_height == c.max_height
            and self._rows_generation == generation
        ):
            return self._rows_cache
        rows = self._render(c)
        self._rows_cache = rows
        self._rows_width = c.width
        self._rows_max_height = c.max_height
        self._rows_generation = generation
        return rows

    def _render(self, c: Constraints) -> list[Line]:
        """Render once and enforce the row contract: clip to width, drop rows past
        ``max_height``."""
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
        """The first free ``b{n}`` id; a generated id never collides with one a
        caller claimed."""
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
        """Append a block, auto id ``b{n}`` when ``id`` is None; duplicate ids and
        the FILL rules raise ``ValueError``."""
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
        """The document's ``FILL`` section, or ``None``."""
        for block in self._blocks:
            if block.sizing is Sizing.FILL:
                return block
        return None


    @property
    def mutation(self) -> int:
        """A monotone count of ``add``/``remove`` calls; equal values prove the
        block list unchanged, so caches compare one integer."""
        return self._mutation

    def get(self, id: str) -> Section:
        """The block with ``id``; a missing id raises ``KeyError``."""
        try:
            return self._by_id[id]
        except KeyError:
            raise KeyError(f"no block with id {id!r}") from None

    def remove(self, id: str) -> Section:
        """Detach the block with ``id`` and return it; a missing id raises
        ``KeyError``."""
        block = self.get(id)
        self._blocks.remove(block)
        del self._by_id[id]
        self._mutation += 1
        return block

    def blocks(self) -> tuple[Section, ...]:
        """Snapshot of the blocks in document order, cached against
        :attr:`mutation`; a handed-out tuple is never touched again."""
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
