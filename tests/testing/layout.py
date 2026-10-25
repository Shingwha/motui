"""Row and screen-text views: what a rendered component or frame says."""

from __future__ import annotations

from motui.kernel.layout import Constraints

__all__ = ["marked", "rows", "texts"]


def texts(component, width: int) -> list[str]:
    """The plain-text rows ``component`` renders at ``width``."""
    return [row.text for row in component.render(Constraints(width=width))]


def rows(tui) -> list[str]:
    """The plain-text rows of the driver's current frame."""
    return [row.text for row in tui.workspace.rows]


def marked(tui) -> list[str]:
    """Per row: the text of the reverse-video pieces, ``""`` when none.

    The default palette paints no reverse outside a caret cell, so the pieces
    this returns are exactly the selection overlay's marks.
    """
    return [
        "".join(seg.text for seg in row.segments if seg.style.reverse)
        for row in tui.rows
    ]
