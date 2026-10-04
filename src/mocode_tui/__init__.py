"""mocode-tui: a full-screen block-document TUI toolkit.

The waves landed in order -- W1 the primitives (style/text/lines/ansi/block),
W2 the render core (screen/viewport/painter), W3 the component library and
its layout containers, W4 the driver (keys/app) -- and this module is now the
final public face pinned by the spec group's module contract table:

* :class:`~mocode_tui.app.TUI` drives a full-screen session;
* :class:`~mocode_tui.block.Document`/:class:`~mocode_tui.block.Block` model
  addressable content, rendered by :class:`~mocode_tui.painter.Painter` onto a
  :class:`~mocode_tui.screen.Screen`;
* :class:`~mocode_tui.keys.KeyDecoder` and the key sources turn terminal
  input into events;
* the component library (``Text``, ``Input``, ``Select``, ...) plus the
  :class:`~mocode_tui.layout.Row`/:class:`~mocode_tui.layout.Column` layout
  containers render state into rows;
* :func:`~mocode_tui.testing.headless_tui` and
  :func:`~mocode_tui.testing.snapshot` make the whole toolkit testable
  without a terminal.
"""

from .app import TUI
from .block import Block, BlockState, Component, Document
from .components import (
    Confirm,
    Divider,
    EditBlock,
    Input,
    Markdown,
    Message,
    Notice,
    Option,
    Panel,
    Select,
    Spinner,
    StatusBar,
    StatusSegment,
    Table,
    Text,
    ToolBlock,
)
from .keys import Key, KeyDecoder, KeySource, Paste, RawTerminalKeys, ScriptedKeys
from .layout import Column, Row
from .lines import Line, Segment, wrap_line
from .painter import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen
from .style import (
    ACCENT,
    BORDER,
    CODE,
    CURSOR,
    DIM,
    ERROR,
    MUTED,
    NONE,
    SELECTION,
    SUCCESS,
    WARNING,
    Style,
)
from .testing import headless_tui, snapshot

__all__ = [
    "ACCENT",
    "BORDER",
    "CODE",
    "CURSOR",
    "DIM",
    "ERROR",
    "MUTED",
    "NONE",
    "SELECTION",
    "SUCCESS",
    "WARNING",
    "Block",
    "BlockState",
    "Column",
    "Component",
    "Confirm",
    "Divider",
    "Document",
    "EditBlock",
    "HeadlessScreen",
    "Input",
    "Key",
    "KeyDecoder",
    "KeySource",
    "Line",
    "Markdown",
    "Message",
    "Notice",
    "Option",
    "Painter",
    "Panel",
    "Paste",
    "RawTerminalKeys",
    "Row",
    "Screen",
    "ScriptedKeys",
    "Segment",
    "Select",
    "Spinner",
    "StatusBar",
    "StatusSegment",
    "Style",
    "Table",
    "TUI",
    "TerminalScreen",
    "Text",
    "ToolBlock",
    "headless_tui",
    "snapshot",
    "wrap_line",
]
