"""motui: a layered, full-screen TUI toolkit.

It takes over the terminal on the alternate screen, renders a document of
addressable blocks one diffed row at a time, owns its own scrollback, and
keeps pinned bands (fixed top and bottom regions, the frame's own footer)
that never scroll away.

Three layers carry it:

* :mod:`motui.core` -- the core and the root of the dependency graph:
  the frozen :class:`~motui.core.block.Component` protocol and the
  addressable ``Block`` document model, the
  :class:`~motui.core.lines.Line` / :class:`~motui.core.lines.Segment`
  row primitive, :class:`~motui.core.style.Style` /
  :class:`~motui.core.theme.Theme`, the measuring helpers, the event
  model, the render core (:class:`~motui.core.screen.Screen`,
  :class:`~motui.core.viewport.Viewport`,
  :class:`~motui.core.painter.Painter`), the frame model
  (:class:`~motui.core.frame.Pane`, :class:`~motui.core.frame.Rect`),
  the selection kernel (:class:`~motui.core.selection.Selection`,
  :func:`~motui.core.selection.highlight`,
  :func:`~motui.core.selection.extract`), and raw terminal bytes into
  events: the pure :class:`~motui.core.KeyDecoder`, the keymaps and the
  terminal key sources.
* :mod:`motui.widgets` -- the generic component library: the renderers plus
  the minimal action primitives, the Markdown rule registries under
  :mod:`motui.widgets.markdown` and the zero-dependency highlighting seam in
  :mod:`motui.widgets.syntax`.
* :mod:`motui.app` -- the high-level :class:`~motui.app.application.App`
  (driver + default interaction policy) and the strategy tiers it composes:
  :class:`~motui.app.TUI`, :class:`~motui.app.focus.FocusManager`,
  :class:`~motui.app.pointer.Pointer`,
  :class:`~motui.app.gesture.SelectionGesture` (with
  :func:`~motui.app.gesture.copy_on_select`),
  :class:`~motui.app.find.Find`, the blocking layer
  (:class:`~motui.app.modal.Modal` with
  :class:`~motui.app.command_palette.CommandPalette`), the overlays
  (:class:`~motui.app.overlays.Toasts`,
  :class:`~motui.app.overlays.Tooltip`,
  :class:`~motui.app.overlays.Stats`), the pane chrome
  (:class:`~motui.app.scrollbar.Scrollbar`) and the command registry
  (:class:`~motui.app.commands.Command`,
  :class:`~motui.app.commands.CommandRegistry`).

The headless helpers :mod:`motui.testing`
(:func:`~motui.testing.headless_tui`,
:func:`~motui.testing.snapshot`) sit beside the app layer.

This module is the curated face: the names one application needs to
start, in one import line.  The root carries :class:`App` and the low-level
:class:`TUI`, the styling vocabulary (:class:`Theme`, :data:`DEFAULT_THEME`,
:class:`ColorPalette`, :class:`Color`, :class:`Glyphs`, :class:`Border`,
:class:`Style`), the component base (:class:`Component`, :class:`Widget`,
:class:`Styles`), the row primitive (:class:`Line`, :class:`Segment`), the
event values (the key, mouse, paste, resize and focus events), the common
content, editing, data and modal components, and the two headless helpers.
Everything else stays public at its own layer namespace::

    from motui import App, Input, Markdown           # the root: the curated face
    from motui.widgets import Row, Panel, Diff       # a layer: the whole library
    from motui.core import Style, Line, Selection    # the core seam
    from motui.core import DEFAULT_INPUT_KEYMAP
    from motui.app import TUI, FocusManager, Pointer, Find, Tooltip

The deep seams stay public at their own module paths -- the painter, the
viewport layout, the document model, the frame and the selection kernel
under :mod:`motui.core`, the byte decoder beside them, and
the Markdown rule registries and the highlighter protocol under
:mod:`motui.widgets` -- for hosts that reach below the layers.

Dependencies point one way: the core depends on nothing outside itself,
``widgets`` builds on it, and the app layer and the headless helpers
compose them from above.
"""

from importlib.metadata import PackageNotFoundError, version

#: The distribution version, read from the installed metadata so the wheel's
#: number is the only place it can drift from.  A source checkout that was
#: never installed carries no metadata and falls back to the number of the
#: release it is cut from.
try:
    __version__ = version("motui")
except PackageNotFoundError:  # pragma: no cover - a pure source checkout
    __version__ = "1.2.1"

from .app import App, CommandPalette, Modal, TUI
from .core import (
    DEFAULT_THEME,
    Border,
    Color,
    ColorPalette,
    Component,
    FocusEvent,
    Glyphs,
    KeyEvent,
    Line,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
    Segment,
    Style,
    Styles,
    Text,
    Theme,
    Widget,
)
from .testing import headless_tui, snapshot
from .widgets import (
    Button,
    Checkbox,
    Column,
    Dialog,
    Editor,
    Input,
    Link,
    List,
    Markdown,
    MultiSelect,
    Option,
    Panel,
    Row,
    ScrollView,
    Select,
    Table,
    Tree,
)

__all__ = [
    "DEFAULT_THEME",
    "App",
    "Border",
    "Button",
    "Checkbox",
    "Color",
    "ColorPalette",
    "Column",
    "CommandPalette",
    "Component",
    "Dialog",
    "Editor",
    "FocusEvent",
    "Glyphs",
    "Input",
    "KeyEvent",
    "Line",
    "Link",
    "List",
    "Markdown",
    "Modal",
    "MouseEvent",
    "MultiSelect",
    "Option",
    "Panel",
    "PasteEvent",
    "ResizeEvent",
    "Row",
    "ScrollView",
    "Segment",
    "Select",
    "Style",
    "Styles",
    "TUI",
    "Table",
    "Text",
    "Theme",
    "Tree",
    "Widget",
    "headless_tui",
    "snapshot",
]
