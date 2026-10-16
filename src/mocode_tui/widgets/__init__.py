"""Component library: renderers over the kernel.

Every component renders through the frozen protocol
``render(width) -> list[Line]`` and depends only on the kernel
(``block``/``lines``/``style``/``text``): no screen, painter, keys or app
imports.  Pure renderers hold to that one method; the interactive ones add
the controller vocabulary of the naming charter beside it -- ``Input`` /
``Editor`` consume events through ``handle(event) -> bool`` (routed by the
keymap they hold), ``Select`` / ``Confirm`` / ``Tabs`` / ``Tree`` /
``Autocomplete`` move with ``move(delta)`` (``select(index)`` on the tab
strip) and answer a mouse hit through ``click(row, col)``; the menus and
the tree add the activation verb, ``activate() -> bool``, and ``Spinner``
advances by hand -- never by reading a clock.  The action primitives
(:class:`Button`, :class:`Checkbox`, :class:`Link`) are the minimal
clickable units; the pointer tier flips ``hover`` on any component that
declares it (:class:`~mocode_tui.core.block.Hoverable`) and calls
``hover_at(row, col)`` where a component has rows.  The layout containers (:class:`Row`,
:class:`Column`, :class:`Spacer`, :class:`Padding`) are components too and
live in :mod:`mocode_tui.widgets.layout`.  This package is the import
surface for the generic component library; the conversational components
(``Message``, ``ToolBlock``, ``EditBlock`` and the ``Composer`` /
``Transcript`` controllers) live in :mod:`mocode_tui.chat`.

:class:`Text` is the kernel's plain-text component
(:mod:`mocode_tui.core.lines`, beside the measuring helpers it renders
through) and is re-exported here.  The built-in syntax-highlighting seam --
:class:`Highlighter`, :class:`RegexHighlighter` and the :func:`highlight` /
:func:`default_highlighter` entry points -- lives one level down, in
:mod:`mocode_tui.widgets.syntax`, and is imported from there.
"""

from ..core.lines import Text
from .autocomplete import Autocomplete
from .button import Button
from .checkbox import Checkbox
from .choice import Confirm, Option, Select
from .decor import Divider, Notice, Panel
from .editor import Editor
from .input import Input
from .layout import Column, Padding, Row, Spacer
from .link import Link
from .markdown import Markdown
from .progress import ProgressBar
from .spinner import Spinner
from .table import Table
from .tabs import Tabs
from .tree import Tree, TreeNode

__all__ = [
    "Autocomplete",
    "Button",
    "Checkbox",
    "Column",
    "Confirm",
    "Divider",
    "Editor",
    "Input",
    "Link",
    "Markdown",
    "Notice",
    "Option",
    "Padding",
    "Panel",
    "ProgressBar",
    "Row",
    "Select",
    "Spacer",
    "Spinner",
    "Table",
    "Tabs",
    "Text",
    "Tree",
    "TreeNode",
]
