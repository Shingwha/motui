"""Tests for motui.widgets.combobox (ComboBox).

The field over a filtered dropdown: a field change re-filters the list, the
dropdown's own four keys are consumed while it is open (``down``/``up``
step, ``enter`` takes, ``escape`` closes), the pick lands the option's value
in ``chosen`` and its label back in the field, and the consumption boundary
follows the open state -- closed, those keys are the field's (and a
declined event the host's), and a pointer report is never consumed.
"""

from motui import KeyEvent, PasteEvent
from motui.kernel.events import MouseEvent
from motui.widgets.choice import Option
from motui.widgets.combobox import ComboBox

#: The dropdown's universe: distinct labels for the filter assertions.
OPTIONS = [
    Option("Autocomplete", value="autocomplete", description="the filter layer"),
    Option("Checkbox", value="checkbox"),
    Option("ComboBox", value="combobox", description="this component"),
    Option("Dialog", value="dialog"),
    Option("Editor", value="editor"),
    Option("Input", value="input"),
    Option("Select", value="select"),
    Option("Table", value="table"),
]


def _rows(combo: ComboBox) -> list[str]:
    """The dropdown's current rendered rows, plain text."""
    return [row.text for row in combo.list.render(60)]


def test_a_field_change_re_filters_the_list_and_the_smaller_budget_is_the_drop():
    combo = ComboBox(OPTIONS, max_rows=8, max_drop_rows=3)
    assert combo.input.text == "" and not combo.is_open
    combo.handle(KeyEvent("A", "A"))  # a printable is the field's, open or closed
    combo.handle(KeyEvent("u", "u"))
    assert combo.input.text == "Au"
    assert len(_rows(combo)) == 1 and "Autocomplete" in _rows(combo)[0]  # the text narrowed the rows
    combo.input.clear()
    combo.open()
    assert combo.is_open
    assert len(_rows(combo)) == 4  # 3 rows plus the (i/n) counter: the drop's own budget
    combo.close()
    assert len(_rows(combo)) == 8  # the standalone list keeps its own cap


def test_enter_takes_the_value_and_writes_the_label_back_into_the_field():
    combo = ComboBox(OPTIONS, text="Dia")
    combo.open()
    assert combo.list.selected.label == "Dialog"
    assert combo.handle(KeyEvent("enter")) is True
    assert combo.chosen == "dialog"  # the option's payload, not the label
    assert combo.input.text == "Dialog"  # and the label is what the field shows
    assert not combo.is_open
    assert combo.list.chosen is None  # the menu's one-shot pick was carried over
    combo.chosen = None  # the host reads it once


def test_escape_closes_with_nothing_chosen():
    combo = ComboBox(OPTIONS)
    combo.open()
    assert combo.handle(KeyEvent("escape")) is True
    assert combo.chosen is None and not combo.is_open


def test_the_consumption_boundary_follows_the_open_state():
    combo = ComboBox(OPTIONS)
    # Closed: the dropdown's keys are the field's -- and not even its own.
    assert combo.handle(KeyEvent("escape")) is False
    assert combo.handle(KeyEvent("enter")) is False
    assert combo.handle(MouseEvent("left", x=0, y=0, kind="press")) is False
    assert combo.handle(PasteEvent("Table")) is True  # a paste is the field's, always
    assert combo.input.text == "Table"

    combo.input.clear()
    combo.open()
    assert combo.handle(KeyEvent("down")) is True and combo.list.index == 1
    assert combo.handle(KeyEvent("up")) is True and combo.list.index == 0
    assert combo.handle(KeyEvent("enter")) is True and combo.chosen == "autocomplete"
    assert not combo.is_open
