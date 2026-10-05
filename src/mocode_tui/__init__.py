"""mocode-tui: a full-screen block-document TUI toolkit.

Four layers compose the toolkit -- ``core`` (the kernel: primitives,
document model, render core, driver), ``keys`` (the event model, the byte
decoder, the keymaps, the key sources), ``widgets`` (the generic component
library) and ``chat`` (the pi-style coding-agent components) -- and this
module is their curated public face: one import line brings in everything a
host application needs.

* :class:`~mocode_tui.core.app.TUI` drives a full-screen session, with
  :class:`~mocode_tui.core.app.EveryHandle` (periodic callbacks) and
  :class:`~mocode_tui.core.app.Hit` (the mouse hit test) beside it;
* :class:`~mocode_tui.core.block.Document` / :class:`Block` /
  :class:`BlockState` model addressable content through the frozen
  :class:`Component` protocol (``render(width) -> list[Line]``), rendered
  by :class:`Painter` onto a :class:`Screen`;
* the render core (:class:`Viewport`, :class:`ScreenLayout`) and its
  surfaces (:class:`TerminalScreen`, :class:`HeadlessScreen`) sit behind
  those names too;
* :class:`~mocode_tui.keys.KeyDecoder` and the key sources turn terminal
  input into events, and :data:`Keymap` with the two shipped default
  tables (:data:`DEFAULT_INPUT_KEYMAP`, :data:`DEFAULT_EDITOR_KEYMAP`)
  binds editing keys for :class:`Input` / :class:`Editor`;
* the component library renders state into rows -- from ``Text``,
  ``Input``, ``Select`` and ``Markdown`` through ``Table``, ``Tabs``,
  ``Tree``, ``ProgressBar``, ``Editor``, ``Autocomplete`` and the ``Row``
  / ``Column`` / ``Spacer`` / ``Padding`` layout containers;
* the chat layer (:mod:`mocode_tui.chat`) owns the pi-style coding-agent
  pieces -- ``Message``, ``ToolBlock``, ``EditBlock``, ``StatusLine``,
  ``SlashPalette`` and the ``Composer`` / ``Transcript`` controllers --
  exported at the root from their new home;
* :class:`Style` and :class:`Theme` (with the shipped
  :data:`~mocode_tui.core.theme.DEFAULT_THEME`, the semantic constants and
  :data:`~mocode_tui.core.style.FG_CODES`) carry every styling default:
  components take an explicit ``style=`` plus an optional ``theme=`` and
  resolve explicit > theme > ``DEFAULT_THEME`` at render;
* :class:`Line` / :class:`Segment` (with :func:`~mocode_tui.core.lines.wrap_line`)
  are the row primitive, and :func:`visible_width` / :func:`wrap_text` /
  :func:`ellipsize_tail` are the toolkit's measuring truth (width / wrap /
  truncate);
* :func:`~mocode_tui.core.testing.headless_tui` and
  :func:`~mocode_tui.core.testing.snapshot` make the whole toolkit testable
  without a terminal, and :class:`Highlighter` /
  :class:`RegexHighlighter` (with :func:`highlight` /
  :func:`default_highlighter`) are the injectable syntax-highlighting seam.
"""

from .chat import Composer, EditBlock, Message, SlashPalette, StatusLine, StreamHandle, ToolBlock, Transcript
from .core import (
    ACCENT,
    BORDER,
    CODE,
    CURSOR,
    DEFAULT_THEME,
    DIM,
    ERROR,
    FG_CODES,
    MUTED,
    NONE,
    RESET,
    SELECTION,
    SUCCESS,
    WARNING,
    Block,
    BlockState,
    Component,
    Document,
    EveryHandle,
    HeadlessScreen,
    Hit,
    Line,
    Painter,
    Screen,
    ScreenLayout,
    Segment,
    Style,
    TUI,
    TerminalScreen,
    Theme,
    Viewport,
    ellipsize_tail,
    headless_tui,
    snapshot,
    visible_width,
    wrap_line,
    wrap_text,
)
from .keys import (
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    Key,
    KeyDecoder,
    KeySource,
    Keymap,
    MouseEvent,
    Paste,
    RawTerminalKeys,
    ScriptedKeys,
)
from .widgets import (
    Autocomplete,
    Column,
    Confirm,
    Divider,
    Editor,
    Highlighter,
    Input,
    Markdown,
    Notice,
    Option,
    Padding,
    Panel,
    ProgressBar,
    RegexHighlighter,
    Row,
    Select,
    Spacer,
    Spinner,
    StatusBar,
    StatusSegment,
    Table,
    Tabs,
    Text,
    Tree,
    TreeNode,
    default_highlighter,
    highlight,
)

__all__ = [
    "ACCENT",
    "BORDER",
    "CODE",
    "CURSOR",
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "DEFAULT_THEME",
    "DIM",
    "ERROR",
    "FG_CODES",
    "MUTED",
    "NONE",
    "RESET",
    "SELECTION",
    "SUCCESS",
    "WARNING",
    "Autocomplete",
    "Block",
    "BlockState",
    "Column",
    "Component",
    "Composer",
    "Confirm",
    "Divider",
    "Document",
    "EditBlock",
    "Editor",
    "EveryHandle",
    "HeadlessScreen",
    "Highlighter",
    "Hit",
    "Input",
    "Key",
    "KeyDecoder",
    "KeySource",
    "Keymap",
    "Line",
    "Markdown",
    "Message",
    "MouseEvent",
    "Notice",
    "Option",
    "Padding",
    "Painter",
    "Panel",
    "Paste",
    "ProgressBar",
    "RawTerminalKeys",
    "RegexHighlighter",
    "Row",
    "Screen",
    "ScreenLayout",
    "ScriptedKeys",
    "Segment",
    "Select",
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
    "Viewport",
    "default_highlighter",
    "ellipsize_tail",
    "headless_tui",
    "highlight",
    "snapshot",
    "visible_width",
    "wrap_line",
    "wrap_text",
]