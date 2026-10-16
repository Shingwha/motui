"""mocode-tui: a full-screen block-document TUI toolkit.

One driver composes four layers.  ``core`` is the kernel -- the frozen
:class:`Component` protocol, the addressable ``Block`` document model, the
:class:`Line` / :class:`Segment` row primitive, :class:`Style` /
:class:`Theme`, the measuring helpers, the event model, the render core
(:class:`Screen`, :class:`Viewport`, :class:`Painter`), the frame model
(:class:`Pane`, :class:`Frame`, :class:`Rect`) and the selection kernel
(:class:`Selection`, :func:`highlight`, :func:`extract`).  ``keys`` turns
raw terminal bytes into events (the pure
:class:`~mocode_tui.keys.KeyDecoder`, the keymaps, the terminal key
source).  ``widgets`` is the generic component library -- renderers plus
the minimal action primitives (:class:`~mocode_tui.widgets.button.Button`,
:class:`~mocode_tui.widgets.checkbox.Checkbox`,
:class:`~mocode_tui.widgets.link.Link`) -- and ``chat`` is
the coding-agent layer.  :class:`TUI` (:mod:`mocode_tui.app`) composes the
kernel into a full-screen session -- one pane, split on demand through
:meth:`~mocode_tui.app.TUI.split`, focused by press and by key -- with the
interaction tiers beside it: :class:`~mocode_tui.gesture.SelectionGesture`
turns mouse reports into document selections,
:class:`~mocode_tui.pointer.Pointer` watches the same reports for hover and
stationary clicks, and :class:`~mocode_tui.focus.FocusRing` registers the
widgets a host may focus, cycles them and routes the keys they take --
plus the headless helpers (:func:`~mocode_tui.testing.headless_tui` and
:func:`~mocode_tui.testing.snapshot`).

This module is the curated face of all of it: the one import line a host
application needs::

    from mocode_tui import Composer, Markdown, TUI, Transcript

The deep seams stay public at their own module paths -- the painter, the
viewport layout, the document model, the frame and the selection kernel
under :mod:`mocode_tui.core`, the byte decoder under
:mod:`mocode_tui.keys`, and the Markdown rule registries and the
highlighter protocol under :mod:`mocode_tui.widgets` -- for hosts that
reach below the root.
"""

from .app import EveryHandle, Hit, TUI
from .chat import Composer, EditBlock, Message, SlashPalette, StreamHandle, ToolBlock, Transcript
from .chrome import Scrollbar, Toasts
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
from .keys import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP
from .focus import FocusRing
from .gesture import SelectionGesture, copy_on_select
from .pointer import Pointer
from .testing import headless_tui, snapshot
from .widgets import (
    Autocomplete,
    Button,
    Checkbox,
    Column,
    Confirm,
    Divider,
    Editor,
    Input,
    Link,
    Markdown,
    Notice,
    Option,
    Padding,
    Panel,
    ProgressBar,
    Row,
    Select,
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
    "ERROR",
    "MUTED",
    "SUCCESS",
    "WARNING",
    "Autocomplete",
    "Block",
    "Button",
    "Checkbox",
    "Column",
    "Component",
    "Composer",
    "Confirm",
    "Divider",
    "EditBlock",
    "Editor",
    "EveryHandle",
    "FocusRing",
    "HeadlessScreen",
    "Hit",
    "Input",
    "Key",
    "Line",
    "Link",
    "Markdown",
    "Message",
    "MouseEvent",
    "Notice",
    "Option",
    "Padding",
    "Pane",
    "Panel",
    "Paste",
    "Pointer",
    "ProgressBar",
    "Row",
    "ScriptedKeys",
    "Scrollbar",
    "Segment",
    "Select",
    "Selection",
    "SelectionGesture",
    "SlashPalette",
    "Spacer",
    "Spinner",
    "StatusLine",
    "StreamHandle",
    "Style",
    "TUI",
    "Table",
    "Tabs",
    "Text",
    "Theme",
    "Toasts",
    "ToolBlock",
    "Transcript",
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
