"""The event router: the default handler chain :class:`App` dispatches.

A handler answers "did I consume this event?"; the App walks the chain,
first claim wins. The mouse tier is one handler so gesture, pointer and
pane focus all see the same report."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..kernel.events import Event, KeyEvent, MouseEvent
from ..kernel.geom import Pos
from ..kernel.hit import Hit
from ..kernel.layout import Scrollable, ScrollableX
from ..widgets.base import Widget

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
    return bool(app._palette is not None and app._palette.is_open and app._palette.handle(event))


def modal(app: App, event: Event) -> bool:
    """The newest open modal consumes every event while it is up."""
    for layer in reversed(app._modals):
        if layer.is_open:
            layer.handle(event)
            return True
    return False


def find(app: App, event: Event) -> bool:
    """The open find bar owns the keys it consumes."""
    return bool(app._find is not None and app._find.is_open and app._find.handle(event))


def toast(app: App, event: Event) -> bool:
    """The toast stack consumes dismissal presses and asks for a repaint."""
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
    if (
        app._drag_target is not None
        and event.kind in ("motion", "release")
        and _drag_event(app, event)
    ):
        return True
    return bool(event.kind == "press" and _drag_press(app, event))


def mouse(app: App, event: Event) -> bool:
    """The mouse tier: gesture, pointer and the pane-focus rule, all three; the
    answer is their OR and the repaint happens once."""
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
    """Route one wheel notch: a horizontal scroller, else a vertical one,
    walking the hit chain deepest first."""
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
    """Move the nearest ``ScrollableX`` one column; a boundary notch lets the
    walk continue outward."""
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
    """Start a drag on the nearest widget overriding ``Widget.on_drag``; only
    the left button starts one."""
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
    """Feed one motion/release to the drag's target; a release is always
    consumed so it never becomes a selection press."""
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
    """Scroll on a page key: the focused ``Scrollable``, else the focused pane."""
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
