"""hit: the value types the controllers pass around.

The controllers in :mod:`motui.app` act on addresses the driver resolves:
:class:`Hit` (a hit-test result), :class:`RowRange` (a pane's visible body
rows as screen rows) and :class:`EveryHandle` (the cancellable handle a
repeating callback returns).  They are plain values with no dependency on
the driver, so they live in the core and both layers can name them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .block import Block, Component
from .frame import Pane

__all__ = ["EveryHandle", "Hit", "RowRange"]


class EveryHandle:
    """Cancellable handle returned by the driver's ``every``."""

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
    """One hit-test result: the pane, the block, the cell, and the chain.

    ``row``/``col`` are 0-based *within the block's own rows*; ``col`` is
    measured against the pane's **inner rect** (chrome subtracted), never the
    outer pane rectangle.  ``pane`` is the pane the cell belongs to -- the
    document half of a hit, which is what lets a drag stay in one document
    when a split holds several.

    ``chain`` is the ancestor walk
    :func:`~motui.core.block.descend_chain` resolved: one
    ``(component, row, col)`` per level, outermost first, in each
    component's own coordinate space.  The leaf views are derived
    properties over its tail, so a host that only needs the deepest
    component reads them exactly as before:

    * :attr:`leaf` -- the deepest component, or ``None`` for an empty chain;
    * :attr:`leaf_row` / :attr:`leaf_col` -- the cell in that component's
      own ``render`` output (``0`` for an empty chain);
    * :attr:`pane_id` -- the id-only view selection and gestures hold.

    The chain is also what a wheel routes with: walk it backwards for the
    nearest :class:`~motui.core.scroll.Scrollable`.
    """

    pane: Pane
    block: Block
    row: int
    col: int
    chain: tuple[tuple[Component, int, int], ...] = ()

    @property
    def leaf(self) -> Component | None:
        """The deepest component in the chain, ``None`` when it is empty."""
        return self.chain[-1][0] if self.chain else None

    @property
    def leaf_row(self) -> int:
        """The leaf's own row for the hit cell (``0`` for an empty chain)."""
        return self.chain[-1][1] if self.chain else 0

    @property
    def leaf_col(self) -> int:
        """The leaf's own column for the hit cell (``0`` for an empty chain)."""
        return self.chain[-1][2] if self.chain else 0

    @property
    def pane_id(self) -> str:
        """The pane's id (the document identity selection and gestures hold)."""
        return self.pane.id
