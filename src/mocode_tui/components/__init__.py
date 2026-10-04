"""Component library: renderers that turn state into rows.

Each component implements the frozen protocol ``render(width) -> list[Line]``
and depends only on the kernel (``block``/``lines``/``style``/``text``):
no screen, painter, keys or app imports.  Exports grow as waves land; the
final face of this package is collected in W3's last commit.
"""

from .chrome import Divider, Notice, Panel
from .text import Markdown, Text

__all__ = ["Divider", "Markdown", "Notice", "Panel", "Text"]
