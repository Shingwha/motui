"""Form: the field stack, focus navigation, values, validation and submission."""

from motui.kernel.cell import Surface
from motui.kernel.layout import Constraints
from motui.widgets import Checkbox, CheckboxGroup, Field, Form, Input, Option

from tests.testing import key, texts


def test_a_form_stacks_labels_components_and_gaps():
    form = Form(
        [
            Field("a", Checkbox("x"), label="One"),
            Field("b", Checkbox("y")),
        ],
        gap=1,
    )
    assert texts(form, 20) == ["One", "[ ] x", "", "[ ] y"]


def test_focus_moves_by_index_and_name_and_marks_the_field_components():
    first, second = Input("a"), Input("b")
    form = Form([Field("a", first), Field("b", second)])
    assert first.focused is True and second.focused is False
    assert form.focus("b") is True
    assert first.focused is False and second.focused is True
    assert form.focus("missing") is False
    assert form.focus(9) is False
    assert form.focus(1) is False


def test_move_clamps_at_the_field_ends():
    form = Form([Field("a", Checkbox("x")), Field("b", Checkbox("y"))])
    assert form.move(1) is True and form.index == 1
    assert form.move(1) is False
    assert form.move(-1) is True and form.index == 0
    assert form.move(-1) is False
    assert Form([]).move(1) is False


def test_the_focused_field_routes_first_then_the_form_navigates():
    field = Input()
    form = Form([Field("a", field), Field("b", Checkbox("y"))])
    assert form.handle(key("x", "x")) is True
    assert field.text == "x"
    assert form.handle(key("tab")) is True and form.index == 1
    assert form.handle(key("down")) is False  # clamped at the last field
    assert form.handle(key("s-tab")) is True and form.index == 0
    assert form.handle(key("up")) is True and form.index == 0  # the focused input took it


def test_enter_validates_every_field_and_submits_the_mapping():
    submitted: list[dict] = []
    form = Form(
        [
            Field("name", Input(), label="Name", validate=lambda v: None if v else "required"),
            Field("agree", Checkbox("agree")),
        ],
        on_submit=submitted.append,
    )
    assert form.handle(key("enter")) is True
    assert form.fields[0].error == "required"
    assert form.take_result() is None and submitted == []

    form.fields[0].component.insert("Ada")
    assert form.handle(key("enter")) is True
    assert form.take_result() == {"name": "Ada", "agree": False}
    assert form.take_result() is None
    assert submitted == [{"name": "Ada", "agree": False}]


def test_values_come_from_the_component_state_or_a_custom_extractor():
    check = Checkbox("x")
    check.checked = True
    group = CheckboxGroup(["a", "b"], marked=(1,))
    form = Form(
        [
            Field("check", check),
            Field("group", group),
            Field("custom", group, value=lambda: list(group.marked)),
        ]
    )
    assert form.activate() is True
    assert form.take_result() == {
        "check": True,
        "group": Option("a", "a"),
        "custom": [1],
    }


def test_reading_a_field_never_consumes_its_one_shot_result():
    menu = CheckboxGroup(["a"], marked=(0,))
    form = Form([Field("pick", menu)])
    form.activate()
    assert menu.take_result() == ["a"]


def test_an_empty_form_submits_an_empty_mapping():
    form = Form([])
    assert form.activate() is True and form.take_result() == {}
    assert form.handle(key("tab")) is False
    assert list(form.render(20)) == []


def test_child_at_maps_component_rows_and_owns_labels_gaps_and_errors():
    field = Checkbox("x")
    form = Form(
        [Field("a", field, label="One", validate=lambda v: "bad"), Field("b", Checkbox("y"))],
        gap=1,
    )
    form.render(20)
    assert form.child_at(1, 0) == (field, 0, 0)
    assert form.child_at(0, 0) is None
    form.activate()
    rows = texts(form, 20)
    assert rows[2] == "bad"
    assert form.child_at(2, 0) is None
    assert form.child_at(5, 0) is None


# -- the 2.0 render contract -------------------------------------------------


def test_a_form_takes_constraints_and_honours_the_height_budget():
    form = Form(
        [Field("a", Checkbox("x"), label="One"), Field("b", Checkbox("y"))],
        gap=1,
    )
    assert isinstance(form.render(Constraints(width=20)), Surface)
    assert form.render(20) == form.render(Constraints(width=20))
    surface = form.render(Constraints(width=20, max_height=2))
    assert [row.text for row in surface] == ["One", "[ ] x"]
    assert list(form.render(Constraints(width=20, max_height=0))) == []


def test_a_truncated_form_keeps_its_child_geometry():
    first, second = Checkbox("x"), Checkbox("y")
    form = Form([Field("a", first, label="One"), Field("b", second)], gap=1)
    form.render(Constraints(width=20, max_height=2))
    assert form.child_at(1, 0) == (first, 0, 0)
    assert form.child_at(3, 0) == (second, 0, 0)
