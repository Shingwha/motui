"""mocode-tui: a full-screen block-document TUI toolkit.

The waves landed in order -- W1 the primitives (style/text/lines/ansi/block),
W2 the render core (screen/viewport/painter), W3 the component library and
its layout containers, W4 the driver (keys/app) -- and this module is now the
final public face pinned by the spec group's module contract table:

* :class:`~mocode_tui.core.app.TUI` drives a full-screen session;
* :class:`~mocode_tui.core.block.Document`/:class:`~mocode_tui.core.block.Block`
  model addressable content, rendered by
  :class:`~mocode_tui.core.painter.Painter` onto a
  :class:`~mocode_tui.core.screen.Screen`;
* :class:`~mocode_tui.keys.KeyDecoder` and the key sources turn terminal
  input into events;
* the component library (``Text``, ``Input``, ``Select``, ...) plus the
  :class:`~mocode_tui.widgets.layout.Row`/:class:`~mocode_tui.widgets.layout.Column`
  layout containers render state into rows;
* :func:`~mocode_tui.core.text.visible_width`,
  :func:`~mocode_tui.core.text.wrap_text` and
  :func:`~mocode_tui.core.text.ellipsize_tail` are the toolkit's measuring
  truth (width / wrap / truncate), exported straight at the package root;
* :func:`~mocode_tui.core.testing.headless_tui` and
  :func:`~mocode_tui.core.testing.snapshot` make the whole toolkit testable
  without a terminal;
* :class:`~mocode_tui.core.theme.Theme` (and the shipped
  :data:`~mocode_tui.core.theme.DEFAULT_THEME`) carries every semantic style
  default: components take an explicit ``style=`` plus an optional
  ``theme=``, and resolve explicit > theme > ``DEFAULT_THEME`` at render.
"""

from .core import (
    ACCENT,
    BORDER,
    CODE,
    CURSOR,
    DEFAULT_THEME,
    DIM,
    ERROR,
    MUTED,
    NONE,
    SELECTION,
    SUCCESS,
    WARNING,
    Block,
    BlockState,
    Component,
    Document,
    HeadlessScreen,
    Line,
    Painter,
    Screen,
    Segment,
    Style,
    TUI,
    TerminalScreen,
    Theme,
    ellipsize_tail,
    headless_tui,
    snapshot,
    visible_width,
    wrap_line,
    wrap_text,
)
from .keys import (
    Key,
    KeyDecoder,
    KeySource,
    MouseEvent,
    Paste,
    RawTerminalKeys,
    ScriptedKeys,
)
from .widgets import (
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
from .widgets.layout import Column, Row

__all__ = [
    "ACCENT",
    "BORDER",
    "CODE",
    "CURSOR",
    "DEFAULT_THEME",
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
    "MouseEvent",
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
    "Theme",
    "ToolBlock",
    "ellipsize_tail",
    "headless_tui",
    "snapshot",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
