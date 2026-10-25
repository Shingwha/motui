"""App: the default orchestration over the low-level :class:`TUI` driver.

:class:`TUI` reads events and owns the document, the frame and the pump; it
deliberately runs no interaction policy.  :class:`App` is that policy
assembled from the controllers this package ships -- :class:`FocusManager`,
:class:`Pointer`, :class:`SelectionGesture`, :class:`Toasts`,
:class:`Tooltip`, :class:`Find`, :class:`Modal` and
:class:`CommandPalette` -- and dispatched in one documented order.  A host
that wants a different order, or no default policy at all, passes
``auto=False`` and drives the ``tui`` itself (the ``TUI`` API is unchanged
and still public).

**The dispatch order** (:meth:`App.dispatch`, first claim wins):

1. the open :class:`~motui.app.command_palette.CommandPalette`;
2. the open :class:`~motui.app.modal.Modal` layers, newest first;
3. the open :class:`~motui.app.find.Find`;
4. :class:`~motui.app.overlays.Toasts`;
5. the controllers added with :meth:`App.mount`, in mount order, when the
   mount is dispatching (the demo's pane ``Scrollbar``);
6. the wheel: the nearest :class:`~motui.core.scroll.Scrollable` in
   ``hit.chain``, otherwise the hit pane, otherwise the focused pane's
   viewport (a :class:`~motui.app.gesture.SelectionGesture` mid-drag claims
   its own wheel first, so its head co-extends);
7. the mouse: a drag in flight (or a press that starts one), then the
   selection gesture, the pointer tier, then a press focuses the pane
   under it;
8. the focused control through :class:`FocusManager`;
9. the page keys: the focused :class:`~motui.core.scroll.Scrollable`, else
   the focused pane's viewport;
10. the keys bound with :meth:`App.bind`, then ``tab``/``s-tab`` cycling;
11. the host hooks ``on_key``/``on_mouse``/``on_event``.

The controller tiers are the existing ones, not re-implementations: the
App only composes them and owns the order.  ``auto=False`` mounts none of
them (``focus``/``toast``/``open_modal`` then report the missing layer).

**Theme propagation.**  :attr:`App.theme` is the application theme:
constructing the App gives it to the driver, and :meth:`App.add` assigns it
to every :class:`~motui.core.widget.Widget` in the mounted subtree whose
``theme`` is still ``None`` (an explicit ``theme=`` stays a local
override).  Re-assigning :attr:`App.theme` walks the mounted components
again and also calls ``set_theme(value)`` on the app-owned overlays
(toasts, tooltip, palette, find) and on every controller added with
:meth:`App.mount`; the walk is best-effort over
``child``/``children``/``body``/``input``/``list``/``_fields``, which
covers the container shapes the library ships.

**Mounted controllers.**  :meth:`App.mount` adds a host controller (a pane
``Scrollbar``, a dev overlay) to the App's controller tier.  A dispatching
mount is called in the documented order and consumes the event when its
``handle`` answers ``True``; ``dispatch=False`` mounts a controller the App
only themes and keeps (the host feeds it itself -- the demo's counting
``Stats``).  :meth:`App.unmount` removes it without detaching: the
controller's lifecycle stays the host's.

**Focus.**  A widget that overrides one of the interaction verbs
(``handle``/``activate``/``select``/``move``/``toggle``) over the
:class:`~motui.core.widget.Widget` defaults is registered in the ring when
it is added; nested widgets are found through the same recursive walk.
:meth:`App.set_focus_targets` replaces the ring (the demo's per-topic
pattern), :meth:`App.focus` addresses one by block id or component.
"""

from __future__ import annotations

import asyncio
import builtins
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any

from ..core.block import Component
from ..core.events import Event, KeyEvent, MouseEvent
from ..core.hit import Hit
from ..core.scroll import Scrollable
from ..terminal.screen import Screen
from ..core.selection import Selection
from ..core.style import ColorMode, Style
from ..core.theme import DEFAULT_THEME, Theme
from ..core.widget import Widget
from .command_palette import CommandPalette
from .driver import TUI
from .find import Find
from .focus import FocusManager
from .gesture import SelectionGesture
from .modal import Modal
from .overlays import Toasts, Tooltip
from .pointer import Pointer

if TYPE_CHECKING:
    from ..core.events import EventSource

__all__ = ["App"]

#: The default scroll table: event name (a key's ``key`` or a wheel report's
#: ``button``) to signed row count, negative scrolling up.
SCROLL_KEYS = {
    "page_up": -1,
    "page_down": 1,
    "wheel_up": -3,
    "wheel_down": 3,
}

#: The attributes the theme/focus walk recurses through: every container
#: shape the library ships (``Row``/``Column``/``Panel``/``Form``/...).
_CHILD_ATTRS = ("child", "children", "body", "input", "list", "_fields")

#: The verbs a widget overrides to count as interactive (the ``Widget``
#: defaults are no-ops).
_INTERACTION_VERBS = ("handle", "activate", "select", "move", "toggle")

#: The report names that count as a button press for pane focus.
_BUTTONS = ("left", "middle", "right")


def _walk(component: Component) -> "list[Component]":
    """Every component in ``component``'s subtree, each object once.

    Best-effort over :data:`_CHILD_ATTRS`: an attribute that is a component
    is visited, a list/tuple of components is visited item by item, and
    anything else is ignored.  Identity dedupe keeps a shared child from
    being themed or registered twice.
    """
    seen: set[int] = set()
    found: list[Component] = []
    stack: list[Component] = [component]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        found.append(current)
        for name in _CHILD_ATTRS:
            child = getattr(current, name, None)
            if child is None:
                continue
            if name == "_fields" and isinstance(child, (list, tuple)):
                # A form's fields are values; the component each one wraps
                # is the actual child.
                for field in child:
                    component = getattr(field, "component", None)
                    if isinstance(component, Component):
                        stack.append(component)
                continue
            if isinstance(child, Component):
                stack.append(child)
            elif isinstance(child, (list, tuple)):
                stack.extend(item for item in child if isinstance(item, Component))
    return found


def _looks_interactive(component: Component) -> bool:
    """Whether ``component`` overrides one of the interaction verbs.

    ``Widget`` answers every verb as a no-op, so an override is the
    library's own signal that the component consumes input; a plain
    renderer (no ``Widget`` at all) is never registered.
    """
    if not isinstance(component, Widget):
        return False
    for name in _INTERACTION_VERBS:
        override = getattr(type(component), name, None)
        if override is not None and override is not getattr(Widget, name, None):
            return True
    return False


class App:
    """The high-level application: driver + the default interaction policy.

    ``theme`` is the application theme (``DEFAULT_THEME`` when omitted) --
    handed to the driver's chrome and assigned to mounted widgets that did
    not take an explicit one.  ``mouse``/``hover``/``color_mode`` are
    forwarded to the default screen (``screen=`` overrides it).
    ``title`` is set through the driver's OSC 2 surface when non-empty.
    ``auto=True`` mounts the default controllers; ``auto=False`` mounts
    none, leaving ``app.tui`` and the caller's own loop (the ``TUI`` is
    still fully usable).  ``keys=`` is the event source, ``throttle`` the
    pump's flush interval.  ``interactive``/``focus_events``/``sync`` are
    the driver's own switches, forwarded verbatim.  ``on_selection``
    replaces the selection gesture's ``on_end`` (the default is
    :func:`~motui.app.gesture.copy_on_select`).
    """

    def __init__(
        self,
        *,
        theme: Theme | None = None,
        mouse: bool = True,
        hover: bool = True,
        color_mode: ColorMode | None = None,
        title: str = "",
        auto: bool = True,
        screen: Screen | None = None,
        keys: "EventSource | None" = None,
        throttle: float = 0.030,
        interactive: bool | None = None,
        focus_events: bool = False,
        sync: bool = True,
        on_selection: Callable[["TUI", Selection], object] | None = None,
    ) -> None:
        self._theme = DEFAULT_THEME if theme is None else theme
        self.tui = TUI(
            screen=screen,
            keys=keys,
            throttle=throttle,
            mouse=mouse,
            hover=hover,
            color_mode=color_mode,
            theme=self._theme,
            interactive=interactive,
            focus_events=focus_events,
            sync=sync,
        )
        self.auto = auto
        self._components: list[Component] = []
        self._bindings: dict[str, Callable[[], object]] = {}
        self._modals: list[Modal] = []
        self._controllers: list[tuple[object, bool]] = []
        self._palette: CommandPalette | None = None
        self._find: Find | None = None
        self._focus: FocusManager | None = None
        self._pointer: Pointer | None = None
        self._gesture: SelectionGesture | None = None
        # The drag route's state: the widget that took the press (a
        # ScrollView bar), and the cell it was last addressed at.
        self._drag_target: Component | None = None
        self._drag_row = 0
        self._drag_col = 0
        self._toasts: Toasts | None = None
        self._tooltip: Tooltip | None = None
        if auto:
            self._focus = FocusManager()
            self._pointer = Pointer(self.tui, ring=self._focus)
            gesture_args = {} if on_selection is None else {"on_end": on_selection}
            self._gesture = SelectionGesture(self.tui, **gesture_args)
            self._toasts = Toasts(self.tui, theme=self._theme)
            self._tooltip = Tooltip(self.tui, self._pointer, theme=self._theme)
        if title:
            self.tui.set_title(title)

    # -- theme ------------------------------------------------------------------

    @property
    def theme(self) -> Theme:
        """The application theme (see the class docstring)."""
        return self._theme

    @theme.setter
    def theme(self, value: Theme) -> None:
        self._theme = value
        self.tui.theme = value
        for component in tuple(self._components):
            for current in _walk(component):
                if isinstance(current, Widget) and current.theme is None:
                    current.theme = value
        for overlay in (self._toasts, self._tooltip, self._palette, self._find):
            self._set_theme(overlay, value)
        for controller, _dispatch in tuple(self._controllers):
            self._set_theme(controller, value)
        self.tui.refresh()

    @staticmethod
    def _set_theme(target: object | None, theme: Theme) -> None:
        """Call ``target.set_theme(theme)`` when the target offers it."""
        if target is None:
            return
        setter = getattr(target, "set_theme", None)
        if setter is not None:
            setter(theme)

    # -- the mounted controllers (advanced hosts) ---------------------------

    @property
    def focus_manager(self) -> FocusManager | None:
        """The mounted focus ring, or ``None`` with ``auto=False``."""
        return self._focus

    @property
    def pointer(self) -> Pointer | None:
        """The mounted pointer tier, or ``None`` with ``auto=False``."""
        return self._pointer

    @property
    def gesture(self) -> SelectionGesture | None:
        """The mounted selection gesture, or ``None`` with ``auto=False``."""
        return self._gesture

    @property
    def toasts(self) -> Toasts | None:
        """The mounted toast stack, or ``None`` with ``auto=False``."""
        return self._toasts

    @property
    def tooltip(self) -> Tooltip | None:
        """The mounted tooltip, or ``None`` with ``auto=False``."""
        return self._tooltip

    @property
    def palette(self) -> CommandPalette | None:
        """The command palette, or ``None`` until :meth:`open_palette` first runs."""
        return self._palette

    @property
    def find_bar(self) -> Find | None:
        """The find tier, or ``None`` until :meth:`find` first runs."""
        return self._find

    @property
    def controllers(self) -> tuple[object, ...]:
        """The controllers added with :meth:`mount`, in mount order."""
        return tuple(controller for controller, _dispatch in self._controllers)

    def mount(self, controller: object, *, dispatch: bool = True) -> None:
        """Register ``controller`` in the App's controller tier.

        A dispatching controller (the default) sees every event after the
        toasts and before the wheel/mouse tiers; ``handle(event)`` returning
        ``True`` consumes it.  ``dispatch=False`` mounts a controller the
        App only themes and keeps: the host feeds it itself (a counting
        overlay whose ``True`` is a repaint cue, not a claim).  Mounting the
        same object twice keeps one entry.  The controller's own lifecycle
        (attaching, detaching) stays the host's -- :meth:`unmount` only
        removes the registration.
        """
        for index, (known, _dispatch) in enumerate(self._controllers):
            if known is controller:
                self._controllers[index] = (known, dispatch)
                return
        self._controllers.append((controller, dispatch))

    def unmount(self, controller: object) -> bool:
        """Remove ``controller`` from the controller tier; ``True`` when held.

        Only the registration is dropped: the controller is not detached
        and keeps whatever it registered on the frame (the host decides the
        lifecycle, the :meth:`mount` contract).
        """
        for index, (known, _dispatch) in enumerate(self._controllers):
            if known is controller:
                del self._controllers[index]
                return True
        return False

    # -- document facade ----------------------------------------------------

    def add(
        self,
        component: Component,
        *,
        id: str | None = None,
        pin: str | None = None,
        pane: Any = None,
    ) -> str:
        """Mount ``component``; answer its block id.

        The component's subtree takes the App theme where no explicit one
        is set, and its interactive widgets join the focus ring (when the
        default controllers are mounted).  With no ``pane=`` the block lands
        in the main (primary) document, never the focused pane.  The id is
        :meth:`~motui.app.driver.TUI.add`'s -- unique across the frame.
        """
        block_id = self.tui.add(component, id=id, pin=pin, pane=pane)
        self._components.append(component)
        walked = _walk(component)
        owned: set[int] = set()
        for current in walked:
            if isinstance(current, Widget) and current.owns_focus:
                owned.update(
                    builtins.id(child) for child in _walk(current) if child is not current
                )
        for current in walked:
            if isinstance(current, Widget) and current.theme is None:
                current.theme = self._theme
            if (
                self._focus is not None
                and builtins.id(current) not in owned
                and _looks_interactive(current)
            ):
                self._focus.add(current)
        return block_id

    def get(self, id: str) -> Component:
        """The component with ``id`` (the driver's frame-wide lookup)."""
        return self.tui.get(id)

    def remove(self, id: str) -> Component:
        """Unmount the component with ``id``; answer it.

        The focus ring drops every widget in its subtree first, so a
        removed target can never keep holding the focus.
        """
        component = self.tui.remove(id)
        self._forget(component)
        return component

    def _forget(self, component: Component) -> None:
        """Drop ``component`` and its subtree from the focus ring and the theme walk."""
        if self._focus is not None:
            for current in _walk(component):
                self._focus.remove(current)
        self._components = [
            held for held in self._components if held is not component
        ]

    # -- focus ------------------------------------------------------------------

    def bind(self, key: str, callback: Callable[[], object]) -> None:
        """Run ``callback`` on ``key`` (after the focused control declines it)."""
        self._bindings[key] = callback

    def focus(self, target: "str | Component") -> bool:
        """Focus a block id or a component, registering it when needed."""
        if isinstance(target, str):
            target = self.tui.get(target)
        if self._focus is None:
            return False
        self._focus.add(target)
        moved = self._focus.focus(target)
        self.tui.refresh()
        return moved

    def focus_next(self) -> bool:
        """Step the focus ring one target forward (wrapping)."""
        if self._focus is None:
            return False
        moved = self._focus.focus_next()
        if moved:
            self.tui.refresh()
        return moved

    def focus_previous(self) -> bool:
        """Step the focus ring one target back (wrapping)."""
        if self._focus is None:
            return False
        moved = self._focus.focus_next(-1)
        if moved:
            self.tui.refresh()
        return moved

    def set_focus_targets(self, targets: Iterable[Component]) -> None:
        """Replace the focus ring with ``targets`` and focus the first one."""
        if self._focus is None:
            return
        for known in tuple(self._focus.targets):
            self._focus.remove(known)
        held = tuple(targets)
        for target in held:
            self._focus.add(target)
        if held:
            self._focus.focus(held[0])
        self.tui.refresh()

    # -- frame surface ------------------------------------------------------------

    def split(self, orientation: str, **kwargs: Any) -> Any:
        """Split a pane (the driver's own ``split``)."""
        return self.tui.split(orientation, **kwargs)

    def dock(self, component: Component, *, edge: str = "bottom", size: int | None = None) -> Any:
        """Dock ``component`` (the driver's own ``dock``); theme it first."""
        for current in _walk(component):
            if isinstance(current, Widget) and current.theme is None:
                current.theme = self._theme
        self._components.append(component)
        return self.tui.dock(component, edge=edge, size=size)

    def undock(self, edge: str = "bottom") -> Any:
        """Release the dock on ``edge`` and forget its component.

        The driver's :meth:`~motui.app.driver.TUI.undock` plus the App-side
        bookkeeping: the docked component's subtree leaves the focus ring
        and the theme walk with it.
        """
        pane = self.tui.undock(edge)
        if pane is not None:
            for block in pane.document.blocks():
                self._forget(block.component)
        return pane

    def toast(self, text: str, *, style: Style | None = None) -> None:
        """Show a toast through the mounted stack (``auto=True``)."""
        if self._toasts is None:
            raise RuntimeError("toasts are not mounted (auto=False)")
        self._toasts.show(text, style=style)

    # -- the blocking layer -------------------------------------------------------

    def open_modal(self, panel: Component, **kwargs: Any) -> Modal:
        """Open ``panel`` in a :class:`Modal`; newest on top of the stack."""
        kwargs.setdefault("theme", self._theme)
        kwargs.setdefault("focus", self._focus)
        modal = Modal(self.tui, panel, **kwargs)
        modal.open()
        self._modals.append(modal)
        return modal

    def open_palette(self, commands: list[object], **kwargs: Any) -> CommandPalette:
        """Open the lazily created command palette over ``commands``."""
        if self._palette is None:
            kwargs.setdefault("theme", self._theme)
            kwargs.setdefault("focus", self._focus)
            self._palette = CommandPalette(self.tui, commands, **kwargs)
        self._palette.open()
        return self._palette

    def find(self) -> Find:
        """Open the lazily created :class:`Find` tier."""
        if self._find is None:
            self._find = Find(self.tui, theme=self._theme)
        self._find.open()
        return self._find

    def quit(self) -> None:
        """End the session (``tui.exit()``: a pending read returns ``None``)."""
        self.tui.exit()

    # -- hooks ------------------------------------------------------------------

    def on_start(self) -> None:
        """Called once before the event loop starts."""

    def on_stop(self) -> None:
        """Called once after the loop left, whatever ended it."""

    def on_event(self, event: Event) -> bool:
        """Last chance for every event; ``True`` consumes it."""
        return False

    def on_key(self, event: KeyEvent) -> bool:
        """Host hook for keys no tier took; ``True`` consumes it."""
        return False

    def on_mouse(self, event: MouseEvent) -> bool:
        """Host hook for mouse reports no tier took; ``True`` consumes it."""
        return False

    # -- dispatch ---------------------------------------------------------------

    def dispatch(self, event: Event) -> bool:
        """Route one event through the default tiers; ``True`` when consumed.

        The order is the class docstring's, first claim wins.
        """
        if self._palette is not None and self._palette.is_open:
            if self._palette.handle(event):
                return True
        for modal in reversed(self._modals):
            if modal.is_open:
                modal.handle(event)
                return True
        if self._find is not None and self._find.is_open:
            if self._find.handle(event):
                return True
        if self._toasts is not None and self._toasts.handle(event):
            self.tui.refresh()
            return True

        for controller, dispatch in tuple(self._controllers):
            if dispatch and controller.handle(event):
                self.tui.refresh()
                return True

        if isinstance(event, MouseEvent) and event.kind == "wheel":
            # A wheel during a selection drag belongs to the gesture first
            # (it co-extends the head); otherwise the wheel tier routes it.
            if self._gesture is not None and self._gesture.handle(event):
                self.tui.refresh()
                return True
            if self._wheel(event):
                return True

        if isinstance(event, MouseEvent):
            # A drag goes first: a press on a bar must never anchor the
            # selection gesture under it (the pane Scrollbar's own rule,
            # now for widgets inside the content).
            if self._drag_target is not None and event.kind in ("motion", "release"):
                if self._drag_event(event):
                    return True
            if event.kind == "press" and self._drag_press(event):
                return True
            gesture = bool(self._gesture is not None and self._gesture.handle(event))
            pointer = bool(self._pointer is not None and self._pointer.handle(event))
            focused = self._press_focuses_a_pane(event)
            if gesture or pointer or focused:
                self.tui.refresh()
                return True

        if self._focus is not None and self._focus.handle(event):
            self.tui.refresh()
            return True

        if isinstance(event, KeyEvent):
            if self._scroll_key(event):
                return True
            if event.key in self._bindings:
                self._bindings[event.key]()
                self.tui.refresh()
                return True
            if event.key == "tab":
                return self.focus_next()
            if event.key in ("s-tab", "backtab"):
                return self.focus_previous()

        if isinstance(event, KeyEvent) and self.on_key(event):
            return True
        if isinstance(event, MouseEvent) and self.on_mouse(event):
            return True
        if self.on_event(event):
            return True
        return False

    def _wheel(self, event: MouseEvent) -> bool:
        """Scroll the nearest ``Scrollable`` under the pointer, else the pane."""
        rows = SCROLL_KEYS.get(event.button)
        if not rows:
            return False
        hit: Hit | None = self.tui.hit(event.x, event.y)
        target: object | None = None
        if hit is not None:
            for component, _row, _col in reversed(hit.chain):
                if isinstance(component, Scrollable):
                    target = component
                    break
        if target is None:
            pane = None if hit is None else hit.pane
            if pane is None or self.tui.frame.is_dock(pane):
                pane = self.tui.frame.focused_pane
            target = pane
        if not isinstance(target, Scrollable):
            return False
        target.scroll_by(rows)
        self.tui.refresh()
        return True

    def _drag_press(self, event: MouseEvent) -> bool:
        """Start a drag on the nearest widget overriding ``Widget.drag``.

        Walks ``hit.chain`` backwards -- the deepest widget first -- and
        hands the press to the first one whose ``drag`` is not the
        :class:`~motui.core.widget.Widget` no-op.  That widget answers
        ``True`` only when the press landed on something it owns (the
        ScrollView's bar column); otherwise the walk goes on and the press
        falls through to the gesture and pointer tiers.  Only the left
        button starts a drag.
        """
        if event.button != "left":
            return False
        hit: Hit | None = self.tui.hit(event.x, event.y)
        if hit is None:
            return False
        for component, row, col in reversed(hit.chain):
            if not isinstance(component, Widget):
                continue
            if type(component).drag is Widget.drag:
                continue
            if component.drag(row, col, "press"):
                self._drag_target = component
                self._drag_row = row
                self._drag_col = col
                self.tui.refresh()
                return True
        return False

    def _drag_event(self, event: MouseEvent) -> bool:
        """Feed one motion/release to the drag's target; ``True`` when taken.

        The target is looked up in the fresh hit chain so the cell arrives
        in its own coordinates; when the pointer left it the last cell is
        used, and a lost target or a release ends the drag.  A release is
        always consumed -- the drag it ends must not become a selection
        press on whatever is under the pointer now.
        """
        target = self._drag_target
        if target is None:
            return False
        row, col = self._drag_row, self._drag_col
        held = False
        hit: Hit | None = self.tui.hit(event.x, event.y)
        if hit is not None:
            for component, found_row, found_col in hit.chain:
                if component is target:
                    row, col, held = found_row, found_col, True
                    self._drag_row, self._drag_col = row, col
                    break
        consumed = bool(target.drag(row, col, event.kind))
        if event.kind == "release" or not held:
            self._drag_target = None
        if consumed or event.kind == "release":
            self.tui.refresh()
        return consumed or event.kind == "release"

    def _scroll_key(self, event: KeyEvent) -> bool:
        """Scroll on a page key: the focused ``Scrollable``, else the pane."""
        rows = SCROLL_KEYS.get(event.key)
        if not rows:
            return False
        target: object | None = None
        focused = None if self._focus is None else self._focus.focused
        if isinstance(focused, Scrollable):
            target = focused
        if target is None:
            pane = self.tui.frame.focused_pane
            target = pane if isinstance(pane, Scrollable) else None
        if not isinstance(target, Scrollable):
            return False
        target.scroll_by(rows)
        self.tui.refresh()
        return True

    def _press_focuses_a_pane(self, event: MouseEvent) -> bool:
        """A button press focuses the pane under it (never a dock)."""
        if event.kind != "press" or event.button not in _BUTTONS:
            return False
        pane = self.tui.pane_at(event.x, event.y)
        if pane is None or self.tui.frame.is_dock(pane):
            return False
        focused = self.tui.frame.focused_pane
        if focused is not None and focused.id == pane.id:
            return False
        self.tui.frame.focus(pane)
        self.tui.refresh()
        return True

    # -- lifecycle ----------------------------------------------------------------

    async def run_session(self, body: Callable[["App"], Awaitable[None]]) -> None:
        """Run ``body(app)`` inside the driver's session bracket."""
        async def loop(_tui: TUI) -> None:
            await body(self)

        await self.tui.run_session(loop)

    async def run_async(self) -> None:
        """Run the default loop until ``quit()`` (or EOF), inside a session."""
        await self.tui.run_session(self._loop)

    async def _loop(self, tui: TUI) -> None:
        """Paint (non-live), read, dispatch -- until the read answers ``None``."""
        self.on_start()
        try:
            while True:
                if not tui.interactive:
                    tui.paint()
                event = await tui.read_event()
                if event is None:
                    break
                self.dispatch(event)
                self.tui.refresh()
        finally:
            self.on_stop()

    def run(self) -> None:
        """The synchronous entry: own an event loop around :meth:`run_async`."""
        asyncio.run(self.run_async())

    def __repr__(self) -> str:
        return (
            f"App(auto={self.auto}, components={len(self._components)}, "
            f"focused={None if self._focus is None else self._focus.focused!r})"
        )
