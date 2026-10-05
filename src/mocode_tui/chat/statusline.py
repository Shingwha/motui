"""StatusLine: the two-sided status row of a coding-agent UI.

:class:`StatusLine` renders one row -- always exactly one -- with a left
part left-aligned and a right part right-aligned, a computed gutter
between them and one trailing column of right margin, so a pinned footer
keeps a constant height no matter what the two sides say.  It is the
library form of the pi demo's ``_StatusRow``: each side is a sequence of
elements, a bare ``str`` or a ``(str, Style)`` tuple, and the whole row
defaults to the theme's ``dim`` (a status bar whispers; it never shouts).

Overflow ruling (decided and documented here): the **left part is
preserved first** and the **right part is cut from its tail** -- the row
is composed at full length and closed with the kernel's
:meth:`~mocode_tui.core.lines.Line.fit`, the exact behaviour the demo's
``_StatusRow`` had (it built the text and let ``fit`` ellipsize the end).
A narrow terminal therefore drops the tail of the right-hand information
-- typically the end of a model name or mode -- while the left-hand
counters stay readable.

``left``/``right`` are plain, reassignable attributes: a host rewrites
them each frame (``status.left = ((spinner.frame, "Working"))``) rather
than rebuilding the component, which is what a status row wants -- it is
state the frame reads, not state the component owns.
"""

from __future__ import annotations

from ..core.lines import Line, Segment, fuse
from ..core.style import Style
from ..core.text import visible_width
from ..core.theme import DEFAULT_THEME, Theme

__all__ = ["StatusLine"]

#: One element of a status side: bare text, or text plus an explicit style.
Element = str | tuple[str, Style]


def _element_text(element: Element) -> str:
    """The text of one element (the style half of a tuple is dropped)."""
    return element[0] if isinstance(element, tuple) else element


def _row(elements, default: Style, gap: tuple[str, Style] | None = None) -> Line:
    """One row from ``str | (str, Style)`` elements with an optional middle.

    ``elements`` is one side (or the whole row, see :meth:`StatusLine.render`);
    ``default`` styles the bare strings.  Adjacent elements sharing one
    style are fused into a single segment, so a row of plain text renders
    as one styled run -- exactly the ``Line.from_text(row, DIM)`` the demo's
    ``_StatusRow`` built -- instead of a stutter of identical escapes.
    """
    parts = list(elements)
    if gap is not None:
        parts.append(gap)
    return Line(fuse(
        Segment(text, style)
        for text, style in (
            (element if isinstance(element, tuple) else (element, default))
            for element in parts
        )
        if text  # an empty element contributes nothing at all
    ))


def _width(elements, default: Style) -> int:
    """The display width one side will render at (styles ignored)."""
    return sum(visible_width(_element_text(element)) for element in elements)


class StatusLine:
    """A dim two-sided status row: left text, right text, gutter between.

    ``left``/``right`` are sequences of :data:`Element` values updated in
    place by the host; ``gap_style`` overrides the gutter's style (the
    theme's ``dim`` by default, same as the elements).  Rendering always
    yields exactly one row, ``fit`` to ``width``: the left part starts at
    column 0, the right part ends one column short of ``width`` (the right
    margin), and the gutter absorbs the difference -- at least one column
    wide, so the two sides never touch.  An over-wide row keeps the left
    part and ellipsizes the right part's tail (see the module docstring).
    """

    __slots__ = ("gap_style", "left", "right", "theme")

    def __init__(
        self,
        *,
        left=(),
        right=(),
        theme: Theme | None = None,
        gap_style: Style | None = None,
    ) -> None:
        self.left = left
        self.right = right
        self.theme = theme
        self.gap_style = gap_style

    def render(self, width: int) -> list[Line]:
        theme = self.theme or DEFAULT_THEME
        default = theme.dim
        gap_style = self.gap_style if self.gap_style is not None else default
        used = _width(self.left, default) + _width(self.right, default)
        gutter = max(1, width - used - 1)  # one trailing column of right margin
        parts = [*self.left, (" " * gutter, gap_style), *self.right]
        return [_row(parts, default).fit(width)]

    def __repr__(self) -> str:
        return f"StatusLine(left={self.left!r}, right={self.right!r})"
