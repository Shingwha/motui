"""Frame overlays: the toast stack, the tooltip and the stats box.

All policy over the frame's ordered overlay registry. Dispatch order:
chrome, then overlays, then content gestures -- a press on a band must be
seen before any hit test."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from ..kernel.document import Component
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.frame import Frame, Rect, splice_row
from ..kernel.cell import Line, overlay
from ..widgets.text import Text
from ..kernel.style import Style
from ..kernel.theme import DEFAULT_THEME, Theme
from ..kernel.layout import ScreenLayout
from ..kernel.layout import Constraints
from ..kernel.text import WrapMode

if TYPE_CHECKING:
    from .runtime import Runtime, Timer
    from .pointer import Pointer

__all__ = ["Stats", "Toasts", "Tooltip"]

#: The four corners a toast stack anchors at.
_CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")

#: A toast's widest band: the clamp ceiling, beside the frame's half-width.
MAX_TOAST_WIDTH = 40

#: How often the one expiry ticker runs while any toast is live.  A toast's
#: last frame is resolved to a tenth of a second; a finer tick would only
#: burn wakeups.
EXPIRY_TICK = 0.1


@dataclass(frozen=True)
class _Toast:
    """One live toast: its component, explicit band style and ``clock()``
    expiry; timestamps stay in the controller."""

    component: Component
    style: Style | None
    expires_at: float


def _stack(
    toasts: Sequence[_Toast], rect: Rect, corner: str
) -> list[tuple[_Toast, Rect, list[Line]]]:
    """Where each live toast paints inside ``rect``: at the ceiling, band as
    wide as its widest row, growing away from ``corner``."""
    ceiling = min(MAX_TOAST_WIDTH, rect.width // 2)
    if ceiling <= 0:
        return []
    measured: list[tuple[_Toast, int, list[Line]]] = []
    for toast in toasts:
        rendered = [row.clip(WrapMode.ELLIPSIS, ceiling) for row in toast.component.render(Constraints(width=ceiling))]
        # An empty component renders no rows, which measures to zero width.
        width = min(max((row.width for row in rendered), default=0), ceiling)
        if width <= 0:
            continue  # nothing to show: an empty component paints no band
        measured.append((toast, width, rendered))
    left = corner.endswith("left")
    placed: list[tuple[_Toast, Rect, list[Line]]] = []
    if corner.startswith("top"):
        cursor = rect.y
        for toast, width, rendered in reversed(measured):
            x = rect.x if left else rect.right - width
            placed.append((toast, Rect(x=x, y=cursor, width=width, height=len(rendered)), rendered))
            cursor += len(rendered) + 1  # one blank row between neighbours
    else:
        cursor = rect.bottom
        for toast, width, rendered in reversed(measured):
            cursor -= len(rendered)
            x = rect.x if left else rect.right - width
            placed.append((toast, Rect(x=x, y=cursor, width=width, height=len(rendered)), rendered))
            cursor -= 1  # one blank row between neighbours
    placed.reverse()  # show order: oldest first
    return placed


def _band_row(row: Line, width: int, band: Style) -> Line:
    """One toast row: content over the band, using the colored-vs-attribute
    overlay rule."""
    content = Line(overlay(band, row.segments))
    return content + Line.filled(width - row.width, band)


class Toasts:
    """A corner-anchored stack of transient toasts over the composed frame.

    Constructing registers the overlay on the frame. The paint is pure
    (frame rows plus the live list); time and input live in the controller --
    one expiry ticker and :meth:`handle` for dismissing."""

    __slots__ = (
        "_corner",
        "_detached",
        "_handle",
        "_max_shown",
        "_style",
        "_theme",
        "_toasts",
        "_ttl",
        "_tui",
    )

    def __init__(
        self,
        tui: Runtime,
        *,
        ttl: float = 4.0,
        max_shown: int = 3,
        corner: str = "top-right",
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        if corner not in _CORNERS:
            raise ValueError(
                f"toast corner must be one of {_CORNERS}, got {corner!r}"
            )
        self._tui = tui
        self._ttl = ttl
        self._max_shown = max_shown
        self._corner = corner
        self._style = style
        self._theme = theme
        self._toasts: list[_Toast] = []
        self._detached = False
        self._handle: Timer | None = None
        # The driver's frame seam (module docstring): the overlay registers
        # here for the frame's life -- a retile re-divides the tiling in
        # place, so nothing carries across.
        tui.frame.add_overlay(self, layer="toast")

    def __repr__(self) -> str:
        return f"Toasts(corner={self._corner!r}, shown={len(self._toasts)})"

    # -- the lifecycle -------------------------------------------------------

    def show(
        self,
        content: str | Component,
        *,
        style: Style | None = None,
        ttl: float | None = None,
    ) -> None:
        """Show a toast, string or Component; a show past ``max_shown`` evicts the
        oldest, and a detached controller is a no-op."""
        if self._detached:
            return
        component = Text(content) if isinstance(content, str) else content
        expires_at = self._tui.clock() + (self._ttl if ttl is None else ttl)
        self._toasts.append(_Toast(component, style, expires_at))
        overflow = len(self._toasts) - self._max_shown
        if overflow > 0:
            del self._toasts[:overflow]
        self._tui.refresh()
        if self._handle is None:
            self._handle = self._tui.every(EXPIRY_TICK, self._tick)

    def detach(self) -> None:
        """Unregister the overlay and cancel the ticker; idempotent."""
        if self._detached:
            return
        self._detached = True
        self._cancel()
        self._toasts = []
        self._tui.frame.remove_overlay(self)

    def set_theme(self, theme: Theme) -> None:
        """Repaint the stack on ``theme``; the band is resolved at paint time, so
        live toasts keep their explicit styles."""
        self._theme = theme
        self._tui.refresh()

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Dismiss the toast under a left press; ``True`` when one was dismissed.
        Consuming the press keeps the gesture from anchoring beneath the band."""
        if self._detached or not self._toasts:
            return False
        if not isinstance(event, MouseEvent) or event.button != "left":
            return False
        if event.kind != "press":
            return False
        rect = self._tui.frame.rect
        if rect is None:
            return False
        for toast, band, _ in _stack(self._toasts, rect, self._corner):
            if band.x <= event.x < band.right and band.y <= event.y < band.bottom:
                self._drop(toast)
                return True
        return False

    # -- the controller -----------------------------------------------------------

    def _tick(self) -> None:
        """One expiry tick: drop the due toasts, and stand the ticker down when the
        stack empties."""
        if self._detached:
            self._cancel()
            return
        now = self._tui.clock()
        kept = [toast for toast in self._toasts if toast.expires_at > now]
        if len(kept) == len(self._toasts):
            return  # nothing came due: no repaint, the ticker keeps its period
        self._toasts = kept
        self._tui.refresh()
        if not kept:
            self._cancel()

    def _drop(self, toast: _Toast) -> None:
        """Remove one toast and stop the ticker when it was the last."""
        self._toasts = [held for held in self._toasts if held is not toast]
        self._tui.refresh()
        if not self._toasts:
            self._cancel()

    def _cancel(self) -> None:
        """Cancel the expiry ticker (a no-op when none is armed)."""
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None

    # -- the paint ---------------------------------------------------------------

    def paint(self, frame: Frame) -> ScreenLayout:
        """The stack over the composed frame, each band spliced into its rectangle;
        the layout comes back unchanged when the stack is empty."""
        layout = frame.layout
        rect = frame.rect
        if rect is None or not self._toasts:
            return layout
        rows = list(layout.rows)
        for toast, band, rendered in _stack(self._toasts, rect, self._corner):
            style = self._resolve_band(toast.style)
            for index, row in enumerate(rendered):
                target = band.y + index
                if not 0 <= target < len(rows):
                    continue  # clipped at the frame's far edge
                rows[target] = splice_row(
                    rows[target],
                    _band_row(row, band.width, style),
                    band.x,
                    band.width,
                    rect.width,
                )
        return replace(layout, rows=rows)

    def _resolve_band(self, style: Style | None) -> Style:
        """The band's style: a toast's own > the controller's > theme > DEFAULT."""
        if style is not None:
            return style
        if self._style is not None:
            return self._style
        theme = self._theme if self._theme is not None else DEFAULT_THEME
        return theme.overlays.toast


class _MountedOverlay:
    """An overlay mounted for the frame's life: register once, detach once;
    detaching is idempotent."""

    __slots__ = ("_detached", "_theme", "_tui")

    def __init__(self, tui: Runtime, *, layer: str, theme: Theme | None = None) -> None:
        self._theme = theme if theme is not None else DEFAULT_THEME
        self._tui = tui
        self._detached = False
        # The driver's frame seam: the overlay registers here for the frame's
        # life -- a retile re-divides the tiling in place, so nothing carries
        # across.
        tui.frame.add_overlay(self, layer=layer)

    def set_theme(self, theme: Theme) -> None:
        """Repaint the overlay on ``theme``; the band resolves at paint time."""
        self._theme = theme
        self._tui.refresh()

    def detach(self) -> None:
        """Unregister the overlay by identity; idempotent."""
        if self._detached:
            return
        self._detached = True
        self._tui.frame.remove_overlay(self)


class Tooltip(_MountedOverlay):
    """A one-row hint band beside the pointer, driven by the hovered leaf's
    ``hint``.

    A pointer that never moved, a leaf without a hint, or no room hands the
    layout back unchanged; the band paints under the pointer and flips above
    on the last row."""

    __slots__ = ("_pointer",)

    def __init__(
        self,
        tui: Runtime,
        pointer: Pointer,
        *,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(tui, layer="tooltip", theme=theme)
        self._pointer = pointer

    def __repr__(self) -> str:
        return f"Tooltip(hovered={self._pointer.hovered!r}, detached={self._detached})"

    # -- the paint -----------------------------------------------------------

    def paint(self, frame: Frame) -> ScreenLayout:
        """The hint band over the composed frame, or the layout itself when idle."""
        layout = frame.layout
        rect = frame.rect
        position = self._pointer.position
        hovered = self._pointer.hovered
        hint = getattr(hovered, "hint", None) if hovered is not None else None
        if rect is None or position is None or not isinstance(hint, str) or not hint:
            return layout  # no pointer, no hint: zero bytes
        row = Line.from_text(hint).clip(WrapMode.ELLIPSIS, rect.width)
        width = row.width
        if width <= 0:
            return layout  # a frame with no column to host the band
        x, y = _tip_origin(position, width, rect)
        rows = list(layout.rows)
        if not 0 <= y < len(rows):
            return layout  # a frame whose rectangle lies outside the rows
        band = self._theme.overlays.toast
        rows[y] = splice_row(
            rows[y], _band_row(row, width, band), x, width, rect.width
        )
        return replace(layout, rows=rows)


def _tip_origin(pointer: tuple[int, int], width: int, rect: Rect) -> tuple[int, int]:
    """Where a one-row band sits for a pointer cell: below it, above it on the
    last row, clamped into the frame."""
    x, y = pointer
    x = min(max(x, rect.x), max(rect.x, rect.right - width))
    if y + 1 < rect.bottom:
        return x, y + 1
    if y - 1 >= rect.y:
        return x, y - 1
    return x, min(max(y, rect.y), rect.bottom - 1)


class Stats(_MountedOverlay):
    """The dev overlay: frames, fps, event count, last event and hover.

    It paints a small top-right stack; :meth:`handle` counts every event and
    its ``True`` is a repaint cue, not a dispatch claim. No timer is armed."""

    __slots__ = (
        "_events",
        "_fps",
        "_last",
        "_sample_at",
        "_sample_frames",
        "pointer",
    )

    #: The shortest window a frame-rate reading may cover, in seconds: the
    #: reading is taken at paint time, once the window has grown this wide.
    SAMPLE_WINDOW = 1.0

    def __init__(
        self,
        tui: Runtime,
        *,
        pointer: Pointer | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(tui, layer="overlay", theme=theme)
        self.pointer = pointer
        self._events = 0
        self._last = ""
        self._fps = 0.0
        self._sample_frames = tui.painter.frames
        self._sample_at = tui.clock()

    def __repr__(self) -> str:
        return (
            f"Stats(frames={self._tui.painter.frames}, fps={self._fps:.1f}, "
            f"events={self._events}, detached={self._detached})"
        )

    # -- the readings ------------------------------------------------------

    @property
    def events(self) -> int:
        """How many events :meth:`handle` has counted."""
        return self._events

    @property
    def last(self) -> str:
        """The last counted event's name (``""`` before the first)."""
        return self._last

    @property
    def fps(self) -> float:
        """The frame rate of the last sampled window (``0.0`` until one is)."""
        return self._fps

    # -- the lifecycle -------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Repaint the box on ``theme``; the band resolves at paint time."""
        self._theme = theme

    # -- the event contract --------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Count ``event``; ``True`` is a repaint cue, not a dispatch claim. Every
        event counts, whatever its tier."""
        self._events += 1
        if isinstance(event, PasteEvent):
            self._last = "paste"
        elif isinstance(event, KeyEvent):
            self._last = event.key
        elif isinstance(event, MouseEvent):
            self._last = event.button
        else:
            self._last = type(event).__name__.lower()
        return True

    # -- the paint -----------------------------------------------------------

    def _lines(self) -> list[str]:
        """The box's rows, read off the live state (four readings, three rows)."""
        lines = [
            f"frames {self._tui.painter.frames}  {self._fps:5.1f} fps",
            f"events {self._events}  last {self._last or '--'}",
        ]
        pointer = self.pointer
        hovered = None if pointer is None else pointer.hovered
        position = None if pointer is None else pointer.position
        if hovered is None or position is None:
            lines.append("hover --")
        else:
            lines.append(f"hover {type(hovered).__name__} ({position[0]}, {position[1]})")
        return lines

    def _sample(self) -> None:
        """Take a frame-rate reading once the window is at least one second wide,
        so the number is not noise."""
        now, frames = self._tui.clock(), self._tui.painter.frames
        elapsed = now - self._sample_at
        if elapsed < self.SAMPLE_WINDOW:
            return
        self._fps = (frames - self._sample_frames) / elapsed
        self._sample_frames, self._sample_at = frames, now

    def paint(self, frame: Frame) -> ScreenLayout:
        """The box in the frame's top-right corner, right-aligned and filled with
        the theme's toast band."""
        layout = frame.layout
        rect = frame.rect
        if rect is None or rect.width <= 0 or rect.height <= 0:
            return layout
        self._sample()  # the one write, and it only reads the clock and the counter
        rows = [Line.from_text(text).clip(WrapMode.ELLIPSIS, rect.width) for text in self._lines()]
        width = min(max((row.width for row in rows), default=0), rect.width)
        if width <= 0:
            return layout
        band = self._theme.overlays.toast
        out = list(layout.rows)
        x = rect.right - width
        for index, row in enumerate(rows):
            y = rect.y + index
            if not 0 <= y < len(out):
                break  # a frame whose rectangle lies outside the rows
            out[y] = splice_row(out[y], _band_row(row, width, band), x, width, rect.width)
        return replace(layout, rows=out)
