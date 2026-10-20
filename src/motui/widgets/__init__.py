"""Component library: renderers over the kernel.

Every component renders through the frozen protocol
``render(width) -> list[Line]`` and depends only on the kernel
(``block``/``lines``/``style``/``text``): no screen, painter, keys or app
imports.  Pure renderers hold to that one method; the interactive ones add
the controller vocabulary of the naming charter beside it -- ``Input`` /
``Editor`` consume events through ``handle(event) -> bool``
(routed by the keymap they hold while the query is theirs), ``Select`` /
``Tabs`` / ``NavList`` / ``Tree`` / ``Autocomplete`` / ``RadioGroup`` /
``Slider`` move with ``move(delta)`` (``select(index)`` on the tab strip and
the navigation rail) and answer a mouse hit
through ``click(row, col)``; the menus, the tree and the form widgets add
the activation verb,
``activate() -> bool``, ``Dialog`` runs its own button keys through
``handle(event)`` and presses a button on a click, and ``Spinner`` advances
by hand -- never by reading a clock.  The action primitives
(:class:`Button`, :class:`Checkbox`, :class:`Link`) are the minimal
clickable units; the form widgets (:class:`RadioGroup`, :class:`Slider`)
hold a
group's one selection and a stepped value, :class:`Collapsible` folds its
body away under a title row, :class:`ComboBox` is the editable field over a
filtered dropdown, and :class:`ShortcutBar` is the chrome-only
row of key hints.  :class:`Diff` renders two texts as one unified diff
(the LCS runs once, at construction) and :class:`List` is the windowed
cursor over a long sequence.  The pointer tier flips ``hover`` on any
component that
declares it (:class:`~motui.kernel.block.Hoverable`) and calls
``hover_at(row, col)`` where a component has rows.  The layout containers (:class:`Row`,
:class:`Column`, :class:`Spacer`, :class:`Padding`) are components too and
live in :mod:`motui.widgets.layout`.  :class:`Delegate` is the single-child
identity wrapper beside them: it answers every protocol surface on the
child's behalf -- the four forwarded ones plus ``child_at`` -- and holds no
state, theme or style of its own.  :class:`StatusLine` (a
two-column status row) rounds out the library; this package is the import
surface for the whole generic component library.

:class:`Text` is the kernel's plain-text component
(:mod:`motui.kernel.lines`, beside the measuring helpers it renders
through) and is re-exported here.  The built-in syntax-highlighting seam --
:class:`Highlighter`, :class:`RegexHighlighter` and the :func:`highlight` /
:func:`default_highlighter` entry points -- lives one level down, in
:mod:`motui.widgets.syntax`, and is imported from there.
"""

from ..kernel.lines import Text
from .action import Button, Checkbox, Link
from .autocomplete import Autocomplete
from .bands import RowBands
from .choice import CheckboxGroup, Option, RadioGroup, Select
from .collapsible import Collapsible
from .combobox import ComboBox
from .decor import Divider, Panel
from .delegate import Delegate
from .dialog import ButtonSpec, Dialog, confirm_dialog, prompt_dialog
from .diff import Diff
from .indicators import ProgressBar, Slider, Spinner
from .layout import Column, Padding, Row, Spacer
from .list import List
from .markdown import Markdown
from .navlist import NavList
from .rows import Notice, ShortcutBar, StatusLine
from .table import Table
from .tabs import Tabs
from .textfield import Editor, Input
from .tree import Tree, TreeNode

__all__ = [
    "Autocomplete",
    "Button",
    "ButtonSpec",
    "Checkbox",
    "CheckboxGroup",
    "Collapsible",
    "Column",
    "ComboBox",
    "Delegate",
    "Dialog",
    "Diff",
    "Divider",
    "Editor",
    "Input",
    "Link",
    "List",
    "Markdown",
    "NavList",
    "Notice",
    "Option",
    "Padding",
    "Panel",
    "ProgressBar",
    "RadioGroup",
    "Row",
    "RowBands",
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
    "confirm_dialog",
    "prompt_dialog",
]
