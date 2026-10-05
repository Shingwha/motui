"""Tests for mocode_tui.widgets.editor (Editor).

Contracts (the W2 spec): a multi-line buffer -- newline breaks at the cursor,
insert accepts "\\n", backspace merges the line above, delete merges the line
below; up/down follow the wrapped rows keeping the column; a focused editor
paints a block cursor, an empty one a dim placeholder; max_rows caps the rows
with a window that keeps the cursor visible; handle_key routes through
DEFAULT_EDITOR_KEYMAP (enter -> newline) and hands unbound keys back.
"""

from dataclasses import replace

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import CURSOR, DIM, NONE, Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.core.events import Key, Paste
from mocode_tui.keys.keymap import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP
from mocode_tui.widgets.editor import Editor


def _key(name: str, char: str = "") -> Key:
    return Key(name, char) if char else Key(name)


def test_default_keymap_is_stored_when_none():
    editor = Editor()
    assert editor.keymap == DEFAULT_EDITOR_KEYMAP
    assert DEFAULT_EDITOR_KEYMAP == {**DEFAULT_INPUT_KEYMAP, "enter": "newline"}


def test_empty_render_and_placeholder():
    assert [row.text for row in Editor().render(10)] == [" "]  # the lone cursor cell
    rows = Editor(placeholder="hint").render(10)
    assert rows[0].text == "hint "  # the cursor trails the hint, as on a typed row
    assert rows[0].segments == (Segment("hint", DIM), Segment(" ", CURSOR))


def test_multiline_insert_and_cursor():
    editor = Editor()
    editor.insert("one")
    assert editor.value == "one" and (editor.row, editor.col) == (0, 3)
    editor.handle_key(_key("enter"))  # newline: the editor consumes enter
    editor.insert("two")
    assert editor.value == "one\ntwo" and (editor.row, editor.col) == (1, 3)
    editor.insert("\nthree")  # a multi-line paste
    assert editor.value == "one\ntwo\nthree" and (editor.row, editor.col) == (2, 5)


def test_backspace_merges_line_above_and_delete_merges_below():
    editor = Editor(text="ab\ncd")
    editor.end()
    assert editor.backspace() is True and editor.value == "a\ncd"
    editor.move_right()  # first column of the second line
    assert editor.backspace() is True
    assert editor.value == "acd" and (editor.row, editor.col) == (0, 1)
    editor = Editor(text="ab\ncd")
    editor.end()
    assert editor.delete() is True and editor.value == "abcd" and (editor.row, editor.col) == (0, 2)
    editor.end()
    assert editor.delete() is False  # the very end


def test_newline_splits_the_line_at_the_cursor():
    editor = Editor(text="abcd")
    editor.move_right()
    editor.move_right()  # between "b" and "c"
    assert editor.newline() is True
    assert editor.lines == ["ab", "cd"] and (editor.row, editor.col) == (1, 0)


def test_move_left_right_cross_lines():
    editor = Editor(text="ab\ncd")
    assert editor.move_left() is False  # buffer start
    editor.end()
    assert editor.move_right() is True and (editor.row, editor.col) == (1, 0)
    assert editor.move_right() is True and (editor.row, editor.col) == (1, 1)
    editor.home()
    assert editor.move_left() is True and (editor.row, editor.col) == (0, 2)
    assert editor.move_right() is True and (editor.row, editor.col) == (1, 0)
    assert editor.end() is True and editor.move_right() is False  # buffer end


def test_move_up_down_cross_lines_keeping_the_column():
    editor = Editor(text="abcde\nxy\nlonger line")
    editor.end()
    assert editor.move_down() is True and (editor.row, editor.col) == (1, 2)  # "xy" clamps
    assert editor.move_down() is True and (editor.row, editor.col) == (2, 2)  # column kept
    assert editor.move_up() is True and (editor.row, editor.col) == (1, 2)
    assert editor.move_up() is True and (editor.row, editor.col) == (0, 2)
    top = Editor(text="a\nb")
    assert top.move_up() is False  # top visual row
    top.end()
    assert top.move_down() is True and (top.row, top.col) == (1, 1)
    assert top.move_down() is False  # bottom visual row


def test_move_up_down_follow_the_wrapped_rows():
    editor = Editor(text="abcdefgh\nwxyz")
    editor.render(4)  # width 4 wraps to "abcd" / "efgh" / "wxyz"
    editor.handle_key(_key("right"))
    assert (editor.row, editor.col) == (0, 1)
    assert editor.handle_key(_key("down")) is True and (editor.row, editor.col) == (0, 5)
    assert editor.handle_key(_key("up")) is True and (editor.row, editor.col) == (0, 1)
    assert editor.handle_key(_key("up")) is True and (editor.row, editor.col) == (0, 1)
    editor.end()  # the end of logical line 0
    assert editor.move_down() is True and (editor.row, editor.col) == (1, 4)  # wraps over


def test_wrap_render_and_block_cursor():
    editor = Editor(text="abcdefgh")
    rows = editor.render(4)
    assert [row.text for row in rows] == ["abcd", "efgh"]
    assert rows[0].segments == (Segment("a", CURSOR), Segment("bcd", NONE))
    assert rows[1].segments == (Segment("efgh", NONE),)  # only the cursor row restyles
    # A full row is exactly full: the cursor space is skipped, no overflow.
    full = Editor(text="abc")
    full.end()
    assert full.render(3)[0].segments == (Segment("abc", NONE),)


def test_narrow_width_guard():
    editor = Editor(text="the quick brown fox\nsecond line")
    for width in (1, 2, 8):
        assert all(row.width <= width for row in editor.render(width))


def test_max_rows_window_keeps_the_cursor_visible():
    text = "\n".join(f"line{i}" for i in range(10))
    assert len(Editor(text=text).render(20)) == 10  # no cap renders every row
    windowed = Editor(text=text, max_rows=3)
    rows = windowed.render(20)
    assert [row.text for row in rows] == ["line0", "line1", "line2"]  # cursor at the start
    windowed.end()
    for _ in range(9):
        windowed.move_down()
    assert (windowed.row, windowed.col) == (9, 5)
    rows = windowed.render(20)
    # "line9 " ends in the reverse-video cursor space: the cursor sits at the end.
    assert [row.text for row in rows] == ["line7", "line8", "line9 "]
    centred = Editor(text=text, max_rows=4)
    for _ in range(5):
        centred.move_down()
    assert [row.text for row in centred.render(20)] == [
        "line3",
        "line4",
        "line5",
        "line6",
    ]


def test_cursor_position_reports_the_block_cursor_cell():
    editor = Editor(text="abcdefgh")
    editor.home()
    for _ in range(5):
        editor.move_right()
    assert editor.cursor_position(4) == (1, 1)  # visual row 1 ("efgh"), column 1
    editor.home()
    assert editor.cursor_position(4) == (0, 0)
    assert Editor().cursor_position(10) == (0, 0)  # the row-start cell
    windowed = Editor(text="\n".join(f"line{i}" for i in range(10)), max_rows=3)
    windowed.end()
    for _ in range(9):
        windowed.move_down()
    assert windowed.cursor_position(20) == (2, 5)  # in-window row index


def test_handle_key_return_semantics():
    editor = Editor()
    assert editor.handle_key(Paste("x\ny")) is True
    assert editor.value == "x\ny" and (editor.row, editor.col) == (1, 1)
    assert editor.handle_key(_key("a", "a")) is True
    assert editor.handle_key(_key("space", " ")) is True
    assert editor.value == "x\nya "
    for name in ("escape", "c-c", "tab", "c-enter", "page_up"):
        assert editor.handle_key(_key(name)) is False
    assert editor.handle_key(_key("enter")) is True  # newline, consumed
    assert editor.handle_key(_key("left")) is True  # bound: consumed even when inert


def test_custom_keymap_overrides_and_drops_bindings():
    hand_off = Editor(keymap={**DEFAULT_EDITOR_KEYMAP})
    del hand_off.keymap["enter"]  # submit stays with the host
    hand_off.insert("ab")
    assert hand_off.handle_key(_key("enter")) is False and hand_off.value == "ab"
    rebound = Editor(keymap={**DEFAULT_EDITOR_KEYMAP, "c-j": "newline"})
    rebound.insert("ab")
    assert rebound.handle_key(_key("c-j")) is True
    assert rebound.value == "ab\n" and (rebound.row, rebound.col) == (1, 0)


def test_value_and_clear():
    editor = Editor(text="a\nb")
    editor.insert("c")  # seeded text parks the cursor at its start
    assert editor.value == "ca\nb"
    editor.clear()
    assert editor.value == "" and editor.lines == [""] and (editor.row, editor.col) == (0, 0)


def test_focused_off_renders_plainly():
    editor = Editor(text="ab", focused=False)
    assert editor.render(10)[0].segments == (Segment("ab", NONE),)
    assert Editor(focused=False).render(10) == [Line()]


def test_style_resolution_explicit_over_theme():
    theme = replace(DEFAULT_THEME, cursor=Style(fg="#00ff00"), dim=Style(italic=True))
    editor = Editor(theme=theme)
    editor.insert("a")
    assert editor.render(10)[0].segments == (Segment("a", NONE), Segment(" ", theme.cursor))
    hint = Editor(placeholder="hi", theme=theme)
    assert hint.render(10)[0].segments == (
        Segment("hi", theme.dim),
        Segment(" ", theme.cursor),
    )
    explicit = Style(fg="#ff00ff")
    override = Editor(cursor_style=explicit, theme=theme)
    override.insert("a")
    assert override.render(10)[0].segments[-1] == Segment(" ", explicit)


def test_repr():
    assert repr(Editor(text="hi")) == "Editor('hi', cursor=(0, 0))"
