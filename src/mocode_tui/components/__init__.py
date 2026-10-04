"""Component library: renderers that turn state into rows.

Each component implements the frozen protocol ``render(width) -> list[Line]``
and depends only on the kernel (``block``/``lines``/``style``/``text``):
no screen, painter, keys or app imports.  Exports grow as waves land; the
final face of this package is collected in W3's last commit.
"""

from .choice import Confirm, Option, Select
from .chrome import Divider, Notice, Panel
from .input import Input
from .spinner import Spinner
from .status import StatusBar, StatusSegment
from .text import Markdown, Text

__all__ = [
    "Confirm",
    "Divider",
    "Input",
    "Markdown",
    "Notice",
    "Option",
    "Panel",
    "Select",
    "Spinner",
    "StatusBar",
    "StatusSegment",
    "Text",
]
