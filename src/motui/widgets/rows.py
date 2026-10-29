"""Row-shaped furniture: the status row, the shortcut bar and the notice.

Three display-only one-row components fitted to the painting width:
``StatusLine`` (left/right with a gutter), ``ShortcutBar`` (key hints) and
``Notice`` (level glyph plus message).  Only the kernel is imported.
"""

from __future__ import annotations

from typing import Sequence

from ..kernel.glyphs import GLYPHS, Glyphs, seat
from ..kernel.cell import Line, Segment, Surface, fuse
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode, visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["Notice", "ShortcutBar", "StatusLine"]

#: One element of a status side: bare text, or text plus an explicit style.
Element = str | tuple[str, Style]


def _element_text(element: Element) -> str:
    """The text of one element (the style half of a tuple is dropped)."""
    return element[0] if isinstance(element, tuple) else element


def _row(elements, default: Style, gap: tuple[str, Style] | None = None) -> Line:
    """One row from ``str | (str, Style)`` elements with an optional middle.

    Adjacent equal-style elements are fused into one segment.
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


class StatusLine(Widget):
    """A dim two-sided status row: left text, right text, gutter between.

    Always exactly one row fitted to the width; the left side is preserved
    and the right tail ellipsized when narrow.  Bare elements use
    ``text.faint``.
    """

    __slots__ = ("left", "right")

    #: Pure display: no key, click, hover or activation verb.
    focusable = False
    clickable = False
    hoverable = False
    activatable = False

    def __init__(
        self,
        *,
        left=(),
        right=(),
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        # A tuple copy: a host that mutates its own list in place would
        # otherwise bypass the snapshot and freeze a sealed block.
        self.left = tuple(left)
        self.right = tuple(right)

    def render(self, c: Constraints) -> Surface:
        """The one status row, fitted to the constraint width."""
        default = self.group("text").faint
        gap_style = default
        used = _width(self.left, default) + _width(self.right, default)
        gutter = max(1, c.width - used - 1)  # one trailing column of right margin
        parts = [*self.left, (" " * gutter, gap_style), *self.right]
        rows = [_row(parts, default).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"StatusLine(left={self.left!r}, right={self.right!r})"


class ShortcutBar(Widget):
    """One row of ``(key, label)`` hints, truncated to the painting width.

    Keys use ``content.accent``, labels ``text.faint``; pairs join with
    ``glyphs.separator``.  An empty bar still owns one row.
    """

    __slots__ = (
        "glyphs",
        "items",
    )

    #: Pure display: no key, click, hover or activation verb.
    focusable = False
    clickable = False
    hoverable = False
    activatable = False

    def __init__(
        self,
        items: Sequence[tuple[str, str]],
        *,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        # A tuple copy of the sequence (same rationale as StatusLine).
        self.items = tuple((key, label) for key, label in items)
        self.glyphs = glyphs

    def render(self, c: Constraints) -> Surface:
        """The one hint row, fitted to the constraint width."""
        key_style = self.group("content").accent
        label_style = self.group("text").faint
        segments: list[Segment] = []
        for index, (key, label) in enumerate(self.items):
            if index:
                segments.append(Segment(self.glyphs.separator, NONE))
            segments.append(Segment(key, key_style))
            segments.append(Segment(f" {label}", label_style))
        rows = [Line(segments).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"ShortcutBar({self.items!r})"


class Notice(Widget):
    """A one-row message with a level glyph.

    ``info`` (and unknown levels), ``success``, ``warn`` and ``error`` map
    to their vocabulary glyph and semantic style; the message stays plain.
    The row is truncated, never wrapped.
    """

    __slots__ = ("glyphs", "level", "text")

    #: Pure display: no key, click, hover or activation verb.
    focusable = False
    clickable = False
    hoverable = False
    activatable = False

    def __init__(
        self,
        text: str,
        *,
        level: str = "info",
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.text = text
        self.level = level
        self.glyphs = glyphs
        # The level is a plain (mutable) attribute, so the pick is
        # state-dependent: the level is looked up per render.

    def _level_style(self) -> tuple[str, Style]:
        """The ``(glyph, style)`` pair this level renders with."""
        if self.level == "success":
            return self.glyphs.notice_success, self.group("status").success
        if self.level == "warn":
            return self.glyphs.notice_warn, self.group("status").warning
        if self.level == "error":
            return self.glyphs.notice_error, self.group("status").danger
        return self.glyphs.notice_info, self.group("text").base

    def render(self, c: Constraints) -> Surface:
        """The one message row, fitted to the constraint width."""
        glyph, style = self._level_style()
        prefix = seat(glyph)
        if not prefix:
            rows = [Line.from_text(self.text, NONE).clip(WrapMode.ELLIPSIS, c.width)]
        else:
            line = Line((Segment(prefix, style), Segment(self.text, NONE)))
            rows = [line.clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return f"Notice({self.text!r}, level={self.level!r})"
