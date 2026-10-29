"""The value types controllers pass around, :class:`Hit` foremost.

A plain value with no dependency on the driver, so the kernel and
:mod:`motui.app` can both name it."""

from __future__ import annotations

from dataclasses import dataclass

from .document import Component, Section
from .frame import Pane

__all__ = ["Hit"]


@dataclass(frozen=True)
class Hit:
    """One hit-test result: the pane, the block, the cell and the ancestor
    chain.

    ``row``/``col`` are 0-based within the block's own rows and measured
    against the pane's inner rect (chrome subtracted). The chain is the
    wheel's route to the nearest scrollable."""

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
