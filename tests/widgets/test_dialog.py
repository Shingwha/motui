"""Dialog, confirm_dialog and prompt_dialog: the box, its buttons and results."""

from motui.widgets import Button, ButtonSpec, Dialog, confirm_dialog, prompt_dialog

from tests.testing import Rows, key, texts


def button_row(dialog: Dialog, width: int = 40, *labels: str) -> int:
    """The rendered row carrying every one of ``labels``."""
    wanted = labels or ("Yes", "No")
    return next(
        index
        for index, row in enumerate(dialog.render(width))
        if all(label in row.text for label in wanted)
    )


def test_confirm_dialog_renders_a_framed_message_and_two_buttons():
    dialog = confirm_dialog("Continue?")
    rows = texts(dialog, 40)
    assert rows[0].startswith("\u250c") and rows[-1].startswith("\u2514")
    assert any("Continue?" in row for row in rows)
    assert "Yes" in rows[-2] and "No" in rows[-2]


def test_enter_takes_the_focused_button_and_escape_cancels():
    dialog = confirm_dialog("Continue?")
    assert dialog.handle(key("enter")) is True
    assert dialog.take_result() is True
    assert dialog.take_result() is None
    assert dialog.handle(key("escape")) is True
    assert dialog.take_result() is None


def test_tab_and_the_arrows_walk_the_button_row_without_wrapping():
    dialog = confirm_dialog("Continue?")
    assert dialog.index == 0
    assert dialog.handle(key("tab")) is True and dialog.index == 1
    assert dialog.handle(key("tab")) is True and dialog.index == 1
    assert dialog.handle(key("left")) is True and dialog.index == 0
    assert dialog.handle(key("left")) is True and dialog.index == 0
    assert dialog.handle(key("x", "x")) is False


def test_a_dangerous_dialog_opens_on_its_cancel_button():
    dialog = confirm_dialog("Delete?", danger=True)
    assert dialog.index == 1
    assert dialog.focused_button.label == "No"
    assert dialog.handle(key("enter")) is True and dialog.take_result() is False


def test_click_presses_the_button_under_the_cell():
    dialog = confirm_dialog("Continue?")
    row = button_row(dialog)
    col = dialog.render(40)[row].text.index("Yes")
    assert dialog.click(row, col) is True
    assert dialog.index == 0
    assert dialog.take_result() is True
    row = button_row(dialog)
    col = dialog.render(40)[row].text.index("No")
    assert dialog.click(row, col) is True
    assert dialog.take_result() is False


def test_a_click_outside_the_buttons_changes_nothing():
    dialog = confirm_dialog("Continue?")
    assert dialog.click(0, 0) is False
    assert dialog.click(1, 2) is False
    assert dialog.take_result() is None


def test_a_borderless_dialog_keeps_the_body_and_the_buttons():
    dialog = confirm_dialog("Continue?", frame=False)
    rows = texts(dialog, 40)
    assert len(rows) == 2
    assert "Continue?" in rows[0]
    assert "Yes" in rows[1] and "No" in rows[1]
    assert dialog.width is None


def test_a_pinned_width_sets_the_box_width():
    dialog = Dialog("T", Rows("body"), ["OK"], width=30)
    assert len(texts(dialog, 40)[0]) == 30


def test_child_at_maps_the_body_and_the_buttons():
    dialog = prompt_dialog("Name")
    dialog.render(40)
    body = dialog.body
    assert dialog.child_at(1, 2) == (body, 0, 0)
    row = button_row(dialog, 40, "OK", "Cancel")
    col = dialog.render(40)[row].text.index("OK")
    hit = dialog.child_at(row, col)
    assert isinstance(hit[0], Button)


def test_button_specs_supply_labels_values_and_the_focused_action():
    dialog = Dialog("T", Rows("body"), [ButtonSpec("Go", 7), ("Stop", 0)])
    assert dialog.focused_button.label == "Go"
    assert dialog.handle(key("enter")) is True
    assert dialog.take_result() == 7


def test_prompt_dialog_carries_an_input_body_and_takes_ok():
    dialog = prompt_dialog("Name", placeholder="type")
    assert dialog.title == "Name"
    assert dialog.body.text == ""
    assert dialog.handle(key("enter")) is True
    assert dialog.take_result() == "ok"
    assert dialog.body.placeholder == "type"
