"""The kernel: primitives, document model, render core, and driver.

Five groups live here:

* the **primitives** -- :class:`~mocode_tui.core.style.Style` plus the
  semantic constants, :func:`~mocode_tui.core.text.visible_width` with the
  wrap/ellipsize helpers, :class:`~mocode_tui.core.lines.Line` /
  :class:`~mocode_tui.core.lines.Segment`, and every escape byte built in
  :mod:`mocode_tui.core.ansi`;
* the **events** -- :class:`~mocode_tui.core.events.Key`,
  :class:`~mocode_tui.core.events.Paste`,
  :class:`~mocode_tui.core.events.MouseEvent`, the
  :class:`~mocode_tui.core.events.KeySource` protocol and the
  :class:`~mocode_tui.core.events.ScriptedKeys` replay source;
* the **document model** -- :class:`~mocode_tui.core.block.Block`,
  :class:`~mocode_tui.core.block.Document` and the frozen
  :class:`~mocode_tui.core.block.Component` protocol;
* the **render core** -- the :class:`~mocode_tui.core.screen.Screen` surfaces,
  :class:`~mocode_tui.core.viewport.Viewport` layout and
  :class:`~mocode_tui.core.painter.Painter` row-diff painting;
* the **driver** -- :class:`~mocode_tui.core.app.TUI` (with its
  :class:`~mocode_tui.core.app.EveryHandle` periodic-callback handles and
  the :class:`~mocode_tui.core.app.Hit` mouse hit test) plus the test
  helpers :func:`~mocode_tui.core.testing.headless_tui` and
  :func:`~mocode_tui.core.testing.snapshot`.

Each layer lives in its own module -- ``style``, ``text``, ``lines``,
``ansi``, ``events``, ``block``, ``screen``, ``viewport``, ``painter``,
``app`` and ``testing`` -- and this package re-exports the public surface, so
``from mocode_tui.core import ...`` is the kernel's single import face.
Components and keys depend on the kernel; the kernel depends on neither.
"""

from .ansi import (
    CLEAR_LINE,
    ESC,
    clear_line,
    clear_screen,
    cursor_position,
    disable_mouse_tracking,
    enable_mouse_tracking,
    enable_vt,
    enter_alt_screen,
    hide_cursor,
    leave_alt_screen,
    show_cursor,
)
from .app import EveryHandle, Hit, TUI
from .block import Block, BlockState, Component, Document
from .events import Key, KeySource, MouseEvent, Paste, ScriptedKeys
from .lines import ELLIPSIS, Line, Segment, wrap_line
from .painter import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen
from .style import (
    ACCENT,
    BORDER,
    CODE,
    CURSOR,
    DIM,
    ERROR,
    FG_CODES,
    MUTED,
    NONE,
    RESET,
    SELECTION,
    SUCCESS,
    WARNING,
    Style,
)
from .testing import headless_tui, snapshot
from .text import ellipsize_tail, terminal_size, visible_width, wrap_text
from .theme import DEFAULT_THEME, Theme
from .viewport import ScreenLayout, Viewport

__all__ = [
    "ACCENT",
    "BORDER",
    "CLEAR_LINE",
    "CODE",
    "CURSOR",
    "DEFAULT_THEME",
    "DIM",
    "ELLIPSIS",
    "ERROR",
    "ESC",
    "FG_CODES",
    "MUTED",
    "NONE",
    "RESET",
    "SELECTION",
    "SUCCESS",
    "WARNING",
    "Block",
    "BlockState",
    "Component",
    "Document",
    "EveryHandle",
    "HeadlessScreen",
    "Hit",
    "Key",
    "KeySource",
    "Line",
    "MouseEvent",
    "Painter",
    "Paste",
    "Screen",
    "ScreenLayout",
    "ScriptedKeys",
    "Segment",
    "Style",
    "TUI",
    "TerminalScreen",
    "Theme",
    "Viewport",
    "clear_line",
    "clear_screen",
    "cursor_position",
    "disable_mouse_tracking",
    "ellipsize_tail",
    "enable_mouse_tracking",
    "enable_vt",
    "enter_alt_screen",
    "headless_tui",
    "hide_cursor",
    "leave_alt_screen",
    "show_cursor",
    "snapshot",
    "terminal_size",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
