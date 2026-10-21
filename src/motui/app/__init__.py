"""The app layer: the driver and the strategy tiers a host mounts on it.

:class:`~motui.app.driver.TUI` is the runtime: the document facade, the
pump, the frame, the selection and the run lifecycle.
:class:`~motui.app.app.App` composes it with the default interaction
policy (the focus ring, the pointer, the selection gesture, the overlays
and the blocking layers) and owns the dispatch order.  Beside them sit the
controllers that make the interaction *policy* a layer rather than a
component's responsibility:

* :class:`~motui.app.focus.FocusManager` -- the widget-focus tier;
* :class:`~motui.app.pointer.Pointer` -- hover tracking and stationary
  clicks;
* :class:`~motui.app.gesture.SelectionGesture` with
  :func:`~motui.app.gesture.copy_on_select` -- the mouse-selection posture;
* :class:`~motui.app.find.Find` -- search over the focused pane's document;
* :class:`~motui.app.modal.Modal` and
  :class:`~motui.app.command_palette.CommandPalette` -- the blocking layer;
* :class:`~motui.app.overlays.Toasts` / ``Tooltip`` / ``Stats`` -- the
  frame overlays;
* :class:`~motui.app.scrollbar.Scrollbar` -- the pane chrome;
* :class:`~motui.app.commands.Command` / ``CommandRegistry`` -- named
  actions a host binds to keys and a palette.

The app layer composes the core and the widget library from above; nothing
below it imports it.
"""

from .app import App
from .command_palette import CommandPalette
from .commands import Command, CommandRegistry
from .driver import TUI
from .find import Find
from .focus import FocusManager
from .gesture import SelectionGesture, copy_on_select
from .modal import Modal
from .overlays import Stats, Toasts, Tooltip
from .pointer import Pointer
from .scrollbar import Scrollbar

__all__ = [
    "App",
    "Command",
    "CommandPalette",
    "CommandRegistry",
    "Find",
    "FocusManager",
    "Modal",
    "Pointer",
    "Scrollbar",
    "SelectionGesture",
    "Stats",
    "TUI",
    "Toasts",
    "Tooltip",
    "copy_on_select",
]
