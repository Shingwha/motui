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
from dataclasses import replace

import motui.widgets as widgets
from motui import Text
from motui.interaction import Palette
from motui.kernel import Component, visible_width
from motui.kernel.glyphs import GLYPHS, Border
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
    "Autocomplete": lambda: Autocomplete(
        [Option("alpha"), Option("beta")], glyphs=replace(GLYPHS, cursor=">")
    ),
    "Button": lambda: Button("Ship it"),
    "Checkbox": lambda: Checkbox(
        "Trace", glyphs=replace(GLYPHS, check_on="[x]", check_off="[ ]")
    ),
    "CheckboxGroup": lambda: CheckboxGroup(["one", _WIDE]),
    "Collapsible": lambda: Collapsible(
        "foldable", Text(_WIDE), glyphs=replace(GLYPHS, fold_open="+", fold_closed="-")
    ),
    "Column": lambda: Column([Text("a"), Text("b")], gap=1),
    "ComboBox": lambda: ComboBox([Option("alpha"), Option("beta")]),
    "ContextMenu": lambda: ContextMenu([Option("alpha"), Option("beta")]),
    "Delegate": lambda: Delegate(Text(_WIDE)),
    "Dialog": lambda: Dialog(
        "Proceed?", Text("body"), ["OK", "Cancel"], border=Border.rounded()
    ),
    "Diff": lambda: Diff("a\nb\nc\nd", "a\nB\nc\nd\ne"),
    "Divider": lambda: Divider(label="section", char="="),
    "Editor": lambda: Editor(text="line one\nline two"),
    "Form": lambda: Form([Field("name", Input())]),
    "Input": lambda: Input(placeholder="type here", glyphs=replace(GLYPHS, prompt=">")),
    "Link": lambda: Link("Read the README"),
    "List": lambda: List(
        ["alpha", _WIDE, "gamma"],
        window=2,
        glyphs=replace(GLYPHS, cursor=">", more_up="^", more_down="v"),
    ),
    "Markdown": lambda: Markdown(
        "# Title\n\nA paragraph with **bold** and 中文 wide text.\n\n- one\n- two\n\n"
        "> quoted\n\n```python\nx = 1\n```\n",
        glyphs=replace(GLYPHS, check_on="[x]", check_off="[ ]"),
    ),
    "MenuBar": lambda: MenuBar(["File", "Edit"], glyphs=replace(GLYPHS, vertical_rule="|")),
    "NavList": lambda: NavList(["one", "two", "three"], glyphs=replace(GLYPHS, rail="|")),
    "Notice": lambda: Notice(
        "something happened", level="error", glyphs=replace(GLYPHS, notice_error="x")
    ),
    "Padding": lambda: Padding(Text("inner"), left=2, right=2, top=1),
    "Panel": lambda: Panel(Text("inner"), title="box", border=Border.double()),
    "ProgressBar": lambda: ProgressBar(0.4, label="work"),
    "RadioGroup": lambda: RadioGroup(["one", _WIDE, "three"]),
    "Row": lambda: Row([Text("a"), Text("b")], gap=1),
    "ScrollView": lambda: ScrollView(
        Text(_WIDE), height=2, scrollbar=True, glyphs=replace(GLYPHS, bar_full="#", bar_empty=".")
    ),
    "Select": lambda: Select(
        [Option("one"), Option("two")], title="pick", glyphs=replace(GLYPHS, cursor=">")
    ),
    "ShortcutBar": lambda: ShortcutBar([("c-n", "next")], glyphs=replace(GLYPHS, separator=" | ")),
    "Slider": lambda: Slider(
        4, minimum=0, maximum=10, glyphs=replace(GLYPHS, slider_track="-", slider_thumb="o")
    ),
    "Spacer": lambda: Spacer(2),
    "Spinner": lambda: Spinner("working"),
    "StatusLine": lambda: StatusLine(left=("ready",), right=("60 fps",)),
    "Table": lambda: Table(
        ["name", "value"], [["alpha", "1"]], grid=Border.ascii()
    ),
    "Tabs": lambda: Tabs(["one", "two", "three"], glyphs=replace(GLYPHS, vertical_rule="|")),
    "Text": lambda: Text(_WIDE),
    "Tree": lambda: Tree(
        [TreeNode("root", [TreeNode("child")], expanded=True)],
        glyphs=replace(GLYPHS, fold_open="+", fold_closed="-"),
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
    cases.append(("Palette", lambda: Palette(headless_tui(80, 8), [Option("/one")], glyphs=replace(GLYPHS, prompt=">"))))

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
