"""Chrome components: :class:`Notice`, :class:`Divider` and :class:`Panel`.

Framing furniture that wraps or marks content rows.  ``Notice`` renders one
message row (leveled prefixes for warn/error), ``Divider`` a full-width rule,
and ``Panel`` a boxed border around any child component, padding it back to
the inner width so the grid stays aligned.  Only the kernel is imported:
layout is computed here, never drawn.
"""

from __future__ import annotations

from ..lines import Line, Segment
from ..style import BORDER, ERROR, NONE, WARNING, Style
from ..text import ellipsize_tail, visible_width

__all__ = ["Divider", "Notice", "Panel"]

#: Row prefixes and styles for the non-info notice levels.
_NOTICE_LEVELS: dict[str, tuple[str, Style]] = {
    "warn": ("WARNING: ", WARNING),
    "error": ("ERROR: ", ERROR),
}


class Notice:
    """A one-row message with an optional level prefix.

    ``info`` renders the text bare; ``warn``/``error`` prepend
    ``"WARNING: "``/``"ERROR: "`` in the matching semantic style.  Any other
    level degrades to plain ``info`` rather than raising.  The row is a
    single line: it is truncated (never wrapped) to ``width``.
    """

    __slots__ = ("level", "text")

    def __init__(self, text: str, *, level: str = "info") -> None:
        self.text = text
        self.level = level

    def render(self, width: int) -> list[Line]:
        prefix = _NOTICE_LEVELS.get(self.level)
        if prefix is None:  # info or unknown -> bare row
            return [Line.from_text(self.text).fit(width)]
        label, style = prefix
        line = Line((Segment(label, style), Segment(self.text, NONE)))
        return [line.fit(width)]

    def __repr__(self) -> str:
        return f"Notice({self.text!r}, level={self.level!r})"


class Divider:
    """A full-width horizontal rule built from one repeated character."""

    __slots__ = ("char", "style")

    def __init__(self, *, char: str = "\u2500", style: Style = BORDER) -> None:
        self.char = char
        self.style = style

    def render(self, width: int) -> list[Line]:
        char_w = visible_width(self.char)
        if width <= 0 or char_w <= 0:
            return [Line()]
        count = width // char_w
        return [Line.from_text(self.char * count, self.style).fit(width)]

    def __repr__(self) -> str:
        return f"Divider(char={self.char!r})"


class Panel:
    """A child component inside a single-line box border.

    The child renders at ``width - 4`` (two border columns plus one padding
    column per side); its rows are padded back to the inner width so the
    right border stays aligned.  ``title`` is embedded in the top border
    when it fits (``width >= 6``); below ``width < 4`` the frame degrades to
    the bare child, still ``fit`` to ``width``.
    """

    __slots__ = ("child", "style", "title")

    def __init__(self, child, *, title: str = "", style: Style = BORDER) -> None:
        self.child = child
        self.title = title
        self.style = style

    def render(self, width: int) -> list[Line]:
        if width < 4:
            return [row.fit(width) for row in self.child.render(width)]
        inner = width - 4
        rows = [row.fit(inner).pad_to(inner) for row in self.child.render(inner)]
        out = [self._top_row(width)]
        for row in rows:
            framed = (
                Line((Segment("\u2502 ", self.style),))
                + row
                + Line((Segment(" \u2502", self.style),))
            )
            out.append(framed.fit(width))
        out.append(self._bottom_row(width))
        return out

    def _top_row(self, width: int) -> Line:
        if self.title and width >= 6:
            label = ellipsize_tail(self.title, width - 5)
            if label:
                fill = f"\u2500 {label} "
                rest = (width - 2) - visible_width(fill)
                return Line.from_text(f"\u250c{fill}{'\u2500' * rest}\u2510", self.style)
        return Line.from_text(f"\u250c{'\u2500' * (width - 2)}\u2510", self.style)

    def _bottom_row(self, width: int) -> Line:
        return Line.from_text(f"\u2514{'\u2500' * (width - 2)}\u2518", self.style)

    def __repr__(self) -> str:
        return f"Panel({self.child!r}, title={self.title!r})"
