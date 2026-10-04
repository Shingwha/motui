"""mocode-tui: a full-screen block-document TUI toolkit.

Each wave appends its exports as it lands: W1 contributed the primitives, W2
the render core (screen/viewport/painter), W3 the component library and its
layout containers (Row/Column; the components themselves are exported from
``mocode_tui.components``).  The final public face lands when W4 closes, per
the spec group's module contract table.
"""

from .block import Block, BlockState, Component, Document
from .layout import Column, Row
from .lines import Line, Segment, wrap_line
from .painter import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen
from .style import Style
from .text import visible_width, wrap_text

__all__ = [
    "Block",
    "BlockState",
    "Column",
    "Component",
    "Document",
    "HeadlessScreen",
    "Line",
    "Painter",
    "Row",
    "Screen",
    "Segment",
    "Style",
    "TerminalScreen",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
