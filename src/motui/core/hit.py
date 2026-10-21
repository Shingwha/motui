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
    """One hit-test result: the pane, the block, the cell, and the leaf.

    ``row``/``col`` are 0-based *within the block's own rows*; ``col`` is
    measured against the pane's **inner rect** (chrome subtracted), never the
    outer pane rectangle.  ``pane`` is the pane the cell belongs to -- the
    document half of a hit, which is what lets a drag stay in one document
    when a split holds several.  ``leaf``/``leaf_row``/``leaf_col`` are the
    deepest component under the cell (:func:`~motui.core.block.descend`),
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
