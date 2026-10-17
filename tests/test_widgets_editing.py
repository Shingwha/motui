"""Tests for the editing components: Input and Editor over one engine.

Cursor-edited text rendered as rows with a reverse-video block cursor; every
shared contract is tested once, parametrized over the two components.
"""

from dataclasses import replace

import pytest

from motui.app import Hit
from motui.interaction import FocusRing
from motui.kernel import Block, Component, visible_width
from motui.kernel.block import Clickable
from motui.kernel.events import Paste
from motui.kernel.lines import Segment
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.keys import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, EDITOR_SUBMIT_KEYMAP
from motui.widgets.editor import Editor
from motui.widgets.input import Input
from motui.widgets.textbuf import UNDO_LIMIT, TextBuffer

from _doubles import key, texts

#: One injected style, round-tripped through every style parameter.
INJECTED = Style(fg="#abcdef")
#: A second one, for a row that carries two injected styles at once.
PROMPT = Style(fg="#123456")

COMPONENTS = [Input, Editor]


def _make(make, text: str = "", **kwargs):
    """Build the component seeded with ``text`` (``Input`` takes no ``text``)."""
    if make is Input:
        field = Input(**kwargs)
        field.insert(text)
        return field
    # Editor renders no prompt, so it keeps no prompt_style to inject into.
    kwargs.pop("prompt_style", None)
    return Editor(text=text, **kwargs)


def _text(component) -> str:
    """The buffer text (``Input`` and ``Editor`` share the ``text`` view)."""
    return component.text


def _pos(component) -> int:
    """The cursor as a flat offset into the buffer text."""
    row, col = component.cursor
    return sum(len(line) + 1 for line in component.text.split("\n")[:row]) + col


def _park(component, offset: int) -> None:
    """Park the cursor at the flat ``offset`` (walks in from the start)."""
    while component.move_left():
        pass
    for _ in range(offset):
        component.move_right()


# ---------------------------------------------------------------------------
# Keymap routing -- one engine, one routing contract, both components
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("make", COMPONENTS)
def test_default_keymap_is_stored_when_none(make):
    field = make()
    assert field.keymap == (DEFAULT_INPUT_KEYMAP if make is Input else DEFAULT_EDITOR_KEYMAP)


def test_editor_keymap_extends_the_input_one_with_enter_as_newline():
    assert DEFAULT_EDITOR_KEYMAP == {**DEFAULT_INPUT_KEYMAP, "enter": "newline"}
    assert "enter" not in Input().keymap  # the return key stays with the host


def test_the_editor_submit_keymap_is_the_editor_chain_without_enter():
    # The three tables are one derivation chain in keys.keymap: input ->
    # editor (+enter) -> editor-submit (-enter, +c-j); every other binding
    # survives the trip verbatim.
    assert EDITOR_SUBMIT_KEYMAP == {**DEFAULT_INPUT_KEYMAP, "c-j": "newline"}
    assert set(EDITOR_SUBMIT_KEYMAP) == set(DEFAULT_EDITOR_KEYMAP) - {"enter"} | {"c-j"}
    assert EDITOR_SUBMIT_KEYMAP["c-j"] == "newline" and "enter" not in EDITOR_SUBMIT_KEYMAP
    assert Editor(keymap=EDITOR_SUBMIT_KEYMAP).keymap is EDITOR_SUBMIT_KEYMAP


@pytest.mark.parametrize("make, end", [(Input, (0, 3)), (Editor, (0, 3))])
def test_printables_and_space_insert_without_a_keymap_entry(make, end):
    field = make(keymap={})
    assert field.handle(key("a", "a")) is True
    assert field.handle(key("b", "b")) is True
    assert field.handle(key("space", " ")) is True
    assert _text(field) == "ab " and field.cursor == end


@pytest.mark.parametrize(
    "make, text, end",
    # The Input folds a paste's newline runs into single spaces (W1): a
    # single-line field stays one row; the Editor keeps the newlines.
    [(Input, "two lines", (0, 9)), (Editor, "two\nlines", (1, 5))],
)
def test_paste_inserts_multiline_text(make, text, end):
    field = make()
    assert field.handle(Paste("two\nlines")) is True
    assert _text(field) == text and field.cursor == end


@pytest.mark.parametrize(
    "pasted, folded",
    [
        ("a\r\nb\nc", "a b c"),
        ("a\rb", "a b"),
        ("one\n\n\ntwo", "one two"),  # consecutive empty lines fold to one space
        ("first\r\n\r\nlast", "first last"),
    ],
)
def test_input_folds_every_newline_run_of_a_paste_into_one_space(pasted, folded):
    field = Input()
    assert field.handle(Paste(pasted)) is True
    assert field.text == folded
    assert field.cursor == (0, len(folded))  # the cursor parks at the end
    # One rendered row: the block cursor trails the folded text.
    assert texts(field, 30) == [f"\u276e {folded} "]


def test_the_editor_keeps_the_newlines_of_the_same_paste():
    editor = Editor()
    assert editor.handle(Paste("a\r\nb\nc")) is True
    assert editor.text == "a\r\nb\nc"  # verbatim: multi-line is its faculty
    assert len(editor.render(10)) == 3


def test_an_explicit_insert_on_the_input_still_keeps_newlines():
    field = Input()
    field.insert("\n")  # the host's own insert is untouched by the paste fold
    assert field.text == "\n"
    assert len(field.render(10)) == 2  # two empty rows, the cursor on the second


@pytest.mark.parametrize("make", COMPONENTS)
@pytest.mark.parametrize("name", ["escape", "tab", "c-c", "c-enter", "page_up"])
def test_unbound_events_come_back_to_the_host(make, name):
    field = _make(make, "ab")
    _park(field, 2)
    assert field.handle(key(name)) is False
    assert _text(field) == "ab" and _pos(field) == 2


def test_enter_is_unbound_on_input_and_bound_on_the_editor():
    assert Input().handle(key("enter")) is False  # the return key stays with the host
    editor = Editor()
    assert editor.handle(key("enter")) is True and editor.text == "\n"


@pytest.mark.parametrize("make", COMPONENTS)
def test_a_bound_key_is_consumed_even_when_inert(make):
    field = make()
    # move_left at the start moves nowhere, yet the key was consumed.
    assert field.handle(key("left")) is True
    assert _pos(field) == 0


@pytest.mark.parametrize(
    "make, action, dropped", [(Input, "clear", "backspace"), (Editor, "newline", "enter")]
)
def test_custom_keymap_rebinds_and_drops(make, action, dropped):
    base = DEFAULT_INPUT_KEYMAP if make is Input else DEFAULT_EDITOR_KEYMAP
    field = _make(make, "ab", keymap={**base, "c-j": action})
    assert field.handle(key("c-j")) is True
    handed_off = _make(make, "ab", keymap={**base})
    del handed_off.keymap[dropped]
    assert handed_off.handle(key(dropped)) is False and _text(handed_off) == "ab"


def test_every_default_input_binding_acts():
    field = Input()
    for name in "abc":
        field.handle(key(name, name))
    assert _text(field) == "abc" and _pos(field) == 3
    assert field.handle(key("left")) is True and _pos(field) == 2
    assert field.handle(key("right")) is True and _pos(field) == 3
    assert field.handle(key("home")) is True and _pos(field) == 0
    # ``c-a`` is the selection's select-all now (the line start is ``home``):
    # the caret walks to the text end and the whole buffer is selected.
    assert field.handle(key("c-a")) is True
    assert field.selection_range() == (0, 3) and _pos(field) == 3
    assert field.clear_selection() is None and field.selection_range() is None
    assert field.handle(key("c-e")) is True and _pos(field) == 3
    assert field.handle(key("end")) is True and _pos(field) == 3
    assert field.handle(key("backspace")) is True and _text(field) == "ab"
    # delete at the end deletes nothing, yet the mapped key was consumed.
    assert field.handle(key("delete")) is True and _text(field) == "ab"
    _park(field, 1)
    assert field.handle(key("delete")) is True and _text(field) == "a"
    assert field.handle(key("c-z")) is True and _text(field) == "ab"  # the history keys
    assert field.handle(key("c-y")) is True and _text(field) == "a"
    assert field.handle(key("c-u")) is True and _text(field) == ""


@pytest.mark.parametrize("make, down_at", [(Input, 78), (Editor, 80)])
def test_handle_before_any_render_uses_the_80_column_fallback(make, down_at):
    field = _make(make, "x" * 100)  # wraps at 80 (Input: inner 78 past the prompt)
    _park(field, 0)
    assert field.handle(key("down")) is True and _pos(field) == down_at
    assert field.handle(key("up")) is True and _pos(field) == 0
    assert field.handle(key("up")) is True  # top row: inert, consumed


# ---------------------------------------------------------------------------
# Editing methods
# ---------------------------------------------------------------------------


def test_insert_backspace_delete_clear():
    field = Input()
    assert field.backspace() is False and field.delete() is False  # empty
    field.insert("ac")
    _park(field, 1)
    field.insert("b")
    assert field.text == "abc" and _pos(field) == 2
    assert field.delete() is True and field.text == "ab" and _pos(field) == 2
    assert field.backspace() is True and field.text == "a"
    field.clear()
    assert field.text == "" and _pos(field) == 0


def test_multiline_insert_moves_the_cursor_onto_the_last_line():
    editor = Editor()
    editor.insert("one")
    editor.handle(key("enter"))  # newline: the editor consumes enter
    editor.insert("two")
    editor.insert("\nthree")  # a multi-line paste
    assert editor.text == "one\ntwo\nthree" and editor.cursor == (2, 5)


def test_newline_splits_the_line_at_the_cursor():
    editor = Editor(text="abcd")
    editor.move_right()
    editor.move_right()  # between "b" and "c"
    assert editor.newline() is True
    assert editor.text == "ab\ncd" and editor.cursor == (1, 0)


def test_backspace_merges_the_line_above_and_delete_merges_below():
    editor = Editor(text="ab\ncd")
    editor.end()
    assert editor.backspace() is True and editor.text == "a\ncd"
    editor.move_right()  # first column of the second line
    assert editor.backspace() is True
    assert editor.text == "acd" and editor.cursor == (0, 1)
    editor = Editor(text="ab\ncd")
    editor.end()
    assert editor.delete() is True and editor.text == "abcd" and editor.cursor == (0, 2)
    editor.end()
    assert editor.delete() is False  # the very end


def test_text_and_clear():
    editor = Editor(text="a\nb")
    editor.insert("c")  # seeded text parks the cursor at its start
    assert editor.text == "ca\nb"
    editor.clear()
    assert editor.text == "" and editor.cursor == (0, 0)


def test_move_left_right_cross_lines_keeping_the_column():
    editor = Editor(text="ab\ncd")
    assert editor.move_left() is False  # buffer start
    editor.end()
    assert editor.move_right() is True and editor.cursor == (1, 0)
    assert editor.move_right() is True and editor.cursor == (1, 1)
    editor.home()
    assert editor.move_left() is True and editor.cursor == (0, 2)
    assert editor.move_right() is True and editor.cursor == (1, 0)
    assert editor.end() is True and editor.move_right() is False  # buffer end
    # up/down keep the column, clamped where a line runs short
    editor = Editor(text="abcde\nxy\nlonger line")
    editor.end()
    assert editor.move_down() is True and editor.cursor == (1, 2)
    assert editor.move_down() is True and editor.cursor == (2, 2)
    assert editor.move_up() is True and editor.cursor == (1, 2)
    assert editor.move_up() is True and editor.cursor == (0, 2)


@pytest.mark.parametrize("make, home, end", [(Input, (0, 3), (0, 5)), (Editor, (1, 0), (1, 2))])
def test_home_and_end_park_within_the_logical_line(make, home, end):
    field = _make(make, "ab\ncd")
    _park(field, 4)  # between "c" and "d"
    assert field.home() is True and field.cursor == home
    assert field.home() is False  # already home
    assert field.end() is True and field.cursor == end
    assert field.end() is False  # already at the line end


@pytest.mark.parametrize("make, width", [(Input, 6), (Editor, 4)])
def test_up_and_down_follow_the_wrapped_rows(make, width):
    # "abcdefgh\nwxyz" wraps to "abcd" / "efgh" / "wxyz" in both geometries
    # (Input: width 6 minus the two-wide prompt; Editor: full width).
    field = _make(make, "abcdefgh\nwxyz")
    field.render(width)
    _park(field, 1)
    assert field.move_down() is True and _pos(field) == 5
    assert field.move_up() is True and _pos(field) == 1
    assert field.move_up() is False  # top visual row


# ---------------------------------------------------------------------------
# Undo and redo -- the buffer's bounded history
# ---------------------------------------------------------------------------


def test_undo_and_redo_round_trip_every_write_point():
    field = _make(Input, "ab")
    field.insert("c")
    assert (field.text, field.cursor) == ("abc", (0, 3))
    assert field.undo() is True
    assert (field.text, field.cursor) == ("ab", (0, 2))  # the cursor rides the snapshot
    assert field.redo() is True and (field.text, field.cursor) == ("abc", (0, 3))
    assert field.redo() is False  # nothing left to redo

    editor = _make(Editor, "ab")
    _park(editor, 1)
    assert editor.backspace() is True and editor.text == "b"
    assert editor.undo() is True and (editor.text, editor.cursor) == ("ab", (0, 1))
    assert editor.redo() is True and editor.text == "b"

    editor = _make(Editor, "ab")
    assert editor.delete() is True and editor.text == "b"
    assert editor.undo() is True and (editor.text, editor.cursor) == ("ab", (0, 0))
    assert editor.redo() is True and editor.text == "b"

    editor = _make(Editor, "ab")
    _park(editor, 1)
    assert editor.newline() is True
    assert (editor.text, editor.cursor) == ("a\nb", (1, 0))
    assert editor.undo() is True and (editor.text, editor.cursor) == ("ab", (0, 1))
    assert editor.redo() is True and editor.text == "a\nb"

    field = _make(Input, "ab")
    field.clear()
    assert (field.text, field.cursor) == ("", (0, 0))
    assert field.undo() is True and (field.text, field.cursor) == ("ab", (0, 2))
    assert field.redo() is True and field.text == ""


def test_empty_stacks_answer_false_and_no_ops_record_nothing():
    field = Input()
    assert field.undo() is False and field.redo() is False
    assert field.backspace() is False and field.delete() is False  # nothing deleted
    assert field.undo() is False  # a deleted nothing is not a step
    field.clear()  # clearing the empty buffer is a no-op
    assert field.undo() is False


def test_runs_of_single_character_inserts_merge_into_one_step():
    field = Input()
    for ch in "abc":
        assert field.handle(key(ch, ch)) is True
    assert field.text == "abc"
    assert field.undo() is True and field.text == ""
    assert field.redo() is True and field.text == "abc"


def test_a_move_or_a_click_breaks_the_run_into_separate_steps():
    field = _make(Input, "ab")  # a multi-character insert: a step of its own
    field.insert("c")
    field.insert("d")  # merges with "c": one step for the run
    assert field.text == "abcd"
    field.move_left()  # a move breaks the run
    field.insert("e")
    assert field.text == "abced"
    assert field.undo() is True and field.text == "abcd"
    assert field.undo() is True and field.text == "ab"
    assert field.undo() is True and field.text == ""
    assert field.undo() is False  # three steps in all: "ab", "cd", "e"


def test_the_history_is_bounded_at_undo_limit_steps():
    buf = TextBuffer("", keymap={})
    for _ in range(UNDO_LIMIT + 50):
        buf.insert("x")
        buf.move_left()
        buf.move_right()  # the moves break the run: one step per insert
    undone = 0
    while buf.undo():
        undone += 1
    assert undone == UNDO_LIMIT
    assert buf.value == "x" * 50  # the oldest 50 insertions fell off the stack
    assert buf.redo() is True  # and the redo tail walks forward again


def test_moves_are_not_history_steps():
    buf = TextBuffer("", keymap={})
    buf.insert("a")
    buf.insert("b")  # merged into one step
    for _ in range(3):
        buf.move_left()
        buf.move_right()
        buf.home()
        buf.end()
        buf.move_up()
        buf.move_down()
    assert buf.value == "ab"
    assert buf.undo() is True and buf.value == ""  # one step: the merged run
    assert buf.undo() is False  # the moves recorded nothing
    assert buf.redo() is True and buf.value == "ab"

    assert buf.place(0, 0) is True  # a click's docking breaks the run too
    buf.insert("c")
    assert buf.value == "cab"
    assert buf.undo() is True and buf.value == "ab"
    assert buf.undo() is True and buf.value == ""


def test_the_history_keys_ride_the_default_tables_and_a_paste_is_one_step():
    for table in (DEFAULT_INPUT_KEYMAP, DEFAULT_EDITOR_KEYMAP, EDITOR_SUBMIT_KEYMAP):
        assert table["c-z"] == "undo" and table["c-y"] == "redo"
    field = Input()
    for ch in "ab":
        field.insert(ch)
    assert field.handle(key("c-z")) is True and field.text == ""
    assert field.handle(key("c-z")) is True  # consumed even with nothing to undo
    assert field.handle(key("c-y")) is True and field.text == "ab"

    editor = Editor(keymap=EDITOR_SUBMIT_KEYMAP)
    assert editor.handle(Paste("one\ntwo")) is True  # one step, three characters
    assert editor.text == "one\ntwo"
    assert editor.handle(key("c-z")) is True and editor.text == ""
    assert editor.handle(key("c-y")) is True and editor.text == "one\ntwo"

    single = Input()
    assert single.handle(Paste("a\r\nb")) is True  # the fold happens first
    assert single.text == "a b"
    assert single.undo() is True and single.text == ""


# ---------------------------------------------------------------------------
# Selection -- the text-internal anchor, the shift chords, the band
# ---------------------------------------------------------------------------


def test_shift_moves_extend_the_selection_from_the_anchor_both_ways():
    field = _make(Input, "hello")
    _park(field, 2)
    assert field.anchor is None and field.selection_range() is None
    assert field.select_left() is True  # the first extension parks the anchor
    assert field.anchor == 2 and field.selection_range() == (1, 2)
    assert field.selected_text == "e"
    assert field.select_left() is True and field.selection_range() == (0, 2)
    assert field.selected_text == "he"
    assert field.select_left() is False  # the buffer start: the selection stays
    assert field.selection_range() == (0, 2)
    for _ in range(2):  # right-ward extension walks back up to the anchor
        assert field.select_right() is True
    assert field.selection_range() is None  # the cursor is back on the anchor
    assert field.selected_text == ""
    assert field.select_right() is True  # and the direction flips freely
    assert field.selection_range() == (2, 3) and field.selected_text == "l"


def test_shift_up_and_down_keep_the_column_of_the_wrapped_rows():
    editor = Editor(text="abcdefgh\nwxyz")
    editor.render(4)  # the wrapped geometry: abcd / efgh / wxyz
    _park(editor, 1)
    assert editor.select_down() is True
    assert editor.selection_range() == (1, 5) and editor.selected_text == "bcde"
    assert editor.select_down() is True
    assert editor.selected_text == "bcdefgh\nw"  # per-character: one cell per row
    assert editor.select_up() is True and editor.selection_range() == (1, 5)
    assert editor.select_up() is True  # the cursor walks back onto the anchor
    assert editor.selection_range() is None
    assert editor.select_up() is False  # the top visual row: nothing more to extend
    assert editor.selection_range() is None


def test_shift_home_and_end_stay_inside_the_logical_line():
    editor = Editor(text="ab\ncd")
    _park(editor, 4)  # between "c" and "d"
    assert editor.select_home() is True
    assert editor.selection_range() == (3, 4) and editor.selected_text == "c"
    assert editor.select_end() is True
    assert editor.selection_range() == (4, 5) and editor.selected_text == "d"
    assert editor.select_end() is False  # already at the line end


def test_select_all_takes_the_whole_buffer_and_c_a_is_its_key():
    field = _make(Input, "hello")
    assert field.select_all() is True
    assert field.anchor == 0 and field.selection_range() == (0, 5)
    assert field.selected_text == "hello" and field.cursor == (0, 5)
    assert Input().select_all() is False  # an empty buffer has nothing to select
    field.clear_selection()
    assert field.selection_range() is None
    assert field.handle(key("c-a")) is True
    assert field.selected_text == "hello"


def test_typing_replaces_the_selection_in_one_history_step():
    field = _make(Input, "hello world")
    _park(field, 6)  # before "world"
    for _ in range(5):
        assert field.select_right() is True
    assert field.selected_text == "world"
    field.insert("there")
    assert field.text == "hello there" and field.selection_range() is None
    assert field.cursor == (0, 11)
    assert field.undo() is True
    assert field.text == "hello world"  # the replaced range comes back with it
    assert field.redo() is True and field.text == "hello there"


def test_backspace_delete_and_newline_delete_the_selection_first():
    editor = Editor(text="one two")
    _park(editor, 3)
    for _ in range(4):
        editor.select_right()
    assert editor.selected_text == " two"
    assert editor.backspace() is True
    assert editor.text == "one" and editor.cursor == (0, 3)
    assert editor.undo() is True and editor.text == "one two"

    editor = Editor(text="one two")
    _park(editor, 3)
    for _ in range(4):
        editor.select_right()
    assert editor.delete() is True
    assert editor.text == "one" and editor.cursor == (0, 3)
    assert editor.undo() is True and editor.text == "one two"

    editor = Editor(text="one two")
    _park(editor, 3)
    for _ in range(4):
        editor.select_right()
    assert editor.newline() is True
    assert editor.text == "one\n" and editor.cursor == (1, 0)
    assert editor.undo() is True and editor.text == "one two"


def test_a_selection_across_the_line_break_deletes_into_one_line():
    editor = Editor(text="ab\ncd")
    _park(editor, 1)
    assert editor.select_down() is True
    assert editor.selection_range() == (1, 4)
    assert editor.selected_text == "b\nc"
    assert editor.delete() is True
    assert editor.text == "ad" and editor.cursor == (0, 1)
    assert editor.undo() is True and editor.text == "ab\ncd"


def test_plain_moves_and_clicks_clear_the_selection():
    field = _make(Input, "hello")
    field.select_left()
    field.select_left()
    assert field.selection_range() == (3, 5)
    assert field.move_left() is True and field.selection_range() is None
    assert field.select_left() is True and field.selection_range() is not None
    assert field.home() is True and field.selection_range() is None
    assert field.select_right() is True
    assert field.click(0, 4) is True and field.selection_range() is None
    field.select_left()
    assert field.end() is True and field.selection_range() is None
    field.select_left()
    assert field.selection_range() is not None
    assert field.move_up() is False  # a single row: the move is inert ...
    assert field.selection_range() is None  # ... and the selection is still dropped


def test_a_shift_move_that_cannot_move_selects_nothing():
    field = _make(Input, "hello")
    _park(field, 0)
    assert field.select_left() is False
    assert field.anchor is None and field.selection_range() is None
    assert field.select_home() is False  # already home: nothing to extend
    assert field.selection_range() is None


def test_the_selection_renders_the_band_over_the_prompted_row():
    theme = replace(DEFAULT_THEME, selection=Style(fg="#ff00ff"))
    field = _make(Input, "abcd", theme=theme)
    _park(field, 1)
    field.select_right()
    field.select_right()  # the selection is "bc"; the cursor sits on "d"
    assert field.selected_text == "bc"
    row = field.render(10)[0]
    assert row.text == "\u276e abcd"
    assert row.segments == (
        Segment("\u276e ", theme.accent),
        Segment("a"),
        Segment("bc", theme.selection),
        Segment("d", theme.cursor),
    )


def test_the_selection_outranks_the_cursor_on_a_cell_they_share():
    styles = dict(selection=Style(fg="#ff00ff"), cursor=Style(underline=True))
    theme = replace(DEFAULT_THEME, **styles)
    field = _make(Input, "abcd", theme=theme)
    _park(field, 3)
    field.select_left()
    field.select_left()  # the cursor is back inside the range: "b" is both
    assert field.selection_range() == (1, 3)
    row = field.render(10)[0]
    assert row.segments == (
        Segment("\u276e ", theme.accent),
        Segment("a"),
        Segment("b", theme.cursor.merge(theme.selection)),  # the band rides on top
        Segment("c", theme.selection),
        Segment("d"),
    )


def test_the_selection_band_renders_in_an_unfocused_field_without_a_cursor():
    theme = replace(DEFAULT_THEME, selection=Style(reverse=True))
    field = _make(Input, "abcd", theme=theme, focused=False)
    _park(field, 1)
    field.select_right()
    row = field.render(10)[0]
    assert row.segments == (
        Segment("\u276e ", theme.accent),
        Segment("a"),
        Segment("b", theme.selection),
        Segment("cd"),
    )


def test_a_selection_spans_the_rendered_rows():
    theme = replace(DEFAULT_THEME, selection=Style(reverse=True))
    editor = Editor(text="abcd\nefgh", theme=theme)
    _park(editor, 2)
    for _ in range(5):  # "cd", the break, "ef"
        assert editor.select_right() is True
    assert editor.selected_text == "cd\nef"
    rows = editor.render(20)
    assert [row.text for row in rows] == ["abcd", "efgh"]
    assert rows[0].segments == (Segment("ab"), Segment("cd", theme.selection))
    assert rows[1].segments == (  # the selected "ef" is one run; the cursor rides "g"
        Segment("ef", theme.selection),
        Segment("g", theme.cursor),
        Segment("h"),
    )


def test_the_selection_chords_ride_the_default_tables():
    chords = {
        "s-left": "select_left",
        "s-right": "select_right",
        "s-up": "select_up",
        "s-down": "select_down",
        "s-home": "select_home",
        "s-end": "select_end",
    }
    for table in (DEFAULT_INPUT_KEYMAP, DEFAULT_EDITOR_KEYMAP, EDITOR_SUBMIT_KEYMAP):
        for name, action in chords.items():
            assert table[name] == action, name
        assert table["c-a"] == "select_all"
    field = Input()
    for ch in "abc":
        field.insert(ch)
    assert field.handle(key("s-left")) is True
    assert field.selected_text == "c"
    assert field.handle(key("s-home")) is True
    assert field.selected_text == "abc" and field.selection_range() == (0, 3)
    assert field.handle(key("s-end")) is True
    assert field.selection_range() is None  # the cursor walked back onto the anchor


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make, width, text, expected",
    [
        (Input, 10, "ab", ["❮ ab "]),  # the block cursor trails the inserted text
        (Editor, 10, "ab", ["ab"]),  # seeded text parks the cursor at its start
        (Input, 6, "a\nbb\nccc", ["❮ a", "  bb", "  ccc "]),  # prompt once, then indent
        (Editor, 4, "abcdefgh", ["abcd", "efgh"]),  # every row a full-width wrap
    ],
)
def test_render_rows(make, width, text, expected):
    assert texts(_make(make, text), width) == expected


@pytest.mark.parametrize("make, width, empty_row", [(Input, 10, "❮  "), (Editor, 10, " ")])
def test_an_empty_focused_field_renders_the_cursor_cell(make, width, empty_row):
    assert texts(make(), width) == [empty_row]


@pytest.mark.parametrize(
    "make, width, hint_row",
    # The hint labels the empty field: it renders dim, and no cursor cell
    # rides it -- the block appears with the first typed character.
    [(Input, 30, "❮ hint"), (Editor, 10, "hint")],
)
def test_the_placeholder_is_dim_and_carries_no_cursor_block(make, width, hint_row):
    theme = replace(DEFAULT_THEME, dim=INJECTED)
    rows = make(placeholder="hint", theme=theme).render(width)
    assert rows[0].text == hint_row
    assert rows[0].segments[-1] == Segment("hint", INJECTED)
    assert all(not segment.style.reverse for segment in rows[0].segments)


def test_the_cursor_block_appears_with_the_first_typed_character():
    field = Editor(placeholder="hint", cursor_style=INJECTED)
    assert field.render(10)[0].segments == (Segment("hint", DEFAULT_THEME.dim),)
    field.insert("x")  # the cursor lands after the character it just typed
    assert field.render(10)[0].segments == (Segment("x", Style()), Segment(" ", INJECTED))


@pytest.mark.parametrize(
    "make, width, text, focused, expected",
    [
        (Input, 20, "abc", False, ["❮ abc"]),
        (Editor, 10, "ab", False, ["ab"]),
        (Input, 20, "abc", True, ["❮ abc "]),  # focused: the block cursor trails
    ],
)
def test_focused_off_renders_plainly_and_the_cursor_block_rides_the_focused_row(
    make, width, text, focused, expected
):
    rows = _make(make, text, focused=focused, style=INJECTED).render(width)
    assert [row.text for row in rows] == expected
    if focused:
        assert rows[0].segments[-1].style == INJECTED.merge(DEFAULT_THEME.cursor)
    else:
        assert rows[0].segments[-1] == Segment(text, INJECTED)  # plain: no cursor cell


@pytest.mark.parametrize(
    "make, width, text, cursor, expected",
    [
        (Input, 20, "abc", 1, (Segment("❮ ", PROMPT), Segment("a"), Segment("b", INJECTED), Segment("c"))),
        (Editor, 10, "abc", 1, (Segment("a"), Segment("b", INJECTED), Segment("c"))),
    ],
)
def test_the_cursor_block_restyles_the_character_under_it(make, width, text, cursor, expected):
    field = _make(make, text, cursor_style=INJECTED, prompt_style=PROMPT)
    _park(field, cursor)
    assert field.render(width)[0].segments == expected


@pytest.mark.parametrize(
    "make, width, text, row",
    # a row that is exactly full has no cell past its edge
    [(Input, 5, "abc", "❮ abc"), (Editor, 3, "abc", "abc")],
)
def test_a_full_row_skips_the_cursor_space(make, width, text, row):
    field = _make(make, text, cursor_style=INJECTED)
    _park(field, len(text))
    rendered = field.render(width)[0]
    assert rendered.text == row and rendered.width == width
    assert not any(seg.text == " " for seg in rendered.segments)  # no cursor space appended


def test_max_rows_caps_the_rows_with_a_window_around_the_cursor():
    text = "\n".join(f"line{i}" for i in range(10))
    assert len(Editor(text=text).render(20)) == 10  # no cap renders every row
    windowed = Editor(text=text, max_rows=3)
    assert texts(windowed, 20) == ["line0", "line1", "line2"]  # cursor at the start
    windowed.end()
    for _ in range(9):
        windowed.move_down()
    assert windowed.cursor == (9, 5)
    # "line9 " ends in the reverse-video cursor space: the cursor sits at the end.
    assert texts(windowed, 20) == ["line7", "line8", "line9 "]
    centred = Editor(text=text, max_rows=4)
    for _ in range(5):
        centred.move_down()
    assert texts(centred, 20) == ["line3", "line4", "line5", "line6"]


@pytest.mark.parametrize(
    "make, width, text, cursor, cell",
    [
        (Input, 6, "abcdefgh", 5, (1, 3)),  # row 1, past the two-wide indent
        (Input, 6, "abcdefgh", 1, (0, 3)),
        (Editor, 4, "abcdefgh", 5, (1, 1)),  # visual row 1 ("efgh"), column 1
        (Editor, 4, "abcdefgh", 0, (0, 0)),
        (Input, 10, "", 0, (0, 2)),  # the prompt-width column of an empty field
        (Editor, 10, "", 0, (0, 0)),  # the row-start cell of an empty field
    ],
)
def test_cursor_position_reports_the_block_cursor_cell(make, width, text, cursor, cell):
    field = _make(make, text)
    _park(field, cursor)
    assert field.cursor_position(width) == cell


def test_cursor_position_indexes_the_max_rows_window():
    windowed = Editor(text="\n".join(f"line{i}" for i in range(10)), max_rows=3)
    windowed.end()
    for _ in range(9):
        windowed.move_down()
    assert windowed.cursor_position(20) == (2, 5)  # in-window row index


def test_style_injection_round_trips_through_the_render():
    theme = replace(DEFAULT_THEME, cursor=INJECTED, dim=Style(italic=True), accent=INJECTED)
    field = _make(Input, "a", theme=theme)
    assert field.render(10)[0].segments[0] == Segment("❮ ", INJECTED)  # the prompt rides accent
    _park(field, 0)
    assert field.render(10)[0].segments[1] == Segment("a", theme.cursor)
    editor = Editor(placeholder="hi", theme=theme)
    assert editor.render(10)[0].segments == (Segment("hi", theme.dim),)
    # an explicit style wins over the theme's field
    override = Editor(cursor_style=Style(fg="#ff00ff"), theme=theme)
    override.insert("a")
    assert override.render(10)[0].segments[-1] == Segment(" ", Style(fg="#ff00ff"))


@pytest.mark.parametrize(
    "make, shown",
    [(Input, "Input('hi', cursor=(0, 2))"), (Editor, "Editor('hi', cursor=(0, 0))")],
)
def test_repr(make, shown):
    assert repr(_make(make, "hi")) == shown


@pytest.mark.parametrize("make", COMPONENTS)
def test_is_a_component(make):
    assert isinstance(make(), Component)


# ---------------------------------------------------------------------------
# TextBuffer.place -- the rendered cell's inverse geometry
# ---------------------------------------------------------------------------


def _buffer(text: str, *, width: int = 20, indent: int = 0) -> TextBuffer:
    """A buffer laid out at ``width``: the geometry ``place`` maps against."""
    buf = TextBuffer(text, keymap={}, indent=indent)
    buf.last_width = width
    return buf


def _cluster_start(text: str, cell: int) -> int:
    """The character index of the cluster covering display ``cell``.

    Stated independently of the engine: the first prefix whose width covers
    the cell; a cell left of the text answers 0 and a cell at or past the
    last cell answers ``len(text)``.
    """
    if cell < 0:
        return 0
    for index in range(len(text)):
        if cell < visible_width(text[: index + 1]):
            return index
    return len(text)


def test_place_docks_the_cursor_on_the_clicked_cell():
    buf = _buffer("hello world")
    assert buf.place(0, 0) is True and (buf.row, buf.col) == (0, 0)  # the first cell
    assert buf.place(0, 5) is True and (buf.row, buf.col) == (0, 5)  # the middle
    assert buf.place(0, 10) is True and (buf.row, buf.col) == (0, 10)  # the last character
    # the row's end cell, one cell past it, and a way-past column all fold
    # onto the row's end (row.end)
    for col in (11, 12, 999):
        assert buf.place(0, col) is True and (buf.row, buf.col) == (0, 11)


def test_place_on_an_empty_line_parks_at_the_line_start():
    buf = _buffer("a\n\nb")
    assert buf.place(1, 0) is True and (buf.row, buf.col) == (1, 0)
    assert buf.place(1, 7) is True and (buf.row, buf.col) == (1, 0)  # past the empty row
    assert buf.place(2, 1) is True and (buf.row, buf.col) == (2, 1)


def test_place_maps_a_wrapped_row_back_to_its_logical_line():
    buf = _buffer("abcdefghij", width=4)  # abcd / efgh / ij
    assert buf.place(1, 2) is True and (buf.row, buf.col) == (0, 6)  # the second segment
    assert buf.place(2, 1) is True and (buf.row, buf.col) == (0, 9)
    assert buf.place(2, 9) is True and (buf.row, buf.col) == (0, 10)  # the line's end
    # the visual row index is not the line index: the fourth visual row is
    # the second logical line
    buf = _buffer("abcdefghij\nxy", width=4)  # abcd / efgh / ij / xy
    assert buf.place(3, 1) is True and (buf.row, buf.col) == (1, 1)


def test_place_folds_the_indent_columns_onto_the_rows_start():
    buf = _buffer("abc", width=10, indent=2)
    assert buf.place(0, 0) is True and (buf.row, buf.col) == (0, 0)  # on the prompt's cell
    assert buf.place(0, 1) is True and (buf.row, buf.col) == (0, 0)
    assert buf.place(0, 3) is True and (buf.row, buf.col) == (0, 1)
    # a wrapped row's indent folds onto that row's own first character
    buf = _buffer("abcd", width=4, indent=2)  # ab / cd
    assert buf.place(1, 0) is True and (buf.row, buf.col) == (0, 2)
    assert buf.place(1, 2) is True and (buf.row, buf.col) == (0, 2)
    assert buf.place(1, 3) is True and (buf.row, buf.col) == (0, 3)


def test_place_lands_both_halves_of_a_wide_character_on_that_character():
    buf = _buffer("a中b")
    assert buf.place(0, 1) is True and buf.col == 1
    assert buf.place(0, 2) is True and buf.col == 1  # the trailing half folds back
    assert buf.place(0, 3) is True and buf.col == 2
    assert buf.place(0, 4) is True and buf.col == 3  # past the text: the row's end


def test_place_lands_both_cells_of_an_emoji_on_its_first_character():
    buf = _buffer("x😀y")
    assert buf.place(0, 1) is True and buf.col == 1
    assert buf.place(0, 2) is True and buf.col == 1  # the second cell of the emoji
    assert buf.place(0, 3) is True and buf.col == 2


def test_place_collapses_a_zwj_cluster_onto_its_first_character():
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467\u200d\U0001F466"
    assert len(family) == 7 and visible_width(family) == 2  # one two-cell cluster
    buf = _buffer(f"a{family}b")
    assert buf.place(0, 2) is True and buf.col == 1  # the cluster's second cell
    assert buf.place(0, 3) is True and buf.col == 8  # the "b" after the cluster


def test_place_answers_false_outside_the_visual_rows_and_changes_nothing():
    buf = _buffer("abc")
    assert buf.place(0, 2) is True and buf.col == 2
    assert buf.place(-1, 0) is False and (buf.row, buf.col) == (0, 2)
    assert buf.place(1, 0) is False and (buf.row, buf.col) == (0, 2)  # one past the only row
    buf = _buffer("abcdefghij", width=4)  # three visual rows
    assert buf.place(3, 0) is False and (buf.row, buf.col) == (0, 0)


def test_place_reports_a_hit_when_the_cursor_already_sat_there():
    buf = _buffer("abc")
    assert buf.place(0, 1) is True
    assert buf.place(0, 1) is True and (buf.row, buf.col) == (0, 1)


@pytest.mark.parametrize("indent", [0, 2])
def test_place_is_the_inverse_of_cursor_position_on_every_rendered_cell(indent):
    # The round-trip probe, rendering-free: for every cell of every visual
    # row the buffer wraps into -- wide characters, an emoji cluster, an
    # empty line and a hard-wrapped word included -- the caret docks on the
    # cluster covering the clicked cell, a cluster's first cell comes back
    # exactly, and the cell the cursor then reports is a fixed point.
    width = 5
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467\u200d\U0001F466"
    text = f"ab\u4e2dcd\U0001F600\n\nx{family}yzlongword"
    buf = _buffer(text, width=width, indent=indent)
    rows = buf.visual_rows(width, indent)
    assert len(rows) > 3  # the fixture really wraps
    for r, row in enumerate(rows):
        for c in range(width):
            assert buf.place(r, c) is True
            r2, c2 = buf.cursor_position(width, indent)
            index = _cluster_start(row.text, c - indent)
            assert buf.offset == row.start + index
            if 0 <= index < len(row.text) and visible_width(row.text[:index]) == c - indent:
                assert (r2, c2) == (r, c)  # a canonical cell round-trips exactly
            assert buf.place(r2, c2) is True
            assert buf.cursor_position(width, indent) == (r2, c2)  # a fixed point


# ---------------------------------------------------------------------------
# Field clicks -- the shell's row policy over TextBuffer.place
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("make", COMPONENTS)
def test_the_fields_are_clickable(make):
    assert isinstance(make(), Clickable)


def test_input_click_places_the_caret_between_the_prompt_and_the_text():
    field = Input(prompt="\u276e ")  # two columns of prompt
    field.insert("abcdef")
    assert field.click(0, 4) is True  # the prompt's two columns, then two characters
    assert field.cursor == (0, 2)
    assert field.click(0, 1) is True  # a cell of the prompt itself
    assert field.cursor == (0, 0)
    assert field.click(0, 99) is True  # past the text: the row's end
    assert field.cursor == (0, 6)
    assert field.click(1, 0) is False and field.cursor == (0, 6)  # a single row only
    assert field.click(-1, 0) is False and field.cursor == (0, 6)


def test_input_click_accepts_the_visual_rows_of_a_multi_row_residue():
    field = Input()
    field.insert("a\nbb")  # the host's own insert keeps the newline (two rows)
    assert len(field.render(10)) == 2
    assert field.click(1, 1) is True  # a cell of the second row's prompt-width indent
    assert field.cursor == (0, 2)  # folds onto that row's first character: "a\n" + 0
    assert field.click(1, 3) is True  # the prompt's two columns, then one character
    assert field.cursor == (0, 3)


def test_editor_click_maps_a_windowed_row_back_to_its_buffer_row():
    editor = Editor(text="\n".join(f"row {i}" for i in range(10)), max_rows=3)
    editor.end()
    for _ in range(4):
        editor.move_down()
    assert editor.cursor == (4, 5)
    assert texts(editor, 20) == ["row 3", "row 4 ", "row 5"]  # the cursor's window
    assert editor.click(2, 2) is True  # the window's third row is buffer row 5
    assert editor.cursor == (5, 2)
    assert texts(editor, 20) == ["row 4", "row 5", "row 6"]  # re-centred on the click
    assert editor.cursor_position(20) == (1, 2)
    assert editor.click(3, 0) is False  # no fourth rendered row: row 6 is outside now
    assert editor.cursor == (5, 2)
    assert editor.click(-1, 0) is False and editor.cursor == (5, 2)


def test_editor_click_without_a_window_indexes_the_whole_buffer():
    editor = Editor(text="abc\ndefgh\nij")
    assert editor.click(2, 1) is True
    assert editor.cursor == (2, 1)
    assert editor.click(3, 0) is False  # one row past the last
    assert editor.cursor == (2, 1)


def test_a_ring_click_reaches_an_unfocused_field_and_then_focuses_it():
    first, second = Editor(text="ab"), Editor(text="cd")
    ring = FocusRing([first, second])
    assert (first.focused, second.focused) == (True, False)
    assert ring.click(Hit(Block("b", second), 0, 1, "p0")) is True
    assert second.cursor == (0, 1)  # the cell was dispatched before the focus moved
    assert ring.focused is second and (first.focused, second.focused) == (False, True)
