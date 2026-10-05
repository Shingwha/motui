"""Status bar component: a priority-ordered, space-separated footer row.

:class:`StatusBar` keeps ``StatusSegment`` values (each with a priority)
and renders as many as fit: segments are considered from the highest
priority down, kept while they fit, and the ones that do not are dropped
(low priority goes first).  The surviving row is truncated to ``width``.
Only the kernel is imported; the clock that would tick a bar lives in W4.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.lines import Line
from ..core.text import visible_width
from ..core.theme import Theme

__all__ = ["StatusBar", "StatusSegment"]


@dataclass(frozen=True)
class StatusSegment:
    """One status-bar cell: text plus a drop priority (higher wins)."""

    text: str
    priority: int = 0


class StatusBar:
    """A single footer row assembled from prioritized segments.

    ``segment(text, priority)`` appends a cell.  ``render(width)`` orders
    cells by priority (descending, insertion order breaking ties).  The
    highest-priority cell is always kept -- truncated by the final ``fit``
    when it alone overflows -- while every lower cell is added only while it
    still fits, so low priority goes first.  An empty bar renders one blank
    row so a pinned footer keeps its height.  ``theme`` is accepted for the
    uniform component signature and carried for hosts that pass one theme
    down a tree of components -- the bar draws no color of its own.
    """

    __slots__ = ("segments", "theme")

    def __init__(
        self,
        *,
        segments: list[StatusSegment] = (),
        theme: Theme | None = None,
    ) -> None:
        self.segments = list(segments)
        self.theme = theme

    def segment(self, text: str, priority: int = 0) -> None:
        """Append a status cell."""
        self.segments.append(StatusSegment(text, priority))

    def render(self, width: int) -> list[Line]:
        kept: list[str] = []
        used = 0
        for position, seg in enumerate(sorted(self.segments, key=lambda s: -s.priority)):
            cell = visible_width(seg.text)
            need = cell + (1 if kept else 0)
            if position == 0 or used + need <= width:
                kept.append(seg.text)
                used += need
        return [Line.from_text(" ".join(kept)).fit(width)]

    def __repr__(self) -> str:
        return f"StatusBar({self.segments!r})"
