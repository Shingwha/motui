"""Decor components: :class:`Notice`, :class:`Divider` and :class:`Panel`.

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
from ..core.theme import Theme, Themed

__all__ = ["Divider", "Notice", "Panel"]


def _labelled_rule(
    char: str,
    lead: int,
    label: str,
    label_style: Style,
    style: Style,
    span: int,
) -> list[Segment]:
    """The segments of a labelled rule over ``span`` columns.

    ``char * lead``, a space, the label, a space, then the closing run of
    ``char`` -- ``char * fill``, floored so the row never exceeds ``span``
    columns.  The label is expected to fit already (each caller ellipsizes
    it against the span it has room for); an empty label degrades to the
    pure rule, and ``span <= 0`` -- or a zero-width ``char`` -- yields no
    segments.  :class:`Divider` renders the segments as built;
    :class:`Panel` fuses them into its one-segment border row.
    """
    char_w = visible_width(char)
    if span <= 0 or char_w <= 0:
        return []
    if not label:
        count = span // char_w
        return [Segment(char * count, style)] if count else []
    used = lead * char_w + 2 + visible_width(label)
    fill = max(0, (span - used) // char_w)
    segments = [
        Segment(char * lead, style),
        Segment(" ", style),
        Segment(label, label_style),
        Segment(" ", style),
    ]
    if fill:
        segments.append(Segment(char * fill, style))
    return segments


class Notice(Themed):
    """A one-row message with an optional level prefix.

    ``info`` renders the text bare; ``warn``/``error`` prepend
    ``"WARNING: "``/``"ERROR: "`` in the matching semantic style, taken from
    the theme's ``notice_levels`` table.  Any other level degrades to plain
    ``info`` rather than raising.  The row is a single line: it is truncated
    (never wrapped) to ``width``.
    """

    __slots__ = ("level", "text", "theme")

    def __init__(self, text: str, *, level: str = "info", theme: Theme | None = None) -> None:
        super().__init__(theme)
        self.text = text
        self.level = level
        self.theme = theme
        # The level is a plain (mutable) attribute, so the pick is
        # state-dependent: the level is looked up in the stored theme per
        # render.

    def render(self, width: int) -> list[Line]:
        prefix = self._theme.notice_levels.get(self.level)
        if prefix is None:  # info or unknown -> bare row
            return [Line.from_text(self.text).fit(width)]
        label, style = prefix
        line = Line((Segment(label, style), Segment(self.text, NONE)))
        return [line.fit(width)]

    def __repr__(self) -> str:
        return f"Notice({self.text!r}, level={self.level!r})"


class Divider(Themed):
    """A horizontal rule built from one repeated character.

    With a ``label`` the rule embeds it: ``char * 2 + " " + label + " " +
    char * fill`` spanning ``max(0, min(width, max_width))`` columns -- the
    shape of an inline working-status line parked on an input box's top
    border.  ``max_width`` caps that span (``None``, the default,
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

    __slots__ = ("char", "label", "label_style", "max_width", "style", "theme")

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
        super().__init__(theme)
        self.char = char
        self.style = style
        self.label = label
        self.label_style = label_style
        self.theme = theme
        self.max_width = max_width
        # ``style`` / ``label_style`` are plain (mutable) attributes -- a
        # host re-labels and re-styles one divider in place -- so the theme
        # fallback resolves against the stored theme at render time.

    def render(self, width: int) -> list[Line]:
        style = self._pick(self.style, "border")
        label_style = self.label_style if self.label_style is not None else NONE
        if width <= 0 or visible_width(self.char) <= 0:
            return [Line()]
        paint = width if self.max_width is None else max(0, min(width, self.max_width))
        label = ellipsize_tail(self.label, paint - 4) if self.label else ""
        segments = _labelled_rule(self.char, 2, label, label_style, style, paint)
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        if self.label:
            return f"Divider(char={self.char!r}, label={self.label!r})"
        return f"Divider(char={self.char!r})"


class Panel(Themed):
    """A child component inside a single-line box border.

    The child renders at ``width - 4`` (two border columns plus one padding
    column per side); its rows are padded back to the inner width so the
    right border stays aligned.  ``title`` is embedded in the top border
    when it fits (``width >= 6``); below ``width < 4`` the frame degrades to
    the bare child, still ``fit`` to ``width``.  ``style`` is the border
    color (the theme's ``border`` when none is given).
    """

    __slots__ = ("child", "style", "theme", "title")

    def __init__(
        self,
        child,
        *,
        title: str = "",
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.child = child
        self.title = title
        self.style = style
        self.theme = theme
        # ``style`` is a plain (mutable) attribute, same in-place restyle
        # affordance as Divider: the theme fallback resolves at render time.

    def render(self, width: int) -> list[Line]:
        style = self._pick(self.style, "border")
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
                # One border segment: the title is embedded between the rule
                # runs and the whole row fuses into one styled run.
                segments = _labelled_rule("\u2500", 1, label, style, style, width - 2)
                text = "".join(segment.text for segment in segments)
                return Line.from_text(f"\u250c{text}\u2510", style)
        return Line.from_text(f"\u250c{'\u2500' * (width - 2)}\u2510", style)

    def _bottom_row(self, width: int, style: Style) -> Line:
        return Line.from_text(f"\u2514{'\u2500' * (width - 2)}\u2518", style)

    def __repr__(self) -> str:
        return f"Panel({self.child!r}, title={self.title!r})"
