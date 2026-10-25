"""pointer: the pointer tier -- position, hover tracking, stationary clicks.

This module is the assembly tier (D3) -- the peer of
:mod:`motui.app.gesture`, :mod:`motui.app.focus` and the driver:
it imports kernel and app, and it is where every pointer *behavior* lands.  The
kernel stays pure (the ``child_at`` coordinate route, the
:func:`~motui.kernel.document.descend` walk and the DECSET 1003 bytes), the
focus tier keeps its click policy (:class:`~motui.app.focus.FocusManager`), and
the driver exposes the minimal imperative surface the pointer reads:
:meth:`~motui.app.Runtime.hit`, which resolves a report's 0-based cell
through the frame's ownership table.

:class:`Pointer` turns mouse reports into hover state and click dispatch.  It
is the *observe* half of the mouse pair the host routes: the selection gesture
owns press/motion/release for drags, the pointer watches the same reports --
flipping the ``hover`` flag of the leaf under the pointer, moving row-level
hover where a component implements ``on_hover``, and completing a stationary
click through the mounted :class:`~motui.app.focus.FocusManager` (or dispatching
the deepest clickable leaf itself when there is none).  A host mounts it
explicitly, the same rule the gesture and the ring follow, and opens 1003 with
``Runtime(hover=True)`` -- a pointer without 1003 never sees a motion report::

    gesture = SelectionGesture(tui)      # the drag selection
    pointer = Pointer(tui, ring=ring)    # the hover and the click
    event = await tui.read_event()
    gesture.handle(event)                # the gesture owns press/release
    if pointer.handle(event):            # the pointer watches beside it
        tui.refresh()                 # a repaint cue, not a dispatch claim
"""

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
    """The pointer tier: what the pointer hovers, and what a click lands on.

    ``tui`` is the driver whose hit test the pointer resolves every report
    through.  ``ring`` mounts the focus tier's click policy: a stationary
    click is handed to :meth:`FocusManager.click <motui.app.focus.FocusManager.click>`,
    which descends to the leaf, dispatches, focuses and activates; without a
    ring the pointer descends the hit itself and dispatches the deepest
    ``clickable`` leaf directly (a mouse-only
    page needs no ring).  ``hover=False`` builds a click-only pointer: it
    never touches a ``hover`` flag, for a host that keeps its screen in the
    smaller 1002 mode.

    **Three contracts hold the tier together.**

    *Hover needs the terminal's any-event tracking.*  The host must open
    DECSET 1003 (``Runtime(hover=True)`` / ``TerminalScreen(hover=True)`` /
    ``HeadlessScreen(hover=True)``): under the default 1002 the terminal
    reports motion only while a button is held, and a pointer that only
    moves is never heard -- the pointer cannot ask for the mode itself.

    *``handle`` never blocks the gesture.*  A press is only remembered
    (``False``); a motion that is a *drag* -- one whose ``button`` is a
    button name (``left``/``middle``/``right``, what mode 1002 sends while
    a button is held) and not ``none`` -- drops the remembered press and
    touches no hover (``False``); only the release of a press landed on its
    own cell -- a **stationary click** -- answers what the clicked component
    answered.  Route the same event through the gesture and the pointer (the
    reference wiring calls the pointer unconditionally beside the gesture --
    the dispatch order is in ``docs/COMPONENTS.md``): drag
    selection sees every report it owns, and the pointer never eats a press
    or a drag release out from under it.

    *The host owns the repaint.*  ``handle`` answers whether what it tracks
    changed -- the hovered leaf entered, left or moved rows, or a click was
    consumed -- and never calls :meth:`~motui.app.Runtime.invalidate`
    itself, the same consume-one-event cue the gesture and the chrome return
    (``if pointer.handle(event): tui.refresh()``).  A motion that changes
    nothing answers ``False``: no change, no bytes.
    """

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
        """The leaf under the pointer -- deepest component of the last hit.

        The component itself, hoverable or not: the pointer tracks the
        *position's* target so a later motion can tell "still the same
        component" from "a new one".  ``None`` while the pointer is over a
        cell no block owns, or before the first motion.
        """
        return self._hovered

    @property
    def position(self) -> tuple[int, int] | None:
        """The last button-free motion's 0-based ``(x, y)``, or ``None``.

        A drag's motion does not move it: under 1002 the only reports a
        hover host sees are press/motion/release, and ``position`` names
        the cell the hover state was resolved at.
        """
        return self._position

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Watch ``event``; answer whether what the pointer tracks changed.

        Only a :class:`~motui.kernel.events.MouseEvent` is ever watched:
        every other event answers ``False`` (the ring's
        :meth:`~motui.app.focus.FocusManager.handle` is the keyboard door).
        The report rules, in the class docstring's order:

        * a button-free motion (``button == "none"``) records the position
          and updates the hover, answering whether the frame would repaint
          (the hovered component entered, left, or moved to another row of
          itself);
        * a motion that names a button -- what mode 1002 sends while one is
          held -- is a drag: the pending click is dropped, no hover is
          touched, and the position stays where the last hover left it
          (``False``);
        * a left press is only remembered (``False``);
        * a left release on the remembered press's cell is a stationary
          click: the cell is hit-tested and dispatched -- through the
          mounted ring's policy, or to the deepest clickable leaf -- and the
          answer is whether a component consumed it;
        * every other report -- a release that ended a drag, a right or
          middle button, a wheel -- answers ``False``.

        A release always ends the pending press, dispatched or not, so a
        click cannot complete twice and cannot rise out of a drag's remains.
        """
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
        """Drop the hover and the pending click -- a pane switch or a resize.

        The pane the pointer was over may have left the frame (a close) or
        been re-laid out under it (a resize, a reflow), so the recorded cell
        no longer means what it did: the hovered component takes
        ``hover = False`` and ``on_hover(None)``, and the position and the
        pending press go with them.  Best-effort by design: the
        pointer is not handed window events itself -- the host calls this
        where it notices one.
        """
        self._set_hovered(None, -1, -1)
        self._press = None
        self._position = None

    def detach(self) -> None:
        """Unmount cleanly (the timer-handle convention): drop every state.

        :meth:`clear`'s drop, plus the pointer goes inert: a detached
        pointer answers ``False`` to every event, so a release arriving
        after unmounting can never dispatch a click.  Idempotent.
        """
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
        """Point the hover at ``target``'s cell; answer whether render changes.

        The same component again: a ``hoverable`` component is told the new
        cell through ``on_hover(pos)`` (the pointer may have crossed rows of
        one list) and its answer is the change; one without the flag is told
        nothing and nothing changed.  A different component: the old one --
        if any -- takes ``hover = False`` and, when hoverable,
        ``on_hover(None)``; the new one takes ``hover = True`` (any component
        carrying the flag, so a non-painting container still reports the
        pointer cue) and, when hoverable, ``on_hover(pos)``.  The answer says
        whether any of that changes what a component paints.
        """
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
