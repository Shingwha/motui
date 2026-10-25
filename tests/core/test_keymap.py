"""The three default keymaps and their derivation chain."""

from __future__ import annotations

from motui.kernel import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, EDITOR_SUBMIT_KEYMAP


def test_input_keymap_binds_the_editing_keys_and_leaves_enter_to_the_host():
    expected = {
        "left": "move_left",
        "right": "move_right",
        "home": "home",
        "end": "end",
        "backspace": "backspace",
        "delete": "delete",
        "up": "move_up",
        "down": "move_down",
        "c-a": "select_all",
        "c-e": "end",
        "c-u": "clear",
        "c-z": "undo",
        "c-y": "redo",
        "s-left": "select_left",
        "s-right": "select_right",
    }
    for name, action in expected.items():
        assert DEFAULT_INPUT_KEYMAP[name] == action
    assert "enter" not in DEFAULT_INPUT_KEYMAP


def test_editor_keymap_is_the_input_table_plus_enter_as_newline():
    assert DEFAULT_EDITOR_KEYMAP == {**DEFAULT_INPUT_KEYMAP, "enter": "newline"}
    assert set(DEFAULT_EDITOR_KEYMAP) == set(DEFAULT_INPUT_KEYMAP) | {"enter"}


def test_editor_submit_keymap_trades_enter_for_c_j_newline():
    assert EDITOR_SUBMIT_KEYMAP == {**DEFAULT_INPUT_KEYMAP, "c-j": "newline"}
    assert "enter" not in EDITOR_SUBMIT_KEYMAP
    assert EDITOR_SUBMIT_KEYMAP["c-j"] == "newline"
    assert set(EDITOR_SUBMIT_KEYMAP) == set(DEFAULT_EDITOR_KEYMAP) - {"enter"} | {"c-j"}


def test_the_tables_are_independent_mutable_copies():
    custom = {**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}
    del custom["left"]
    assert "c-j" not in DEFAULT_INPUT_KEYMAP
    assert "left" in DEFAULT_INPUT_KEYMAP
    assert DEFAULT_EDITOR_KEYMAP is not DEFAULT_INPUT_KEYMAP
    assert EDITOR_SUBMIT_KEYMAP is not DEFAULT_EDITOR_KEYMAP
