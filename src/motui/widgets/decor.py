"""Decor components: :class:`Divider` and :class:`Panel`.

``Divider`` draws a horizontal rule (optionally with a label); ``Panel``
frames or pads any child.  Only the kernel is imported and colors resolve
from the component's theme at render time.
"""

from __future__ import annotations

from ..kernel.document import Component
from ..kernel.glyphs import GLYPHS, Border, Glyphs
from ..kernel.cell import Line, Segment, Surface
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode, ellipsize_tail, visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["Divider", "Panel"]


def _answer(rows: list[Line], c: Constraints) -> Surface:
    """The decorated rows as a clipped surface, honouring ``max_height``.

    The memo keeps the untruncated rows for a later, larger budget.
    """
    if c.max_height is not None:
        rows = rows[: c.max_height]
    return Surface.clipped(rows, c.width)



def _labelled_rule(
    char: str,
    lead: int,
    label: str,
    label_style: Style,
    style: Style,
    span: int,
) -> list[Segment]:
    """The segments of a labelled rule over ``span`` columns.

    ``char * lead``, a space, the label, a space, then the closing run,
    floored to ``span``.  The caller has already ellipsized the label; an
    empty label degrades to the pure rule.
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


class Divider(Widget):
    """A horizontal rule built from one repeated character.

    A ``label`` embeds as ``char * 2 + " " + label + " " + fill`` within
    ``min(width, max_width)``; it is tail-ellipsized when it does not fit
    (degrading to the pure rule when nothing survives).  ``borders.base``
    draws the rule, ``text.muted`` the label.
    """

    __slots__ = (
        "char",
        "glyphs",
        "label",
        "max_width",
    )

    def __init__(
        self,
        *,
        char: str | None = None,
        label: str = "",
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
        max_width: int | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.glyphs = glyphs
        self.char = glyphs.horizontal_rule if char is None else char
        self.label = label
        self.max_width = max_width

    def render(self, c: Constraints) -> Surface:
        """The rule at the constraints' width, as a clipped surface."""
        width = c.width
        style = self.group("borders").base
        label_style = self.group("text").muted
        if width <= 0 or visible_width(self.char) <= 0:
            return _answer([Line()], c)
        paint = width if self.max_width is None else max(0, min(width, self.max_width))
        label = ellipsize_tail(self.label, paint - 4) if self.label else ""
        segments = _labelled_rule(self.char, 2, label, label_style, style, paint)
        return _answer([Line(segments).clip(WrapMode.ELLIPSIS, width)], c)

    def __repr__(self) -> str:
        if self.label:
            return f"Divider(char={self.char!r}, label={self.label!r})"
        return f"Divider(char={self.char!r})"


class Panel(Widget):
    """A child component inside a single-line box border.

    The child renders at ``width - 4`` and rows are padded back so the right
    border aligns; ``title`` embeds in the top border when it fits.  Below
    ``width < 4`` the frame degrades to the bare child.  ``child_at`` maps
    content cells only.  ``frame=False`` drops the box and title: the child
    renders at ``width - 2`` with one pad column per side, and
    ``surfaces.base`` becomes a ground merged under the child's styles.
    The framed answer is memoized on child-row identity.
    """

    __slots__ = (
        "_border",
        "_child_rows",
        "_glyphs",
        "_inner",
        "_memo",
        "_width",
        "child",
        "frame",
        "title",
    )

    def __init__(
        self,
        child,
        *,
        title: str = "",
        frame: bool = True,
        border: Border | None = None,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.child = child
        # The explicit tree: the child is this panel's child; assigning the
        # list points a widget child's ``parent`` back at the panel (a pure
        # ``Component`` child has no ``parent`` and is left alone).
        self.children = [child]
        self.title = title
        self.frame = frame
        self._glyphs = glyphs
        self._border = glyphs.box if border is None else border
        # No cached geometry before the first render: `child_at` declines
        # every cell until `render` stores the layout it painted.
        self._child_rows = 0
        self._inner = 0
        self._width = 0
        #: The wrap memo: ``(child-row identity tuple, width, title, frame,
        #: resolved band)`` -> ``(wrapped rows, the child rows that key it)``
        #: -- the child rows are kept precisely so their identities stay
        #: pinned, and a hit hands back copies.  ``None`` until the first
        #: render.
        self._memo: tuple[tuple, list[Line], list[Line]] | None = None

    def render(self, c: Constraints) -> Surface:
        """Wrap the child in the panel and return the clipped surface."""
        width = c.width
        if self.frame:
            style = self.group("borders").base
            framed = width >= 4
            lead = 2 if framed else 0  # the border and one pad column per side
        else:
            # Borderless: no frame to color, so ``borders.base`` is never
            # consulted -- ``surfaces.base`` is the ground instead.
            style = self.group("surfaces").base
            framed = False
            lead = 1 if width >= 2 else 0  # one pad column per side
        inner = width - 2 * lead  # never negative: the lead is 0 below the minimum
        self._width = width
        self._inner = inner
        child_rows = list(self.child.render(Constraints(width=inner)))
        key = (tuple(map(id, child_rows)), width, self.title, self.frame, style, self._border)
        memo = self._memo
        if memo is not None and memo[0] == key:
            self._child_rows = len(memo[2])
            return _answer(list(memo[1]), c)
        if not framed:
            rows = [self._bare_row(row, width, lead, style) for row in child_rows]
            self._child_rows = len(rows)
            self._memo = (key, rows, child_rows)
            return _answer(rows, c)
        rows = [row.clip(WrapMode.ELLIPSIS, inner).fill(inner) for row in child_rows]
        self._child_rows = len(rows)
        out = [self._top_row(width, style)]
        for row in rows:
            framed_row = (
                Line((Segment(f"{self._border.left} ", style),))
                + row
                + Line((Segment(f" {self._border.right}", style),))
            )
            out.append(framed_row.clip(WrapMode.ELLIPSIS, width))
        out.append(self._bottom_row(width, style))
        self._memo = (key, out, child_rows)
        return _answer(out, c)

    def _bare_row(self, row: Line, width: int, lead: int, ground: Style) -> Line:
        """One unwrapped row: lead pad, child, fill to ``width``.

        The ground merges under the child's segments (``NONE`` leaves them
        untouched); ``lead == 0`` is the bare-child degradation.
        """
        if lead == 0:
            return row.clip(WrapMode.ELLIPSIS, width)
        pad = ground
        return (Line((Segment(" " * lead, pad),)) + row).clip(WrapMode.ELLIPSIS, width).fill(width, pad)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning a content cell of the last render; panel cells answer ``None``."""
        if row < 0 or col < 0:
            return None
        if self.frame:
            top, lead = (1, 2) if self._width >= 4 else (0, 0)
        else:
            top, lead = 0, (1 if self._width >= 2 else 0)
        if top <= row < top + self._child_rows and lead <= col < lead + self._inner:
            return self.child, row - top, col - lead
        return None

    def _top_row(self, width: int, style: Style) -> Line:
        border = self._border
        if self.title and width >= 6:
            label = ellipsize_tail(self.title, width - 5)
            if label:
                # One border segment: the title is embedded between the rule
                # runs and the whole row fuses into one styled run.
                segments = _labelled_rule(
                    border.top, 1, label, style, style, width - 2
                )
                text = "".join(segment.text for segment in segments)
                return Line.from_text(
                    f"{border.top_left}{text}{border.top_right}", style
                )
        return Line.from_text(
            f"{border.top_left}{border.top * (width - 2)}{border.top_right}", style
        )

    def _bottom_row(self, width: int, style: Style) -> Line:
        border = self._border
        return Line.from_text(
            f"{border.bottom_left}{border.bottom * (width - 2)}{border.bottom_right}",
            style,
        )

    def __repr__(self) -> str:
        mode = "" if self.frame else ", frame=False"
        return f"Panel({self.child!r}, title={self.title!r}{mode})"
