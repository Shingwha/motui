"""ScrollPanel: a window over any component's rows and columns.

A :class:`ScrollPanel` renders its child at the width it can give it and
shows a fixed-height slice of the result.  It is the composition-layer
answer to "this content is taller or wider than its slot": charts, long
forms, a panel's body, a markdown document -- any component works
unchanged, because the child keeps rendering through the one ``render(c)``
protocol.

Three knobs decide the window:

* ``height`` -- how many rows to show; ``None`` (the default) shows the
  child's every row and makes vertical scrolling a no-op;
* ``offset`` -- the first visible child row, clamped to the last window
  ``max(0, total_rows - height)``;
* ``bar`` -- paint one-cell bars: the vertical one in the rightmost column
  (the child then rendering at ``width - 1`` columns) and the horizontal
  one in the bottom row.

``axis`` picks the directions: ``"y"`` (the default) moves rows only,
``"x"`` moves columns only and never clips the child's height, and
``"both"`` moves the two axes independently.  Horizontal overflow is legal
by contract -- a child may answer a surface wider than its constraints --
and the panel hard-cuts every row with
:func:`~motui.kernel.cell.cut_line`, no ellipsis: the removed columns are
scrollable, so a ``…`` would claim a truncation that did not happen.  The
vertical-only path keeps the 1.x ``clip(ELLIPSIS)`` rule and its bytes.

The bars use :attr:`~motui.kernel.glyphs.Glyphs.bar_empty` and
:attr:`~motui.kernel.glyphs.Glyphs.bar_full` in ``chrome.scrollbar`` and
``chrome.scrollbar_thumb``.  Both take their geometry from the same
:meth:`~motui.kernel.layout.ScrollAxis.thumb` formula: proportional to the
visible fraction, at least one cell, and no thumb at all when the content
fits the window (the bar then paints its plain track).  With ``"both"``
the bars meet in the bottom-right corner, which the vertical track owns.

:meth:`ScrollPanel.on_key` owns the scrolling keys through the class
``keymap`` -- ``up``/``down`` one row, ``page_up``/``page_down`` one window,
``home``/``end`` the edges -- and :meth:`ScrollPanel.on_mouse` the wheel on
both axes (``wheel_left``/``wheel_right`` move one column).  Each answers
``True`` only when an offset actually moved, so a host keeps the boundaries'
keys.  :meth:`ScrollPanel.drag` owns the vertical bar
itself: a press on the thumb grabs it, the motions map the grabbed row
through the same thumb geometry, a press on the track pages toward it, and
the release ends the drag.  ``ScrollPanel`` is a
:class:`~motui.kernel.document.Container`: a visible cell maps to the child
cell ``(offset + row, x_offset + col)``, and the bars' column and row
belong to the view.  ``revision`` folds the child's own snapshot (identity
when it has none) with the knobs and both offsets, so a sealed block around
a scroll view still repaints when the child changes in place.
"""

from __future__ import annotations

from dataclasses import replace

from ..kernel.cell import Line, Segment, Surface, cut_line
from ..kernel.document import Component, Revisioned
from ..kernel.geom import Pos
from ..kernel.events import KeyEvent, MouseEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints, ScrollAxis, ScrollState
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget
from .strip import Keymap

__all__ = ["ScrollPanel"]


class ScrollPanel(Widget):
    """A clipped, scrollable window over one child component.

    ``height=None`` shows every child row; a fixed ``height`` shows exactly
    that many rows, padding with blank rows when the child is shorter (so
    the view's slot never jumps).  ``offset`` starts at the requested row
    (never negative) and is clamped into the legal range on every render,
    which is what makes a child that shrinks safe.  ``child``, ``height``,
    ``bar`` and ``axis`` are ordinary attributes a host may change on
    resize; :attr:`offset`, :attr:`x_offset`, :attr:`total_rows` and
    :attr:`total_columns` are read-only views of the last render's geometry.

    The width split is deliberate: with a vertical bar the child renders at
    ``width - 1``, so the bar never covers content; without one it renders
    at ``width``.  The bottom bar is painted inside the ``height`` slot, so
    it costs one content row rather than growing the surface.  Every
    painted row is fitted back to the painting width.

    ``axis`` names the scrolling directions: ``"y"`` (the default) moves
    rows only, ``"x"`` moves columns only and shows every child row, and
    ``"both"`` clamps the two offsets independently.  Any other value is
    rejected at construction rather than silently ignored.
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
        "_state",
        "_x",
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
        # The view never follows the tail: its state holds the offset plus
        # the last render's content and window rows, with stick-to-bottom
        # off.  Before the first render the upper clamp is unknown, so a
        # fixed-height view accepts a requested offset and clamps it then
        # (the ``_rendered`` flag keeps that one rule).
        self._state = ScrollState(offset=max(0, offset))
        # The horizontal axis is the immutable 2.0 value: one offset plus the
        # last render's content columns and window columns, re-derived by a
        # pure ``clamp`` on every render.  No tail-follow rule: a wide
        # document has no analogous "bottom".
        self._x = ScrollAxis()
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
        return self._state.offset

    @property
    def x_offset(self) -> int:
        """The first visible child column (the last render's clamped value)."""
        return self._x.offset

    @property
    def total_rows(self) -> int:
        """The child rows the last render produced (``0`` before one)."""
        return self._state.content_height

    @property
    def total_columns(self) -> int:
        """The child columns the last render produced (``0`` before one)."""
        return self._x.content

    @property
    def viewport_height(self) -> int:
        """The visible content rows (a bottom bar's row excluded)."""
        bar = 1 if self._bar_horizontal else 0
        if self.height is None:
            return max(0, self._state.content_height - bar)
        return max(0, self.height - bar)

    @property
    def viewport_width(self) -> int:
        """The visible content columns: the last render's inner width."""
        return self._x.viewport

    @property
    def scroll_state(self) -> ScrollState:
        """The view's live scroll geometry (offset, content and window rows)."""
        return self._state

    def _max_offset(self) -> int:
        return self._state.max_offset()

    # -- scrolling --------------------------------------------------------------

    def scroll_to(self, offset: int) -> bool:
        """Move the window's first row to ``offset`` (clamped); ``True`` when it moved.

        The clamp uses the last render's row count; before the first render
        a fixed-height view accepts the offset and clamps it on that render,
        while ``height=None`` never scrolls (every row is visible).  The
        view never follows the tail, so the state's stick flag stays off.
        """
        state = self._state
        target = max(0, int(offset))
        if self.height is None:
            target = 0
        elif self._rendered:
            target = min(target, state.max_offset())
        if target == state.offset:
            return False
        state.offset = target
        state.stick_to_bottom = False
        return True

    def scroll_up(self, n: int = 1) -> bool:
        """Scroll up ``n`` rows; ``True`` when the offset moved."""
        return self.scroll_to(self._state.offset - max(0, int(n)))

    def scroll_down(self, n: int = 1) -> bool:
        """Scroll down ``n`` rows; ``True`` when the offset moved."""
        return self.scroll_to(self._state.offset + max(0, int(n)))

    def scroll_by(self, delta: int) -> bool:
        """Step the window ``delta`` rows (clamped); ``True`` when it moved."""
        return self.scroll_to(self._state.offset + int(delta))

    def scroll_to_x(self, offset: int) -> bool:
        """Move the window's first column to ``offset`` (clamped).

        ``True`` when the offset moved.  A y-only view has no horizontal
        extent and declines.  The clamp uses the last render's column
        count; before the first render the offset is accepted and clamped
        by that render, mirroring :meth:`scroll_to`.
        """
        if self.axis == "y":
            return False
        target = max(0, int(offset))
        if self._rendered:
            target = min(target, self._x.max_offset)
        if target == self._x.offset:
            return False
        self._x = replace(self._x, offset=target)
        return True

    def scroll_x(self, delta: int) -> bool:
        """Step the window ``delta`` columns (clamped); ``True`` when it moved."""
        return self.scroll_to_x(self._x.offset + int(delta))

    def scroll_x_to_end(self) -> bool:
        """Move the window to the last column (clamped); ``True`` when it moved."""
        return self.scroll_to_x(self._x.max_offset)

    def scroll_x_by(self, delta: int) -> bool:
        """The structural horizontal-wheel face: step ``delta`` columns.

        The same move :meth:`scroll_x` makes; it exists as its own verb so
        the app's wheel route can find a horizontal scroller through
        :class:`~motui.kernel.layout.ScrollableX` without importing this
        widget.
        """
        return self.scroll_x(delta)

    def reveal(self, row: int) -> bool:
        """Bring the child ``row`` into the window, moving as little as possible.

        The row is clamped into the child's rows; a target already visible
        (or a view that shows everything) moves nothing.  ``False`` before
        the first render, for an empty child, or when the row was visible.
        """
        moved = self._state.reveal(row)
        self._state.stick_to_bottom = False
        return moved

    # -- events -----------------------------------------------------------------

    def on_action(self, name: str) -> bool:
        """Run one named scrolling action; ``False`` for an unknown name.

        ``prev`` / ``next`` step one row, ``page_prev`` / ``page_next`` one
        window, ``first`` / ``last`` the edges, and ``scroll_prev`` /
        ``scroll_next`` one column on an x-scrolling view.  Every name
        answers whether the offset actually moved (the 1.x ``handle``
        rule), so a boundary keeps the key for the host; an unknown name
        answers ``False`` untouched.
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
        """Route one scrolling key through :attr:`keymap` to :meth:`on_action`.

        The default table binds the arrows, the page keys and the edges.
        A key release and every key no entry names are declined, so the
        host's dispatch still gets its turn.
        """
        if not isinstance(event, KeyEvent) or event.kind == "release":
            return False
        action = self.keymap.get(event.key)
        if action is None:
            return False
        return self.on_action(action)

    def on_mouse(self, event: MouseEvent) -> bool:
        """Route one wheel notch to the axis it names.

        ``wheel_up`` / ``wheel_down`` move one row on ``"y"`` / ``"both"``,
        ``wheel_left`` / ``wheel_right`` one column on ``"x"`` / ``"both"``;
        the other axis's wheel is declined, so a y-only view leaves
        horizontal scrolling to its host.
        """
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
        """Advance one step of a bar drag; ``True`` when the view took it.

        Only the vertical bar's column (``pos.x == self._last_inner``,
        inside the painted content rows) can start a drag: a press on the
        thumb records the grab -- its bar row and the offset it was taken
        at -- while a press on the track pages one viewport toward the
        pointer's side.  A motion while grabbed maps the row delta through
        the thumb geometry anchored at the grab (the same ``(start,
        length)`` :meth:`ScrollState.thumb` paints), so the thumb never
        jumps; a release ends the drag and answers whether there was a grab
        to end.  A view without a vertical bar, a content that fits the
        window (no thumb to map) and a press outside the bar column all
        decline.
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
        state = self._state
        thumb = state.thumb(self._last_height)
        if thumb is None:
            return False
        start, length = thumb
        if phase == "press":
            if start <= row < start + length:
                self._grab = (row, state.offset)
            else:
                page = self.viewport_height
                self.scroll_by(page if row >= start + length else -page)
            return True
        grab_row, grab_offset = self._grab
        track = max(1, self._last_height - length)
        span = max(1, state.content_height - state.viewport_height)
        self.scroll_to(grab_offset + round((row - grab_row) * span / track))
        return True

    def on_click(self, pos: Pos) -> bool:
        """Take a click on a bar cell as a press-and-release drag.

        A click on the content columns is declined so the focus ring's
        descend reaches the child; the bars are the view's own (the child
        never renders there), so a click there answers ``True`` whatever it
        did -- clicking a bar with no thumb is still a click on the bar.
        The bottom bar's row only consumes the click; horizontal dragging
        is not part of this wave.
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

        The geometry is the last :meth:`render`'s: rows/columns past the
        painted window, the bars' row and column, blank padding rows and
        any negative coordinate answer ``None``.  Before the first render
        every cell answers ``None``.
        """
        if row < 0 or col < 0:
            return None
        if row >= self._last_height or col >= self._last_inner:
            return None
        local_row = self._last_offset + row
        local_col = self._last_x + col
        if local_row >= self._state.content_height:
            return None
        if self.axis in ("x", "both") and local_col >= self._x.content:
            return None
        return self.child, local_row, local_col

    # -- rendering --------------------------------------------------------------

    def revision(self) -> object:
        """The row cache's snapshot: child identity/snapshot plus the knobs.

        A :class:`~motui.kernel.document.Revisioned` child contributes its own
        snapshot -- the value its block would key on -- so an in-place edit
        moves this key before any render.  A child without one (or with its
        memory switched off by a ``None`` snapshot) contributes its
        identity; like any non-revisioned component it is re-rendered per
        layout.  Both offsets, ``height``, ``bar``, ``axis`` and the
        ``theme``/``styles`` chrome sources are the rest of the view's own
        mutable input.
        """
        child = self.child
        snapshot: object = None
        if isinstance(child, Revisioned):
            snapshot = child.revision()
        child_key: object = snapshot if snapshot is not None else id(child)
        return (
            child_key,
            self._state.offset,
            self._x.offset,
            self.height,
            self.bar,
            self.glyphs,
            self.theme,
            self.styles,
            self.axis,
        )

    def render(self, c: Constraints) -> Surface:
        """Render the child at the inner width and paint the visible window.

        The window height is the explicit ``height`` when the view has one
        -- the host's slot wins outright -- and the child's natural row
        count otherwise, capped by ``c.max_height`` when the constraint
        carries a budget.  A bottom bar is painted inside that slot, so the
        content window is one row shorter; a right-hand bar takes one
        column from the child's width.  The two offsets clamp independently
        against this render's extents.  Horizontal rows are hard-cut with
        ``cut_line`` (no ``…``); vertical-only rows keep the 1.x
        ``clip(ELLIPSIS)`` path byte for byte.
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
        state = self._state
        state.content_height = content_h
        state.viewport_height = inner_h
        state.clamp()
        x = ScrollAxis(offset=self._x.offset, content=content_w, viewport=inner_w).clamp()
        self._x = x
        start = state.offset
        start_x = x.offset
        self._last_inner = inner_w
        self._last_offset = start
        self._last_x = start_x
        self._last_height = inner_h
        self._last_bar_y = bar_y
        self._last_bar_x = bar_x and height > 0
        self._rendered = True
        horizontal = self.axis in ("x", "both")
        thumb = state.thumb(inner_h)
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
            f"ScrollPanel(axis={self.axis!r}, offset={self._state.offset}, "
            f"x_offset={self._x.offset}, height={self.height!r}, "
            f"bar={self.bar}, total_rows={self._state.content_height}, "
            f"total_columns={self._x.content})"
        )
