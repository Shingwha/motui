"""The 2.0 kernel: pure values with no dependency on the 1.x core.

This wave introduces the values only; no production code imports them yet.
The package is deliberately a leaf: it may depend on the standard library and
on ``wcwidth``, and on nothing else in ``motui``.
"""

from __future__ import annotations

from .cell import Cell, Line, Segment, Surface
from .geom import Axis, Pos, Rect, Size
from .layout import Constraints, Scroll, ScrollAxis
from .text import WrapMode

__all__ = [
    "Axis",
    "Cell",
    "Constraints",
    "Line",
    "Pos",
    "Rect",
    "Scroll",
    "ScrollAxis",
    "Segment",
    "Size",
    "Surface",
    "WrapMode",
]
