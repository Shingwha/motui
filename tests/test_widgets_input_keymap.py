"""Tests for mocode_tui.widgets.input keymap routing (Input.handle_key).

The editing methods themselves are covered by ``test_widgets_input.py``;
these tests pin the routing contract from the W2 spec: printables and pastes
insert, the keymap's names call the same-named methods, and every unbound
event comes back ``False`` for the host to route.
"""

from mocode_tui.keys.events import Key, Paste
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
    assert field.handle_key(_key("a", "a"), 20) is True
    assert field.handle_key(_key("b", "b"), 20) is True
    assert field.handle_key(_key("space", " "), 20) is True
    assert field.text == "ab " and field.cursor == 3


def test_paste_inserts_multiline_text():
    field = Input()
    assert field.handle_key(Paste("two\nlines"), 20) is True
    assert field.text == "two\nlines" and field.cursor == 9


def test_default_keymap_every_binding_acts():
    field = Input()
    field.handle_key(_key("a", "a"), 20)
    field.handle_key(_key("b", "b"), 20)
    field.handle_key(_key("c", "c"), 20)
    assert field.text == "abc" and field.cursor == 3
    assert field.handle_key(_key("left"), 20) is True and field.cursor == 2
    assert field.handle_key(_key("right"), 20) is True and field.cursor == 3
    assert field.handle_key(_key("home"), 20) is True and field.cursor == 0
    assert field.handle_key(_key("c-a"), 20) is True and field.cursor == 0
    assert field.handle_key(_key("c-e"), 20) is True and field.cursor == 3
    assert field.handle_key(_key("end"), 20) is True and field.cursor == 3
    assert field.handle_key(_key("backspace"), 20) is True and field.text == "ab"
    # delete at the end deletes nothing, yet the mapped key was consumed.
    assert field.handle_key(_key("delete"), 20) is True and field.text == "ab"
    field.handle_key(_key("left"), 20)
    assert field.handle_key(_key("delete"), 20) is True and field.text == "a"
    assert field.handle_key(_key("c-u"), 20) is True and field.text == "" and field.cursor == 0


def test_unbound_keys_return_false_and_never_mutate():
    field = Input()
    field.insert("ab")
    for name in ("enter", "escape", "tab", "c-c", "c-enter", "page_up"):
        assert field.handle_key(_key(name), 20) is False
        assert field.text == "ab" and field.cursor == 2


def test_handle_key_true_even_when_the_action_cannot_move():
    field = Input()
    # move_left at the start moves nowhere, yet the key was consumed.
    assert field.handle_key(_key("left"), 20) is True
    assert field.cursor == 0


def test_custom_keymap_overrides_and_drops_bindings():
    field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
    field.insert("xy")
    assert field.handle_key(_key("c-j"), 20) is True
    assert field.text == "" and field.cursor == 0
    # A dropped binding comes back to the host instead of moving the cursor.
    drop = Input(keymap={**DEFAULT_INPUT_KEYMAP})
    del drop.keymap["backspace"]
    drop.insert("ab")
    assert drop.handle_key(_key("backspace"), 20) is False and drop.text == "ab"


def test_handle_key_width_seeds_up_down_without_a_render():
    field = Input()
    field.insert("abcdefgh")  # wraps to "abcd" / "efgh" at width 6 (inner 4)
    field.cursor = 1
    assert field.handle_key(_key("down"), 6) is True and field.cursor == 5
    assert field.handle_key(_key("up"), 6) is True and field.cursor == 1
    assert field.handle_key(_key("up"), 6) is True and field.cursor == 1  # top row


def test_widget_protocol_unchanged():
    field = Input()
    field.insert("hi")
    rows = field.render(80)
    assert [row.text for row in rows] == ["\u276e hi "]
