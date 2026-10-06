"""Tests for the editing components: Input and Editor over one engine.

Cursor-edited text rendered as rows with a reverse-video block cursor; every
shared contract is tested once, parametrized over the two components.
"""

from dataclasses import replace

import pytest

from mocode_tui.core.block import Component
from mocode_tui.core.events import Paste
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.keys.keymap import (
    COMPOSER_KEYMAP,
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
)
from mocode_tui.widgets.editor import Editor
from mocode_tui.widgets.input import Input

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


def test_the_composer_keymap_is_the_editor_chain_without_enter():
    # The three tables are one derivation chain in keys.keymap: input ->
    # editor (+enter) -> composer (-enter, +c-j); every other binding
    # survives the trip verbatim.
    assert COMPOSER_KEYMAP == {**DEFAULT_INPUT_KEYMAP, "c-j": "newline"}
    assert set(COMPOSER_KEYMAP) == set(DEFAULT_EDITOR_KEYMAP) - {"enter"} | {"c-j"}
    assert COMPOSER_KEYMAP["c-j"] == "newline" and "enter" not in COMPOSER_KEYMAP
    assert Editor(keymap=COMPOSER_KEYMAP).keymap is COMPOSER_KEYMAP


@pytest.mark.parametrize("make, end", [(Input, (0, 3)), (Editor, (0, 3))])
def test_printables_and_space_insert_without_a_keymap_entry(make, end):
    field = make(keymap={})
    assert field.handle(key("a", "a")) is True
    assert field.handle(key("b", "b")) is True
    assert field.handle(key("space", " ")) is True
    assert _text(field) == "ab " and field.cursor == end


@pytest.mark.parametrize("make, end", [(Input, (0, 9)), (Editor, (1, 5))])
def test_paste_inserts_multiline_text(make, end):
    field = make()
    assert field.handle(Paste("two\nlines")) is True
    assert _text(field) == "two\nlines" and field.cursor == end


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
    assert field.handle(key("c-a")) is True and _pos(field) == 0
    assert field.handle(key("c-e")) is True and _pos(field) == 3
    assert field.handle(key("end")) is True and _pos(field) == 3
    assert field.handle(key("backspace")) is True and _text(field) == "ab"
    # delete at the end deletes nothing, yet the mapped key was consumed.
    assert field.handle(key("delete")) is True and _text(field) == "ab"
    _park(field, 1)
    assert field.handle(key("delete")) is True and _text(field) == "a"
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
