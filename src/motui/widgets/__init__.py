"""Component library: renderers over the kernel.

Every component renders through the frozen protocol
``render(width) -> list[Line]`` and depends only on the kernel
(``block``/``lines``/``style``/``text``): no screen, painter, keys or app
imports.  Pure renderers hold to that one method; the interactive ones add
the controller vocabulary of the naming charter beside it -- ``Input`` /
``Editor`` / ``Palette`` consume events through ``handle(event) -> bool``
(routed by the keymap they hold while the query is theirs), ``Select`` /
``Confirm`` / ``Tabs`` / ``Tree`` / ``Autocomplete`` / ``Radio`` /
``Slider`` move with
``move(delta)`` (``select(index)`` on the tab strip) and answer a mouse hit
through ``click(row, col)``; the menus, the tree and the form widgets add
the activation verb,
``activate() -> bool``, and ``Spinner`` advances by hand -- never by reading
a clock.  The action primitives
(:class:`Button`, :class:`Checkbox`, :class:`Link`) are the minimal
clickable units; the form widgets (:class:`Radio`, :class:`Slider`) hold a
group's one selection and a stepped value, :class:`Collapsible` folds its
body away under a title row, and :class:`ShortcutBar` is the chrome-only
row of key hints.  :class:`Diff` renders two texts as one unified diff
(the LCS runs once, at construction) and :class:`List` is the windowed
cursor over a long sequence.  The pointer tier flips ``hover`` on any
component that
declares it (:class:`~motui.kernel.block.Hoverable`) and calls
``hover_at(row, col)`` where a component has rows.  The layout containers (:class:`Row`,
:class:`Column`, :class:`Spacer`, :class:`Padding`) are components too and
live in :mod:`motui.widgets.layout`.  :class:`StatusLine` (a
two-column status row) and :class:`Palette` (a self-contained command
palette) round out the library; this package is the import surface for the
whole generic component library.

:class:`Text` is the kernel's plain-text component
(:mod:`motui.kernel.lines`, beside the measuring helpers it renders
through) and is re-exported here.  The built-in syntax-highlighting seam --
:class:`Highlighter`, :class:`RegexHighlighter` and the :func:`highlight` /
:func:`default_highlighter` entry points -- lives one level down, in
:mod:`motui.widgets.syntax`, and is imported from there.
"""

from ..kernel.lines import Text
from .autocomplete import Autocomplete
from .button import Button
from .checkbox import Checkbox
from .choice import Confirm, Option, Select
from .collapsible import Collapsible
from .decor import Divider, Notice, Panel
from .diff import Diff
from .editor import Editor
from .input import Input
from .layout import Column, Padding, Row, Spacer
from .link import Link
from .list import List
from .markdown import Markdown
from .palette import Palette
from .progress import ProgressBar
from .radio import Radio
from .shortcutbar import ShortcutBar
from .slider import Slider
from .spinner import Spinner
from .statusline import StatusLine
from .table import Table
from .tabs import Tabs
from .tree import Tree, TreeNode

__all__ = [
    "Autocomplete",
    "Button",
    "Checkbox",
    "Collapsible",
    "Column",
    "Confirm",
    "Diff",
    "Divider",
    "Editor",
    "Input",
    "Link",
    "List",
    "Markdown",
    "Notice",
    "Option",
    "Padding",
    "Palette",
    "Panel",
    "ProgressBar",
    "Radio",
    "Row",
    "Select",
    "ShortcutBar",
    "Slider",
    "Spacer",
    "Spinner",
    "StatusLine",
    "Table",
    "Tabs",
    "Text",
    "Tree",
    "TreeNode",
]
