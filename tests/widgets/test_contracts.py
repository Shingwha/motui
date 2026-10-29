"""Cross-widget contracts: one test, every family that shares the verb."""

from __future__ import annotations

from dataclasses import replace

from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import (
    Align,
    Autocomplete,
    Button,
    Canvas,
    Checkbox,
    CheckboxGroup,
    Collapsible,
    Column,
    ComboBox,
    ContextMenu,
    Dialog,
    Diff,
    Divider,
    Editor,
    Form,
    Input,
    Link,
    List,
    Markdown,
    MenuBar,
    MultiSelect,
    NavList,
    Notice,
    Option,
    Padding,
    Panel,
    ProgressBar,
    RadioGroup,
    Row,
    ScrollPanel,
    Select,
    ShortcutBar,
    Slider,
    Spacer,
    Spinner,
    Stack,
    StatusLine,
    Table,
    Tabs,
    Text,
    Tree,
    TreeNode,
)
from motui.widgets.base import (
    CURSOR_KEYMAP,
    ActionWidget,
    Container,
    CursorWidget,
    Keymap,
    ResultWidget,
    Widget,
)
from tests.testing import key

THREE = [Option("one"), Option("two"), Option("three")]
OPTIONS = [
    Option("Autocomplete", value="autocomplete"),
    Option("Checkbox", value="checkbox"),
]


def _pick_combo(combo: ComboBox) -> bool:
    combo.open = True
    return combo.on_key(key("enter"))


def test_take_reads_the_result_once():
    for build, activate, expected in [
        (lambda: Select(THREE), lambda widget: widget.on_action("activate"), "one"),
        (lambda: List(["a"]), lambda widget: widget.on_action("activate"), "a"),
        (lambda: Form([]), lambda widget: widget.on_action("activate"), {}),
        (lambda: ComboBox(OPTIONS), _pick_combo, "autocomplete"),
    ]:
        widget = build()
        assert widget.take() is None
        assert activate(widget) is True
        assert widget.take() == expected
        assert widget.take() is None
        assert activate(widget) is True
        assert widget.take() == expected


def test_a_theme_assignment_repaints_the_next_render():
    for build in [lambda: Button("Run"), lambda: Checkbox("Bold"), lambda: Select(THREE)]:
        widget = build()
        plain = widget.render(Constraints(width=20))
        mark = Style(underline=True)
        other = replace(
            DEFAULT_THEME,
            text=replace(DEFAULT_THEME.text, base=mark),
            content=replace(DEFAULT_THEME.content, accent=mark),
            rows=replace(DEFAULT_THEME.rows, inactive=mark),
        )
        widget.theme = other
        assert widget.render(Constraints(width=20)) != plain


# -- ResultWidget: one pending slot, read once -----------------------------


class _ResultProbe(ResultWidget):
    """A bare result widget: the base supplies the whole contract."""

    __slots__ = ()


def test_result_widget_take_reads_the_value_once_and_clears():
    probe = _ResultProbe()

    assert probe.take() is None
    probe._emit("value")
    assert probe.take() == "value"
    assert probe.take() is None


def test_result_widget_keeps_legal_false_zero_empty_and_none_pending():
    for value in [False, 0, "", None]:
        probe = _ResultProbe()
        probe._emit(value)
        assert probe.take() == value
        assert probe.take() is None
        # ``take`` consumed the pending slot, legal None included.
        assert probe._clear_result() is False


def test_result_widget_emit_none_is_distinct_from_no_pending():
    probe = _ResultProbe()

    assert probe._clear_result() is False
    probe._emit(None)
    # The slot is pending even though the payload is None.
    assert probe._clear_result() is True
    assert probe.take() is None
    assert probe._clear_result() is False


def test_result_widget_emit_and_clear_touch_only_when_state_changes():
    probe = _ResultProbe()
    before = probe.generation

    probe._emit(1)
    assert probe.generation == before + 1
    assert probe.take() == 1  # reading does not touch
    assert probe.generation == before + 1
    assert probe._clear_result() is False  # nothing to clear: no touch
    assert probe.generation == before + 1
    probe._emit(2)
    assert probe._clear_result() is True
    assert probe.generation == before + 3


# -- ActionWidget: the activate/toggle door and the disabled gate ----------


class _ActionProbe(ActionWidget):
    """An action widget whose verbs record the call and emit a token."""

    __slots__ = ("calls",)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.calls: list[str] = []

    def activate(self) -> bool:
        self.calls.append("activate")
        if self.disabled:
            return False
        self._emit("activated")
        return True

    def toggle(self) -> bool:
        self.calls.append("toggle")
        if self.disabled:
            return False
        self._emit("toggled")
        return True


def test_action_widget_on_action_delegates_to_activate_and_toggle():
    probe = _ActionProbe()

    assert probe.on_action("activate") is True
    assert probe.calls == ["activate"]
    assert probe.take() == "activated"
    assert probe.on_action("toggle") is True
    assert probe.calls == ["activate", "toggle"]
    assert probe.take() == "toggled"
    assert probe.on_action("prev") is False
    assert probe.calls == ["activate", "toggle"]


def test_action_widget_on_click_runs_activate():
    probe = _ActionProbe()

    assert probe.on_click(Pos(x=3, y=2)) is True
    assert probe.calls == ["activate"]
    assert probe.take() == "activated"


def test_a_disabled_action_widget_refuses_every_door():
    for build in [
        lambda: Button("x", disabled=True),
        lambda: Checkbox("x", disabled=True),
        lambda: Link("x", disabled=True),
    ]:
        control = build()

        assert control.on_action("activate") is False
        assert control.on_action("toggle") is False
        assert control.on_click(Pos()) is False
        assert control.take() is None


def test_action_widget_defaults_to_no_hint_and_enabled():
    probe = _ActionProbe()

    assert probe.hint == ""
    assert probe.disabled is False
    assert probe.activatable is True


# -- CursorWidget: state, verbs and the unified keymap ----------------------


class _CursorContract(CursorWidget):
    """A CursorWidget over a small entry list."""

    __slots__ = ("disabled_rows", "items", "wrap_rows")

    def __init__(self, items=(), *, disabled=(), wrap=False) -> None:
        super().__init__()
        self.items = list(items)
        self.disabled_rows = tuple(disabled)
        self.wrap_rows = wrap

    def _entry_count(self) -> int:
        return len(self.items)

    def _entry_at(self, index: int) -> object | None:
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def _cursor_disabled(self):
        return self.disabled_rows

    def _cursor_wraps(self) -> bool:
        return self.wrap_rows


def test_cursor_widget_state_and_verbs():
    probe = _CursorContract(["a", "b", "c"])

    assert probe.index == 0 and probe.selected == "a"
    assert probe.select(2) is True and probe.selected == "c"
    assert probe.move(-1) is True and probe.index == 1
    assert probe.home() is True and probe.index == 0
    assert probe.end() is True and probe.index == 2
    probe.items = []
    assert probe.index == 0 and probe.selected is None


def test_cursor_widget_disabled_rows_are_refused_and_stepped_over():
    probe = _CursorContract(["a", "b", "c"], disabled=(1,))

    assert probe.select(1) is False and probe.index == 0
    assert probe.move(1) is True and probe.index == 2


def test_cursor_widget_keymap_is_the_unified_table():
    probe = _CursorContract(["a", "b"])

    assert CursorWidget.keymap == CURSOR_KEYMAP
    assert probe.keymap == CURSOR_KEYMAP
    probe.keymap["j"] = "next"
    assert probe.keymap["j"] == "next"
    assert "j" not in CURSOR_KEYMAP
    assert "j" not in CursorWidget.keymap


def test_cursor_widget_bases_are_routed_by_the_unified_keymap():
    probe = _CursorContract(["a", "b"])
    probe.on_action("next")
    assert probe.index == 1
    assert probe.on_action("first") is True
    assert probe.index == 0


# -- Keymap: class default, instance copy, no write-through ----------------


class _KeymapProbe(Widget):
    """A widget that declares one family key table."""

    __slots__ = ()

    keymap = Keymap({"j": "next", "k": "prev"})


def test_keymap_answers_the_class_table_on_the_class():
    assert _KeymapProbe.keymap == {"j": "next", "k": "prev"}


def test_keymap_answers_a_private_copy_on_an_instance():
    probe = _KeymapProbe()

    assert probe.keymap == _KeymapProbe.keymap
    assert probe.keymap is not _KeymapProbe.keymap
    probe.keymap["x"] = "activate"
    assert probe.keymap["x"] == "activate"
    assert "x" not in _KeymapProbe.keymap
    assert "x" not in _KeymapProbe.keymap


def test_keymap_instance_assignment_replaces_only_that_copy():
    one, two = _KeymapProbe(), _KeymapProbe()

    one.keymap = {"a": "toggle"}
    assert one.keymap == {"a": "toggle"}
    assert two.keymap == {"j": "next", "k": "prev"}
    assert _KeymapProbe.keymap == {"j": "next", "k": "prev"}


def test_the_base_widget_keymap_is_an_empty_instance_copy():
    widget = Widget()

    assert Widget.keymap == {}
    assert widget.keymap == {}
    assert widget.keymap is not Widget.keymap
    widget.keymap["z"] = "next"
    assert Widget.keymap == {}
    assert widget.keymap == {"z": "next"}


def test_keymap_is_reexported_from_strip():
    from motui.widgets.base import Keymap as BaseKeymap
    from motui.widgets.strip import Keymap as StripKeymap

    assert StripKeymap is BaseKeymap


# -- Capability flags: one table for every public component ----------------
#
# Per-family files used to repeat one ``focusable/clickable/hoverable/
# activatable`` test each.  The table below is the single source: a
# component's flags are part of its public contract, not a render detail.

CAPABILITIES = {
    # Action family: all four doors.
    "Button": (lambda: Button("x"), (True, True, True, True)),
    "Checkbox": (lambda: Checkbox("x"), (True, True, True, True)),
    "Link": (lambda: Link("x"), (True, True, True, True)),
    # Text fields: focus and pointer, no activation verb.
    "Input": (lambda: Input(), (True, True, True, False)),
    "Editor": (lambda: Editor(), (True, True, True, False)),
    # Choice, navigation and data families: cursor + result.
    "Select": (lambda: Select(THREE), (True, True, True, True)),
    "MultiSelect": (lambda: MultiSelect(THREE), (True, True, True, True)),
    "RadioGroup": (lambda: RadioGroup(["a"]), (True, True, True, True)),
    "CheckboxGroup": (lambda: CheckboxGroup(["a"]), (True, True, True, True)),
    "List": (lambda: List(["a"]), (True, True, True, True)),
    "Table": (lambda: Table([["a"]], headers=["h"]), (True, True, True, True)),
    "Tree": (lambda: Tree([TreeNode("a")]), (True, True, True, True)),
    "Tabs": (lambda: Tabs(["a"]), (True, True, True, True)),
    "MenuBar": (lambda: MenuBar(["a"]), (True, True, True, True)),
    "NavList": (lambda: NavList(["a"]), (True, True, True, True)),
    "Autocomplete": (lambda: Autocomplete([Option("a")]), (True, True, True, True)),
    "ContextMenu": (lambda: ContextMenu([Option("a")]), (True, True, True, True)),
    # The combo is pointer-driven but has no activation verb of its own.
    "ComboBox": (lambda: ComboBox([Option("a")]), (True, True, False, True)),
    # Indicators: only the slider is interactive.
    "Slider": (lambda: Slider(1), (True, True, True, True)),
    "ProgressBar": (lambda: ProgressBar(0.5), (False, False, False, False)),
    "Spinner": (lambda: Spinner("x"), (False, False, False, False)),
    # Plain text is a pointer target for its spans, not a focus target.
    "Text": (lambda: Text("hi"), (False, True, True, False)),
    "Markdown": (lambda: Markdown("# x"), (False, True, True, False)),
    # Scrollable and foldable: focus + click, no hover/activation.
    "ScrollPanel": (
        lambda: ScrollPanel(Text("x"), height=2),
        (True, True, False, False),
    ),
    "Collapsible": (lambda: Collapsible(Text("x")), (True, True, True, True)),
    # Display-only furniture and containers.
    "StatusLine": (lambda: StatusLine(left=["a"]), (False, False, False, False)),
    "ShortcutBar": (lambda: ShortcutBar([("a", "b")]), (False, False, False, False)),
    "Notice": (lambda: Notice("x"), (False, False, False, False)),
    "Divider": (lambda: Divider(), (False, False, False, False)),
    "Spacer": (lambda: Spacer(1), (False, False, False, False)),
    "Canvas": (lambda: Canvas(width=2, height=2), (False, False, False, False)),
    "Diff": (lambda: Diff("a", "b"), (False, False, False, False)),
    "Align": (lambda: Align(Text("x")), (False, False, False, False)),
    "Stack": (lambda: Stack([Text("x")]), (False, False, False, False)),
    "Row": (lambda: Row([Text("x")]), (False, False, False, False)),
    "Column": (lambda: Column([Text("x")]), (False, False, False, False)),
    "Panel": (lambda: Panel(Text("x")), (False, False, False, False)),
    "Padding": (lambda: Padding(Text("x")), (False, False, False, False)),
    "Dialog": (lambda: Dialog(Text("x")), (False, False, False, False)),
    "Form": (lambda: Form([]), (False, False, False, False)),
    "Widget": (lambda: Widget(), (False, False, False, False)),
    "Container": (lambda: Container(), (False, False, False, False)),
}


def test_capability_flags_are_one_table_for_every_component():
    for name, (build, expected) in CAPABILITIES.items():
        widget = build()
        actual = (
            widget.focusable,
            widget.clickable,
            widget.hoverable,
            widget.activatable,
        )
        assert actual == expected, f"{name}: {actual} != {expected}"

