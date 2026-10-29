"""ScrollPanel: a window over any component's rows and columns.

Renders the child at the width it can give it and shows a fixed-height (and
optionally column-windowed) slice.  ``height``, ``offset``/``x_offset`` and
``bar``/``axis`` decide the window; bars share one thumb formula.  Keys,
wheel and vertical-bar drag move it; ``child_at`` maps visible cells back.
"""

from __future__ import annotations

from dataclasses import replace

from ..kernel.cell import Line, Segment, Surface, cut_line
from ..kernel.document import Component
from ..kernel.geom import Pos
from ..kernel.events import KeyEvent, MouseEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints, Scroll, ScrollAxis
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget
from .strip import Keymap

__all__ = ["ScrollPanel"]


class ScrollPanel(Widget):
    """A clipped, scrollable window over one child component.

    ``height=None`` shows every row; a fixed height pads short children so
    the slot never jumps. Offsets clamp on each render.  A vertical bar
    takes one column from the child, a bottom bar one row from the window.
    ``axis`` is ``"y"``, ``"x"`` or ``"both"``; any other value raises.
    Offsets/totals are read-only views of the last render.
    """

    __slots__ = (
        "_grab",
        "_keymap",
        "_last_bar_x",
        "_last_bar_y",
        "_last_height",
        "_last_inner",
        "_last_offset",
        "_last_x",
        "_rendered",
        "_scroll",
        "axis",
        "bar",
        "child",
        "glyphs",
        "height",
    )

    #: The view takes the keyboard and clicks on its bars; it paints no hover
    #: state and has no activation verb (a scroll is a move, not a pick).
    focusable = True
    clickable = True
    hoverable = False
    activatable = False

    #: The default key table (a per-instance copy backs ``self.keymap``).
    keymap = Keymap(
        {
            "up": "prev",
            "down": "next",
            "page_up": "page_prev",
            "page_down": "page_next",
            "home": "first",
            "end": "last",
        }
    )

    def __init__(
        self,
        child: Component,
        *,
        height: int | None = None,
        offset: int = 0,
        bar: bool = False,
        axis: str = "y",
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        # The instance's own key table: rebinding one entry never reaches
        # the class default (see :class:`~motui.widgets.strip.Keymap`).
        self._keymap = dict(type(self).keymap)
        if axis not in ("y", "x", "both"):
            raise ValueError(f"axis must be 'y', 'x' or 'both', got {axis!r}")
        self.axis = axis
        self.child = child
        # The explicit tree: the window's one child is mounted below it, so
        # walk(), theme/focus propagation and resize broadcasts reach it.
        self.children = [child]
        self.glyphs = glyphs
        self.height = None if height is None else max(0, height)
        self.bar = bool(bar)
        # The old focus default of the data/navigation family; a ScrollPanel
        # renders the same either way, but the flag stays part of the base.
        self.focused = True
        # The view never follows the tail: its scroll value holds the two
        # offsets plus the last render's content and window extents, with
        # stick-to-bottom off on both axes.  Before the first render the
        # upper clamp is unknown, so a fixed-height view accepts a requested
        # offset and clamps it then (the ``_rendered`` flag keeps that one
        # rule).  A wide document has no analogous "bottom", so x is plain.
        self._scroll = Scroll(
            x=ScrollAxis(),
            y=ScrollAxis(offset=max(0, offset)),
        )
        # The last render's geometry: the child's row count, the inner
        # width, the offsets actually painted, the painted row count and
        # which bars were painted.
        self._last_inner = 0
        self._last_offset = 0
        self._last_x = 0
        self._last_height = 0
        self._last_bar_y = False
        self._last_bar_x = False
        #: Whether a render has established ``total_rows`` yet.  Before the
        #: first render the upper clamp is unknown, so a fixed-height view
        #: accepts a requested offset and clamps it on the first render.
        self._rendered = False
        #: The in-flight bar drag: ``(bar row, offset at the grab)``.  ``None``
        #: when the bar is not held.
        self._grab: tuple[int, int] | None = None

    # -- geometry ---------------------------------------------------------------

    @property
    def _bar_vertical(self) -> bool:
        """Whether this view paints the right-hand bar."""
        return self.bar and self.axis in ("y", "both")

    @property
    def _bar_horizontal(self) -> bool:
        """Whether this view paints the bottom bar."""
        return self.bar and self.axis in ("x", "both")

    @property
    def offset(self) -> int:
        """The first visible child row (the last render's clamped value)."""
        return self._scroll.y.offset

    @property
    def x_offset(self) -> int:
        """The first visible child column (the last render's clamped value)."""
        return self._scroll.x.offset

    @property
    def total_rows(self) -> int:
        """The child rows the last render produced (``0`` before one)."""
        return self._scroll.y.content

    @property
    def total_columns(self) -> int:
        """The child columns the last render produced (``0`` before one)."""
        return self._scroll.x.content

    @property
    def viewport_height(self) -> int:
        """The visible content rows (a bottom bar's row excluded)."""
        bar = 1 if self._bar_horizontal else 0
        if self.height is None:
            return max(0, self._scroll.y.content - bar)
        return max(0, self.height - bar)

    @property
    def viewport_width(self) -> int:
        """The visible content columns: the last render's inner width."""
        return self._scroll.x.viewport

    @property
    def scroll(self) -> Scroll:
        """The view's immutable scroll value: the vertical and horizontal windows."""
        return self._scroll

    def _max_offset(self) -> int:
        return self._scroll.y.max_offset

    # -- scrolling --------------------------------------------------------------

    def scroll_to(self, offset: int) -> bool:
        """Move the first visible row to ``offset`` (clamped); True when it moved.

        Before the first render the offset is accepted and clamped then;
        ``height=None`` never scrolls.
        """
        y = self._scroll.y
        target = max(0, int(offset))
        if self.height is None:
            target = 0
        elif self._rendered:
            target = min(target, y.max_offset)
        if target == y.offset:
            return False
        self._scroll = self._scroll.with_y(replace(y, offset=target, sticky=False))
        self.touch()
        return True

    def scroll_up(self, n: int = 1) -> bool:
        """Scroll up ``n`` rows; ``True`` when the offset moved."""
        return self.scroll_to(self._scroll.y.offset - max(0, int(n)))

    def scroll_down(self, n: int = 1) -> bool:
        """Scroll down ``n`` rows; ``True`` when the offset moved."""
        return self.scroll_to(self._scroll.y.offset + max(0, int(n)))

    def scroll_by(self, delta: int) -> bool:
        """Step the window ``delta`` rows (clamped); ``True`` when it moved."""
        return self.scroll_to(self._scroll.y.offset + int(delta))

    def scroll_to_x(self, offset: int) -> bool:
        """Move the first visible column to ``offset`` (clamped); True when moved.

        A y-only view declines; before the first render the offset is
        accepted and clamped then.
        """
        if self.axis == "y":
            return False
        x = self._scroll.x
        target = max(0, int(offset))
        if self._rendered:
            target = min(target, x.max_offset)
        if target == x.offset:
            return False
        self._scroll = self._scroll.with_x(replace(x, offset=target))
        self.touch()
        return True

    def scroll_x(self, delta: int) -> bool:
        """Step the window ``delta`` columns (clamped); ``True`` when it moved."""
        return self.scroll_to_x(self._scroll.x.offset + int(delta))

    def scroll_x_to_end(self) -> bool:
        """Move the window to the last column (clamped); ``True`` when it moved."""
        return self.scroll_to_x(self._scroll.x.max_offset)

    def scroll_x_by(self, delta: int) -> bool:
        """The ``ScrollableX`` face of :meth:`scroll_x` (one column step)."""
        return self.scroll_x(delta)

    def reveal(self, row: int) -> bool:
        """Bring child ``row`` into the window, moving as little as possible.

        ``False`` before the first render, for an empty child, or when the
        row is already visible.
        """
        y = self._scroll.y
        revealed = y.reveal(row)
        moved = revealed.offset != y.offset
        self._scroll = self._scroll.with_y(replace(revealed, sticky=False))
        if moved:
            self.touch()
        return moved

    # -- events -----------------------------------------------------------------

    def on_action(self, name: str) -> bool:
        """Run a scrolling action: prev/next, page_*, first/last, scroll_prev/next.

        The answer is whether an offset moved, so a boundary keeps the key;
        unknown names decline.
        """
        if name == "prev":
            return self.scroll_up(1)
        if name == "next":
            return self.scroll_down(1)
        if name == "page_prev":
            return self.scroll_up(self.viewport_height)
        if name == "page_next":
            return self.scroll_down(self.viewport_height)
        if name == "first":
            return self.scroll_to(0)
        if name == "last":
            return self.scroll_to(self._max_offset()) if self._rendered else False
        if name == "scroll_prev":
            return self.scroll_x(-1)
        if name == "scroll_next":
            return self.scroll_x(1)
        return False

    def on_key(self, event: KeyEvent) -> bool:
        """Route a scrolling key through :attr:`keymap`; releases and unbound keys decline."""
        if not isinstance(event, KeyEvent) or event.kind == "release":
            return False
        action = self.keymap.get(event.key)
        if action is None:
            return False
        return self.on_action(action)

    def on_mouse(self, event: MouseEvent) -> bool:
        """Route one wheel notch to the axis it names; the other axis declines."""
        if not isinstance(event, MouseEvent):
            return False
        if event.button == "wheel_up":
            return self.on_action("prev") if self.axis in ("y", "both") else False
        if event.button == "wheel_down":
            return self.on_action("next") if self.axis in ("y", "both") else False
        if event.button == "wheel_left":
            return self.on_action("scroll_prev")
        if event.button == "wheel_right":
            return self.on_action("scroll_next")
        return False

    def on_drag(self, pos: Pos, phase: str) -> bool:
        """Advance a vertical-bar drag; True when the view took it.

        A press on the thumb grabs it (its row and offset); a press on the
        track pages toward the pointer.  Motions map through the thumb
        geometry anchored at the grab, so it never jumps; a release ends the
        drag.  Views without a vertical bar, fitting content or presses off
        the bar decline.
        """
        row, col = pos.y, pos.x
        if phase == "release":
            grabbed = self._grab is not None
            self._grab = None
            return grabbed
        if not self._bar_vertical or phase not in ("press", "motion"):
            return False
        if phase == "press" and (col != self._last_inner or row >= self._last_height):
            return False
        if phase == "motion" and self._grab is None:
            return False
        y = self._scroll.y
        thumb = y.thumb(self._last_height)
        if thumb is None:
            return False
        start, length = thumb
        if phase == "press":
            if start <= row < start + length:
                self._grab = (row, y.offset)
            else:
                page = self.viewport_height
                self.scroll_by(page if row >= start + length else -page)
            return True
        grab_row, grab_offset = self._grab
        track = max(1, self._last_height - length)
        span = max(1, y.content - y.viewport)
        self.scroll_to(grab_offset + round((row - grab_row) * span / track))
        return True

    def on_click(self, pos: Pos) -> bool:
        """Take a click on a bar cell as a press-and-release drag.

        Content columns decline so the focus ring can descend to the child;
        either bar consumes the click.  The bottom bar does not drag yet.
        """
        if not self.bar or not self._rendered:
            return False
        if self._last_bar_x and pos.y == self._last_height:
            return True
        if self._last_bar_y and pos.x == self._last_inner:
            self.on_drag(pos, "press")
            self.on_drag(pos, "release")
            return True
        return False

    # -- container --------------------------------------------------------------

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a visible cell to ``(child, offset + row, x_offset + col)``.

        Bars, padding rows, out-of-range cells and pre-render cells answer
        ``None``.
        """
        if row < 0 or col < 0:
            return None
        if row >= self._last_height or col >= self._last_inner:
            return None
        local_row = self._last_offset + row
        local_col = self._last_x + col
        if local_row >= self._scroll.y.content:
            return None
        if self.axis in ("x", "both") and local_col >= self._scroll.x.content:
            return None
        return self.child, local_row, local_col

    # -- rendering --------------------------------------------------------------

    def render(self, c: Constraints) -> Surface:
        """Render the child at the inner width and paint the visible window.

        The slot is ``height`` when set (capped by ``max_height`` for a
        natural-height view); bars take a row/column from it.  Offsets clamp
        per render.  Horizontal rows are hard-cut (no ellipsis); vertical
        rows keep the ellipsis rule.
        """
        width = c.width
        bar_y = self._bar_vertical and width > 0
        bar_x = self._bar_horizontal
        inner_w = max(0, width - (1 if bar_y else 0))
        surface = self.child.render(Constraints(width=inner_w))
        child_rows = list(surface)
        content_w = max([surface.width, *(row.width for row in child_rows)], default=0)
        content_h = len(child_rows)
        # The explicit height is the host's slot and wins over the budget;
        # a natural-height view fills the budget it was offered.
        height = content_h if self.height is None else self.height
        if self.height is None and c.max_height is not None:
            height = min(height, c.max_height)
        height = max(0, height)
        inner_h = max(0, height - (1 if bar_x else 0))
        y = replace(
            self._scroll.y, content=content_h, viewport=inner_h
        ).clamp()
        x = replace(
            self._scroll.x, content=content_w, viewport=inner_w
        ).clamp()
        self._scroll = Scroll(x=x, y=y)
        start = y.offset
        start_x = x.offset
        self._last_inner = inner_w
        self._last_offset = start
        self._last_x = start_x
        self._last_height = inner_h
        self._last_bar_y = bar_y
        self._last_bar_x = bar_x and height > 0
        self._rendered = True
        horizontal = self.axis in ("x", "both")
        thumb = y.thumb(inner_h)
        thumb_start, thumb_length = thumb if thumb is not None else (0, 0)
        # The chrome roles resolve once per render: track and thumb.
        chrome = self.group("chrome") if (bar_y or bar_x) else None
        out: list[Line] = []
        for row in range(inner_h):
            index = start + row
            if index < content_h:
                line = child_rows[index]
                if horizontal:
                    line = cut_line(line, start_x, start_x + inner_w)
                    # ``cut_line`` may reach one column past a wide cluster
                    # boundary; the hard CLIP keeps the row invariant without
                    # inventing an ellipsis.
                    line = line.clip(WrapMode.CLIP, inner_w)
                else:
                    line = line.clip(WrapMode.ELLIPSIS, inner_w)
            else:
                line = Line()
            if bar_y:
                line = line.fill(inner_w)
                if thumb_start <= row < thumb_start + thumb_length:
                    glyph, style = self.glyphs.bar_full, chrome.scrollbar_thumb
                else:
                    glyph, style = self.glyphs.bar_empty, chrome.scrollbar
                line = Line((*line.segments, Segment(glyph, style)))
            out.append(line.clip(WrapMode.ELLIPSIS, width))
        if bar_x and height > 0:
            columns = x.thumb(inner_w)
            column_start, column_length = columns if columns is not None else (0, 0)
            cells: list[Segment] = []
            for col in range(inner_w):
                if column_start <= col < column_start + column_length:
                    glyph, style = self.glyphs.bar_full, chrome.scrollbar_thumb
                else:
                    glyph, style = self.glyphs.bar_empty, chrome.scrollbar
                cells.append(Segment(glyph, style))
            if bar_y:
                # The corner is not on either track; the vertical bar owns it
                # so the right column reads as one continuous strip.
                cells.append(Segment(self.glyphs.bar_empty, chrome.scrollbar))
            out.append(Line(cells))
        return Surface.clipped(out, c.width)

    def __repr__(self) -> str:
        return (
            f"ScrollPanel(axis={self.axis!r}, offset={self._scroll.y.offset}, "
            f"x_offset={self._scroll.x.offset}, height={self.height!r}, "
            f"bar={self.bar}, total_rows={self._scroll.y.content}, "
            f"total_columns={self._scroll.x.content})"
        )
