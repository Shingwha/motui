"""host: the narrow driver surface the interaction tiers see.

The interaction layer is policy over a running driver -- it scrolls, selects,
hovers and paints -- but it must not import the driver itself, or the layer
graph would gain a cycle (``app`` imports ``interaction`` for its composition
root).  This module is the seam: the value types a tier passes around
(:class:`Hit`, :class:`RowRange`, :class:`EveryHandle`) and the
:class:`Host` protocol the driver structurally satisfies.

The protocol is deliberately narrow -- the driver's frame and screen, its
repaint cue, its event read, its clock and timer handles, its hit test, its
selection write and its visible-row read, its clipboard write, and the two
component factories a self-contained tier builds its fields through.  A tier
that needs a little more of the driver still receives a ``TUI`` at runtime;
the protocol pins the surface the layer contract promises, and the driver
keeps its richer public face for hosts.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .block import Block, Component, Document
from .events import Event
from .frame import Frame, Pane
from .painter import Painter
from .screen import Screen
from .selection import Selection

__all__ = ["EveryHandle", "Hit", "Host", "RowRange"]


class EveryHandle:
    """Cancellable handle returned by ``Host.every``."""

    __slots__ = ("_cancelled",)

    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` has been called."""
        return self._cancelled

    def cancel(self) -> None:
        """Stop future invocations (a callback already running finishes)."""
        self._cancelled = True

    def __repr__(self) -> str:
        return f"EveryHandle(cancelled={self._cancelled})"


@dataclass(frozen=True)
class RowRange:
    """A pane's visible body rows as screen rows: ``first`` .. ``last`` inclusive."""

    first: int
    last: int


@dataclass(frozen=True)
class Hit:
    """One hit-test result: the pane, the block, the cell, and the leaf.

    ``row``/``col`` are 0-based *within the block's own rows*; ``col`` is
    measured against the pane's **inner rect** (chrome subtracted), never the
    outer pane rectangle.  ``pane`` is the pane the cell belongs to -- the
    document half of a hit, which is what lets a drag stay in one document
    when a split holds several.  ``leaf``/``leaf_row``/``leaf_col`` are the
    deepest component under the cell (:func:`~motui.kernel.block.descend`),
    when one was resolved; ``hit_leaf`` is the convenience entry for that
    walk, and ``pane_id`` the id-only view existing tiers read.
    """

    pane: Pane
    block: Block
    row: int
    col: int
    leaf: Component | None = None
    leaf_row: int = 0
    leaf_col: int = 0

    @property
    def pane_id(self) -> str:
        """The pane's id (the document identity selection and gestures hold)."""
        return self.pane.id


@runtime_checkable
class Host(Protocol):
    """The driver surface the interaction tiers are allowed to see."""

    #: The screen the tier reads its size from (and writes copies through).
    screen: Screen
    #: The frame the tier registers overlays and chrome on.
    frame: Frame
    #: The focused pane's document (the selection gesture extracts from it).
    document: Document
    #: The document selection the driver stores, and the pane it lives in.
    selection: Selection | None
    selection_pane: Pane | None
    #: The scroll-key table the driver intercepts (the gesture reads wheel rows).
    scroll_keys: dict[str, int]
    #: The painter (the dev stats read its frame count).
    painter: Painter

    def reveal(self, bid: str, row: int) -> bool:
        """Bring one block row on screen; ``False`` for an unknown id."""

    def refresh(self) -> None:
        """Mark the frame dirty; the pump repaints once the throttle allows."""

    async def read_event(self) -> Event | None:
        """Read the next event, or ``None`` at EOF/without a source."""

    def clock(self) -> float:
        """The driver's monotonic clock: the one seam time enters through."""

    def every(
        self, seconds: float, fn: Callable[[], object]
    ) -> EveryHandle:
        """Call ``fn`` every ``seconds`` until the handle is cancelled."""

    def hit(self, x: int, y: int) -> Hit | None:
        """Resolve a 0-based terminal cell to a pane, a block and a cell."""

    def set_selection(
        self, selection: Selection | None, *, pane: Pane | str | None = None
    ) -> None:
        """Replace the document selection; ``None`` clears it."""

    def visible_range(self, pane: Pane | str | None = None) -> RowRange | None:
        """A pane's visible body rows as screen rows (the focused pane by default)."""

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the terminal's clipboard; answer whether it went."""

    def make_input(self, **kwargs: object) -> object:
        """Build an ``Input`` field for a tier's own query row."""

    def make_autocomplete(
        self, options: Sequence[object], **kwargs: object
    ) -> object:
        """Build an ``Autocomplete`` list over ``options`` for a tier's panel."""
