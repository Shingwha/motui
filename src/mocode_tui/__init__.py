"""mocode-tui: a full-screen block-document TUI toolkit.

The toolkit is four layers under one driver: ``core`` is the kernel -- the
frozen :class:`Component` protocol, the addressable ``Block`` document
model, the :class:`Line` / :class:`Segment` row primitive,
:class:`Style` / :class:`Theme`, the measuring helpers, the events model
and the render core (:class:`Screen`, :class:`Viewport`,
:class:`Painter`); ``keys`` turns raw terminal bytes into events (the pure
:class:`~mocode_tui.keys.KeyDecoder`, the keymaps, the terminal key
source); ``widgets`` is the generic component library; and ``chat`` is the
pi-style coding-agent layer.  :class:`TUI` (:mod:`mocode_tui.app`) composes
the kernel into a full-screen session, with the headless helpers
(:func:`~mocode_tui.testing.headless_tui` and
:func:`~mocode_tui.testing.snapshot`) beside it.  This module is the
curated face of all of it -- one import line brings in everything a host
application needs -- while the deep seams stay public at their own module
paths: the painter, the viewport layout and the document model under
:mod:`mocode_tui.core`, the byte decoder under :mod:`mocode_tui.keys`, and
the Markdown rule registries and the highlighter protocol under
:mod:`mocode_tui.widgets`, for hosts that reach below the root.
"""

from .app import EveryHandle, Hit, TUI
from .chat import Composer, EditBlock, Message, SlashPalette, StatusLine, StreamHandle, ToolBlock, Transcript
from .core import (
    ACCENT,
    DEFAULT_THEME,
    DIM,
    ERROR,
    MUTED,
    SUCCESS,
    WARNING,
    Block,
    Component,
    HeadlessScreen,
    Key,
    KeySource,
    Line,
    MouseEvent,
    Paste,
    Screen,
    ScriptedKeys,
    Segment,
    Style,
    TerminalScreen,
    Text,
    Theme,
    visible_width,
    wrap_text,
)
from .keys import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, Keymap, RawTerminalKeys
from .selection import SelectionGesture, copy_on_select
from .testing import headless_tui, snapshot
from .widgets import (
    Autocomplete,
    Column,
    Confirm,
    Divider,
    Editor,
    Input,
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
    StatusBar,
    StatusSegment,
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
    "Column",
    "Component",
    "Composer",
    "Confirm",
    "Divider",
    "EditBlock",
    "Editor",
    "EveryHandle",
    "HeadlessScreen",
    "Hit",
    "Input",
    "Key",
    "KeySource",
    "Keymap",
    "Line",
    "Markdown",
    "Message",
    "MouseEvent",
    "Notice",
    "Option",
    "Padding",
    "Panel",
    "Paste",
    "ProgressBar",
    "RawTerminalKeys",
    "Row",
    "Screen",
    "ScriptedKeys",
    "Segment",
    "Select",
    "SelectionGesture",
    "SlashPalette",
    "Spacer",
    "Spinner",
    "StatusBar",
    "StatusLine",
    "StatusSegment",
    "StreamHandle",
    "Style",
    "TUI",
    "Table",
    "Tabs",
    "TerminalScreen",
    "Text",
    "Theme",
    "ToolBlock",
    "Transcript",
    "Tree",
    "TreeNode",
    "copy_on_select",
    "headless_tui",
    "snapshot",
    "visible_width",
    "wrap_text",
]
