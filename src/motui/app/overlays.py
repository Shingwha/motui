"""overlays: the frame overlays -- the toast stack, the tooltip and the stats box.

This module is the overlay tier, the peer of
:mod:`motui.app.scrollbar` and :mod:`motui.app`: it imports the
driver and the kernel, and nothing below it imports it.  Everything here is
*policy* -- how long a toast lives, what a hint band looks like, what the
dev box reads -- over a mechanism the kernel owns: the frame's ordered
overlay registry (:meth:`~motui.core.frame.Frame.add_overlay`), where an
overlay paints over the composed frame, in registration order.  The
time- and input-shaped halves ride the driver's
:meth:`~motui.app.TUI.every` handles and the host's own dispatch.

:class:`Toasts` is the reference overlay (D3): a corner-anchored stack of
transient bands painted over the composed frame.  Constructing one
registers the overlay; ``detach()`` unregisters it and cancels the ticker.
Its paint is a pure function of the frame's rows and the live toast list --
time and input live in the controller, never in the kernel -- and it routes
a press that lands inside a toast's own rectangle, so a host dispatches
through it the same way.

:class:`Tooltip` is the pointer's own overlay (D9): a one-row hint band
painted beside the cell the :class:`~motui.app.pointer.Pointer` last
hovered, read from the hovered leaf's ``hint`` attribute.  Constructing one
registers the overlay; ``detach()`` unregisters it.  Its paint is a pure
function of the pointer's live state and the frame's rows, and an untriggered
paint -- no pointer, no ``hint`` -- hands the layout back unchanged: the
zero-byte case.

:class:`Stats` is the developer's overlay (D14): a small band stack in the
frame's top-right corner reading ``painter.frames``, the frame rate over
its last window (``tui.clock()`` -- the box's own sample rule, no new
timing mechanism), the events the host fed through :meth:`Stats.handle` and
the last one's name, and the leaf the pointer hovers with the cell it last
moved over.  Same registration contract as the tooltip: constructed
mounted, ``detach()`` unmounts.

**The dispatch order** is the one rule every module of this tier writes out:
a host routes an event through the chrome first, then the overlays, then
the content gestures, then its own dispatch.  It is geometric here -- a
toast's band is derived from the frame's rectangles, while the frame's
ownership table resolves its cells as content, so each controller must see
the event before any hit test runs, or a press would anchor a selection
under the band.

The seam this module reads rather than owns is documented where it lives:
the driver's **frame**, through its public :attr:`~motui.app.TUI.frame`
property -- the tiling, its overlay registry and the composed rows -- and
the driver's **pump**, through the public :meth:`~motui.app.TUI.every`
handle the expiry ticker rides.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from ..core.block import Component
from ..core.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..core.frame import Frame, Rect, splice_row
from ..core.hit import EveryHandle
from ..core.lines import Line, Text, overlay
from ..core.style import Style
from ..core.theme import DEFAULT_THEME, Theme, Themed
from ..core.viewport import ScreenLayout

if TYPE_CHECKING:
    from .driver import TUI
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
    """One live toast: the component it shows, its band style, its expiry.

    ``style`` is the toast's own explicit band style, or ``None`` to resolve
    through the charter (the controller's ``style`` > its ``theme`` >
    :data:`DEFAULT_THEME <motui.core.theme.DEFAULT_THEME>`).
    ``expires_at`` is a ``tui.clock()`` reading taken when the toast was
    shown -- timestamps live in the controller, the layout stays timeless.
    """

    component: Component
    style: Style | None
    expires_at: float


def _stack(
    toasts: Sequence[_Toast], rect: Rect, corner: str
) -> list[tuple[_Toast, Rect, list[Line]]]:
    """Where each live toast paints inside ``rect``: the shared geometry.

    A toast renders at the *ceiling* -- :data:`MAX_TOAST_WIDTH` or the
    frame's half width, whichever is smaller -- and its band is as wide as
    the widest row that render produced, capped at the ceiling: a short
    toast is a short band, a long one wraps at the ceiling and never covers
    more than half the frame.  The rows are the component's own, fit to the
    ceiling, so a component that ignores its width is truncated by the same
    final guard the widgets apply.  A frame too narrow to host even one
    column yields no geometry, and an empty component (no rows, or rows that
    measure nothing) paints no band.

    The stack grows away from ``corner``: the newest toast sits at the
    corner and the older ones follow it, one blank row between neighbours,
    the tail clipped at the frame's far edge (the rows past the frame paint
    nothing).  The rectangle each toast gets is the one the paint splices
    through and the press test routes with -- one derivation, two readers.

    The toasts come back in show order (oldest first), each with its
    rectangle and its content rows.
    """
    ceiling = min(MAX_TOAST_WIDTH, rect.width // 2)
    if ceiling <= 0:
        return []
    measured: list[tuple[_Toast, int, list[Line]]] = []
    for toast in toasts:
        rendered = [row.fit(ceiling) for row in toast.component.render(ceiling)]
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
            placed.append((toast, Rect(x, cursor, width, len(rendered)), rendered))
            cursor += len(rendered) + 1  # one blank row between neighbours
    else:
        cursor = rect.bottom
        for toast, width, rendered in reversed(measured):
            cursor -= len(rendered)
            x = rect.x if left else rect.right - width
            placed.append((toast, Rect(x, cursor, width, len(rendered)), rendered))
            cursor -= 1  # one blank row between neighbours
    placed.reverse()  # show order: oldest first
    return placed


def _band_row(row: Line, width: int, band: Style) -> Line:
    """One toast row: its content over the band's filled background.

    The colored-vs-attribute rule of :func:`~motui.core.lines.overlay`
    -- the band paints underneath, a segment carrying a color of its own
    keeps it and an attribute-only one shows the band through -- then the
    row is filled out to ``width`` with
    :meth:`~motui.core.lines.Line.filled`, the band primitive, so a
    blank content row reads as a solid band row.
    """
    content = Line(overlay(band, row.segments))
    return content + Line.filled(width - row.width, band)


class Toasts:
    """A corner-anchored stack of transient toasts over the composed frame.

    ``tui`` is the driver whose frame the overlay registers on, whose clock
    stamps each toast's expiry and whose pump the expiry ticker rides.
    ``ttl`` is how long a toast lives (a per-show ``ttl`` overrides it);
    ``max_shown`` the most toasts the stack holds -- a show past it evicts
    the oldest.  ``corner`` anchors the stack
    (one of ``top-left``, ``top-right``, ``bottom-left``,
    ``bottom-right``); the newest toast sits at the corner and the stack
    grows away from it, one blank row between neighbours.  ``style`` /
    ``theme`` are the band's explicit style and the rest, each resolved at
    render time through the charter -- a toast's own ``style`` > the
    controller's ``style`` > the theme's ``overlays.toast`` > :data:`DEFAULT_THEME
    <motui.core.theme.DEFAULT_THEME>` -- so ``Theme(overlays=...)``
    restyles every band and an explicit style wins over both.  The ticker's
    period is the module's :data:`EXPIRY_TICK`; a toast's last frame needs
    no finer resolution than that.

    Constructing the controller registers the overlay on the frame, where
    it stays for the frame's life -- a retile rewrites the pane rectangles
    in place rather than rebuilding the frame, and the driver's own
    selection overlay rides the same registry.  A toast is shown with
    :meth:`show`
    -- a plain string (wrapped in a :class:`~motui.core.lines.Text`)
    or any Component, the customizability charter, so a toast can be a
    Notice, a Spinner or a host's own renderable.  ``detach()`` drops the
    stack, unregisters the overlay and cancels the ticker.

    **The paint** is the pure half: the frame's rows and the live toast
    list are its only inputs.  Each toast renders at the clamp ceiling,
    takes a :meth:`~motui.core.lines.Line.filled` band as wide as its
    widest row, and is spliced into the frame rows at its corner
    rectangle; an empty stack hands the layout back unchanged.  **The
    controller** owns everything time- and input-shaped: one ``tui.every``
    ticker checks expiry against ``tui.clock()`` and drops the due toasts,
    and :meth:`handle` consumes a press inside a toast's rectangle to
    dismiss it -- the selection/autoscroll pattern verbatim, timestamps and
    routing in the controller, mechanism in the kernel.
    """

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
        tui: TUI,
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
        self._handle: EveryHandle | None = None
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
        """Show a toast: ``content`` is a string (wrapped in a Text) or any
        Component.

        ``style`` is the toast's own band style (it wins over the
        controller's) and ``ttl`` its lifetime in seconds (``None`` keeps
        the controller's).  The expiry is stamped from ``tui.clock()`` at
        the show, a show past ``max_shown`` evicts the oldest toasts, the
        one expiry ticker arms on the first show, and the frame is
        invalidated so the pump paints the new stack.  A detached
        controller stays detached: the show is a no-op.
        """
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
        """Unregister the overlay and cancel the ticker (the EveryHandle
        convention).

        The symmetric of the constructor's registration: the frame drops
        the controller from its overlay registry
        (:meth:`~motui.core.frame.Frame.remove_overlay`, the chrome
        unregister's mirror), the stack empties, the ticker cancels, and
        the next composition paints as if no toast ever showed.
        ``detach`` is idempotent: :attr:`_detached` is the one identity
        that makes it so -- a second detach returns before it could claim
        an unregister the registry no longer owes -- and :meth:`show` reads
        the same flag, so a detached controller stays detached.
        """
        if self._detached:
            return
        self._detached = True
        self._cancel()
        self._toasts = []
        self._tui.frame.remove_overlay(self)

    def set_theme(self, theme: Theme) -> None:
        """Repaint the stack on ``theme`` (the App's re-skin road).

        The band is resolved at paint time, so this stores the theme and
        invalidates the frame; live toasts keep their own explicit styles
        and their expiry, and the registration rides untouched.
        """
        self._theme = theme
        self._tui.refresh()

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Dismiss the toast under the pointer; ``True`` when one was
        dismissed.

        The consume-a-key contract
        (:meth:`~motui.widgets.textfield.Input.handle` /
        :meth:`~motui.widgets.textfield.Editor.handle` /
        :meth:`~motui.app.gesture.SelectionGesture.handle`), at the dispatch
        position the module docstring gives overlays: after chrome, before the
        content gestures.  A left press inside any live toast's rectangle --
        the geometry :func:`_stack` derives, the same one the paint splices
        through -- drops that toast and is consumed, so the gesture never
        anchors a selection under the band and the host never dispatches a
        click on the text beneath it.  Every other event passes through
        untouched, a press outside every toast included; a detached
        controller's stack is empty, so it dismisses nothing.
        """
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
        """One expiry tick (pump callback): drop the due toasts, or stop.

        Reads ``tui.clock()`` -- the one seam time enters through -- and
        keeps the toasts whose expiry is still ahead.  A change invalidates
        the frame; a stack that emptied stands the ticker down, since a
        ticker with nothing to expire is exactly the waste the selection
        gesture's edge ticker stands down for too.
        """
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
        """Remove one toast (the dismiss path) and stop the ticker when last."""
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
        """The stack over the composed frame: each live toast's band spliced
        into its rectangle.

        Pure -- the frame's rows and the live toast list are the only inputs,
        and the very layout comes back when the stack is empty (the identity
        an empty overlay registry runs on).  A detached controller is never
        painted: :meth:`detach` unregisters it, and the registry is what
        calls this.
        """
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


class _MountedOverlay(Themed):
    """An overlay mounted for the frame's life: register once, detach once.

    ``layer`` is the frame layer the subclass owns (``tooltip`` for the
    pointer's hint band, ``overlay`` for the dev box).  Construction registers
    on the driver's frame; :meth:`detach` unregisters by identity and is
    idempotent -- a second call never touches the registry.
    """

    __slots__ = ("_detached", "_tui")

    def __init__(self, tui: TUI, *, layer: str, theme: Theme | None = None) -> None:
        super().__init__(theme)
        self._tui = tui
        self._detached = False
        # The driver's frame seam: the overlay registers here for the frame's
        # life -- a retile re-divides the tiling in place, so nothing carries
        # across.
        tui.frame.add_overlay(self, layer=layer)

    def set_theme(self, theme: Theme) -> None:
        """Repaint the overlay on ``theme`` (the App's re-skin road).

        The band is resolved at paint time, so this is the stored theme plus
        the repaint cue -- the registration rides untouched.
        """
        self._theme = theme
        self._tui.refresh()

    def detach(self) -> None:
        """Unregister the overlay (the ``EveryHandle`` convention).

        The symmetric of the constructor's registration; idempotent --
        :attr:`_detached` is the one identity that makes it so, so a second
        detach never claims an unregister the registry no longer owes.
        """
        if self._detached:
            return
        self._detached = True
        self._tui.frame.remove_overlay(self)


class Tooltip(_MountedOverlay):
    """A one-row hint band beside the pointer, driven by the leaf's ``hint``.

    ``tui`` is the driver whose frame the overlay registers on; ``pointer``
    the :class:`~motui.app.pointer.Pointer` whose tracked cell and hovered
    leaf the band reads.  ``theme`` is the style source: the band paints with
    the theme's :attr:`~motui.core.theme.OverlayStyles.toast`, the same
    band the toasts use, so ``Theme(overlays=...)`` restyles both at once.

    Constructing the controller registers the overlay on the frame, where it
    stays for the frame's life (the :class:`Toasts` shape: a retile rewrites
    the pane rectangles in place, and the driver's own selection overlay rides
    the same registry); ``detach()`` unregisters it by identity and is
    idempotent.

    **The paint is the whole controller.**  It reads live state -- the
    pointer's last button-free motion (``pointer.position``) and the leaf it
    hovers (``pointer.hovered``) -- plus that leaf's ``hint`` attribute
    (``getattr``; only a non-empty :class:`str` counts).  A pointer that never
    moved, a leaf without a hint, or a frame too narrow to host one column
    hands the layout back unchanged, which is the zero-byte case.  Otherwise
    the band is one row high and as wide as the hint, fit to the frame, and
    it paints **under** the pointer's cell -- flipping above it on the last
    row, clamped into the frame on both axes.  Nothing is cached and no event
    is consumed: a leaf that changes its ``hint``, or a pointer that moves to
    another leaf, shows on the next composition (the host's repaint cue is
    the pointer's own answer), and the tooltip has no ``handle`` because it
    owns no input.
    """

    __slots__ = ("_pointer",)

    def __init__(
        self,
        tui: TUI,
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
        """The hint band over the composed frame; the layout itself when idle.

        Pure: the frame's rows, its rectangle and the pointer's live state are
        the only inputs, and the very layout comes back when there is nothing
        to show.  A detached controller is never painted: :meth:`detach`
        unregisters it, and the registry is what calls this.
        """
        layout = frame.layout
        rect = frame.rect
        position = self._pointer.position
        hovered = self._pointer.hovered
        hint = getattr(hovered, "hint", None) if hovered is not None else None
        if rect is None or position is None or not isinstance(hint, str) or not hint:
            return layout  # no pointer, no hint: zero bytes
        row = Line.from_text(hint).fit(rect.width)
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
    """Where a one-row band of ``width`` sits for a pointer at ``pointer``.

    Pure arithmetic over the frame's rectangle: the band goes on the row
    **under** the pointer's cell when the frame has one, flips above it on the
    last row, and both coordinates are clamped into ``rect`` -- the geometry
    the paint splices through, so a tip can never paint outside the frame.  A
    one-row frame has neither room below nor above: the band lands on the
    pointer's own row, clamped.
    """
    x, y = pointer
    x = min(max(x, rect.x), max(rect.x, rect.right - width))
    if y + 1 < rect.bottom:
        return x, y + 1
    if y - 1 >= rect.y:
        return x, y - 1
    return x, min(max(y, rect.y), rect.bottom - 1)


class Stats(_MountedOverlay):
    """The dev overlay: frames, the frame rate, events, the last key, the hover.

    ``Stats(tui, *, pointer=None, theme=None)`` is the readout a developer
    mounts while building a session (D14) -- the demo toggles it with
    ``c-g``.  It paints a small band stack in the frame's **top-right
    corner**, three rows wide as their content:

    * ``frames``: :attr:`~motui.terminal.paint.Painter.frames`, every
      painted frame (read at composition time, so the frame being painted
      is not counted yet), beside the frame rate;
    * the **frame rate** over the overlay's own last window of at least a
      second -- :meth:`_sample` divides the frames since the window opened
      by the wall time since then (``tui.clock()``), because a rate off a
      10 ms window is noise.  No timer is armed: both readings are
      existing fields;
    * ``events``: how many events the host fed through :meth:`handle`, and
      the last one's name (``paste`` for a paste, which carries none);
    * ``hover``: the hovered leaf's class name and the pointer's last
      button-free motion, ``--`` while the pointer hovers nothing.

    Constructing the controller registers the overlay on the frame (where
    it stays for the frame's life, the :class:`Tooltip` rule); ``detach()``
    unregisters it and is idempotent -- the demo's ``c-g`` is one
    construction per mount and one detach per unmount.  ``pointer`` is the
    tier whose live state the box reads and it is a plain attribute on
    purpose: a host that rebuilds its pointer (the demo does, per page)
    points the overlay at the new one.  ``theme`` is the band's style
    source -- the box paints with the theme's
    :attr:`~motui.core.theme.OverlayStyles.toast`, the band toasts and the
    tooltip share, so one theme field restyles all three --
    and :meth:`set_theme` follows a re-skin.

    **The host feeds every event.**  :meth:`handle` counts one event and
    answers ``True`` as a **repaint cue** (the :class:`~motui.app.pointer.Pointer`
    reading): the overlay consumes nothing, so route it beside the other
    tiers -- never in a ``consumed`` chain -- and repaint when it answers.
    The paint itself is otherwise pure: the frame's rows, its rectangle and
    the controller's readings are the only inputs, and a frame with no room
    for the box hands the layout back unchanged (the zero-byte case).
    """

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
        tui: TUI,
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
        """The last counted event's name (``""`` before the first, ``paste``
        for a paste)."""
        return self._last

    @property
    def fps(self) -> float:
        """The frame rate of the last sampled window (``0.0`` until one is)."""
        return self._fps

    # -- the lifecycle -------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Repaint the box on ``theme`` (the :class:`Find` tier's re-skin road).

        Only the band is themed and it is resolved at paint time, so this is
        the stored theme, one line -- the registration rides untouched.
        """
        self._theme = theme

    # -- the event contract --------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Count ``event``; ``True`` is a repaint cue, not a dispatch claim.

        The host feeds every event of its round through here -- the box's
        counters are its own, the driver keeps none.  Every event counts,
        whatever its tier: a key, a paste, a mouse report, a resize or a
        focus report.  ``True`` always (the count moved), read the way the
        pointer's answer is read::

            if stats.handle(event):
                tui.refresh()
        """
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
        """Take a frame-rate reading when the window is at least a second wide.

        The overlay's own rule: frames since the window opened over the
        wall time since then.  The
        window only narrows on a reading, so the number a frame shows is the
        rate over a real second of painting.
        """
        now, frames = self._tui.clock(), self._tui.painter.frames
        elapsed = now - self._sample_at
        if elapsed < self.SAMPLE_WINDOW:
            return
        self._fps = (frames - self._sample_frames) / elapsed
        self._sample_frames, self._sample_at = frames, now

    def paint(self, frame: Frame) -> ScreenLayout:
        """The box in the frame's top-right corner; the layout when there is none.

        The band stack is as wide as its widest row and pinned to the
        frame's right edge (top-right: ``x = rect.right - width``), each row
        filled to that width with the theme's ``toast`` band -- the same
        band primitive the toasts and the tooltip paint with.  A frame too
        narrow for one column, or a rectangle outside the composed rows,
        hands the layout back unchanged.  A detached controller is never
        painted: :meth:`detach` unregisters it, and the registry is what
        calls this.
        """
        layout = frame.layout
        rect = frame.rect
        if rect is None or rect.width <= 0 or rect.height <= 0:
            return layout
        self._sample()  # the one write, and it only reads the clock and the counter
        rows = [Line.from_text(text).fit(rect.width) for text in self._lines()]
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
