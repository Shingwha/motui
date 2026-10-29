"""Component library: renderers over the kernel.

Every component renders through ``render(c) -> Surface`` and depends only on
the kernel; interactive components add typed hooks.  This package is the
import surface for the generic library.
"""

from .action import Button, ButtonKind, Checkbox, Link
from .autocomplete import Autocomplete
from .base import Widget
from .canvas import Canvas, Sparkline
from .choice import CheckboxGroup, MultiSelect, Option, RadioGroup, Select
from .collapsible import Collapsible
from .combobox import ComboBox
from .decor import Divider, Panel
from .dialog import ButtonSpec, Dialog, confirm_dialog, prompt_dialog
from .diff import Diff
from .form import Field, Form
from .indicators import ProgressBar, Slider, Spinner
from .layout import Align, Column, Padding, Row, Spacer, Stack
from .list import List
from .markdown import Markdown
from .menubar import ContextMenu, MenuBar
from .navlist import NavList
from .pixel_canvas import LayerName, PixelCanvas
from .rows import Notice, ShortcutBar, StatusLine
from .scroll import ScrollPanel
from .table import Table
from .tabs import Tabs
from .text import Text
from .textfield import Editor, Input
from .tree import Tree, TreeNode

__all__ = [
    "Align",
    "Autocomplete",
    "Button",
    "ButtonKind",
    "ButtonSpec",
    "Canvas",
    "Checkbox",
    "CheckboxGroup",
    "Collapsible",
    "Column",
    "ComboBox",
    "ContextMenu",
    "Dialog",
    "Diff",
    "Divider",
    "Editor",
    "Field",
    "Form",
    "Input",
    "LayerName",
    "Link",
    "List",
    "Markdown",
    "MenuBar",
    "MultiSelect",
    "NavList",
    "Notice",
    "Option",
    "Padding",
    "Panel",
    "PixelCanvas",
    "ProgressBar",
    "RadioGroup",
    "Row",
    "ScrollPanel",
    "Select",
    "ShortcutBar",
    "Slider",
    "Spacer",
    "Sparkline",
    "Spinner",
    "Stack",
    "StatusLine",
    "Table",
    "Tabs",
    "Text",
    "Tree",
    "TreeNode",
    "Widget",
    "confirm_dialog",
    "prompt_dialog",
]
