"""Tests for mocode_tui.widgets.input keymap routing (Input.handle_key).

The editing methods themselves are covered by ``test_widgets_input.py``;
these tests pin the routing contract from the W2 spec: printables and pastes
insert, the keymap's names call the same-named methods, and every unbound
event comes back ``False`` for the host to route.
"""

from mocode_tui.core.events import Key, Paste
from mocode_tui.keys.keymap import DEFAULT_INPUT_KEYMAP
from mocode_tui.widgets.input import Input


def _key(name: str, char: str = "") -> Key:
    return Key(name, char) if char else Key(name)


def test_default_keymap_is_stored_when_none():
    field = Input()
    assert field.keymap == DEFAULT_INPUT_KEYMAP
    assert "enter" not in field.keymap  # the return key stays with the host


def test_printables_and_space_insert_without_a_keymap_entry():
    field = Input(keymap={})
    assert field.handle_key(_key("a", "a")) is True
    assert field.handle_key(_key("b", "b")) is True
    assert field.handle_key(_key("space", " ")) is True
    assert field.text == "ab " and field.cursor == 3


def test_paste_inserts_multiline_text():
    field = Input()
    assert field.handle_key(Paste("two\nlines")) is True
    assert field.text == "two\nlines" and field.cursor == 9


def test_default_keymap_every_binding_acts():
    field = Input()
    field.handle_key(_key("a", "a"))
    field.handle_key(_key("b", "b"))
    field.handle_key(_key("c", "c"))
    assert field.text == "abc" and field.cursor == 3
    assert field.handle_key(_key("left")) is True and field.cursor == 2
    assert field.handle_key(_key("right")) is True and field.cursor == 3
    assert field.handle_key(_key("home")) is True and field.cursor == 0
    assert field.handle_key(_key("c-a")) is True and field.cursor == 0
    assert field.handle_key(_key("c-e")) is True and field.cursor == 3
    assert field.handle_key(_key("end")) is True and field.cursor == 3
    assert field.handle_key(_key("backspace")) is True and field.text == "ab"
    # delete at the end deletes nothing, yet the mapped key was consumed.
    assert field.handle_key(_key("delete")) is True and field.text == "ab"
    field.handle_key(_key("left"))
    assert field.handle_key(_key("delete")) is True and field.text == "a"
    assert field.handle_key(_key("c-u")) is True and field.text == "" and field.cursor == 0


def test_unbound_keys_return_false_and_never_mutate():
    field = Input()
    field.insert("ab")
    for name in ("enter", "escape", "tab", "c-c", "c-enter", "page_up"):
        assert field.handle_key(_key(name)) is False
        assert field.text == "ab" and field.cursor == 2


def test_handle_key_true_even_when_the_action_cannot_move():
    field = Input()
    # move_left at the start moves nowhere, yet the key was consumed.
    assert field.handle_key(_key("left")) is True
    assert field.cursor == 0


def test_custom_keymap_overrides_and_drops_bindings():
    field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
    field.insert("xy")
    assert field.handle_key(_key("c-j")) is True
    assert field.text == "" and field.cursor == 0
    # A dropped binding comes back to the host instead of moving the cursor.
    drop = Input(keymap={**DEFAULT_INPUT_KEYMAP})
    del drop.keymap["backspace"]
    drop.insert("ab")
    assert drop.handle_key(_key("backspace")) is False and drop.text == "ab"


def test_handle_key_before_any_render_uses_the_80_column_fallback():
    field = Input()
    field.insert("x" * 100)  # wraps at 80 (the pre-render fallback), inner 78
    field.cursor = 0
    assert field.handle_key(_key("down")) is True and field.cursor == 78
    assert field.handle_key(_key("up")) is True and field.cursor == 0
    assert field.handle_key(_key("up")) is True and field.cursor == 0  # top row: inert, consumed


def test_widget_protocol_unchanged():
    field = Input()
    field.insert("hi")
    rows = field.render(80)
    assert [row.text for row in rows] == ["\u276e hi "]
