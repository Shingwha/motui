"""ScrollView: a window over any component's rows.

A :class:`ScrollView` renders its child at the width it can give it and
shows a fixed-height slice of the result.  It is the composition-layer
answer to "this content is taller than its slot": charts, long forms, a
panel's body, a markdown document -- any component works unchanged,
because the child keeps rendering through the one ``render(width)``
protocol.

Three knobs decide the window:

* ``height`` -- how many rows to show; ``None`` (the default) shows the
  child's every row and makes scrolling a no-op;
* ``offset`` -- the first visible child row, clamped to the last window
  ``max(0, total_rows - height)``;
* ``scrollbar`` -- paint a one-column bar in the rightmost column, the
  child then rendering at ``width - 1`` columns.

The bar uses :attr:`~motui.core.glyphs.Glyphs.bar_empty` and
:attr:`~motui.core.glyphs.Glyphs.bar_full` in ``chrome.scrollbar`` and
``chrome.scrollbar_thumb``.  The geometry is the one
:meth:`~motui.core.scroll.ScrollState.thumb` formula: proportional to the
visible fraction, at least one cell, and no thumb at all when the content
fits the window (the bar then paints its plain track).

:meth:`ScrollView.handle` owns the scrolling keys -- ``up``/``down`` one
row, ``page_up``/``page_down`` one window, ``home``/``end`` the edges --
and the vertical wheel.  It answers ``True`` only when the offset
actually moved, so a host keeps the boundaries' keys.  ``ScrollView`` is a
:class:`~motui.core.block.Container`: a visible cell maps to the child
row ``offset + row``, and the scrollbar column belongs to the view.
``revision`` folds the child's own snapshot (identity when it has none)
with the three knobs, so a sealed block around a scroll view still
repaints when the child changes in place.
"""

from __future__ import annotations

from ..core.block import Component, Revisioned
from ..core.events import Event, KeyEvent, MouseEvent
from ..core.glyphs import GLYPHS, Glyphs
from ..core.lines import Line, Segment
from ..core.scroll import ScrollState
from ..core.style import Style
from ..core.theme import Theme, Themed

__all__ = ["ScrollView"]


class ScrollView(Themed):
    """A clipped, scrollable window over one child component.

    ``height=None`` shows every child row; a fixed ``height`` shows exactly
    that many rows, padding with blank rows when the child is shorter (so
    the view's slot never jumps).  ``offset`` starts at the requested row
    (never negative) and is clamped into the legal range on every render,
    which is what makes a child that shrinks safe.  ``child``, ``height``
    and ``scrollbar`` are ordinary attributes a host may change on resize;
    :attr:`offset` and :attr:`total_rows` are read-only views of the last
    render's geometry.

    The width split is deliberate: with a scrollbar the child renders at
    ``width - 1``, so the bar never covers content; without one it renders
    at ``width``.  Every painted row is fitted back to the painting width.
    """

    __slots__ = (
        "_last_height",
        "_last_inner",
        "_last_offset",
        "_rendered",
        "_state",
        "_thumb_style",
        "_track_style",
        "child",
        "glyphs",
        "height",
        "scrollbar",
    )

    def __init__(
        self,
        child: Component,
        *,
        height: int | None = None,
        offset: int = 0,
        scrollbar: bool = False,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.child = child
        self.glyphs = glyphs
        self.height = None if height is None else max(0, height)
        self.scrollbar = bool(scrollbar)
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
        self._track_style: Style = self._theme.chrome.scrollbar
        self._thumb_style: Style = self._theme.chrome.scrollbar_thumb
        #: Whether a render has established ``total_rows`` yet.  Before the
        #: first render the upper clamp is unknown, so a fixed-height view
        #: accepts a requested offset and clamps it on the first render.
        self._rendered = False

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

        A :class:`~motui.core.block.Revisioned` child contributes its own
        snapshot -- the value its block would key on -- so an in-place edit
        moves this key before any render.  A child without one (or with its
        memory switched off by a ``None`` snapshot) contributes its
        identity; like any non-revisioned component it is re-rendered per
        layout.  ``offset``, ``height`` and ``scrollbar`` are the rest of
        the view's own mutable input.
        """
        child = self.child
        snapshot: object = None
        if isinstance(child, Revisioned):
            snapshot = child.revision()
        child_key: object = snapshot if snapshot is not None else id(child)
        return (child_key, self._state.offset, self.height, self.scrollbar, self.glyphs)

    def render(self, width: int) -> list[Line]:
        """Render the child at the inner width and paint the visible window."""
        bar_width = 1 if self.scrollbar and width > 0 else 0
        inner = max(0, width - bar_width)
        child_rows = list(self.child.render(inner))
        state = self._state
        state.content_height = len(child_rows)
        height = self.viewport_height
        state.viewport_height = height
        state.clamp()
        start = state.offset
        self._last_inner = inner
        self._last_offset = start
        self._last_height = height
        self._rendered = True
        thumb = state.thumb(height)
        thumb_start, thumb_length = thumb if thumb is not None else (0, 0)
        out: list[Line] = []
        for row in range(height):
            index = start + row
            line = child_rows[index].fit(inner) if index < state.content_height else Line()
            if bar_width:
                line = line.fill(inner)
                if thumb_start <= row < thumb_start + thumb_length:
                    glyph, style = self.glyphs.bar_full, self._thumb_style
                else:
                    glyph, style = self.glyphs.bar_empty, self._track_style
                line = Line((*line.segments, Segment(glyph, style)))
            out.append(line.fit(width))
        return out

    def __repr__(self) -> str:
        return (
            f"ScrollView(offset={self._state.offset}, height={self.height!r}, "
            f"scrollbar={self.scrollbar}, total_rows={self._state.content_height})"
        )
