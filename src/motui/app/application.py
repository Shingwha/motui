"""App: the default orchestration over the low-level Runtime.

Composes the shipped controllers and owns the dispatch order (palette,
modals, find, toasts, mounts, wheel, mouse, focus, page keys, bindings,
host hooks). ``auto=False`` mounts no policy."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

from ..kernel.document import Component, Placement, Section, Sizing
from ..kernel.events import Event, KeyEvent, MouseEvent, ResizeEvent
from ..kernel.geom import Axis
from ..kernel.selection import Selection
from ..kernel.style import Style
from ..kernel.theme import DEFAULT_THEME, Theme
from ..terminal.screen import TerminalOptions
from ..terminal.terminal import Terminal
from ..widgets.base import Widget
from .command_palette import CommandPalette
from .commands import CommandRegistry
from .find import Find
from .focus import FocusManager, focus_targets, iter_widgets
from .gesture import SelectionGesture
from .modal import Modal
from .overlays import Toasts, Tooltip
from .pointer import Pointer
from .router import DEFAULT_HANDLERS, Handler
from .runtime import Runtime, Timer, _stdin_isatty
from .workspace import Workspace

__all__ = ["App"]

def _nodes(component: Component) -> Iterator[Component]:
    """Every node of ``component``'s explicit tree, depth first; a component
    without ``walk`` is its own one-node tree."""
    walk = getattr(component, "walk", None)
    if callable(walk):
        yield from walk()
    else:
        yield component


class App:
    """The high-level application: runtime plus the default interaction policy.

    ``theme`` propagates to mounted widgets that took none. ``auto=True``
    mounts the default controllers; ``auto=False`` leaves the runtime and the
    caller's own loop."""

    def __init__(
        self,
        *,
        theme: Theme | None = None,
        terminal: TerminalOptions | None = None,
        throttle: float = 0.030,
        auto: bool = True,
        title: str = "",
        on_selection: Callable[[Workspace, Selection], object] | None = None,
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
        """Register ``controller`` in the App's controller tier; a dispatching one
        sees events after the toasts. ``dispatch=False`` mounts one the App only
        themes and keeps -- the host feeds it itself."""
        for index, (known, _dispatch) in enumerate(self._controllers):
            if known is controller:
                self._controllers[index] = (known, dispatch)
                return
        self._controllers.append((controller, dispatch))

    def unmount(self, controller: object) -> bool:
        """Remove ``controller`` from the tier; only the registration is dropped,
        never the controller's own lifecycle."""
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
        """Mount ``component``; its subtree takes the App theme and joins the focus
        ring. With no ``pane`` the block lands in the primary document."""
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
        """Fill a pane with ``component``; the component takes the theme and joins
        the focus ring exactly as an added one does."""
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
        """Unmount ``section``; the focus ring drops its subtree first, so a
        removed target can never keep the focus."""
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
        """Call ``fn`` every ``period`` seconds; answer the cancellable timer."""
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
        """Every mounted node once, depth first, in frame order -- the tree's own
        explicit walk, shared nodes yielded once."""
        yield from iter_widgets(self.workspace)

    # -- focus ------------------------------------------------------------------

    def bind(self, key: str, callback: Callable[[], object]) -> None:
        """Run ``callback`` on ``key``, after the focused control declines it."""
        self._bindings[key] = callback

    def focus(self, target: str | Component) -> bool:
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
        """Split a pane (the workspace's own ``split``); ``weights`` are the
        children's shares."""
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
        """Dock ``component`` (the workspace's own ``dock``); theme it first."""
        for current in _nodes(component):
            if isinstance(current, Widget) and current.theme is None:
                current.theme = self._theme
        self._components.append(component)
        return self.workspace.dock(component, placement=placement, size=size)

    def undock(
        self,
        placement: Placement = Placement.BOTTOM,
    ) -> Any:
        """Release the dock at ``placement`` and forget its component's subtree."""
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
        """Open the lazily created palette over ``commands``; any other type raises
        ``TypeError``."""
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
        """Route one event through the handler chain, first claim wins. A resize
        first reaches every mounted widget's ``on_resize`` and then keeps
        travelling: the broadcast informs, it never consumes."""
        if type(event) is ResizeEvent:
            for widget in iter_widgets(self.workspace):
                on_resize = getattr(widget, "on_resize", None)
                if on_resize is not None:
                    on_resize(event)
        return any(handler(self, event) for handler in self.handlers)

    # -- lifecycle ----------------------------------------------------------------

    async def run_session(self, body: Callable[[App], Awaitable[None]]) -> None:
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
        """The synchronous entry: own an event loop around :meth:`run_async`; a
        Ctrl+C interrupt is a quit, not a crash."""
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(self.run_async())

    def __repr__(self) -> str:
        return (
            f"App(auto={self.auto}, components={len(self._components)}, "
            f"focused={None if self._focus is None else self._focus.focused!r})"
        )
