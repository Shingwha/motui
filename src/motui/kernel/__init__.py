"""The kernel: primitives, events, document model, and render core.

Six groups live here:

* the **primitives** -- :class:`~motui.kernel.style.Style` plus the
  semantic constants, :func:`~motui.kernel.text.visible_width` with the
  wrap/ellipsize helpers, the :class:`~motui.kernel.lines.Line` /
  :class:`~motui.kernel.lines.Segment` row model with the plain-text
  :class:`~motui.kernel.lines.Text` component and the inline-action
  lookup :func:`~motui.kernel.lines.action_at`, every escape byte
  built in :mod:`motui.kernel.ansi`, and the two values the component
  families fold into their own state: the cursor/window arithmetic
  :class:`~motui.kernel.cursor.CursorWindow` and the multiple-selection
  :class:`~motui.kernel.mark.MarkSet` with the row prefix
  :func:`~motui.kernel.mark.mark_prefix`;
* the **events** -- :class:`~motui.kernel.events.Key`,
  :class:`~motui.kernel.events.Paste`,
  :class:`~motui.kernel.events.MouseEvent`, the
  :class:`~motui.kernel.events.KeySource` protocol and the
  :class:`~motui.kernel.events.ScriptedKeys` replay source;
* the **document model** -- :class:`~motui.kernel.block.Block`,
  :class:`~motui.kernel.block.Document`, the frozen
  :class:`~motui.kernel.block.Component` protocol and the interaction
  protocols a component answers -- :class:`~motui.kernel.block.Clickable`,
  :class:`~motui.kernel.block.Activable`,
  :class:`~motui.kernel.block.Focusable`,
  :class:`~motui.kernel.block.Hoverable` and
  :class:`~motui.kernel.block.Revisioned` (the row cache's change token),
  plus the container coordinate
  primitives :class:`~motui.kernel.block.Container` and
  :func:`~motui.kernel.block.descend`;
* the **render core** -- the :class:`~motui.kernel.screen.Screen` surfaces,
  :class:`~motui.kernel.viewport.Viewport` layout and
  :class:`~motui.kernel.painter.Painter` row-diff painting;
* the **frame model** -- :class:`~motui.kernel.frame.Rect` and
  :meth:`~motui.kernel.frame.Split.rects` (the screen's rectangles and
  their division), plus :class:`~motui.kernel.frame.Frame`, the
  multi-pane compositor an advanced host drives directly;
* the **selection overlay** -- the :class:`~motui.kernel.selection.Selection`
  value (document-space addresses), the pure
  :func:`~motui.kernel.selection.highlight` overlay a composition root
  applies between layout and paint, and
  :func:`~motui.kernel.selection.extract`.

Each group lives in its own module -- ``style``, ``text``, ``lines``,
``ansi``, ``cursor``, ``mark``, ``events``, ``block``, ``screen``,
``viewport``, ``painter``, ``frame`` and ``selection`` -- and this package
re-exports the public surface, so ``from motui.kernel import ...`` is the
kernel's single import face.  The kernel depends on nothing outside
itself: the components and the keys depend on it, never the other way
around, and the driver
(:class:`~motui.app.TUI`) and the headless helpers
(:func:`~motui.testing.headless_tui` /
:func:`~motui.testing.snapshot`) sit one level up, in the layers that
compose the kernel with ``keys``.
"""

from .ansi import (
    CLEAR_LINE,
    ESC,
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
from .block import (
    Activable,
    Block,
    BlockState,
    Clickable,
    Component,
    Container,
    Document,
    Focusable,
    Hoverable,
    Revisioned,
    descend,
)
from .cursor import CursorWindow
from .events import Key, KeySource, MouseEvent, Paste, ScriptedKeys
from .frame import Frame, Pane, Rect
from .lines import ELLIPSIS, Line, Segment, Text, action_at, wrap_line
from .mark import MarkSet, mark_prefix
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
    "Activable",
    "Block",
    "BlockState",
    "Clickable",
    "Component",
    "Container",
    "CursorWindow",
    "Document",
    "Focusable",
    "Frame",
    "HeadlessScreen",
    "Hoverable",
    "Key",
    "KeySource",
    "Line",
    "MarkSet",
    "MouseEvent",
    "Painter",
    "Pane",
    "Paste",
    "Rect",
    "Revisioned",
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
    "action_at",
    "clear_screen",
    "cursor_position",
    "descend",
    "disable_mouse_tracking",
    "ellipsize_tail",
    "enable_mouse_tracking",
    "enable_vt",
    "enter_alt_screen",
    "extract",
    "hide_cursor",
    "highlight",
    "leave_alt_screen",
    "mark_prefix",
    "show_cursor",
    "terminal_size",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
