"""App: the default orchestration over the low-level :class:`Runtime`.

:class:`Runtime` reads events and owns the document, the frame and the pump;
it deliberately runs no interaction policy.  :class:`App` is that policy
assembled from the controllers this package ships -- :class:`FocusManager`,
:class:`Pointer`, :class:`SelectionGesture`, :class:`Toasts`,
:class:`Tooltip`, :class:`Find`, :class:`Modal` and
:class:`CommandPalette` -- and dispatched in one documented order.  A host
that wants a different order, or no default policy at all, passes
``auto=False`` and drives the ``runtime`` itself (the ``Runtime`` API is
unchanged and still public).

**The dispatch order** (:meth:`App.dispatch`, first claim wins):

1. the open :class:`~motui.app.command_palette.CommandPalette`;
2. the open :class:`~motui.app.modal.Modal` layers, newest first;
3. the open :class:`~motui.app.find.Find`;
4. :class:`~motui.app.overlays.Toasts`;
5. the controllers added with :meth:`App.mount`, in mount order, when the
   mount is dispatching (the demo's pane ``Scrollbar``);
6. the wheel: a horizontal notch goes to the nearest
   :class:`~motui.kernel.layout.ScrollableX` in ``hit.chain`` (one
   column); a vertical notch to the nearest
   :class:`~motui.kernel.layout.Scrollable` in ``hit.chain``, otherwise
   the hit pane, otherwise the focused pane's viewport (a
   :class:`~motui.app.gesture.SelectionGesture` mid-drag claims its own
   wheel first, so its head co-extends);
7. the mouse: a drag in flight (or a press that starts one), then the
   selection gesture, the pointer tier, then a press focuses the pane
   under it;
8. the focused control through :class:`FocusManager`;
9. the page keys: the focused :class:`~motui.kernel.layout.Scrollable`, else
   the focused pane's viewport;
10. the keys bound with :meth:`App.bind`, then ``tab``/``s-tab`` cycling;
11. the host hooks ``on_key``/``on_mouse``/``on_event``.

The controller tiers are the existing ones, not re-implementations: the
App only composes them and owns the order.  ``auto=False`` mounts none of
them (``focus``/``toast``/``open_modal`` then report the missing layer).

**Theme propagation.**  :attr:`App.theme` is the application theme:
constructing the App gives it to the runtime, and :meth:`App.add` assigns it
to every :class:`~motui.widgets.base.Widget` in the mounted subtree whose
``theme`` is still ``None`` (an explicit ``theme=`` stays a local
override).  The subtree is the widget's explicit :meth:`Widget.walk`, so
the theme pass and the focus ring read the same tree.  Re-assigning
:attr:`App.theme` walks the mounted components again and also calls
``set_theme(value)`` on the app-owned overlays (toasts, tooltip, palette,
find) and on every controller added with :meth:`App.mount`.

**Mounted controllers.**  :meth:`App.mount` adds a host controller (a pane
``Scrollbar``, a dev overlay) to the App's controller tier.  A dispatching
mount is called in the documented order and consumes the event when its
``handle`` answers ``True``; ``dispatch=False`` mounts a controller the App
only themes and keeps (the host feeds it itself -- the demo's counting
``Stats``).  :meth:`App.unmount` removes it without detaching: the
controller's lifecycle stays the host's.

**Focus.**  The ring is derived from the tree, never registered: every
mounted pane and dock contributes its document roots in paint order, and a
preorder walk keeps the nodes that are ``focusable`` (or a
``focus_scope``, whose subtree the ring stops at).  Mounting and removing
a block re-derives the ring, so a removed target can never keep the
focus.  :meth:`App.focus` addresses one target by block id or component.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

from ..kernel.document import Component, Placement, Section, Sizing
from ..kernel.events import Event, KeyEvent, MouseEvent, ResizeEvent
from ..kernel.geom import Axis
from ..terminal.screen import TerminalOptions
from ..terminal.terminal import Terminal
from ..kernel.selection import Selection
from ..kernel.style import Style
from ..kernel.theme import DEFAULT_THEME, Theme
from ..widgets.base import Widget
from .command_palette import CommandPalette
from .commands import CommandRegistry
from .runtime import Runtime, Timer, _stdin_isatty
from .find import Find
from .focus import FocusManager, focus_targets, iter_widgets
from .gesture import SelectionGesture
from .modal import Modal
from .overlays import Toasts, Tooltip
from .pointer import Pointer
from .router import DEFAULT_HANDLERS, Handler
from .workspace import Workspace

__all__ = ["App"]

def _nodes(component: Component) -> Iterator[Component]:
    """Every node of ``component``'s explicit tree, depth first.

    A component without ``walk`` is its own one-node tree.  The explicit
    tree is the only source: an attribute that merely looks like a child
    (a ``ScrollPanel.child``) is not guessed at.
    """
    walk = getattr(component, "walk", None)
    if callable(walk):
        yield from walk()
    else:
        yield component


class App:
    """The high-level application: runtime + the default interaction policy.

    ``theme`` is the application theme (``DEFAULT_THEME`` when omitted) --
    handed to the runtime's chrome and assigned to mounted widgets that did
    not take an explicit one.  ``terminal=`` is the one configuration door:
    a :class:`~motui.terminal.screen.TerminalOptions` from which the App
    builds one :class:`~motui.terminal.terminal.Terminal` and hands it to
    the runtime; with none given the defaults build a live terminal screen.
    ``title`` is set through the runtime's OSC 2 surface when non-empty.
    ``auto=True`` mounts the default controllers; ``auto=False`` mounts
    none, leaving :attr:`runtime`/``workspace`` and the caller's own loop
    (the ``Runtime`` is still fully usable).  ``throttle`` is the pump's
    flush interval.  ``on_selection`` replaces the selection gesture's
    ``on_end`` (the default is
    :func:`~motui.app.gesture.copy_on_select`).  ``handlers`` is the host's
    ordered handler chain (:data:`~motui.app.router.DEFAULT_HANDLERS` when
    ``None`` and ``auto=True``); ``auto=False`` builds none, and a tuple
    passed explicitly is used as given.  A handler is
    ``handler(app, event) -> bool``: first claim wins.
    """

    def __init__(
        self,
        *,
        theme: Theme | None = None,
        terminal: TerminalOptions | None = None,
        throttle: float = 0.030,
        auto: bool = True,
        title: str = "",
        on_selection: Callable[["Workspace", Selection], object] | None = None,
        handlers: tuple[Handler, ...] | None = None,
    ) -> None:
        self._theme = DEFAULT_THEME if theme is None else theme
        endpoint = Terminal(TerminalOptions() if terminal is None else terminal)
        self.runtime: Runtime = Runtime(
            endpoint,
            throttle=throttle,
            interactive=endpoint.live and _stdin_isatty(),
            theme=self._theme,
        )
        self.workspace: Workspace = self.runtime.workspace
        self.terminal: Terminal = endpoint
        self.auto = auto
        self.handlers: tuple[Handler, ...]
        if handlers is not None:
            self.handlers = tuple(handlers)
        elif auto:
            self.handlers = DEFAULT_HANDLERS
        else:
            self.handlers = ()
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
        # ScrollPanel bar), and the cell it was last addressed at.
        self._drag_target: Component | None = None
        self._drag_row = 0
        self._drag_col = 0
        self._toasts: Toasts | None = None
        self._tooltip: Tooltip | None = None
        if auto:
            self._focus = FocusManager()
            # The controllers drive the workspace (the frame, the hit test,
            # the selection) and read the runtime seams it exposes (clock,
            # every, painter, refresh, screen, clipboard).
            self._pointer = Pointer(self.workspace, ring=self._focus)
            gesture_args = {} if on_selection is None else {"on_end": on_selection}
            self._gesture = SelectionGesture(self.workspace, **gesture_args)
            self._toasts = Toasts(self.workspace, theme=self._theme)
            self._tooltip = Tooltip(self.workspace, self._pointer, theme=self._theme)
        if title:
            self.runtime.set_title(title)

    # -- theme ------------------------------------------------------------------

    @property
    def theme(self) -> Theme:
        """The application theme (see the class docstring)."""
        return self._theme

    @theme.setter
    def theme(self, value: Theme) -> None:
        self._theme = value
        self.workspace.theme = value
        for component in tuple(self._components):
            for current in _nodes(component):
                if isinstance(current, Widget) and current.theme is None:
                    current.theme = value
        for overlay in (self._toasts, self._tooltip, self._palette, self._find):
            self._set_theme(overlay, value)
        for controller, _dispatch in tuple(self._controllers):
            self._set_theme(controller, value)
        self.runtime.refresh()

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
        placement: Placement = Placement.FLOW,
        sizing: Sizing = Sizing.NATURAL,
        pane: Any = None,
    ) -> Section:
        """Mount ``component``; answer its section.

        The component's subtree takes the App theme where no explicit one
        is set, and its interactive widgets join the focus ring (when the
        default controllers are mounted).  With no ``pane=`` the block lands
        in the main (primary) document, never the focused pane.  The section
        carries :meth:`~motui.app.runtime.Runtime.add`'s id -- unique across
        the frame -- and the mounted component.
        ``placement``/``sizing`` are the document's own spellings.
        """
        section = self.workspace.add(
            component,
            id=id,
            placement=placement,
            sizing=sizing,
            pane=pane,
        )
        self._mount(component)
        return section

    def fill(self, component: Component, *, pane: Any = None) -> Section:
        """Fill a pane with ``component``; answer the ``FILL`` section.

        The fill replaces the pane's document (a fill is the pane's whole
        content), so this goes through
        :meth:`~motui.app.workspace.Workspace.fill` rather than :meth:`add`.
        The component still takes the App theme
        and joins the focus ring exactly as an added one does: the two
        mounting paths share :meth:`_mount`.
        """
        section = self.workspace.fill(component, pane=pane)
        self._mount(component)
        return section

    def _mount(self, component: Component) -> None:
        """Take a freshly mounted component into the theme walk and focus ring."""
        self._components.append(component)
        for current in _nodes(component):
            if isinstance(current, Widget) and current.theme is None:
                current.theme = self._theme
        self._sync_focus()

    def _sync_focus(self) -> None:
        """Re-derive the ring from the tree after a mount or an unmount."""
        if self._focus is not None:
            self._focus.sync(focus_targets(self.workspace))

    def get(self, id: str) -> Section:
        """The section with ``id`` (the workspace's frame-wide lookup)."""
        return self.workspace.get(id)

    def remove(self, section: Section) -> Section:
        """Unmount ``section``; answer the section it held.

        The focus ring drops every widget in its subtree first, so a
        removed target can never keep holding the focus.  Removal is
        addressed by the ``Section`` value :meth:`add` answers, not by a
        bare id: the section carries the component whose theme/focus entry
        must be forgotten.
        """
        if not isinstance(section, Section):
            raise TypeError(f"App.remove() takes a Section, got {type(section).__name__}")
        section = self.workspace.remove(section.id)
        self._forget(section.widget)
        return section

    def _forget(self, component: Component) -> None:
        """Drop ``component`` from the theme walk and re-derive the focus ring."""
        self._components = [
            held for held in self._components if held is not component
        ]
        self._sync_focus()

    # -- runtime proxies ----------------------------------------------------------

    def every(
        self,
        period: float,
        fn: Callable[[], object],
        *,
        catch_up: str = "skip",
    ) -> Timer:
        """Call ``fn`` every ``period`` seconds; answer the cancellable timer.

        The :meth:`Runtime.every <motui.app.runtime.Runtime.every>` schedule:
        the first run lands one period from now and every run adds exactly
        one period.  ``catch_up`` is ``"skip"`` or ``"coalesce"``.
        """
        return self.runtime.every(period, fn, catch_up=catch_up)

    def animation(self, hz: float, draw: Callable[[], object]) -> Timer:
        """Call ``draw`` at ``hz`` frames per second; answer the timer."""
        return self.runtime.animation(hz, draw)

    def invalidate(self) -> None:
        """Mark the frame dirty (the next pump paint shows the change)."""
        self.runtime.invalidate()

    def paint_now(self) -> None:
        """Paint one frame now, bypassing the throttle."""
        self.runtime.paint_now()

    def walk(self) -> Iterator[Component]:
        """Every mounted node once, depth first, in frame order.

        The tree the App itself derives the focus ring and the resize
        broadcast from: every pane and dock document root, each walked
        explicitly (``Widget.walk``), shared nodes yielded once.
        """
        yield from iter_widgets(self.workspace)

    # -- focus ------------------------------------------------------------------

    def bind(self, key: str, callback: Callable[[], object]) -> None:
        """Run ``callback`` on ``key`` (after the focused control declines it)."""
        self._bindings[key] = callback

    def focus(self, target: "str | Component") -> bool:
        """Focus a block id or a component that is in the tree-derived ring."""
        if isinstance(target, str):
            target = self.workspace.get(target).widget
        if self._focus is None:
            return False
        self._focus.sync(focus_targets(self.workspace))
        moved = self._focus.focus(target)
        self.runtime.refresh()
        return moved

    def focus_next(self) -> bool:
        """Step the focus ring one target forward (wrapping)."""
        if self._focus is None:
            return False
        self._focus.sync(focus_targets(self.workspace))
        moved = self._focus.focus_next()
        if moved:
            self.runtime.refresh()
        return moved

    def focus_previous(self) -> bool:
        """Step the focus ring one target back (wrapping)."""
        if self._focus is None:
            return False
        self._focus.sync(focus_targets(self.workspace))
        moved = self._focus.focus_next(-1)
        if moved:
            self.runtime.refresh()
        return moved

    # -- frame surface ------------------------------------------------------------

    def split(
        self,
        axis: Axis,
        *,
        weights: tuple[float, ...] = (1, 1),
        min_size: int = 1,
        separator: bool = True,
        pane: Any = None,
    ) -> tuple[Any, ...]:
        """Split a pane (the workspace's own ``split``).

        ``axis`` is :class:`~motui.kernel.geom.Axis` (``X`` divides the
        width, ``Y`` the height) and ``weights`` the children's shares.
        """
        return self.workspace.split(
            axis,
            weights=weights,
            min_size=min_size,
            separator=separator,
            pane=pane,
        )

    def dock(
        self,
        component: Component,
        *,
        placement: Placement = Placement.BOTTOM,
        size: int | None = None,
    ) -> Any:
        """Dock ``component`` (the workspace's own ``dock``); theme it first.

        ``placement`` is ``TOP`` or ``BOTTOM``; ``FLOW`` raises.
        """
        for current in _nodes(component):
            if isinstance(current, Widget) and current.theme is None:
                current.theme = self._theme
        self._components.append(component)
        return self.workspace.dock(component, placement=placement, size=size)

    def undock(
        self,
        placement: Placement = Placement.BOTTOM,
    ) -> Any:
        """Release the dock named by ``placement`` and forget its component.

        The workspace's :meth:`~motui.app.workspace.Workspace.undock` plus
        the App-side bookkeeping: the docked component's subtree leaves the
        focus ring and the theme walk with it.
        """
        pane = self.workspace.undock(placement)
        if pane is not None:
            for block in pane.document.blocks():
                self._forget(block.widget)
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
        modal = Modal(self.workspace, panel, **kwargs)
        modal.open()
        self._modals.append(modal)
        return modal

    def open_palette(
        self,
        commands: CommandRegistry,
        **kwargs: Any,
    ) -> CommandPalette:
        """Open the lazily created command palette over ``commands``.

        ``commands`` is a :class:`~motui.app.commands.CommandRegistry`; its
        :meth:`~motui.app.commands.CommandRegistry.options` view is what the
        palette renders.  Any other type raises ``TypeError`` -- the palette
        speaks one command model, not a bare list of options.
        """
        if not isinstance(commands, CommandRegistry):
            raise TypeError(
                "App.open_palette() takes a CommandRegistry, got "
                f"{type(commands).__name__}"
            )
        if self._palette is None:
            kwargs.setdefault("theme", self._theme)
            kwargs.setdefault("focus", self._focus)
            self._palette = CommandPalette(
                self.workspace, commands.options(), **kwargs
            )
        self._palette.open()
        return self._palette

    def find(self) -> Find:
        """Open the lazily created :class:`Find` tier."""
        if self._find is None:
            self._find = Find(self.workspace, theme=self._theme)
        self._find.open()
        return self._find

    def quit(self) -> None:
        """End the session (``runtime.exit()``: a pending read returns ``None``)."""
        self.runtime.exit()

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
        """Route one event through the handler chain; ``True`` when consumed.

        The chain is :attr:`handlers` -- by default
        :data:`~motui.app.router.DEFAULT_HANDLERS`, in the class
        docstring's order, first claim wins.  A
        :class:`~motui.kernel.events.ResizeEvent` first reaches every
        mounted widget's ``on_resize`` (the whole tree, a focus scope's
        subtree included) and then keeps travelling: the broadcast informs,
        it never consumes.  A host that passes its own ``handlers`` gets
        exactly those tiers; ``auto=False`` builds the App with none.
        """
        if type(event) is ResizeEvent:
            for widget in iter_widgets(self.workspace):
                on_resize = getattr(widget, "on_resize", None)
                if on_resize is not None:
                    on_resize(event)
        for handler in self.handlers:
            if handler(self, event):
                return True
        return False

    # -- lifecycle ----------------------------------------------------------------

    async def run_session(self, body: Callable[["App"], Awaitable[None]]) -> None:
        """Run ``body(app)`` inside the runtime's session bracket."""
        async def loop(_runtime: Runtime) -> None:
            await body(self)

        await self.runtime.run_session(loop)

    async def run_async(self) -> None:
        """Run the default loop until ``quit()`` (or EOF), inside a session."""
        await self.runtime.run_session(self._loop)

    async def _loop(self, runtime: Runtime) -> None:
        """Paint (non-live), read, dispatch -- until the read answers ``None``."""
        self.on_start()
        try:
            while True:
                if not runtime.interactive:
                    runtime.paint()
                event = await runtime.read_event()
                if event is None:
                    break
                self.dispatch(event)
                self.runtime.refresh()
        finally:
            self.on_stop()

    def run(self) -> None:
        """The synchronous entry: own an event loop around :meth:`run_async`.

        A Ctrl+C interrupt is a quit, not a crash.  The signal cancels the
        session task, so ``run_async`` unwinds through its normal teardown
        (``on_stop``, source close, screen leave); ``asyncio.run`` then
        raises ``KeyboardInterrupt``, which this entry swallows so a host
        sees a clean exit instead of a traceback.
        """
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            pass

    def __repr__(self) -> str:
        return (
            f"App(auto={self.auto}, components={len(self._components)}, "
            f"focused={None if self._focus is None else self._focus.focused!r})"
        )
