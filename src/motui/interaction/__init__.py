"""The interaction tier: the strategies a host mounts on the driver.

The strategy layer -- focus, the pointer, the gestures, search, the modal,
the overlays and the scrollbar -- one module per strategy, each a controller
*beside* the driver rather than inside it:

* :class:`~motui.interaction.focus.FocusManager` -- the widget-focus tier:
  the targets a host may focus, their cycle, the key-routing table a
  focused target owns, the click policy and the nested focus traps.
* :class:`~motui.interaction.pointer.Pointer` -- the pointer posture:
  hover tracking and stationary clicks beside the gesture.
* :class:`~motui.interaction.gesture.SelectionGesture` and its shipped
  ``on_end`` default :func:`~motui.interaction.gesture.copy_on_select` --
  the mouse-selection posture: press/drag/release over the kernel's pure
  selection model, the edge auto-scroll, and the word-then-line click
  count.
* :class:`~motui.interaction.find.Find` -- the search tier over the
  focused pane's document: its own query row, the matches it addresses and
  the reveal of the current one.
* :class:`~motui.interaction.modal.Modal` -- the blocking layer: an
  overlay that scrims the frame, places a panel (centered or anchored) and
  routes every event into it, dismissing on a click outside.
  :class:`~motui.interaction.palette.Palette` is its first shipped panel --
  a query row over the filtered command list.
* :class:`~motui.interaction.overlays.Toasts` / ``Tooltip`` / ``Stats`` --
  the frame overlays: transient bands, the pointer's hint and the dev box,
  over the frame's own overlay registry.
* :class:`~motui.interaction.scrollbar.Scrollbar` -- the pane chrome: a
  budgeted strip whose thumb maps the scroll, registered on a pane.

Each module imports the kernel and the ``Host`` protocol seam and holds no
rendering of its own; the strategies are what makes the interaction *policy*
a layer, never a component's responsibility.  No module here imports
``motui.app`` or ``motui.widgets``: the driver's surface is
:class:`~motui.kernel.host.Host`, and the widgets a self-contained tier
composes (``Palette``'s query row and list) are built through its
``make_input``/``make_autocomplete`` factories.
"""

from .find import Find
from .focus import FocusManager
from .gesture import SelectionGesture, copy_on_select
from .modal import Modal
from .overlays import Stats, Toasts, Tooltip
from .palette import Palette
from .pointer import Pointer
from .scrollbar import Scrollbar

__all__ = [
    "Find",
    "FocusManager",
    "Modal",
    "Palette",
    "Pointer",
    "Scrollbar",
    "SelectionGesture",
    "Stats",
    "Toasts",
    "Tooltip",
    "copy_on_select",
]
