"""The event router: the default handler chain :class:`App` dispatches.

A handler answers one question -- *did I consume this event?* -- and the App
walks :attr:`App.handlers` in order, first claim wins.  The order below is
the documented one, unchanged from the 1.x ``dispatch`` if-chain:

1. the open command palette;
2. the open modal layers, newest first;
3. the open find bar;
4. the toast stack;
5. the mounted controllers, in mount order;
6. the wheel (a selection drag mid-flight claims it first);
7. the drag in flight, or the press that starts one;
8. the mouse tier: the selection gesture, the pointer and the pane-focus
   rule -- in that order, and all three see the report;
9. the focus ring;
10. the page keys (the focused ``Scrollable``, else the focused pane);
11. the key bindings, then ``tab``/``s-tab`` cycling;
12. the host hooks ``on_key``/``on_mouse``/``on_event``.

The mouse tier is **one** handler on purpose: the gesture consumes a press,
but the pointer still has to watch the same report (its click policy pairs
the press with the release) and the pane-focus rule still moves focus --
exactly as the reference wiring calls all three beside each other.  A
per-tier early return would hide the report from the later two.

Handlers own their repaint cue: one that moves state calls ``app.invalidate()``
before answering ``True``, and one that answers ``False`` leaves the frame
alone.  A :class:`~motui.kernel.events.ResizeEvent` is broadcast by
``App.dispatch`` itself before the chain runs -- it informs, it never
consumes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..kernel.events import Event, KeyEvent, MouseEvent
from ..kernel.geom import Pos
from ..kernel.hit import Hit
from ..kernel.layout import Scrollable, ScrollableX
from ..widgets.base import Widget
from .focus import iter_widgets

if TYPE_CHECKING:
    from .application import App

__all__ = ["DEFAULT_HANDLERS", "Handler"]

#: One tier: ``handler(app, event) -> consumed``.
Handler = Callable[["App", Event], bool]

#: The default scroll table: event name (a key's ``key`` or a wheel report's
#: ``button``) to signed row count, negative scrolling up.
SCROLL_KEYS = {
    "page_up": -1,
    "page_down": 1,
    "wheel_up": -3,
    "wheel_down": 3,
}

#: The report names that count as a button press for pane focus.
_BUTTONS = ("left", "middle", "right")


def palette(app: App, event: Event) -> bool:
    """The open command palette owns the keyboard until it closes."""
    if app._palette is not None and app._palette.is_open:
        if app._palette.handle(event):
            return True
    return False


def modal(app: App, event: Event) -> bool:
    """The newest open modal consumes every event while it is up."""
    for layer in reversed(app._modals):
        if layer.is_open:
            layer.handle(event)
            return True
    return False


def find(app: App, event: Event) -> bool:
    """The open find bar owns the keys it consumes."""
    if app._find is not None and app._find.is_open:
        if app._find.handle(event):
            return True
    return False


def toast(app: App, event: Event) -> bool:
    """The toast stack consumes dismissal keys and asks for a repaint."""
    if app._toasts is not None and app._toasts.handle(event):
        app.invalidate()
        return True
    return False


def controllers(app: App, event: Event) -> bool:
    """The mounted dispatching controllers, in mount order."""
    for controller, dispatch in tuple(app._controllers):
        if dispatch and controller.handle(event):
            app.invalidate()
            return True
    return False


def wheel(app: App, event: Event) -> bool:
    """Route one wheel notch: a selection drag first, then the scroll target."""
    if not (isinstance(event, MouseEvent) and event.kind == "wheel"):
        return False
    # A wheel during a selection drag belongs to the gesture first
    # (it co-extends the head); otherwise the wheel tier routes it.
    if app._gesture is not None and app._gesture.handle(event):
        app.invalidate()
        return True
    return _wheel(app, event)


def drag(app: App, event: Event) -> bool:
    """Feed an in-flight drag, or start one on a press."""
    if not isinstance(event, MouseEvent):
        return False
    # A drag goes first: a press on a bar must never anchor the
    # selection gesture under it (the pane Scrollbar's own rule,
    # now for widgets inside the content).
    if app._drag_target is not None and event.kind in ("motion", "release"):
        if _drag_event(app, event):
            return True
    if event.kind == "press" and _drag_press(app, event):
        return True
    return False


def mouse(app: App, event: Event) -> bool:
    """The mouse tier: gesture, pointer and the pane-focus rule, all three.

    They run even when an earlier one consumed -- the pointer watches the
    press the gesture owns, and the press still focuses its pane -- so the
    answer is the OR of the three and the repaint happens once.
    """
    if not isinstance(event, MouseEvent):
        return False
    gesture = bool(app._gesture is not None and app._gesture.handle(event))
    pointer = bool(app._pointer is not None and app._pointer.handle(event))
    focused = _press_focuses_a_pane(app, event)
    if gesture or pointer or focused:
        app.invalidate()
        return True
    return False


def focus(app: App, event: Event) -> bool:
    """The focused control through the focus ring."""
    if app._focus is not None and app._focus.handle(event):
        app.invalidate()
        return True
    return False


def page_keys(app: App, event: Event) -> bool:
    """Scroll on a page key: the focused ``Scrollable``, else the pane."""
    if not isinstance(event, KeyEvent):
        return False
    return _scroll_key(app, event)


def bindings(app: App, event: Event) -> bool:
    """The host's key bindings, then ``tab``/``s-tab`` focus cycling."""
    if not isinstance(event, KeyEvent):
        return False
    if event.key in app._bindings:
        app._bindings[event.key]()
        app.invalidate()
        return True
    if event.key == "tab":
        return app.focus_next()
    if event.key in ("s-tab", "backtab"):
        return app.focus_previous()
    return False


def host(app: App, event: Event) -> bool:
    """The App's own hooks: ``on_key``, ``on_mouse``, then ``on_event``."""
    if isinstance(event, KeyEvent) and app.on_key(event):
        return True
    if isinstance(event, MouseEvent) and app.on_mouse(event):
        return True
    return app.on_event(event)


#: The default chain, in dispatch order (see the module docstring).
DEFAULT_HANDLERS: tuple[Handler, ...] = (
    palette,
    modal,
    find,
    toast,
    controllers,
    wheel,
    drag,
    mouse,
    focus,
    page_keys,
    bindings,
    host,
)


# -- the tier implementations -------------------------------------------------


def _wheel(app: App, event: MouseEvent) -> bool:
    """Route one wheel notch: a horizontal scroller, else a vertical one.

    ``wheel_left``/``wheel_right`` walk ``hit.chain`` deepest first for
    the structural :class:`~motui.kernel.layout.ScrollableX` face and
    move its window one column.  ``wheel_up``/``wheel_down`` keep the
    1.x route: the nearest :class:`~motui.kernel.layout.Scrollable`,
    else the hit pane, else the focused pane.
    """
    if event.button in ("wheel_left", "wheel_right"):
        return _wheel_x(app, event)
    rows = SCROLL_KEYS.get(event.button)
    if not rows:
        return False
    hit: Hit | None = app.workspace.hit(event.x, event.y)
    target: object | None = None
    if hit is not None:
        for component, _row, _col in reversed(hit.chain):
            if isinstance(component, Scrollable):
                target = component
                break
    if target is None:
        pane = None if hit is None else hit.pane
        if pane is None or app.workspace.frame.is_dock(pane):
            pane = app.workspace.frame.focused_pane
        target = pane
    if not isinstance(target, Scrollable):
        return False
    target.scroll_by(rows)
    app.invalidate()
    return True


def _wheel_x(app: App, event: MouseEvent) -> bool:
    """Move the nearest ``ScrollableX`` one column; ``True`` when taken.

    The hit chain is walked deepest first, exactly like the vertical
    branch, so a nested horizontal panel wins over an outer one.  A
    target only consumes the notch when its offset moved: an ``"x"``
    view at its last column (or a y-only view, whose structural method
    declines) lets the walk continue outward.  The frame is refreshed
    on the move.
    """
    hit: Hit | None = app.workspace.hit(event.x, event.y)
    if hit is None:
        return False
    delta = -1 if event.button == "wheel_left" else 1
    for component, _row, _col in reversed(hit.chain):
        if isinstance(component, ScrollableX) and component.scroll_x_by(delta):
            app.invalidate()
            return True
    return False


def _drag_press(app: App, event: MouseEvent) -> bool:
    """Start a drag on the nearest widget overriding ``Widget.on_drag``.

    Walks ``hit.chain`` backwards -- the deepest widget first -- and
    hands the press to the first one whose ``on_drag`` is not the
    :class:`~motui.widgets.base.Widget` no-op.  That widget answers
    ``True`` only when the press landed on something it owns (the
    ScrollPanel's bar column); otherwise the walk goes on and the press
    falls through to the gesture and pointer tiers.  Only the left
    button starts a drag.
    """
    if event.button != "left":
        return False
    hit: Hit | None = app.workspace.hit(event.x, event.y)
    if hit is None:
        return False
    for component, row, col in reversed(hit.chain):
        if not isinstance(component, Widget):
            continue
        if type(component).on_drag is Widget.on_drag:
            continue
        if component.on_drag(Pos(x=col, y=row), "press"):
            app._drag_target = component
            app._drag_row = row
            app._drag_col = col
            app.invalidate()
            return True
    return False


def _drag_event(app: App, event: MouseEvent) -> bool:
    """Feed one motion/release to the drag's target; ``True`` when taken.

    The target is looked up in the fresh hit chain so the cell arrives
    in its own coordinates; when the pointer left it the last cell is
    used, and a lost target or a release ends the drag.  A release is
    always consumed -- the drag it ends must not become a selection
    press on whatever is under the pointer now.
    """
    target = app._drag_target
    if target is None:
        return False
    row, col = app._drag_row, app._drag_col
    held = False
    hit: Hit | None = app.workspace.hit(event.x, event.y)
    if hit is not None:
        for component, found_row, found_col in hit.chain:
            if component is target:
                row, col, held = found_row, found_col, True
                app._drag_row, app._drag_col = row, col
                break
    consumed = bool(target.on_drag(Pos(x=col, y=row), event.kind))
    if event.kind == "release" or not held:
        app._drag_target = None
    if consumed or event.kind == "release":
        app.invalidate()
    return consumed or event.kind == "release"


def _scroll_key(app: App, event: KeyEvent) -> bool:
    """Scroll on a page key: the focused ``Scrollable``, else the pane."""
    rows = SCROLL_KEYS.get(event.key)
    if not rows:
        return False
    target: object | None = None
    focused = None if app._focus is None else app._focus.focused
    if isinstance(focused, Scrollable):
        target = focused
    if target is None:
        pane = app.workspace.frame.focused_pane
        target = pane if isinstance(pane, Scrollable) else None
    if not isinstance(target, Scrollable):
        return False
    target.scroll_by(rows)
    app.invalidate()
    return True


def _press_focuses_a_pane(app: App, event: MouseEvent) -> bool:
    """A button press focuses the pane under it (never a dock)."""
    if event.kind != "press" or event.button not in _BUTTONS:
        return False
    pane = app.workspace.pane_at(event.x, event.y)
    if pane is None or app.workspace.frame.is_dock(pane):
        return False
    focused = app.workspace.frame.focused_pane
    if focused is not None and focused.id == pane.id:
        return False
    app.workspace.frame.focus(pane)
    app.invalidate()
    return True
