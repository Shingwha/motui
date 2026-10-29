"""The pane chrome: the Scrollbar.

A budgeted strip whose thumb maps the pane's scroll state; the strip is
the pane's scrolling window (body-scoped chrome), so pinned rows keep the
column empty. Dispatch order: chrome before gestures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

from ..kernel.events import Event, MouseEvent
from ..kernel.frame import Chrome, Pane, Rect
from ..kernel.geom import Axis
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, Segment
from ..kernel.layout import ScrollAxis, ScreenLayout
from ..kernel.style import Style
from ..kernel.theme import DEFAULT_THEME, Theme
from ..widgets.scroll import ScrollPanel

if TYPE_CHECKING:
    from .runtime import Runtime, Timer

__all__ = ["Scrollbar", "ScrollbarStyles"]


@dataclass(frozen=True, slots=True)
class ScrollbarStyles:
    """Explicit track/thumb style overrides; a ``None`` field falls through to
    the theme."""

    track: Style | None = None
    thumb: Style | None = None


class _Thumb(NamedTuple):
    """One thumb's geometry over one strip: position, length, travel and scroll
    range."""

    pos: int
    length: int
    track: int
    scroll: int


def _thumb_of(layout: ScreenLayout, height: int, min_thumb: int) -> _Thumb | None:
    """The thumb a laid-out pane maps onto a ``height``-row strip, or ``None``
    when nothing scrolls; the kernel's one thumb formula."""
    axis = ScrollAxis(
        offset=layout.offset,
        content=layout.total_rows,
        viewport=len(layout.body_rows),
    )
    span = axis.thumb(height, min_thumb)
    if span is None:
        return None
    pos, length = span
    track = max(1, height - length)
    scroll = max(1, axis.max_offset)
    return _Thumb(pos, length, track, scroll)


class Scrollbar:
    """A right-edge scrollbar chrome: a budgeted strip that maps the scroll.

    ``axis=Axis.X`` maps a ScrollPanel's horizontal state on the bottom edge.
    The strip is the window, so a press test and the painted cells describe one
    rectangle. Constructing registers the chrome; ``detach`` unregisters it."""

    __slots__ = (
        "_axis",
        "_chrome",
        "_grab",
        "_glyphs",
        "_handle",
        "_held",
        "_min_thumb",
        "_pane_id",
        "_repeat",
        "_scroll_tick",
        "_size",
        "_strip_cache",
        "_styles",
        "_target",
        "_theme",
        "_thumb",
        "_track",
        "_tui",
    )

    def __init__(
        self,
        tui: Runtime,
        *,
        pane: str | None = None,
        axis: Axis = Axis.Y,
        target: ScrollPanel | None = None,
        size: int = 1,
        min_thumb: int = 1,
        styles: ScrollbarStyles | None = None,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        scroll_tick: float = 0.05,
    ) -> None:
        if axis not in (Axis.X, Axis.Y):
            raise ValueError(f"axis must be Axis.X or Axis.Y, got {axis!r}")
        self._tui = tui
        self._axis = axis
        self._size = size
        self._min_thumb = min_thumb
        self._styles = styles
        self._glyphs = glyphs
        self._track = glyphs.bar_empty
        self._thumb = glyphs.bar_full
        self._theme = theme
        self._scroll_tick = scroll_tick
        # The driver's frame seam (module docstring): the bar registers on
        # whichever pane currently holds the id, and a split keeps that id
        # on the first child -- so the registration rides any retile, which
        # rewrites pane rectangles in place rather than rebuilding panes.
        frame = tui.frame
        if pane is None:
            first = frame.panes[0] if frame.panes else None
            host = first
        else:
            host = frame.pane(pane)
        if host is None:
            known = [held.id for held in frame.panes]
            raise ValueError(f"no pane named {pane!r}: the frame holds {known}")
        self._pane_id = host.id
        if axis is Axis.X:
            # The horizontal bar maps one ScrollPanel's x state over the
            # pane's bottom row.  An explicit target wins; otherwise the
            # pane's document must hold exactly one ScrollPanel, because
            # with two there is no honest implicit answer.
            self._target = target if target is not None else self._find_target(host)
            self._chrome = Chrome(
                "bottom", size, self._paint_horizontal, scope="pane"
            )
        else:
            self._target = None
            self._chrome = Chrome("right", size, self._paint, scope="body")
        host.add_chrome(self._chrome)
        self._held = False
        self._grab: tuple[int, int] | None = None  # (strip row, offset) of the grab
        self._repeat = 0  # the held-track page direction: 0, 1 (down), -1 (up)
        self._handle: Timer | None = None
        # The last strip painted and the state it was painted from: the memo
        # of :meth:`_paint`, keyed by everything that paint reads.
        self._strip_cache: tuple[tuple, tuple[Line, ...]] | None = None

    @staticmethod
    def _find_target(pane: Pane) -> ScrollPanel:
        """The pane document's unique ScrollPanel, for an implicit axis-X target."""
        found = [
            block.widget
            for block in pane.document.blocks()
            if isinstance(block.widget, ScrollPanel)
        ]
        if len(found) != 1:
            raise ValueError(
                "an axis-X Scrollbar needs an explicit target or exactly one "
                f"ScrollPanel in pane {pane.id!r}'s document, found {len(found)}"
            )
        return found[0]

    def __repr__(self) -> str:
        return (
            f"Scrollbar(pane={self._pane_id!r}, size={self._size}, "
            f"axis={self._axis.value})"
        )

    # -- the event contract --------------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Advance the bar with ``event``; ``True`` when consumed. The bar owns the
        left press on its strip and the motion/release that follow; every wheel
        report stays the host's."""
        if self._axis is Axis.X:
            return False  # display-only this wave: never swallow an event
        if not isinstance(event, MouseEvent):
            return False
        if event.button != "left":
            return False  # the wheel reports and the other buttons stay the host's
        if event.kind == "press":
            if not self._covers(event.x, event.y):
                return False  # outside the strip: the content is under the pointer
            self._held = True
            self._press(event.y)
            return True
        if not self._held:
            return False  # the press was never ours: nothing to drag or repeat
        if event.kind == "release":
            self._release()
            return True
        if event.kind == "motion":
            self._motion(event.x, event.y)
            return True
        return False

    # -- lifecycle ---------------------------------------------------------------

    def detach(self) -> None:
        """Unregister the chrome and cancel the ticker; idempotent."""
        self._release()  # drops the in-flight drag and the held-track ticker
        pane = self._pane()
        if pane is not None and self._chrome in pane.chrome:
            pane.remove_chrome(self._chrome)

    def set_theme(self, theme: Theme) -> None:
        """Repaint the strip on ``theme``; the memo is keyed by the resolved styles,
        so dropping it is the whole change."""
        self._theme = theme
        self._strip_cache = None
        self._tui.refresh()

    # -- the paint ---------------------------------------------------------------

    def _paint(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The strip: track and thumb rows, memoized on everything it reads --
        layout state, length, size, glyphs and resolved styles."""
        if length <= 0:
            return []
        track_style, thumb_style = self._resolve_track(), self._resolve_thumb()
        key = (
            layout.offset,
            layout.total_rows,
            len(layout.body_rows),
            length,
            self._size,
            self._min_thumb,
            self._track,
            self._thumb,
            track_style,
            thumb_style,
        )
        cached = self._strip_cache
        if cached is not None and cached[0] == key:
            return list(cached[1])
        thumb = _thumb_of(layout, length, self._min_thumb)
        first = thumb.pos if thumb is not None else 0
        last = first + thumb.length if thumb is not None else 0
        track_line = Line.from_text(self._track * self._size, track_style)
        thumb_line = Line.from_text(self._thumb * self._size, thumb_style)
        strip = tuple(
            thumb_line if first <= index < last else track_line
            for index in range(length)
        )
        self._strip_cache = (key, strip)
        return list(strip)

    def _paint_horizontal(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The bottom strip: one row of track and thumb from the target's own x
        state, through the same thumb formula."""
        target = self._target
        if length <= 0 or target is None:
            return []
        track_style, thumb_style = self._resolve_track(), self._resolve_thumb()
        axis = target.scroll.x
        span = axis.thumb(length, self._min_thumb)
        first, last = (span[0], span[0] + span[1]) if span is not None else (0, 0)
        cells = [
            Segment(
                self._thumb if first <= column < last else self._track,
                thumb_style if first <= column < last else track_style,
            )
            for column in range(length)
        ]
        return [Line(cells)]

    def _resolve_track(self) -> Style:
        """The track's style: ``styles.track`` > theme > DEFAULT."""
        if self._styles is not None and self._styles.track is not None:
            return self._styles.track
        theme = self._theme if self._theme is not None else DEFAULT_THEME
        return theme.chrome.scrollbar

    def _resolve_thumb(self) -> Style:
        """The thumb's style: ``styles.thumb`` > theme > DEFAULT."""
        if self._styles is not None and self._styles.thumb is not None:
            return self._styles.thumb
        theme = self._theme if self._theme is not None else DEFAULT_THEME
        return theme.chrome.scrollbar_thumb

    # -- the pane, geometrically ---------------------------------------------------

    def _pane(self) -> Pane | None:
        """The bar's pane as the driver's frame holds it right now."""
        return self._tui.frame.pane(self._pane_id)

    def _strip(self) -> Rect | None:
        """The band the kernel granted the bar's chrome -- the same derivation the
        compositor paints, so routing and painting can never disagree."""
        pane = self._pane()
        if pane is None:
            return None
        return pane.band(self._chrome)

    def _covers(self, x: int, y: int) -> bool:
        """Whether the cell sits inside the bar's strip (the routing test)."""
        strip = self._strip()
        return strip is not None and (
            strip.x <= x < strip.right and strip.y <= y < strip.bottom
        )

    def _geometry(self) -> _Thumb | None:
        """The thumb over the pane's last laid-out strip, ``None`` without one."""
        layout = self._tui.frame.pane_layout(self._pane_id)
        strip = self._strip()
        if layout is None or strip is None:
            return None
        return _thumb_of(layout, strip.height, self._min_thumb)

    # -- the gesture ---------------------------------------------------------------

    def _press(self, y: int) -> None:
        """Grab the thumb under the pointer, or page the track and arm the repeat
        ticker."""
        self._cancel_repeat()
        strip = self._strip()
        if strip is None:
            return
        thumb = self._geometry()
        row = y - strip.y
        pane = self._pane()
        if (
            thumb is not None
            and pane is not None
            and thumb.pos <= row < thumb.pos + thumb.length
        ):
            self._grab = (row, pane.viewport.offset)
            return
        divider = (
            thumb.pos + thumb.length // 2 if thumb is not None else strip.height // 2
        )
        self._repeat = -1 if row < divider else 1
        self._page(self._repeat)
        self._handle = self._tui.every(self._scroll_tick, self._tick)

    def _motion(self, x: int, y: int) -> None:
        """Drag the grabbed thumb, or stand a held track page down on edge-exit."""
        strip = self._strip()
        if strip is None:
            self._cancel_repeat()
            return
        if self._grab is not None:
            self._drag(y - strip.y)
            return
        if not (strip.x <= x < strip.right and strip.y <= y < strip.bottom):
            self._cancel_repeat()  # edge-exit

    def _drag(self, row: int) -> None:
        """Scroll so the grabbed thumb point rides at ``row``, anchored at the grab
        so the thumb never jumps."""
        grab = self._grab
        thumb = self._geometry()
        pane = self._pane()
        if grab is None or thumb is None or pane is None:
            return
        target = grab[1] + round((row - grab[0]) * thumb.scroll / thumb.track)
        target = max(0, min(thumb.scroll, target))
        delta = target - pane.viewport.offset
        if delta == 0:
            return
        if delta > 0:
            pane.viewport.scroll_down(delta)
        else:
            pane.viewport.scroll_up(-delta)
        self._tui.refresh()

    def _release(self) -> None:
        """End the drag or the held page: the bar stops with the button."""
        self._held = False
        self._grab = None
        self._cancel_repeat()

    def _page(self, side: int) -> None:
        """Scroll one window page toward ``side`` on this bar's own pane."""
        layout = self._tui.frame.pane_layout(self._pane_id)
        pane = self._pane()
        if layout is None or pane is None:
            return
        page = len(layout.body_rows)
        if page <= 0:
            return
        if side > 0:
            pane.viewport.scroll_down(page)
        else:
            pane.viewport.scroll_up(page)
        self._tui.refresh()

    def _tick(self) -> None:
        """One held-track tick: page again, or stand down at the document end."""
        if self._repeat == 0:
            self._cancel_repeat()
            return
        pane = self._pane()
        if pane is None:
            self._cancel_repeat()
            return
        before = pane.viewport.offset
        self._page(self._repeat)
        if pane.viewport.offset == before:
            self._cancel_repeat()  # pinned at the document's end

    def _cancel_repeat(self) -> None:
        """Cancel the held-track ticker (a no-op when none is armed)."""
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        self._repeat = 0

