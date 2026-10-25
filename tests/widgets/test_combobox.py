"""ComboBox: the editable field over a filtered dropdown it owns the state of."""

from motui.kernel.cell import Surface
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.widgets import ComboBox, Option

from tests.testing import key, paste, press

OPTIONS = [
    Option("Autocomplete", value="autocomplete"),
    Option("Checkbox", value="checkbox"),
    Option("ComboBox", value="combobox"),
    Option("Dialog", value="dialog"),
]


def drop_texts(combo: ComboBox) -> list[str]:
    return [row.text for row in combo.list.render(Constraints(width=60))]


def test_a_field_change_re_filters_the_list():
    combo = ComboBox(OPTIONS)
    assert combo.input.text == "" and not combo.is_open
    assert combo.handle(key("A", "A")) is True
    assert combo.handle(key("u", "u")) is True
    assert combo.input.text == "Au"
    assert drop_texts(combo) == ["\u2192 Autocomplete"]


def test_the_dropdown_uses_the_smaller_window_budget():
    combo = ComboBox(OPTIONS, max_rows=8, max_drop_rows=2)
    combo.open()
    assert combo.is_open
    assert len(drop_texts(combo)) == 3  # two rows plus the counter
    combo.close()
    assert len(drop_texts(combo)) == 4


def test_enter_takes_the_value_and_writes_the_label_into_the_field():
    combo = ComboBox(OPTIONS, text="Dia")
    combo.open()
    assert combo.list.selected.label == "Dialog"
    assert combo.handle(key("enter")) is True
    assert combo.take_result() == "dialog"
    assert combo.take_result() is None
    assert combo.input.text == "Dialog"
    assert not combo.is_open


def test_escape_closes_with_nothing_pending():
    combo = ComboBox(OPTIONS)
    combo.open()
    assert combo.handle(key("escape")) is True
    assert combo.take_result() is None and not combo.is_open


def test_the_consumption_boundary_follows_the_open_state():
    combo = ComboBox(OPTIONS)
    assert combo.handle(key("escape")) is False
    assert combo.handle(key("enter")) is False
    assert combo.handle(paste("Table")) is True
    assert combo.input.text == "Table"
    combo.input.clear()
    combo.open()
    assert combo.handle(key("down")) is True and combo.list.index == 1
    assert combo.handle(key("up")) is True and combo.list.index == 0
    assert combo.handle(key("enter")) is True and combo.take_result() == "autocomplete"
    assert not combo.is_open


def test_a_paste_while_open_reaches_the_field_and_keeps_the_dropdown():
    combo = ComboBox(OPTIONS)
    combo.open()
    assert combo.handle(paste("Dialog")) is True
    assert combo.input.text == "Dialog" and combo.is_open
    assert combo.take_result() is None


def test_pointer_reports_are_declined_so_the_host_owns_the_mouse():
    combo = ComboBox(OPTIONS, text="Dialog")
    assert combo.handle(press(0, 0)) is False
    assert combo.input.text == "Dialog"


def test_child_at_maps_every_rendered_input_row():
    combo = ComboBox(OPTIONS, text="Dialog")
    assert combo.child_at(0, 0) is None
    rows = combo.render(Constraints(width=40))
    assert rows
    assert combo.child_at(0, 12) == (combo.input, 0, 12)
    assert combo.child_at(len(rows), 0) is None


def test_focus_and_click_delegate_to_the_field():
    combo = ComboBox(OPTIONS, text="Dialog")
    combo.render(Constraints(width=40))
    combo.focused = False
    assert combo.input.focused is False
    assert combo.click(0, 3) is True
    assert combo.input.cursor == (0, 1)


def test_enter_with_no_match_closes_and_leaves_nothing_pending():
    combo = ComboBox(OPTIONS)
    combo.open()
    for char in "zzz":
        assert combo.handle(key(char, char)) is True
    assert combo.handle(key("enter")) is True
    assert combo.take_result() is None and not combo.is_open


# -- the 2.0 render contract -------------------------------------------------


def test_a_combo_takes_constraints_and_honours_the_height_budget():
    combo = ComboBox(OPTIONS, text="Dialog")
    assert isinstance(combo.render(Constraints(width=40)), Surface)
    assert combo.render(Constraints(width=40)) == combo.render(Constraints(width=40))
    assert list(combo.render(Constraints(width=40, max_height=0))) == []
    assert combo.render(Constraints(width=40, max_height=1)).height == 1
    # The child geometry is the untruncated field render's.
    assert combo.child_at(0, 0) == (combo.input, 0, 0)


# -- the 2.0 tree and typed hooks ---------------------------------------------


def test_the_combo_owns_its_field_and_dropdown_in_the_tree():
    combo = ComboBox(OPTIONS, text="Dialog")

    assert (combo.focusable, combo.clickable, combo.activatable) == (
        True,
        True,
        True,
    )
    assert combo.children == [combo.input, combo.list]
    assert combo.input.parent is combo and combo.list.parent is combo
    assert list(combo.walk()) == [combo, combo.input, combo.list]


def test_on_key_is_the_typed_spelling_of_handle():
    typed, legacy = ComboBox(OPTIONS), ComboBox(OPTIONS)

    assert typed.on_key(key("D", "D")) is True
    assert legacy.handle(key("D", "D")) is True
    assert typed.input.text == legacy.input.text == "D"


def test_on_click_docks_the_field_caret():
    combo = ComboBox(OPTIONS, text="Dialog")
    combo.render(Constraints(width=40))

    assert combo.on_click(Pos(y=0, x=3)) is True
    assert combo.input.cursor == (0, 1)


def test_on_action_activates_the_open_dropdown_only():
    combo = ComboBox(OPTIONS)

    assert combo.on_action("activate") is False
    combo.open()
    assert combo.on_action("activate") is True
    assert combo.take() == "autocomplete"
    assert combo.is_open is False and combo.input.text == "Autocomplete"

    # Other names are editing actions and belong to the field.
    assert combo.on_action("move_left") is True
    assert combo.input.cursor == (0, 11)


def test_take_is_the_result_door_and_the_alias_agrees():
    combo = ComboBox(OPTIONS)

    combo.open()
    assert combo.handle(key("enter")) is True
    assert combo.take() == "autocomplete"

    combo.open()
    assert combo.handle(key("enter")) is True
    assert combo.take_result() == "autocomplete"
