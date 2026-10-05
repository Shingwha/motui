"""Text component: :class:`Text`.

A plain content component: ``render(width)`` is a pure function of the
component's text and the given width.  ``Text`` keeps the caller's line
structure verbatim (one logical line per ``"\\n"``, word-wrapped).  Like every
component, this module only depends on the kernel (``block``/``lines``/
``style``/``text``) and never touches the screen.  The Markdown renderer
lives in :mod:`mocode_tui.widgets.markdown`.
"""

from __future__ import annotations

from ..core.lines import Line
from ..core.style import NONE, Style
from ..core.text import wrap_text

__all__ = ["Text"]


class Text:
    """A block of plain text rendered verbatim, line by line.

    ``text`` is a mutable attribute (streaming text assigns to it).  Each
    logical line (``split("\\n")``) is word-wrapped with
    :func:`~mocode_tui.core.text.wrap_text` into rows of at most ``width`` columns,
    so blank lines survive as blank rows.  Every row carries ``style`` and is
    ``fit`` to ``width`` as a final guard.
    """

    __slots__ = ("style", "text")

    def __init__(self, text: str = "", *, style: Style = NONE) -> None:
        self.text = text
        self.style = style

    def render(self, width: int) -> list[Line]:
        out: list[Line] = []
        for row in self.text.split("\n"):
            for piece in wrap_text(row, width):
                out.append(Line.from_text(piece, self.style).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Text({self.text!r})"
