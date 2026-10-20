"""Tests for motui.widgets.form: Field, navigation, validation and submit.

The rendered stack (labels, component rows, errors, gaps), the focus
mirroring, the controller-first routing, value extraction by duck typing,
validation and the one-shot submission, the container geometry and the
revision snapshot.
"""

from __future__ import annotations

import pytest

from _doubles import texts

from motui.kernel import (
    Block,
    Component,
    Container,
    KeyEvent,
    Line,
    PasteEvent,
    Revisioned,
    Theme,
)
from motui.kernel.block import Controller, Focusable
from motui.kernel.style import Style
from motui.widgets import Field, Form


class _Rows:
    """A field component: rows plus a writable ``focused`` flag."""

    def __init__(self, *rows: str, focused: bool = False) -> None:
        self.rows = list(rows)
        self.text = rows[0] if rows else ""
        self.focused = focused

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(row).fit(width) for row in self.rows]


class _ControllerRows(_Rows):
    """A field component that consumes a chosen set of key names."""

    def __init__(self, *rows: str, consumes: tuple[str, ...] = ("x",)) -> None:
        super().__init__(*rows)
        self.consumes = consumes
        self.events: list[object] = []

    def handle(self, event) -> bool:
        self.events.append(event)
        if isinstance(event, KeyEvent):
            return event.key in self.consumes
        return isinstance(event, PasteEvent)


class _RevisionedRows:
    """A mutable field component outside the form's own state."""

    def __init__(self, *rows: str) -> None:
        self.rows = list(rows)
        self.tick = 0

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(row).fit(width) for row in self.rows]

    def revision(self) -> object:
        return (tuple(self.rows), self.tick)


def _form(*fields: Field, **kwargs) -> Form:
    return Form(fields, **kwargs)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_a_form_stacks_label_component_and_error_rows():
    component = _Rows("input")
    form = _form(Field("name", component, label="Name"))
    assert texts(form, 20) == ["Name", "input"]


def test_an_empty_label_renders_no_label_row():
    form = _form(Field("age", _Rows("42")))
    assert texts(form, 20) == ["42"]


def test_the_gap_is_blank_rows_between_fields_not_after_the_last():
    form = _form(
        Field("a", _Rows("one")),
        Field("b", _Rows("two")),
        Field("c", _Rows("three")),
        gap=2,
    )
    assert texts(form, 20) == [
        "one",
        "",
        "",
        "two",
        "",
        "",
        "three",
    ]


def test_an_error_row_follows_its_component_after_a_failed_submit():
    bad = Field("age", _Rows("x"), label="Age", validate=lambda v: "not a number")
    form = _form(bad, Field("name", _Rows("ok"), label="Name"))
    assert texts(form, 20) == ["Age", "x", "Name", "ok"]
    assert form.activate() is False
    assert texts(form, 20) == ["Age", "x", "not a number", "Name", "ok"]
    bad.validate = None
    assert form.activate() is True
    assert texts(form, 20) == ["Age", "x", "Name", "ok"]


def test_labels_and_errors_use_the_theme_bands():
    accent = Style(fg="#abcdef")
    error = Style(fg="#ff0000")
    theme = Theme(accent=accent, error=error)
    field = Field("age", _Rows("x"), label="Age", validate=lambda v: "bad")
    form = Form([field], theme=theme)
    form.activate()
    rows = form.render(20)
    assert rows[0].segments[0].style == accent
    assert rows[2].segments[0].style == error


def test_every_row_is_fitted_to_the_painting_width():
    form = _form(Field("name", _Rows("x" * 40), label="a" * 40))
    rows = form.render(10)
    assert all(row.width <= 10 for row in rows)


def test_an_empty_form_renders_nothing():
    form = _form()
    assert form.render(20) == []
    assert form.fields == ()
    assert form.index == 0


# ---------------------------------------------------------------------------
# Focus and movement
# ---------------------------------------------------------------------------


def test_the_initial_index_is_clamped_and_mirrored_onto_focusable_fields():
    first, second = _Rows("a"), _Rows("b")
    form = _form(Field("a", first), Field("b", second), index=9)
    assert form.index == 1
    assert (first.focused, second.focused) == (False, True)


def test_focus_by_position_and_name_moves_and_mirrors():
    first, second = _Rows("a"), _Rows("b")
    form = _form(Field("a", first), Field("b", second))
    assert form.focus("b") is True
    assert form.index == 1
    assert (first.focused, second.focused) == (False, True)
    assert form.focus(0) is True
    assert (first.focused, second.focused) == (True, False)
    assert form.focus(0) is False  # already there
    assert form.focus("missing") is False
    assert form.focus(99) is False
    assert form.focus(-1) is False
    assert form.index == 0


def test_move_clamps_at_the_ends_and_reports_only_real_moves():
    a, b, c = _Rows("a"), _Rows("b"), _Rows("c")
    form = _form(Field("a", a), Field("b", b), Field("c", c))
    assert form.move(0) is False
    assert form.move(1) is True and form.index == 1
    assert form.move(99) is True and form.index == 2
    assert form.move(1) is False
    assert form.move(-99) is True and form.index == 0
    assert form.move(-1) is False
    assert form.move(1) is True
    assert (a.focused, b.focused, c.focused) == (False, True, False)


def test_a_non_focusable_field_is_tracked_without_a_flag():
    class Plain:
        def render(self, width: int) -> list[Line]:
            return [Line.from_text("x")]

    form = _form(Field("plain", Plain()), Field("rows", _Rows("y")))
    assert form.focus(0) is False  # already at 0
    assert form.focus(1) is True
    assert form.focus(0) is True
    assert form.index == 0


# ---------------------------------------------------------------------------
# Event routing
# ---------------------------------------------------------------------------


def test_the_focused_fields_controller_wins_over_navigation():
    field = _ControllerRows("x", consumes=("tab", "x", "enter"))
    form = _form(Field("a", field), Field("b", _Rows("y")))
    assert form.handle(KeyEvent("tab")) is True
    assert form.index == 0  # the field consumed it; the form did not move
    assert form.handle(KeyEvent("x", "x")) is True
    assert form.index == 0


def test_navigation_keys_step_and_only_consume_a_real_move():
    form = _form(Field("a", _Rows("a")), Field("b", _Rows("b")), Field("c", _Rows("c")))
    assert form.handle(KeyEvent("down")) is True and form.index == 1
    assert form.handle(KeyEvent("tab")) is True and form.index == 2
    assert form.handle(KeyEvent("tab")) is False  # the form lets the host move on
    assert form.handle(KeyEvent("up")) is True and form.index == 1
    assert form.handle(KeyEvent("s-tab")) is True and form.index == 0
    assert form.handle(KeyEvent("s-tab")) is False
    assert form.handle(KeyEvent("down", kind="release")) is False


def test_a_paste_goes_to_the_focused_field():
    field = _ControllerRows("x")
    form = _form(Field("a", field))
    assert form.handle(PasteEvent("pasted")) is True
    assert field.events == [PasteEvent("pasted")]


def test_enter_activates_the_form_and_is_always_consumed():
    submitted: list[dict[str, object]] = []
    field = Field("x", _Rows("value"))
    form = _form(field, on_submit=submitted.append)
    assert form.handle(KeyEvent("enter")) is True
    assert submitted == [{"x": "value"}]
    assert form.take_result() == {"x": "value"}


def test_enter_with_a_validation_error_is_consumed_but_not_submitted():
    submitted: list[dict[str, object]] = []
    field = Field("x", _Rows("value"), validate=lambda v: "bad")
    form = _form(field, on_submit=submitted.append)
    assert form.handle(KeyEvent("enter")) is True
    assert submitted == []
    assert form.take_result() is None
    assert field.error == "bad"


def test_an_unbound_key_is_declined():
    form = _form(Field("a", _Rows("a")))
    assert form.handle(KeyEvent("q", "q")) is False


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------


class _Text:
    def __init__(self, text):
        self.text = text

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(str(self.text))]


class _Checked:
    checked = True

    def render(self, width: int) -> list[Line]:
        return [Line.from_text("x")]


class _Selected:
    selected = "choice"

    def render(self, width: int) -> list[Line]:
        return [Line.from_text("x")]


class _Marked:
    marked = (1, 2)

    def render(self, width: int) -> list[Line]:
        return [Line.from_text("x")]


class _CallableValue:
    def value(self):
        return "called"

    def render(self, width: int) -> list[Line]:
        return [Line.from_text("x")]


class _Nothing:
    def render(self, width: int) -> list[Line]:
        return [Line.from_text("x")]


@pytest.mark.parametrize(
    "component, expected",
    [
        (_Text("text"), "text"),
        (_Checked(), True),
        (_Selected(), "choice"),
        (_Marked(), (1, 2)),
        (_CallableValue(), "called"),
        (_Nothing(), None),
    ],
)
def test_values_come_from_the_components_own_state(component, expected):
    form = _form(Field("f", component))
    assert form.activate() is True
    assert form.take_result() == {"f": expected}


def test_the_value_attribute_wins_over_text():
    class Both:
        value = "v"
        text = "t"

        def render(self, width: int) -> list[Line]:
            return [Line.from_text("x")]

    form = _form(Field("f", Both()))
    assert form.activate() is True
    assert form.take_result() == {"f": "v"}


def test_a_field_value_hook_wins_over_the_component():
    hook = lambda: "hooked"
    form = _form(Field("f", _Text("text"), value=hook))
    assert form.activate() is True
    assert form.take_result() == {"f": "hooked"}


# ---------------------------------------------------------------------------
# Validation and submission
# ---------------------------------------------------------------------------


def test_validation_receives_the_extracted_value_per_field():
    seen: list[object] = []
    form = _form(
        Field("a", _Text("one"), validate=lambda v: seen.append(v) or None),
        Field("b", _Text("two"), validate=lambda v: seen.append(v) or "nope"),
    )
    assert form.activate() is False
    assert seen == ["one", "two"]
    assert (form.fields[0].error, form.fields[1].error) == (None, "nope")
    assert form.take_result() is None


def test_a_successful_submit_leaves_the_mapping_pending_once_and_calls_back():
    calls: list[dict[str, object]] = []
    form = _form(
        Field("first", _Text("1")),
        Field("second", _Text("2")),
        on_submit=calls.append,
    )
    assert form.activate() is True
    assert calls == [{"first": "1", "second": "2"}]
    assert form.take_result() == {"first": "1", "second": "2"}
    assert form.take_result() is None


def test_a_failed_submit_clears_an_older_pending_result():
    field = Field("n", _Text("ok"))
    form = _form(field)
    assert form.activate() is True  # the result stays pending, unread
    field.validate = lambda v: "bad"
    assert form.activate() is False
    assert form.take_result() is None


def test_an_empty_form_activates_to_an_empty_mapping():
    calls: list[dict[str, object]] = []
    form = _form(on_submit=calls.append)
    assert form.activate() is True
    assert calls == [{}]
    assert form.take_result() == {}


# ---------------------------------------------------------------------------
# The container door
# ---------------------------------------------------------------------------


def test_child_at_maps_component_rows_and_declines_form_owned_rows():
    first, second = _Rows("a", "b"), _Rows("c")
    form = _form(
        Field("first", first, label="First"),
        Field("second", second),
        gap=1,
    )
    form.render(20)
    assert form.child_at(0, 0) is None  # the label row
    assert form.child_at(1, 3) == (first, 0, 3)
    assert form.child_at(2, 0) == (first, 1, 0)
    assert form.child_at(3, 0) is None  # the gap
    assert form.child_at(4, 0) == (second, 0, 0)
    assert form.child_at(5, 0) is None
    assert form.child_at(-1, 0) is None
    assert form.child_at(0, -1) is None


def test_child_at_declines_before_the_first_render():
    form = _form(Field("a", _Rows("a")))
    assert form.child_at(0, 0) is None


def test_an_error_row_is_not_the_childs():
    field = Field("a", _Rows("a"), validate=lambda v: "bad")
    form = _form(field)
    form.activate()
    form.render(10)
    assert form.child_at(0, 0) == (field.component, 0, 0)
    assert form.child_at(1, 0) is None  # the error row


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------


def test_the_snapshot_moves_with_errors_index_gap_and_theme():
    component = _RevisionedRows("a")
    form = _form(Field("a", component), Field("b", _Rows("b")))
    before = form.revision()
    assert form.revision() == before
    form.move(1)
    assert form.revision() != before
    before = form.revision()
    form.fields[0].error = "bad"
    assert form.revision() != before
    before = form.revision()
    form.fields[0].error = None
    component.rows = ["a", "b"]
    component.tick += 1
    assert form.revision() != before
    assert _form(Field("a", _Rows("a")), gap=0).revision() != _form(
        Field("a", _Rows("a")), gap=2
    ).revision()
    assert _form(Field("a", _Rows("a"))).revision() != _form(
        Field("a", _Rows("a")), theme=Theme(dim=Style(dim=True))
    ).revision()


def test_a_sealed_block_around_a_form_follows_a_field_component():
    component = _RevisionedRows("a")
    form = _form(Field("a", component), gap=0)
    block = Block("form", form)
    assert [row.text for row in block.rows(10)] == ["a"]
    block.seal()
    component.rows = ["a", "b"]
    component.tick += 1
    assert [row.text for row in block.rows(10)] == ["a", "b"]


def test_a_form_is_a_container_and_a_revisioned_component():
    form = _form(Field("a", _Rows("a")))
    assert isinstance(form, Component)
    assert isinstance(form, Container)
    assert isinstance(form, Revisioned)
    assert isinstance(_Rows(), Focusable)
    assert isinstance(_ControllerRows(), Controller)
