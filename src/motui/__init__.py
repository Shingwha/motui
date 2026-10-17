"""motui: a full-screen block-document TUI toolkit.

One driver composes four layers.  ``core`` is the kernel -- the frozen
:class:`Component` protocol, the addressable ``Block`` document model, the
:class:`Line` / :class:`Segment` row primitive, :class:`Style` /
:class:`Theme`, the measuring helpers, the event model, the render core
(:class:`Screen`, :class:`Viewport`, :class:`Painter`), the frame model
(:class:`Pane`, :class:`Frame`, :class:`Rect`), the interaction protocols a
component answers (:class:`~motui.core.block.Clickable`,
:class:`~motui.core.block.Activable`,
:class:`~motui.core.block.Focusable`,
:class:`~motui.core.block.Hoverable`,
:class:`~motui.core.block.Container`) and the selection kernel
(:class:`Selection`, :func:`highlight`, :func:`extract`).  ``keys`` turns
raw terminal bytes into events (the pure
:class:`~motui.keys.KeyDecoder`, the keymaps, the terminal key
source).  ``widgets`` is the generic component library -- the renderers plus
the minimal action primitives (:class:`~motui.widgets.button.Button`,
:class:`~motui.widgets.checkbox.Checkbox`,
:class:`~motui.widgets.link.Link`), the form widgets
(:class:`~motui.widgets.radio.Radio`,
:class:`~motui.widgets.slider.Slider`,
:class:`~motui.widgets.collapsible.Collapsible`,
:class:`~motui.widgets.shortcutbar.ShortcutBar`), the two data views
(:class:`~motui.widgets.diff.Diff`,
:class:`~motui.widgets.list.List`) and the two-column
:class:`~motui.widgets.statusline.StatusLine` and self-contained
:class:`~motui.widgets.palette.Palette`.  :class:`TUI`
(:mod:`motui.app`) composes the kernel into a full-screen session --
one pane, split on demand through
:meth:`~motui.app.TUI.split`, focused by press and by key -- with the
assembly tiers beside it: :class:`~motui.chrome.Scrollbar` /
:class:`~motui.chrome.Toasts` / :class:`~motui.chrome.Tooltip` /
:class:`~motui.chrome.Stats`
(the frame chrome, the overlay registry, and the dev readout), :class:`~motui.gesture.SelectionGesture` (mouse reports
into document selections), :class:`~motui.pointer.Pointer` (hover and
stationary clicks beside the gesture), :class:`~motui.search.Find` (the
search tier over the focused pane's document) and
:class:`~motui.focus.FocusRing` (registered targets, the cycle, the
routing table and the click policy) -- plus the headless helpers
(:func:`~motui.testing.headless_tui` and
:func:`~motui.testing.snapshot`).

This module is the curated face of all of it: the one import line a host
application needs::

    from motui import Markdown, Palette, StatusLine, TUI

The deep seams stay public at their own module paths -- the painter, the
viewport layout, the document model, the frame and the selection kernel
under :mod:`motui.core`, the byte decoder under
:mod:`motui.keys`, and the Markdown rule registries and the
highlighter protocol under :mod:`motui.widgets` -- for hosts that
reach below the root.
"""

from .app import EveryHandle, Hit, TUI
from .chrome import Scrollbar, Stats, Toasts, Tooltip
from .core import (
    ACCENT,
    DEFAULT_THEME,
    DIM,
    ERROR,
    MUTED,
    Pane,
    SUCCESS,
    WARNING,
    Block,
    Component,
    HeadlessScreen,
    Key,
    Line,
    MouseEvent,
    Paste,
    ScriptedKeys,
    Segment,
    Selection,
    Style,
    Text,
    Theme,
    extract,
    highlight,
    visible_width,
    wrap_text,
)
from .keys import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, EDITOR_SUBMIT_KEYMAP
from .focus import FocusRing
from .gesture import SelectionGesture, copy_on_select
from .pointer import Pointer
from .search import Find
from .testing import headless_tui, snapshot
from .widgets import (
    Autocomplete,
    Button,
    Checkbox,
    Collapsible,
    Column,
    Confirm,
    Diff,
    Divider,
    Editor,
    Input,
    Link,
    List,
    Markdown,
    Notice,
    Option,
    Padding,
    Palette,
    Panel,
    ProgressBar,
    Radio,
    Row,
    Select,
    ShortcutBar,
    Slider,
    Spacer,
    Spinner,
    StatusLine,
    Table,
    Tabs,
    Tree,
    TreeNode,
)

__all__ = [
    "ACCENT",
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "DEFAULT_THEME",
    "DIM",
    "EDITOR_SUBMIT_KEYMAP",
    "ERROR",
    "MUTED",
    "SUCCESS",
    "WARNING",
    "Autocomplete",
    "Block",
    "Button",
    "Checkbox",
    "Collapsible",
    "Column",
    "Component",
    "Confirm",
    "Diff",
    "Divider",
    "Editor",
    "EveryHandle",
    "Find",
    "FocusRing",
    "HeadlessScreen",
    "Hit",
    "Input",
    "Key",
    "Line",
    "Link",
    "List",
    "Markdown",
    "MouseEvent",
    "Notice",
    "Option",
    "Padding",
    "Palette",
    "Pane",
    "Panel",
    "Paste",
    "Pointer",
    "ProgressBar",
    "Radio",
    "Row",
    "ScriptedKeys",
    "Scrollbar",
    "Segment",
    "Select",
    "Selection",
    "SelectionGesture",
    "ShortcutBar",
    "Slider",
    "Spacer",
    "Spinner",
    "Stats",
    "StatusLine",
    "Style",
    "TUI",
    "Table",
    "Tabs",
    "Text",
    "Theme",
    "Toasts",
    "Tooltip",
    "Tree",
    "TreeNode",
    "copy_on_select",
    "extract",
    "headless_tui",
    "highlight",
    "snapshot",
    "visible_width",
    "wrap_text",
]
