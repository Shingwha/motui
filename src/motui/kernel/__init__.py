"""The 2.0 kernel: pure values and protocols, with no I/O and no terminal.

A leaf package: standard library and ``wcwidth`` only. Bytes and the
terminal live one layer up, in :mod:`motui.terminal`."""

from __future__ import annotations

from .cell import (
    ELLIPSIS,
    Cell,
    Line,
    Segment,
    Surface,
    action_at,
    cut_line,
    slice_line,
    wrap_line,
)
from .document import Component, Document, Section
from .events import (
    Event,
    EventSource,
    FocusEvent,
    KeyEvent,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)
from .frame import Chrome, Frame, Pane, Separator, Split
from .geom import Axis, Pos, Rect, Size
from .glyphs import GLYPHS, Border, Glyphs
from .hit import Hit
from .keymap import (
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    EDITOR_SUBMIT_KEYMAP,
    Keymap,
)
from .layout import Constraints, RowSpan, ScreenLayout, Scroll, ScrollAxis, Viewport
from .overlay import Overlay
from .selection import Selection, extract, highlight
from .style import FG_CODES, NONE, RESET, Color, ColorMode, Style, sgr_prefix
from .text import WrapMode, ellipsize_tail, visible_width, wrap_text
from .theme import DEFAULT_THEME, ColorPalette, Styles, Theme

__all__ = [
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "DEFAULT_THEME",
    "EDITOR_SUBMIT_KEYMAP",
    "ELLIPSIS",
    "FG_CODES",
    "GLYPHS",
    "NONE",
    "RESET",
    "Axis",
    "Border",
    "Cell",
    "Chrome",
    "Color",
    "ColorMode",
    "ColorPalette",
    "Component",
    "Constraints",
    "Document",
    "Event",
    "EventSource",
    "FocusEvent",
    "Frame",
    "Glyphs",
    "Hit",
    "KeyEvent",
    "Keymap",
    "Line",
    "MouseEvent",
    "Overlay",
    "Pane",
    "PasteEvent",
    "Pos",
    "Rect",
    "ResizeEvent",
    "RowSpan",
    "ScreenLayout",
    "Scroll",
    "ScrollAxis",
    "Section",
    "Segment",
    "Selection",
    "Separator",
    "Size",
    "Split",
    "Style",
    "Styles",
    "Surface",
    "Theme",
    "Viewport",
    "WrapMode",
    "action_at",
    "cut_line",
    "ellipsize_tail",
    "extract",
    "highlight",
    "sgr_prefix",
    "slice_line",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
