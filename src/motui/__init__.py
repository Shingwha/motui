"""motui: a layered, full-screen TUI toolkit.

It takes over the terminal on the alternate screen, renders a document of
addressable blocks one diffed row at a time, owns its own scrollback, and
keeps pinned bands (fixed top and bottom regions, the frame's own footer)
that never scroll away.

Five layers carry it:

* :mod:`motui.kernel` -- the kernel and the root of the dependency graph:
  the frozen :class:`~motui.kernel.block.Component` protocol and the
  addressable ``Block`` document model, the
  :class:`~motui.kernel.lines.Line` / :class:`~motui.kernel.lines.Segment`
  row primitive, :class:`~motui.kernel.style.Style` /
  :class:`~motui.kernel.theme.Theme`, the measuring helpers, the event
  model, the render core (:class:`~motui.kernel.screen.Screen`,
  :class:`~motui.kernel.viewport.Viewport`,
  :class:`~motui.kernel.painter.Painter`), the frame model
  (:class:`~motui.kernel.frame.Pane`, :class:`~motui.kernel.frame.Rect`)
  and the selection kernel (:class:`~motui.kernel.selection.Selection`,
  :func:`~motui.kernel.selection.highlight`,
  :func:`~motui.kernel.selection.extract`).
* :mod:`motui.keys` -- raw terminal bytes into events: the pure
  :class:`~motui.keys.KeyDecoder`, the keymaps and the terminal key
  sources.
* :mod:`motui.widgets` -- the generic component library: the renderers plus
  the minimal action primitives, the Markdown rule registries under
  :mod:`motui.widgets.markdown` and the zero-dependency highlighting seam in
  :mod:`motui.widgets.syntax`.
* :mod:`motui.interaction` -- the strategy tiers a host mounts on the
  driver: :class:`~motui.interaction.focus.FocusRing`,
  :class:`~motui.interaction.pointer.Pointer`,
  :class:`~motui.interaction.gesture.SelectionGesture` (with
  :func:`~motui.interaction.gesture.copy_on_select`),
  :class:`~motui.interaction.find.Find`, the blocking layer
  (:class:`~motui.interaction.modal.Modal` with
  :class:`~motui.interaction.palette.Palette`), the overlays
  (:class:`~motui.interaction.overlays.Toasts`,
  :class:`~motui.interaction.overlays.Tooltip`,
  :class:`~motui.interaction.overlays.Stats`) and the pane chrome
  (:class:`~motui.interaction.scrollbar.Scrollbar`).
* :mod:`motui.app` -- :class:`~motui.app.TUI`, the driver and the
  composition root -- with :mod:`motui.testing`
  (:func:`~motui.testing.headless_tui`,
  :func:`~motui.testing.snapshot`) beside it.

This module is the curated face: the 34 names one application needs to
start, in one import line.  The root carries the driver, the styling trio
(:class:`Theme`, :data:`DEFAULT_THEME`, :class:`Style`), the row primitive
(:class:`Line`, :class:`Segment`), the event trio (:class:`Key`,
:class:`MouseEvent`, :class:`Paste`), the content, editing, data, selection,
action and modal components a host reaches for first, the wiring entry
points of the interaction tier, and the two headless helpers.  Everything
else stays public at its own layer namespace::

    from motui import TUI, Input, Markdown          # the root: 34 names
    from motui.widgets import Row, Panel, Diff      # a layer: the whole library
    from motui.kernel import Style, Line, Selection # the kernel seam
    from motui.keys import DEFAULT_INPUT_KEYMAP
    from motui.interaction import FocusRing, Pointer, Find, Tooltip

The deep seams stay public at their own module paths -- the painter, the
viewport layout, the document model, the frame and the selection kernel
under :mod:`motui.kernel`, the byte decoder under :mod:`motui.keys`, and
the Markdown rule registries and the highlighter protocol under
:mod:`motui.widgets` -- for hosts that reach below the layers.

Dependencies point one way: the kernel depends on nothing outside itself,
``keys`` and ``widgets`` build on it, and the interaction tiers, the driver
and the headless helpers compose them from above.
"""

from importlib.metadata import PackageNotFoundError, version

#: The distribution version, read from the installed metadata so the wheel's
#: number is the only place it can drift from.  A source checkout that was
#: never installed carries no metadata and falls back to the number of the
#: release it is cut from.
try:
    __version__ = version("motui")
except PackageNotFoundError:  # pragma: no cover - a pure source checkout
    __version__ = "1.1.8"

from .app import TUI
from .interaction import (
    FocusRing,
    Modal,
    Palette,
    Pointer,
    Scrollbar,
    SelectionGesture,
    Toasts,
)
from .kernel import (
    DEFAULT_THEME,
    Key,
    Line,
    MouseEvent,
    Paste,
    Segment,
    Style,
    Text,
    Theme,
)
from .testing import headless_tui, snapshot
from .widgets import (
    Button,
    Checkbox,
    Dialog,
    Editor,
    Input,
    Link,
    List,
    Markdown,
    NavList,
    Option,
    Select,
    StatusLine,
    Table,
    Tabs,
    Tree,
)

__all__ = [
    "DEFAULT_THEME",
    "Button",
    "Checkbox",
    "Dialog",
    "Editor",
    "FocusRing",
    "Input",
    "Key",
    "Line",
    "Link",
    "List",
    "Markdown",
    "Modal",
    "MouseEvent",
    "NavList",
    "Option",
    "Palette",
    "Paste",
    "Pointer",
    "Scrollbar",
    "Segment",
    "Select",
    "SelectionGesture",
    "StatusLine",
    "Style",
    "TUI",
    "Table",
    "Tabs",
    "Text",
    "Theme",
    "Toasts",
    "Tree",
    "headless_tui",
    "snapshot",
]
