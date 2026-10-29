"""motui: a layered, full-screen TUI toolkit.

The curated face for applications: ``App`` plus the styling vocabulary,
row primitive, event values and common components. Layers stay public
at their own namespaces: ``kernel`` (pure values and protocols),
``pixel`` (optional sub-cell raster), ``widgets``, ``terminal``; the app
layer composes them from above."""

from importlib.metadata import PackageNotFoundError, version

#: The distribution version, read from the installed metadata so the wheel's
#: number is the only place it can drift from.  A source checkout that was
#: never installed carries no metadata and falls back to the number of the
#: release it is cut from.
try:
    __version__ = version("motui")
except PackageNotFoundError:  # pragma: no cover - a pure source checkout
    __version__ = "2.1.0"

from .app import App, CommandPalette, Modal
from .kernel import (
    DEFAULT_THEME,
    Border,
    Color,
    ColorPalette,
    Component,
    FocusEvent,
    Glyphs,
    KeyEvent,
    Line,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
    Segment,
    Style,
    Styles,
    Theme,
)
from .testing import headless_tui, snapshot
from .widgets import (
    Button,
    Checkbox,
    Column,
    Dialog,
    Editor,
    Input,
    Link,
    List,
    Markdown,
    MultiSelect,
    Option,
    Panel,
    Row,
    ScrollPanel,
    Select,
    Table,
    Text,
    Tree,
    Widget,
)

__all__ = [
    "DEFAULT_THEME",
    "App",
    "Border",
    "Button",
    "Checkbox",
    "Color",
    "ColorPalette",
    "Column",
    "CommandPalette",
    "Component",
    "Dialog",
    "Editor",
    "FocusEvent",
    "Glyphs",
    "Input",
    "KeyEvent",
    "Line",
    "Link",
    "List",
    "Markdown",
    "Modal",
    "MouseEvent",
    "MultiSelect",
    "Option",
    "Panel",
    "PasteEvent",
    "ResizeEvent",
    "Row",
    "ScrollPanel",
    "Segment",
    "Select",
    "Style",
    "Styles",
    "Table",
    "Text",
    "Theme",
    "Tree",
    "Widget",
    "headless_tui",
    "snapshot",
]
