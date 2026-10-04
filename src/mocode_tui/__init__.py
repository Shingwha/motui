"""mocode-tui: a full-screen block-document TUI toolkit.

W1 exports only the primitives that exist in this wave.  Later waves append
their exports (screen/painter/keys/app/components/testing); the final public
face lands when W4 closes, per the spec group's module contract table.
"""

from .block import Block, BlockState, Component, Document
from .lines import Line, Segment, wrap_line
from .style import Style
from .text import visible_width, wrap_text

__all__ = [
    "Block",
    "BlockState",
    "Component",
    "Document",
    "Line",
    "Segment",
    "Style",
    "visible_width",
    "wrap_line",
    "wrap_text",
]
