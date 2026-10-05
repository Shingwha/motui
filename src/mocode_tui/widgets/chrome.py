"""Chrome components: :class:`Notice`, :class:`Divider` and :class:`Panel`.

Framing furniture that wraps or marks content rows.  ``Notice`` renders one
message row (leveled prefixes for warn/error), ``Divider`` a horizontal
rule capped at ``max_width`` columns when given (full ``width`` otherwise;
optionally embedding a label -- the ``── label ───`` inline status row),
and ``Panel`` a boxed border around any child component, padding it back to
the inner width so the grid stays aligned.  Only the kernel is imported:
layout is computed here, never drawn.  The notice levels and the divider /
panel border color come from the :class:`~mocode_tui.core.theme.Theme` the
component was built with.
"""

from __future__ import annotations

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import ellipsize_tail, visible_width
from ..core.theme import DEFAULT_THEME, Theme

__all__ = ["Divider", "Notice", "Panel"]


class Notice:
    """A one-row message with an optional level prefix.

    ``info`` renders the text bare; ``warn``/``error`` prepend
    ``"WARNING: "``/``"ERROR: "`` in the matching semantic style, taken from
    the theme's ``notice_levels`` table.  Any other level degrades to plain
    ``info`` rather than raising.  The row is a single line: it is truncated
    (never wrapped) to ``width``.
    """

    __slots__ = ("_theme", "level", "text", "theme")

    def __init__(self, text: str, *, level: str = "info", theme: Theme | None = None) -> None:
        self.text = text
        self.level = level
        self.theme = theme
        # The level is a plain (mutable) attribute, so the pick is
        # state-dependent: the resolved theme is stored, the level looked
        # up in it per render.
        self._theme = theme or DEFAULT_THEME

    def render(self, width: int) -> list[Line]:
        prefix = self._theme.notice_levels.get(self.level)
        if prefix is None:  # info or unknown -> bare row
            return [Line.from_text(self.text).fit(width)]
        label, style = prefix
        line = Line((Segment(label, style), Segment(self.text, NONE)))
        return [line.fit(width)]

    def __repr__(self) -> str:
        return f"Notice({self.text!r}, level={self.level!r})"


class Divider:
    """A horizontal rule built from one repeated character.

    With a ``label`` the rule embeds it: ``char * 2 + " " + label + " " +
    char * fill`` spanning ``max(0, min(width, max_width))`` columns -- the
    ``── ⠋ Working ───`` inline status line the pi UI parks on its input
    box's top border.  ``max_width`` caps that span (``None``, the default,
    spans the whole ``width``): the rule comes out left-aligned and the
    shorter row is legal, since a painter clears the tail past it.  The
    label carries ``label_style``; the rules and the two spaces carry
    ``style`` (the theme's ``border`` when none is given).  A label that
    does not fit the capped width minus 4 is truncated with
    :func:`~mocode_tui.core.text.ellipsize_tail`; when nothing survives
    the truncation the row degrades to the pure rule, exactly like an empty
    ``label``.  ``label`` / ``label_style`` / ``max_width`` are plain
    mutable attributes, so a host can re-label one divider in place (the
    demo's working spinner does), re-cap it, and invalidate.
    """

    __slots__ = ("_theme", "char", "label", "label_style", "max_width", "style", "theme")

    def __init__(
        self,
        *,
        char: str = "\u2500",
        style: Style | None = None,
        label: str = "",
        label_style: Style | None = None,
        theme: Theme | None = None,
        max_width: int | None = None,
    ) -> None:
        self.char = char
        self.style = style
        self.label = label
        self.label_style = label_style
        self.theme = theme
        self.max_width = max_width
        # ``style`` / ``label_style`` are plain (mutable) attributes -- a
        # host re-labels and re-styles one divider in place -- so the theme
        # fallback resolves against the stored theme at render time.
        self._theme = theme or DEFAULT_THEME

    def render(self, width: int) -> list[Line]:
        style = self.style if self.style is not None else self._theme.border
        label_style = self.label_style if self.label_style is not None else NONE
        char_w = visible_width(self.char)
        if width <= 0 or char_w <= 0:
            return [Line()]
        paint = width if self.max_width is None else max(0, min(width, self.max_width))
        label = ellipsize_tail(self.label, paint - 4) if self.label else ""
        if not label:  # empty (or fully truncated): the pure rule
            count = paint // char_w
            return [Line.from_text(self.char * count, style).fit(width)]
        used = 2 * char_w + 2 + visible_width(label)  # char*2 + " " + label + " "
        fill = max(0, (paint - used) // char_w)
        segments = [
            Segment(self.char * 2, style),
            Segment(" ", style),
            Segment(label, label_style),
            Segment(" ", style),
        ]
        if fill:
            segments.append(Segment(self.char * fill, style))
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        if self.label:
            return f"Divider(char={self.char!r}, label={self.label!r})"
        return f"Divider(char={self.char!r})"


class Panel:
    """A child component inside a single-line box border.

    The child renders at ``width - 4`` (two border columns plus one padding
    column per side); its rows are padded back to the inner width so the
    right border stays aligned.  ``title`` is embedded in the top border
    when it fits (``width >= 6``); below ``width < 4`` the frame degrades to
    the bare child, still ``fit`` to ``width``.  ``style`` is the border
    color (the theme's ``border`` when none is given).
    """

    __slots__ = ("_theme", "child", "style", "theme", "title")

    def __init__(
        self,
        child,
        *,
        title: str = "",
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        self.child = child
        self.title = title
        self.style = style
        self.theme = theme
        # ``style`` is a plain (mutable) attribute, same in-place restyle
        # affordance as Divider: the theme fallback resolves at render time.
        self._theme = theme or DEFAULT_THEME

    def render(self, width: int) -> list[Line]:
        style = self.style if self.style is not None else self._theme.border
        if width < 4:
            return [row.fit(width) for row in self.child.render(width)]
        inner = width - 4
        rows = [row.fit(inner).pad_to(inner) for row in self.child.render(inner)]
        out = [self._top_row(width, style)]
        for row in rows:
            framed = (
                Line((Segment("\u2502 ", style),))
                + row
                + Line((Segment(" \u2502", style),))
            )
            out.append(framed.fit(width))
        out.append(self._bottom_row(width, style))
        return out

    def _top_row(self, width: int, style: Style) -> Line:
        if self.title and width >= 6:
            label = ellipsize_tail(self.title, width - 5)
            if label:
                fill = f"\u2500 {label} "
                rest = (width - 2) - visible_width(fill)
                return Line.from_text(f"\u250c{fill}{'\u2500' * rest}\u2510", style)
        return Line.from_text(f"\u250c{'\u2500' * (width - 2)}\u2510", style)

    def _bottom_row(self, width: int, style: Style) -> Line:
        return Line.from_text(f"\u2514{'\u2500' * (width - 2)}\u2518", style)

    def __repr__(self) -> str:
        return f"Panel({self.child!r}, title={self.title!r})"
