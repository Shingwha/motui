"""The app layer: the runtime and the strategy tiers a host mounts on it.

Runtime owns the session, Workspace what is on screen, and App the
default policy and dispatch order; the controllers beside them make
interaction policy a layer rather than a component's responsibility."""

from .application import App
from .command_palette import CommandPalette
from .commands import Command, CommandRegistry
from .find import Find
from .focus import FocusManager
from .gesture import SelectionGesture, copy_on_select
from .modal import Modal
from .overlays import Stats, Toasts, Tooltip
from .pointer import Pointer
from .router import DEFAULT_HANDLERS, Handler
from .runtime import Runtime
from .scrollbar import Scrollbar, ScrollbarStyles
from .workspace import Workspace

__all__ = [
    "DEFAULT_HANDLERS",
    "App",
    "Command",
    "CommandPalette",
    "CommandRegistry",
    "Find",
    "FocusManager",
    "Handler",
    "Modal",
    "Pointer",
    "Runtime",
    "Scrollbar",
    "ScrollbarStyles",
    "SelectionGesture",
    "Stats",
    "Toasts",
    "Tooltip",
    "Workspace",
    "copy_on_select",
]
