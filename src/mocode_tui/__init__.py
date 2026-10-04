"""mocode-tui: a full-screen block-document TUI toolkit.

Each wave appends its exports as it lands: W1 contributed the primitives, W2
the render core (screen/viewport/painter); keys/app/components/testing follow.
The final public face lands when W4 closes, per the spec group's module
contract table.
"""

from .block import Block, BlockState, Component, Document
from .lines import Line, Segment, wrap_line
from .painter import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen
from .style import Style
from .text import visible_width, wrap_text

__all__ = [
    "Block",
    "BlockState",
    "Component",
    "Document",
    "HeadlessScreen",
    "Line",
    "Painter",
    "Screen",
    "Segment",
    "Style",
    "TerminalScreen",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
