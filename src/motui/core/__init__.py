"""The kernel: primitives, events, document model, and render core.

Six groups live here:

* the **primitives** -- :class:`~motui.core.style.Style` plus the
  semantic constants, :func:`~motui.core.text.visible_width` with the
  wrap/ellipsize helpers, the :class:`~motui.core.lines.Line` /
  :class:`~motui.core.lines.Segment` row model with the plain-text
  :class:`~motui.core.lines.Text` component and the inline-action
  lookup :func:`~motui.core.lines.action_at`, and every escape byte
  built in :mod:`motui.core.ansi`;
* the **events** -- :class:`~motui.core.events.Key`,
  :class:`~motui.core.events.Paste`,
  :class:`~motui.core.events.MouseEvent`, the
  :class:`~motui.core.events.KeySource` protocol and the
  :class:`~motui.core.events.ScriptedKeys` replay source;
* the **document model** -- :class:`~motui.core.block.Block`,
  :class:`~motui.core.block.Document`, the frozen
  :class:`~motui.core.block.Component` protocol and the interaction
  protocols a component answers -- :class:`~motui.core.block.Clickable`,
  :class:`~motui.core.block.Activable`,
  :class:`~motui.core.block.Focusable` and
  :class:`~motui.core.block.Hoverable`, plus the container coordinate
  primitives :class:`~motui.core.block.Container` and
  :func:`~motui.core.block.descend`;
* the **render core** -- the :class:`~motui.core.screen.Screen` surfaces,
  :class:`~motui.core.viewport.Viewport` layout (with the
  :data:`~motui.core.viewport.MORE_BELOW` marker row it paints when
  content waits below the window) and
  :class:`~motui.core.painter.Painter` row-diff painting;
* the **frame model** -- :class:`~motui.core.frame.Rect` and
  :meth:`~motui.core.frame.Split.rects` (the screen's rectangles and
  their division), plus :class:`~motui.core.frame.Frame`, the
  multi-pane compositor an advanced host drives directly;
* the **selection overlay** -- the :class:`~motui.core.selection.Selection`
  value (document-space addresses), the pure
  :func:`~motui.core.selection.highlight` overlay a composition root
  applies between layout and paint, and
  :func:`~motui.core.selection.extract`.

Each group lives in its own module -- ``style``, ``text``, ``lines``,
``ansi``, ``events``, ``block``, ``screen``, ``viewport``, ``painter``,
``frame`` and ``selection`` -- and this package re-exports the public
surface, so ``from motui.core import ...`` is the kernel's single
import face.  The kernel depends on nothing outside itself: the components
and the keys depend on it, never the other way around, and the driver
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
    descend,
)
from .events import Key, KeySource, MouseEvent, Paste, ScriptedKeys
from .frame import Frame, Pane, Rect
from .lines import ELLIPSIS, Line, Segment, Text, action_at, wrap_line
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
    "Activable",
    "Block",
    "BlockState",
    "Clickable",
    "Component",
    "Container",
    "Document",
    "Focusable",
    "Frame",
    "HeadlessScreen",
    "Hoverable",
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
    "show_cursor",
    "terminal_size",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
