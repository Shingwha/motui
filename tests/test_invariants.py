"""Rendering invariants: every public component survives every awkward width.

The matrix is the shipped component surface.  For each component and each
width the three properties are the contract:

* **bounded** -- no row is wider than the width it was rendered for;
* **idempotent** -- a second ``render(width)`` answers the same rows;
* **drift-free** -- rendering at another width in between does not change
  what ``width`` renders.

Everything is freshly built per case, so one case cannot leak state into the
next.  The matrix is complete by construction: adding a public ``Component``
class without a factory fails the completeness test.
"""

from __future__ import annotations

import inspect

import motui.widgets as widgets
from motui import Text
from motui.interaction import Palette
from motui.kernel import Component, visible_width
from motui.testing import headless_tui
from motui.widgets import (
    Autocomplete,
    Button,
    Checkbox,
    CheckboxGroup,
    Collapsible,
    Column,
    ComboBox,
    ContextMenu,
    Delegate,
    Dialog,
    Diff,
    Divider,
    Editor,
    Field,
    Form,
    Input,
    Link,
    List,
    Markdown,
    MenuBar,
    NavList,
    Notice,
    Option,
    Padding,
    Panel,
    ProgressBar,
    RadioGroup,
    Row,
    ScrollView,
    Select,
    ShortcutBar,
    Slider,
    Spacer,
    Spinner,
    StatusLine,
    Table,
    Tabs,
    TreeNode,
    Tree,
)

WIDTHS = (0, 1, 2, 3, 7, 20, 80)

_WIDE = "a long line with 中文 wide characters and words longer than any tiny width"

CASES = {
    "Autocomplete": lambda: Autocomplete([Option("alpha"), Option("beta")]),
    "Button": lambda: Button("Ship it"),
    "Checkbox": lambda: Checkbox("Trace"),
    "CheckboxGroup": lambda: CheckboxGroup(["one", _WIDE]),
    "Collapsible": lambda: Collapsible("foldable", Text(_WIDE)),
    "Column": lambda: Column([Text("a"), Text("b")], gap=1),
    "ComboBox": lambda: ComboBox([Option("alpha"), Option("beta")]),
    "ContextMenu": lambda: ContextMenu([Option("alpha"), Option("beta")]),
    "Delegate": lambda: Delegate(Text(_WIDE)),
    "Dialog": lambda: Dialog("Proceed?", Text("body"), ["OK", "Cancel"]),
    "Diff": lambda: Diff("a\nb\nc\nd", "a\nB\nc\nd\ne"),
    "Divider": lambda: Divider(label="section"),
    "Editor": lambda: Editor(text="line one\nline two"),
    "Form": lambda: Form([Field("name", Input())]),
    "Input": lambda: Input(placeholder="type here"),
    "Link": lambda: Link("Read the README"),
    "List": lambda: List(["alpha", _WIDE, "gamma"], window=2),
    "Markdown": lambda: Markdown(
        "# Title\n\nA paragraph with **bold** and 中文 wide text.\n\n- one\n- two\n\n"
        "> quoted\n\n```python\nx = 1\n```\n"
    ),
    "MenuBar": lambda: MenuBar(["File", "Edit"]),
    "NavList": lambda: NavList(["one", "two", "three"]),
    "Notice": lambda: Notice("something happened", level="error"),
    "Padding": lambda: Padding(Text("inner"), left=2, right=2, top=1),
    "Panel": lambda: Panel(Text("inner"), title="box"),
    "ProgressBar": lambda: ProgressBar(0.4, label="work"),
    "RadioGroup": lambda: RadioGroup(["one", _WIDE, "three"]),
    "Row": lambda: Row([Text("a"), Text("b")], gap=1),
    "ScrollView": lambda: ScrollView(Text(_WIDE), height=2),
    "Select": lambda: Select([Option("one"), Option("two")], title="pick"),
    "ShortcutBar": lambda: ShortcutBar([("c-n", "next")]),
    "Slider": lambda: Slider(4, minimum=0, maximum=10),
    "Spacer": lambda: Spacer(2),
    "Spinner": lambda: Spinner("working"),
    "StatusLine": lambda: StatusLine(left=("ready",), right=("60 fps",)),
    "Table": lambda: Table(["name", "value"], [["alpha", "1"]]),
    "Tabs": lambda: Tabs(["one", "two", "three"]),
    "Text": lambda: Text(_WIDE),
    "Tree": lambda: Tree(
        [TreeNode("root", [TreeNode("child")], expanded=True)]
    ),
}


def test_the_matrix_covers_every_public_component():
    public = {
        name
        for name in widgets.__all__
        if inspect.isclass(getattr(widgets, name))
        and issubclass(getattr(widgets, name), Component)
    }
    assert public == set(CASES), public.symmetric_difference(CASES)


def test_render_is_bounded_idempotent_and_drift_free():
    cases = [(name, factory) for name, factory in CASES.items()]
    cases.append(("Palette", lambda: Palette(headless_tui(80, 8), [Option("/one")])))

    for name, factory in cases:
        for width in WIDTHS:
            component = factory()
            first = component.render(width)
            for row in first:
                assert row.width <= width, f"{name}@{width}: row.width {row.width}"
                assert visible_width(row.text) <= width, (
                    f"{name}@{width}: text {row.text!r} is too wide"
                )

            assert component.render(width) == first, f"{name}@{width}: not idempotent"

            other = 80 if width != 80 else 1
            component.render(other)
            assert component.render(width) == first, f"{name}@{width}: drifted"
