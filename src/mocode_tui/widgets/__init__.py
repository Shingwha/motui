"""Component library: renderers that turn state into rows.

Each component implements the frozen protocol ``render(width) -> list[Line]``
and depends only on the kernel (``block``/``lines``/``style``/``text``): no
screen, painter, keys or app imports.  The layout containers (:class:`Row`,
:class:`Column`) are components too and live in
:mod:`mocode_tui.widgets.layout` -- this package is the single import
surface for every component, layout containers included.
"""

from .choice import Confirm, Option, Select
from .chrome import Divider, Notice, Panel
from .input import Input
from .layout import Column, Row
from .markdown import Markdown
from .message import Message
from .spinner import Spinner
from .status import StatusBar, StatusSegment
from .table import Table
from .text import Text
from .tools import EditBlock, ToolBlock

__all__ = [
    "Column",
    "Confirm",
    "Divider",
    "EditBlock",
    "Input",
    "Markdown",
    "Message",
    "Notice",
    "Option",
    "Panel",
    "Row",
    "Select",
    "Spinner",
    "StatusBar",
    "StatusSegment",
    "Table",
    "Text",
    "ToolBlock",
]
