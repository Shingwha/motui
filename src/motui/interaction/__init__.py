"""The interaction tier: the four strategies a host mounts on the driver.

One module per strategy, each a controller *beside* the driver rather than
inside it:

* :class:`~motui.interaction.focus.FocusRing` -- the widget-focus tier:
  the targets a host may focus, their cycle, the key-routing table a
  focused target owns and the click policy.  It is the peer of
  :mod:`motui.interaction.gesture`.
* :class:`~motui.interaction.gesture.SelectionGesture` and its shipped
  ``on_end`` default :func:`~motui.interaction.gesture.copy_on_select` --
  the mouse-selection posture: press/drag/release over the kernel's pure
  selection model, the edge auto-scroll, and the word-then-line click
  count.
* :class:`~motui.interaction.pointer.Pointer` -- the pointer posture:
  hover tracking and stationary clicks beside the gesture.
* :class:`~motui.interaction.search.Find` -- the search tier over the
  focused pane's document: its own query row, the matches it addresses and
  the reveal of the current one.

Each module imports the kernel and the driver and holds no rendering of its
own; the strategies are what makes the interaction *policy* a layer, never a
component's responsibility.
"""

from .focus import FocusRing
from .gesture import SelectionGesture, copy_on_select
from .palette import Palette
from .pointer import Pointer
from .search import Find

__all__ = ["Find", "FocusRing", "Palette", "Pointer", "SelectionGesture", "copy_on_select"]
