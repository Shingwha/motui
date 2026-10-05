"""The kernel: primitives, events, document model, and render core.

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
  :class:`~mocode_tui.core.viewport.Viewport` layout (with the
  :data:`~mocode_tui.core.viewport.MORE_BELOW` marker row it paints when
  content waits below the window) and
  :class:`~mocode_tui.core.painter.Painter` row-diff painting;
* the **frame model** -- :class:`~mocode_tui.core.frame.Rect` and
  :func:`~mocode_tui.core.frame.split_rect` (the screen's rectangles and
  their division), plus :class:`~mocode_tui.core.frame.Frame`, the
  multi-pane compositor an advanced host drives directly;
* the **selection overlay** -- the :class:`~mocode_tui.core.selection.Selection`
  value (document-space addresses), the pure
  :func:`~mocode_tui.core.selection.highlight` overlay a composition root
  applies between layout and paint, and
  :func:`~mocode_tui.core.selection.extract`.

Each group lives in its own module -- ``style``, ``text``, ``lines``,
``ansi``, ``events``, ``block``, ``screen``, ``selection``, ``viewport``,
``painter`` and ``frame`` --
and this package re-exports the public surface, so ``from mocode_tui.core
import ...`` is the kernel's single import face.  Components and keys depend
on the kernel; the kernel depends on neither.  The driver (``TUI``) and the
headless test helpers (``headless_tui`` / ``snapshot``) used to live here and
now sit one level up, in :mod:`mocode_tui.app` and
:mod:`mocode_tui.testing`, precisely because they compose the kernel with the
``keys`` layer.
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
from .block import Block, BlockState, Component, Document
from .events import Key, KeySource, MouseEvent, Paste, ScriptedKeys
from .frame import Frame, Pane, Rect, split_rect
from .lines import ELLIPSIS, Line, Segment, wrap_line
from .painter import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen
from .selection import Selection, extract, highlight
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
from .text import Text, ellipsize_tail, terminal_size, visible_width, wrap_text
from .theme import DEFAULT_THEME, Theme
from .viewport import MORE_BELOW, ScreenLayout, Viewport

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
    "MORE_BELOW",
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
    "Frame",
    "HeadlessScreen",
    "Key",
    "KeySource",
    "Line",
    "MouseEvent",
    "Painter",
    "Pane",
    "Paste",
    "Rect",
    "Screen",
    "ScreenLayout",
    "ScriptedKeys",
    "Segment",
    "Selection",
    "Style",
    "TerminalScreen",
    "Text",
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
    "extract",
    "hide_cursor",
    "highlight",
    "leave_alt_screen",
    "show_cursor",
    "split_rect",
    "terminal_size",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
