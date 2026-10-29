"""The pointer tier: position, hover tracking and stationary clicks.

It observes the same reports the gesture owns: drags pass through
untouched, and only a release on the press's own cell counts as a click."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..kernel.document import Component, descend
from ..kernel.events import Event, MouseEvent
from ..kernel.geom import Pos
from ..kernel.hit import Hit
from .focus import FocusManager

if TYPE_CHECKING:
    from .runtime import Runtime

__all__ = ["Pointer"]

#: The names a motion report carries while a button is held: SGR's motion bit
#: with the button's own low bits, which is every motion mode 1002 sends --
#: and therefore what makes a motion a drag rather than a hover.
_DRAG_NAMES = ("left", "middle", "right")


class Pointer:
    """The pointer tier: what the pointer hovers and what a click lands on.

    Hover needs DECSET 1003. ``handle`` never blocks the gesture and answers
    a repaint cue only; without a ring a click dispatches the deepest
    clickable leaf itself."""

    __slots__ = ("_detached", "_hover", "_hovered", "_position", "_press", "_ring", "_tui")

    def __init__(
        self,
        tui: Runtime,
        *,
        ring: FocusManager | None = None,
        hover: bool = True,
    ) -> None:
        self._tui = tui
        self._ring = ring
        self._hover = hover
        self._detached = False
        self._hovered: Component | None = None
        self._position: tuple[int, int] | None = None
        self._press: tuple[int, int] | None = None

    # -- the pointer's state -----------------------------------------------------

    @property
    def hovered(self) -> Component | None:
        """The leaf under the pointer -- the deepest component of the last hit, or
        ``None`` before the first motion."""
        return self._hovered

    @property
    def position(self) -> tuple[int, int] | None:
        """The last button-free motion's 0-based ``(x, y)``, or ``None``; a drag's
        motion does not move it."""
        return self._position

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Watch ``event``; a button-free motion updates hover, a drag is ignored,
        and a stationary left release dispatches a click."""
        if self._detached or not isinstance(event, MouseEvent):
            return False
        kind = event.kind
        if kind == "motion":
            if event.button in _DRAG_NAMES:
                self._press = None  # a drag: the pending click is gone
                return False
            self._position = (event.x, event.y)
            if not self._hover:
                return False
            return self._update_hover(event.x, event.y)
        if kind == "press":
            if event.button == "left":
                self._press = (event.x, event.y)
            return False
        if kind == "release":
            press, self._press = self._press, None
            if event.button != "left" or press != (event.x, event.y):
                return False
            return self._dispatch_click(event.x, event.y)
        return False

    def clear(self) -> None:
        """Drop the hover and the pending click -- a pane switch or a resize."""
        self._set_hovered(None, -1, -1)
        self._press = None
        self._position = None

    def detach(self) -> None:
        """Unmount cleanly: drop every state and go inert; idempotent."""
        self._detached = True
        self.clear()

    # -- the internals ------------------------------------------------------------

    def _update_hover(self, x: int, y: int) -> bool:
        """Resolve the cell and move the hover; answer whether it changed."""
        target: Component | None = None
        row = col = -1
        hit = self._tui.hit(x, y)
        if hit is not None:
            target, row, col = descend(hit.block.widget, hit.row, hit.col)
        return self._set_hovered(target, row, col)

    def _set_hovered(self, target: Component | None, row: int, col: int) -> bool:
        """Point the hover at ``target``'s cell and tell hoverable components;
        answers whether what a component paints changes."""
        old = self._hovered
        if target is old:
            if target is None:
                return False
            if not bool(getattr(target, "hoverable", False)):
                return False
            on_hover = getattr(target, "on_hover", None)
            return bool(on_hover(Pos(x=col, y=row))) if on_hover is not None else False
        changed = False
        if old is not None:
            if hasattr(old, "hover") and old.hover:
                old.hover = False
                changed = True
            on_hover = getattr(old, "on_hover", None)
            if (
                bool(getattr(old, "hoverable", False))
                and on_hover is not None
                and on_hover(None)
            ):
                changed = True
        self._hovered = target
        if target is not None:
            if hasattr(target, "hover") and not target.hover:
                target.hover = True
                changed = True
            on_hover = getattr(target, "on_hover", None)
            if (
                bool(getattr(target, "hoverable", False))
                and on_hover is not None
                and on_hover(Pos(x=col, y=row))
            ):
                changed = True
        return changed

    def _dispatch_click(self, x: int, y: int) -> bool:
        """Resolve a stationary click's cell and dispatch it; consumed?"""
        hit: Hit | None = self._tui.hit(x, y)
        if hit is None:
            return False
        if self._ring is not None:
            return self._ring.click(hit)
        component, row, col = descend(hit.block.widget, hit.row, hit.col)
        if not bool(getattr(component, "clickable", False)):
            return False
        on_click = getattr(component, "on_click", None)
        return bool(on_click(Pos(x=col, y=row))) if on_click is not None else False

    def __repr__(self) -> str:
        return (
            f"Pointer(hovered={self._hovered!r}, position={self._position!r}, "
            f"detached={self._detached})"
        )
