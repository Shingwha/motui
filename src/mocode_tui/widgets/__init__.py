"""Component library: renderers that turn state into rows.

Each component implements the frozen protocol ``render(width) -> list[Line]``
and depends only on the kernel (``block``/``lines``/``style``/``text``): no
screen, painter, keys or app imports.  The layout containers (:class:`Row`,
:class:`Column`, :class:`Spacer`, :class:`Padding`) are components too and
live in :mod:`mocode_tui.widgets.layout`.  This package is the import
surface for the generic component library; the pi-style chat components
(``Message``, ``ToolBlock``, ``EditBlock``, and the ``Composer`` /
``Transcript`` controllers) live in :mod:`mocode_tui.chat` and are no
longer re-exported here.  The built-in syntax-highlighting seam
(:class:`Highlighter`, :class:`RegexHighlighter` and the
:func:`highlight`/:func:`default_highlighter` entry points) lives here as
well, in :mod:`mocode_tui.widgets.syntax`.
"""

from .autocomplete import Autocomplete
from .choice import Confirm, Option, Select
from .chrome import Divider, Notice, Panel
from .editor import Editor
from .input import Input
from .layout import Column, Padding, Row, Spacer
from .markdown import Markdown
from .progress import ProgressBar
from .spinner import Spinner
from .status import StatusBar, StatusSegment
from .syntax import Highlighter, RegexHighlighter, default_highlighter, highlight
from .table import Table
from .tabs import Tabs
from .text import Text
from .tree import Tree, TreeNode

__all__ = [
    "Autocomplete",
    "Column",
    "Confirm",
    "Divider",
    "Editor",
    "Highlighter",
    "Input",
    "Markdown",
    "Notice",
    "Option",
    "Padding",
    "Panel",
    "ProgressBar",
    "RegexHighlighter",
    "Row",
    "Select",
    "Spacer",
    "Spinner",
    "StatusBar",
    "StatusSegment",
    "Table",
    "Tabs",
    "Text",
    "Tree",
    "TreeNode",
    "default_highlighter",
    "highlight",
]
