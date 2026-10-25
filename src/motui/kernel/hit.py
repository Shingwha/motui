"""hit: the value types the controllers pass around.

The controllers in :mod:`motui.app` act on addresses the driver resolves:
:class:`Hit` (a hit-test result).  A pane's visible rows are a
:class:`~motui.kernel.layout.RowSpan`, which lives with the layout values.
:class:`Hit` is a plain value with no dependency on
the driver, so it lives in the core and both layers can name it; the
cancellable timer handle lives with the runtime
(:class:`motui.app.runtime.Timer`), where the pump owns it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .document import Component, Section
from .frame import Pane

__all__ = ["Hit"]


@dataclass(frozen=True)
class Hit:
    """One hit-test result: the pane, the block, the cell, and the chain.

    ``row``/``col`` are 0-based *within the block's own rows*; ``col`` is
    measured against the pane's **inner rect** (chrome subtracted), never the
    outer pane rectangle.  ``pane`` is the pane the cell belongs to -- the
    document half of a hit, which is what lets a drag stay in one document
    when a split holds several.

    ``chain`` is the ancestor walk
    :func:`~motui.kernel.block.descend_chain` resolved: one
    ``(component, row, col)`` per level, outermost first, in each
    component's own coordinate space.  The leaf views are derived
    properties over its tail, so a host that only needs the deepest
    component reads them exactly as before:

    * :attr:`leaf` -- the deepest component, or ``None`` for an empty chain;
    * :attr:`leaf_row` / :attr:`leaf_col` -- the cell in that component's
      own ``render`` output (``0`` for an empty chain);
    * :attr:`pane_id` -- the id-only view selection and gestures hold.

    The chain is also what a wheel routes with: walk it backwards for the
    nearest :class:`~motui.kernel.scroll.Scrollable`.
    """

    pane: Pane
    block: Section
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
