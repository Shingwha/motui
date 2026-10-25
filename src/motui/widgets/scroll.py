"""ScrollPanel: a window over any component's rows.

A :class:`ScrollPanel` renders its child at the width it can give it and
shows a fixed-height slice of the result.  It is the composition-layer
answer to "this content is taller than its slot": charts, long forms, a
panel's body, a markdown document -- any component works unchanged,
because the child keeps rendering through the one ``render(c)``
protocol.

Three knobs decide the window:

* ``height`` -- how many rows to show; ``None`` (the default) shows the
  child's every row and makes scrolling a no-op;
* ``offset`` -- the first visible child row, clamped to the last window
  ``max(0, total_rows - height)``;
* ``bar`` -- paint a one-column bar in the rightmost column, the child
  then rendering at ``width - 1`` columns.

The bar uses :attr:`~motui.kernel.glyphs.Glyphs.bar_empty` and
:attr:`~motui.kernel.glyphs.Glyphs.bar_full` in ``chrome.scrollbar`` and
``chrome.scrollbar_thumb``.  The geometry is the one
:meth:`~motui.kernel.layout.ScrollState.thumb` formula: proportional to the
visible fraction, at least one cell, and no thumb at all when the content
fits the window (the bar then paints its plain track).

:meth:`ScrollPanel.handle` owns the scrolling keys -- ``up``/``down`` one
row, ``page_up``/``page_down`` one window, ``home``/``end`` the edges --
and the vertical wheel.  It answers ``True`` only when the offset
actually moved, so a host keeps the boundaries' keys.  :meth:`ScrollPanel.drag`
owns the bar itself: a press on the thumb grabs it, the motions map the
grabbed row through the same thumb geometry, a press on the track pages
toward it, and the release ends the drag.  ``ScrollPanel`` is a
:class:`~motui.kernel.document.Container`: a visible cell maps to the child
row ``offset + row``, and the scrollbar column belongs to the view.
``revision`` folds the child's own snapshot (identity when it has none)
with the three knobs, so a sealed block around a scroll view still
repaints when the child changes in place.
"""

from __future__ import annotations

from ..kernel.document import Component, Revisioned
from ..kernel.events import Event, KeyEvent, MouseEvent
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, Segment, Surface
from ..kernel.layout import (Constraints, ScrollState)
from ..kernel.theme import Styles, Theme
from ..kernel.text import WrapMode
from ..widgets.base import Widget

__all__ = ["ScrollPanel"]


class ScrollPanel(Widget):
    """A clipped, scrollable window over one child component.

    ``height=None`` shows every child row; a fixed ``height`` shows exactly
    that many rows, padding with blank rows when the child is shorter (so
    the view's slot never jumps).  ``offset`` starts at the requested row
    (never negative) and is clamped into the legal range on every render,
    which is what makes a child that shrinks safe.  ``child``, ``height``
    and ``bar`` are ordinary attributes a host may change on resize;
    :attr:`offset` and :attr:`total_rows` are read-only views of the last
    render's geometry.

    The width split is deliberate: with a bar the child renders at
    ``width - 1``, so the bar never covers content; without one it renders
    at ``width``.  Every painted row is fitted back to the painting width.

    ``axis`` names the scrolling direction.  This wave implements the
    vertical axis only (``"y"``); the horizontal and two-axis modes arrive
    with the immutable ``Scroll`` values in W2.6, so any other value is
    rejected at construction rather than silently ignored.
    """

    __slots__ = (
        "_grab",
        "_last_height",
        "_last_inner",
        "_last_offset",
        "_rendered",
        "_state",
        "axis",
        "bar",
        "child",
        "glyphs",
        "height",
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
        if axis != "y":
            raise ValueError(f"axis must be 'y' in this wave, got {axis!r}")
        self.axis = axis
        self.child = child
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
        # The last render's geometry: the child's row count, the inner
        # width, the offset actually painted, and the painted row count.
        self._last_inner = 0
        self._last_offset = 0
        self._last_height = 0
        #: Whether a render has established ``total_rows`` yet.  Before the
        #: first render the upper clamp is unknown, so a fixed-height view
        #: accepts a requested offset and clamps it on the first render.
        self._rendered = False
        #: The in-flight bar drag: ``(bar row, offset at the grab)``.  ``None``
        #: when the bar is not held.
        self._grab: tuple[int, int] | None = None

    # -- geometry ---------------------------------------------------------------

    @property
    def offset(self) -> int:
        """The first visible child row (the last render's clamped value)."""
        return self._state.offset

    @property
    def total_rows(self) -> int:
        """The child rows the last render produced (``0`` before one)."""
        return self._state.content_height

    @property
    def viewport_height(self) -> int:
        """The visible row count: ``height``, or every row when it is ``None``."""
        if self.height is None:
            return self._state.content_height
        return max(0, self.height)

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

    def handle(self, event: Event) -> bool:
        """Consume one scrolling event; ``True`` only when the window moved.

        Keys: ``up``/``down`` step one row, ``page_up``/``page_down`` one
        window, ``home``/``end`` jump to the edges.  The vertical wheel
        (``wheel_up``/``wheel_down``) steps one row; every other event --
        including a key this view does not bind -- is declined, so the
        host's dispatch still gets its turn.
        """
        if isinstance(event, MouseEvent):
            if event.button == "wheel_up":
                return self.scroll_up(1)
            if event.button == "wheel_down":
                return self.scroll_down(1)
            return False
        if not isinstance(event, KeyEvent) or event.kind == "release":
            return False
        key = event.key
        if key == "up":
            return self.scroll_up(1)
        if key == "down":
            return self.scroll_down(1)
        if key == "page_up":
            return self.scroll_up(self.viewport_height)
        if key == "page_down":
            return self.scroll_down(self.viewport_height)
        if key == "home":
            return self.scroll_to(0)
        if key == "end":
            return self.scroll_to(self._max_offset()) if self._rendered else False
        return False

    def drag(self, row: int, col: int, kind: str) -> bool:
        """Advance one step of a bar drag; ``True`` when the view took it.

        Only the bar column (``col == self._last_inner``) can start a
        drag: a press on the thumb records the grab -- its bar row and the
        offset it was taken at -- while a press on the track pages one
        viewport toward the pointer's side.  A motion while grabbed maps
        the row delta through the thumb geometry anchored at the grab (the
        same ``(start, length)`` :meth:`ScrollState.thumb` paints), so the
        thumb never jumps; a release ends the drag and answers whether
        there was a grab to end.  A view without a bar, a content that
        fits the window (no thumb to map) and a press outside the bar
        column all decline.
        """
        if kind == "release":
            grabbed = self._grab is not None
            self._grab = None
            return grabbed
        if not self.bar or kind not in ("press", "motion"):
            return False
        if kind == "press" and col != self._last_inner:
            return False
        if kind == "motion" and self._grab is None:
            return False
        state = self._state
        thumb = state.thumb(self._last_height)
        if thumb is None:
            return False
        start, length = thumb
        if kind == "press":
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

    def click(self, row: int, col: int) -> bool:
        """Take a click on the bar column as a press-and-release drag.

        A click on the content columns is declined so the focus ring's
        descend reaches the child; the bar column is the view's own (the
        child never renders there), so it answers ``True`` whatever the
        click did -- clicking a bar with no thumb is still a click on the
        bar.
        """
        if not self.bar or not self._rendered or col != self._last_inner:
            return False
        self.drag(row, col, "press")
        self.drag(row, col, "release")
        return True

    # -- container --------------------------------------------------------------

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a visible cell to ``(child, offset + row, col)``.

        The geometry is the last :meth:`render`'s: rows past the painted
        window, the scrollbar column, blank padding rows and any negative
        coordinate answer ``None``.  Before the first render every cell
        answers ``None``.
        """
        if row < 0 or col < 0:
            return None
        if row >= self._last_height or col >= self._last_inner:
            return None
        local = self._last_offset + row
        if local >= self._state.content_height:
            return None
        return self.child, local, col

    # -- rendering --------------------------------------------------------------

    def revision(self) -> object:
        """The row cache's snapshot: child identity/snapshot plus the knobs.

        A :class:`~motui.kernel.document.Revisioned` child contributes its own
        snapshot -- the value its block would key on -- so an in-place edit
        moves this key before any render.  A child without one (or with its
        memory switched off by a ``None`` snapshot) contributes its
        identity; like any non-revisioned component it is re-rendered per
        layout.  ``offset``, ``height`` and ``bar`` are the rest of the
        view's own mutable input, and ``theme``/``styles`` are the
        chrome roles' source (read at render time).
        """
        child = self.child
        snapshot: object = None
        if isinstance(child, Revisioned):
            snapshot = child.revision()
        child_key: object = snapshot if snapshot is not None else id(child)
        return (
            child_key,
            self._state.offset,
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
        carries a budget.  Every painted row is clipped into the surface.
        """
        width = c.width
        bar_width = 1 if self.bar and width > 0 else 0
        inner = max(0, width - bar_width)
        child_rows = list(self.child.render(Constraints(width=inner)))
        state = self._state
        state.content_height = len(child_rows)
        height = self.viewport_height
        # The explicit height is the host's slot and wins over the budget;
        # a natural-height view fills the budget it was offered.
        if self.height is None and c.max_height is not None:
            height = min(height, c.max_height)
        state.viewport_height = height
        state.clamp()
        start = state.offset
        self._last_inner = inner
        self._last_offset = start
        self._last_height = height
        self._rendered = True
        thumb = state.thumb(height)
        thumb_start, thumb_length = thumb if thumb is not None else (0, 0)
        # The chrome roles resolve once per render: track and thumb.
        chrome = self.group("chrome") if bar_width else None
        out: list[Line] = []
        for row in range(height):
            index = start + row
            line = child_rows[index].clip(WrapMode.ELLIPSIS, inner) if index < state.content_height else Line()
            if bar_width:
                line = line.fill(inner)
                if thumb_start <= row < thumb_start + thumb_length:
                    glyph, style = self.glyphs.bar_full, chrome.scrollbar_thumb
                else:
                    glyph, style = self.glyphs.bar_empty, chrome.scrollbar
                line = Line((*line.segments, Segment(glyph, style)))
            out.append(line.clip(WrapMode.ELLIPSIS, width))
        return Surface.clipped(out, c.width)

    def __repr__(self) -> str:
        return (
            f"ScrollPanel(offset={self._state.offset}, height={self.height!r}, "
            f"bar={self.bar}, total_rows={self._state.content_height})"
        )
