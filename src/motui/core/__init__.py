"""The core: primitives, events, document model, render core, and input.

Nine groups live here:

* the **primitives** -- :class:`~motui.core.style.Style`,
  :func:`~motui.core.text.visible_width` with the
  wrap/ellipsize helpers, the :class:`~motui.core.lines.Line` /
  :class:`~motui.core.lines.Segment` row model with the plain-text
  :class:`~motui.core.lines.Text` component and the inline-action
  lookup :func:`~motui.core.lines.action_at`, every escape byte
  built in :mod:`motui.core.ansi`, and the two values the component
  families fold into their own state: the cursor/window arithmetic
  :class:`~motui.core.cursor.Cursor` and the multiple-selection
  :class:`~motui.core.mark.MarkSet` with the row prefix
  :func:`~motui.core.mark.mark_prefix`;
* the **clipboard** -- the one-method :class:`~motui.core.clipboard.Clipboard`
  capability with the screen-backed
  :class:`~motui.core.clipboard.ScreenClipboard` and the recording
  :class:`~motui.core.clipboard.MemoryClipboard`;
* the **events** -- the :class:`~motui.core.events.Event` base, the five
  value types :class:`~motui.core.events.KeyEvent`,
  :class:`~motui.core.events.MouseEvent`,
  :class:`~motui.core.events.PasteEvent`,
  :class:`~motui.core.events.ResizeEvent` and
  :class:`~motui.core.events.FocusEvent`, and the
  :class:`~motui.core.events.EventSource` protocol;
* the **document model** -- :class:`~motui.core.block.Block`,
  :class:`~motui.core.block.Document`, the frozen
  :class:`~motui.core.block.Component` protocol and the interaction
  protocols a component answers -- :class:`~motui.core.block.Clickable`,
  :class:`~motui.core.block.Activable`,
  :class:`~motui.core.block.Focusable`,
  :class:`~motui.core.block.Hoverable` and
  :class:`~motui.core.block.Revisioned` (the row cache's change token),
  :class:`~motui.core.block.Controller` (the event-consumption verb) and
  :class:`~motui.core.block.Resultful` (the one-shot ``take_result()``
  result), plus the container coordinate
  primitives :class:`~motui.core.block.Container` and
  :func:`~motui.core.block.descend`;
* the **render core** -- the :class:`~motui.core.screen.Screen` surfaces,
  :class:`~motui.core.viewport.Viewport` layout and
  :class:`~motui.core.painter.Painter` row-diff painting;
* the **frame model** -- :class:`~motui.core.frame.Rect` and
  :meth:`~motui.core.frame.Split.rects` (the screen's rectangles and
  their division), plus :class:`~motui.core.frame.Frame`, the
  multi-pane compositor an advanced host drives directly;
* the **hit values** -- :class:`~motui.core.hit.Hit`, the hit-test result
  the controllers pass around, with :class:`~motui.core.hit.RowRange` and
  :class:`~motui.core.hit.EveryHandle`;
* the **selection overlay** -- the :class:`~motui.core.selection.Selection`
  value (document-space addresses), the pure
  :func:`~motui.core.selection.highlight` overlay a composition root
  applies between layout and paint, and
  :func:`~motui.core.selection.extract`;
* the **input** -- the pure :class:`~motui.core.decoder.KeyDecoder`
  (``bytes -> events``), the :class:`~motui.core.keymap.Keymap` and its
  three default tables, and :class:`~motui.core.sources.RawTerminalKeys`
  with the Windows console plumbing in :mod:`motui.core.console`.

Each group lives in its own module -- ``style``, ``text``, ``lines``,
``ansi``, ``cursor``, ``mark``, ``events``, ``block``, ``screen``,
``viewport``, ``painter``, ``frame``, ``selection``, ``decoder``,
``keymap``, ``sources`` and ``console`` -- and this package re-exports the
public surface, so ``from motui.core import ...`` is the layer's single
import face.  The core depends on nothing outside itself: the widgets
build on it, never the other way around, and the driver
(:class:`~motui.app.TUI`) and the headless helpers
(:func:`~motui.testing.headless_tui` /
:func:`~motui.testing.snapshot`) sit one level up, in the layers that
compose the core.
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
    Clickable,
    Component,
    Container,
    Controller,
    Document,
    Focusable,
    Hoverable,
    Resultful,
    Revisioned,
    descend,
)
from .clipboard import Clipboard, MemoryClipboard, ScreenClipboard
from .cursor import Cursor
from .decoder import KeyDecoder
from .events import (
    Event,
    EventSource,
    FocusEvent,
    KeyEvent,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)
from .frame import Frame, Pane, Rect
from .glyphs import GLYPHS, Border, Glyphs
from .hit import EveryHandle, Hit, RowRange
from .keymap import (
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    EDITOR_SUBMIT_KEYMAP,
    Keymap,
)
from .lines import ELLIPSIS, Line, Segment, Text, action_at, wrap_line
from .mark import MarkSet, mark_prefix
from .painter import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen
from .scroll import Scrollable, ScrollState
from .selection import Selection, extract, highlight
from .sources import RawTerminalKeys
from .style import FG_CODES, NONE, RESET, Style
from .text import ellipsize_tail, terminal_size, visible_width, wrap_text
from .theme import DEFAULT_THEME, ColorPalette, Theme
from .viewport import ScreenLayout, Viewport

__all__ = [
    "CLEAR_LINE",
    "ColorPalette",
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "DEFAULT_THEME",
    "EDITOR_SUBMIT_KEYMAP",
    "ELLIPSIS",
    "ESC",
    "FG_CODES",
    "GLYPHS",
    "NONE",
    "RESET",
    "Activable",
    "Border",
    "Block",
    "Clickable",
    "Clipboard",
    "Component",
    "Container",
    "Controller",
    "Cursor",
    "Document",
    "Event",
    "EventSource",
    "EveryHandle",
    "FocusEvent",
    "Focusable",
    "Frame",
    "Glyphs",
    "HeadlessScreen",
    "Hit",
    "Hoverable",
    "KeyDecoder",
    "KeyEvent",
    "Keymap",
    "Line",
    "MarkSet",
    "MemoryClipboard",
    "MouseEvent",
    "Painter",
    "Pane",
    "PasteEvent",
    "RawTerminalKeys",
    "Rect",
    "ResizeEvent",
    "Resultful",
    "Revisioned",
    "RowRange",
    "Screen",
    "ScreenClipboard",
    "ScreenLayout",
    "ScrollState",
    "Scrollable",
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
