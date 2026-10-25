"""Input and Editor: one editing contract, rendered as rows with a block cursor.

The public behavior: keymap routing, insert/backspace/delete/newline, undo and
redo with merged typing runs, the text selection, the rendered rows (prompt,
placeholder, mask, window) and the click/cursor mapping.
"""

from dataclasses import replace

import pytest

from motui.kernel.keymap import DEFAULT_EDITOR_KEYMAP
from motui.kernel.cell import Surface
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.text import WrapMode
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import Editor, Input
from motui.widgets.textbuf import TextBuffer

from tests.testing import key, paste, texts

FIELDS = [Input, Editor]
INJECTED = Style(fg="#abcdef")
BODY_STYLES = Styles(text=replace(DEFAULT_THEME.text, base=INJECTED))
CARET_STYLES = Styles(text=replace(DEFAULT_THEME.text, caret=INJECTED))


def park(field, offset: int) -> None:
    """Park the cursor at the flat ``offset`` through the public moves."""
    while field.move_left():
        pass
    for _ in range(offset):
        field.move_right()


def flat(field) -> int:
    """The cursor as a flat offset into the component's text."""
    row, col = field.cursor
    return sum(len(line) + 1 for line in field.text.split("\n")[:row]) + col


# -- routing -----------------------------------------------------------------


@pytest.mark.parametrize("make", FIELDS)
def test_printables_insert_at_the_cursor(make):
    field = make()
    assert field.handle(key("a", "a")) is True
    assert field.handle(key("space", " ")) is True
    assert field.text == "a " and field.cursor == (0, 2)


@pytest.mark.parametrize("make, consumed, expected", [(Input, False, ""), (Editor, True, "\n")])
def test_enter_is_the_editors_newline_and_the_inputs_submit_gesture(make, consumed, expected):
    field = make()
    assert field.handle(key("enter")) is consumed
    assert field.text == expected


@pytest.mark.parametrize("name", ["escape", "page_up"])
def test_unbound_keys_are_declined_and_change_nothing(name):
    field = Input("ab")
    park(field, 2)
    assert field.handle(key(name)) is False
    assert field.text == "ab" and flat(field) == 2


def test_a_custom_keymap_rebinds_and_drops_a_key():
    field = Input("ab", keymap={"c-j": "clear"})
    assert field.handle(key("c-j")) is True and field.text == ""
    editor = Editor("ab", keymap={"c-j": "newline"})
    park(editor, 2)
    assert editor.handle(key("c-j")) is True and editor.text == "ab\n"


def test_input_folds_every_newline_run_of_a_paste_into_one_space():
    field = Input()
    assert field.handle(paste("a\r\n\r\nb\nc")) is True
    assert field.text == "a b c" and field.cursor == (0, 5)
    assert texts(field, 30) == ["\u276f a b c "]


def test_editor_keeps_the_newlines_of_a_paste():
    editor = Editor()
    assert editor.handle(paste("a\r\nb\nc")) is True
    assert editor.text == "a\r\nb\nc"
    assert len(editor.render(Constraints(width=10))) == 3


def test_an_explicit_insert_keeps_newlines_even_in_an_input():
    field = Input()
    field.insert("\n")
    # The buffer keeps the logical break; the single-line view paints it as
    # one space, so the field still renders exactly one row.
    assert field.text == "\n" and len(field.render(Constraints(width=10))) == 1
    assert field.render(Constraints(width=10))[0].text == "\u276f   "


# -- editing verbs -----------------------------------------------------------


def test_insert_backspace_delete_and_clear():
    field = Input()
    assert field.backspace() is False and field.delete() is False
    field.insert("ac")
    park(field, 1)
    field.insert("b")
    assert field.text == "abc" and flat(field) == 2
    assert field.delete() is True and field.text == "ab"
    assert field.backspace() is True and field.text == "a"
    field.clear()
    assert field.text == "" and field.cursor == (0, 0)


def test_newline_splits_the_line_at_the_cursor():
    editor = Editor("abcd")
    park(editor, 2)
    assert editor.newline() is True
    assert editor.text == "ab\ncd" and editor.cursor == (1, 0)


def test_backspace_and_delete_merge_lines():
    editor = Editor("ab\ncd")
    editor.end()
    assert editor.backspace() is True and editor.text == "a\ncd"
    editor.move_right()
    assert editor.backspace() is True
    assert editor.text == "acd" and editor.cursor == (0, 1)
    editor = Editor("ab\ncd")
    editor.end()
    assert editor.delete() is True and editor.text == "abcd" and editor.cursor == (0, 2)
    editor.end()
    assert editor.delete() is False


def test_moves_cross_line_boundaries_and_clamp():
    editor = Editor("ab\ncd")
    assert editor.move_left() is False
    editor.end()
    assert editor.move_right() is True and editor.cursor == (1, 0)
    editor.home()
    assert editor.move_left() is True and editor.cursor == (0, 2)
    editor.move_right()
    editor.end()
    assert editor.cursor == (1, 2) and editor.move_right() is False


def test_up_and_down_follow_the_wrapped_rows():
    editor = Editor("abcdefgh\nwxyz")
    editor.render(Constraints(width=4))
    park(editor, 1)
    assert editor.move_down() is True and flat(editor) == 5
    assert editor.move_up() is True and flat(editor) == 1
    assert editor.move_up() is False


def test_home_and_end_stay_inside_the_logical_line():
    field = Input("ab\ncd")
    park(field, 4)
    assert field.home() is True and field.cursor == (0, 3)
    assert field.home() is False
    assert field.end() is True and field.cursor == (0, 5)
    assert field.end() is False


# -- history -----------------------------------------------------------------


def test_undo_and_redo_round_trip_a_change():
    field = Input()
    field.insert("ab")
    assert field.undo() is True and field.text == ""
    assert field.redo() is True and field.text == "ab"
    assert field.redo() is False


def test_runs_of_single_character_inserts_merge_into_one_step():
    field = Input()
    for char in "abc":
        assert field.handle(key(char, char)) is True
    assert field.undo() is True and field.text == ""
    assert field.redo() is True and field.text == "abc"


def test_a_move_breaks_the_typing_run_into_a_separate_step():
    field = Input()
    field.insert("ab")
    field.move_left()
    field.insert("c")
    assert field.text == "acb"
    assert field.undo() is True and field.text == "ab"
    assert field.undo() is True and field.text == ""
    assert field.undo() is False


def test_the_undo_history_is_bounded():
    field = Input()
    for _ in range(150):
        field.insert("x")
        field.move_left()
        field.move_right()
    undone = 0
    while field.undo():
        undone += 1
    assert undone == 100
    assert field.text == "x" * 50


# -- selection ---------------------------------------------------------------


def test_shift_moves_extend_the_selection_from_the_anchor_both_ways():
    field = Input("hello")
    park(field, 2)
    assert field.selection_range() is None
    assert field.select_left() is True
    assert field.selection_range() == (1, 2) and field.selected_text == "e"
    assert field.select_left() is True and field.selected_text == "he"
    assert field.select_left() is False and field.selection_range() == (0, 2)
    assert field.select_right() is True and field.select_right() is True
    assert field.selection_range() is None
    assert field.select_right() is True and field.selected_text == "l"


def test_select_all_takes_the_whole_buffer():
    field = Input("hello")
    assert field.select_all() is True
    assert field.selection_range() == (0, 5) and field.selected_text == "hello"
    assert Input().select_all() is False
    field.clear_selection()
    assert field.selection_range() is None


def test_typing_replaces_the_selection_in_one_history_step():
    field = Input("hello world")
    park(field, 6)
    for _ in range(5):
        assert field.select_right() is True
    field.insert("there")
    assert field.text == "hello there" and field.cursor == (0, 11)
    assert field.undo() is True and field.text == "hello world"


def test_plain_moves_and_clicks_clear_the_selection():
    field = Input("hello")
    park(field, 5)
    field.select_left()
    assert field.selection_range() == (4, 5)
    field.move_left()
    assert field.selection_range() is None
    field.select_left()
    field.click(0, 4)
    assert field.selection_range() is None


def test_the_selection_renders_as_a_band_over_the_text():
    theme = replace(
        DEFAULT_THEME,
        text=replace(
            DEFAULT_THEME.text,
            selection=Style(reverse=True),
            caret=Style(underline=True),
        ),
    )
    field = Input("abcd", theme=theme)
    park(field, 1)
    field.select_right()
    field.select_right()
    row = field.render(Constraints(width=10))[0]
    assert row.text == "\u276f abcd"
    marked = [seg for seg in row.segments if seg.style.reverse]
    assert "".join(seg.text for seg in marked) == "bc"
    assert all(seg.style.underline is False for seg in marked)


def test_the_selection_outranks_the_cursor_on_a_shared_cell():
    theme = replace(
        DEFAULT_THEME,
        text=replace(
            DEFAULT_THEME.text,
            selection=Style(reverse=True),
            caret=Style(underline=True),
        ),
    )
    field = Input("abcd", theme=theme)
    park(field, 3)
    field.select_left()
    field.select_left()
    row = field.render(Constraints(width=10))[0]
    shared = [seg.text for seg in row.segments if seg.style.reverse and seg.style.underline]
    assert shared == ["b"]


# -- rendering ---------------------------------------------------------------


@pytest.mark.parametrize(
    "make, width, text, expected",
    [
        (Input, 10, "ab", ["\u276f ab"]),
        (Input, 6, "a\nbb\nccc", ["\u276f a bb"]),
        (Editor, 4, "abcdefgh", ["abcd", "efgh"]),
    ],
)
def test_render_rows(make, width, text, expected):
    assert texts(make(text), width) == expected


@pytest.mark.parametrize("make, expected", [(Input, "\u276f  "), (Editor, " ")])
def test_an_empty_focused_field_renders_the_cursor_cell(make, expected):
    assert texts(make(), 10) == [expected]


@pytest.mark.parametrize("make, expected", [(Input, "\u276f hint"), (Editor, "hint")])
def test_the_placeholder_is_dim_and_carries_no_cursor_cell(make, expected):
    theme = replace(DEFAULT_THEME, text=replace(DEFAULT_THEME.text, faint=INJECTED))
    row = make(placeholder="hint", theme=theme).render(Constraints(width=10))[0]
    assert row.text == expected
    assert row.segments[-1].style == INJECTED
    assert all(seg.style.reverse is False for seg in row.segments)


@pytest.mark.parametrize("make, expected", [(Input, "\u276f abc")])
def test_unfocused_fields_render_without_a_cursor(make, expected):
    field = make("abc", styles=BODY_STYLES)
    field.focused = False
    row = field.render(Constraints(width=20))[0]
    assert row.text == expected
    assert row.segments[-1].style == INJECTED


def test_the_cursor_block_restyles_the_character_under_it():
    field = Editor("abc", styles=CARET_STYLES)
    park(field, 1)
    segments = field.render(Constraints(width=10))[0].segments
    assert [seg.text for seg in segments] == ["a", "b", "c"]
    assert segments[1].style == Style().merge(INJECTED)


def test_a_row_end_cursor_is_a_space_unless_the_row_is_full():
    field = Editor("abc", styles=CARET_STYLES)
    park(field, 3)
    row = field.render(Constraints(width=10))[0]
    assert row.text == "abc " and row.segments[-1].text == " "
    full = Editor("abc", styles=CARET_STYLES)
    park(full, 3)
    assert full.render(Constraints(width=3))[0].text == "abc"
    assert all(seg.text != " " for seg in full.render(Constraints(width=3))[0].segments)


def test_a_mask_replaces_rendered_characters_and_keeps_the_text_plain():
    field = Editor("hunter2", mask="\u2022")
    field.focused = False
    assert field.render(Constraints(width=20))[0].text == "\u2022" * 7
    assert field.text == "hunter2" and field.mask == "\u2022"
    wide = Editor("\u4e2dab", mask="\u2022")
    wide.focused = False
    assert wide.render(Constraints(width=20))[0].text == "\u2022" * 4


def test_the_mask_keeps_the_cursor_geometry_of_the_plain_text():
    masked, plain = Input(mask="\u2022"), Input()
    for field in (masked, plain):
        field.insert("abc")
        park(field, 1)
    assert masked.render(Constraints(width=20))[0].text == "\u276f \u2022\u2022\u2022"
    assert masked.cursor_position(20) == plain.cursor_position(20)


def test_max_rows_windows_the_rows_around_the_cursor():
    text = "\n".join(f"line{i}" for i in range(10))
    assert len(Editor(text).render(Constraints(width=20))) == 10
    windowed = Editor(text, max_rows=3)
    assert texts(windowed, 20) == ["line0", "line1", "line2"]
    windowed.end()
    for _ in range(9):
        windowed.move_down()
    assert texts(windowed, 20) == ["line7", "line8", "line9 "]


@pytest.mark.parametrize(
    "make, width, text, cursor, cell",
    [
        (Input, 6, "abcdefgh", 5, (0, 5)),
        (Editor, 4, "abcdefgh", 5, (1, 1)),
    ],
)
def test_cursor_position_reports_the_block_cursor_cell(make, width, text, cursor, cell):
    field = make(text)
    park(field, cursor)
    assert field.cursor_position(width) == cell


def test_a_theme_assignment_repaints_the_memoized_rows():
    field = Input("abc")
    plain = field.render(Constraints(width=20))
    field.theme = replace(
        DEFAULT_THEME, text=replace(DEFAULT_THEME.text, base=Style(underline=True))
    )
    repainted = field.render(Constraints(width=20))
    assert repainted != plain
    assert any(seg.style.underline for seg in repainted[0].segments)


def test_the_hover_flag_merges_the_theme_band_over_the_whole_row():
    theme = replace(DEFAULT_THEME, surfaces=replace(DEFAULT_THEME.surfaces, hover=Style(reverse=True)))
    field = Input("ab", theme=theme)
    plain = field.render(Constraints(width=10))
    field.hover = True
    marked = field.render(Constraints(width=10))
    assert marked != plain
    assert all(seg.style.reverse for seg in marked[0].segments)
    field.hover = False
    assert field.render(Constraints(width=10)) == plain


# -- clicks and the public input surface -------------------------------------


def test_click_places_the_cursor_between_the_prompt_and_the_text():
    field = Input()
    field.insert("abcdef")
    assert field.click(0, 4) is True and field.cursor == (0, 2)
    assert field.click(0, 1) is True and field.cursor == (0, 0)
    assert field.click(0, 99) is True and field.cursor == (0, 6)
    assert field.click(1, 0) is False and field.cursor == (0, 6)


def test_editor_click_maps_a_windowed_row_back_to_its_buffer_row():
    editor = Editor("\n".join(f"row {i}" for i in range(10)), max_rows=3)
    editor.end()
    for _ in range(4):
        editor.move_down()
    assert texts(editor, 20) == ["row 3", "row 4 ", "row 5"]
    assert editor.click(2, 2) is True and editor.cursor == (5, 2)
    assert editor.click(3, 0) is False and editor.cursor == (5, 2)


@pytest.mark.parametrize("make", FIELDS)
def test_read_only_declines_routed_events_until_the_host_clears_the_flag(make):
    field = make("keep", read_only=True)
    assert field.handle(key("x", "x")) is False
    assert field.handle(paste("paste")) is False
    assert field.text == "keep"
    field.read_only = False
    park(field, len(field.text))
    assert field.handle(key("x", "x")) is True and field.text == "keepx"


def test_the_text_setter_replaces_the_buffer_and_clears_history():
    field = Editor("first")
    field.insert("!")
    field.text = "second\nline"
    assert field.text == "second\nline" and field.cursor == (0, 0)
    assert field.undo() is False


# -- the value cache ---------------------------------------------------------


def test_value_reads_between_writes_share_one_string():
    buffer = TextBuffer("ab\ncd", keymap=DEFAULT_EDITOR_KEYMAP)
    value = buffer.value
    assert value == "ab\ncd"
    assert buffer.value is value


def test_an_edit_updates_value_once_and_caches_again():
    buffer = TextBuffer("ab\ncd", keymap=DEFAULT_EDITOR_KEYMAP)
    assert buffer.value is buffer.value
    buffer.end()
    buffer.insert("x")
    assert buffer.value == "abx\ncd"
    assert buffer.value is buffer.value


def test_undo_and_redo_keep_value_true():
    buffer = TextBuffer("ab", keymap=DEFAULT_EDITOR_KEYMAP)
    assert buffer.value == "ab"
    buffer.end()
    buffer.insert("c")
    assert buffer.value == "abc"
    assert buffer.undo() is True and buffer.value == "ab"
    assert buffer.redo() is True and buffer.value == "abc"


def test_set_text_rejoins_the_replacement():
    buffer = TextBuffer("ab", keymap=DEFAULT_EDITOR_KEYMAP)
    assert buffer.value == "ab"
    buffer.set_text("x\ny")
    assert buffer.value == "x\ny"
    assert buffer.value is buffer.value


# -- the 2.0 render contract -------------------------------------------------


def test_the_text_fields_take_constraints_and_honour_the_height_budget():
    field = Input("hello")
    assert isinstance(field.render(Constraints(width=20)), Surface)
    assert field.render(Constraints(width=20)) == field.render(Constraints(width=20))
    assert list(field.render(Constraints(width=20, max_height=0))) == []
    assert field.render(Constraints(width=20, max_height=1)).height == 1

    editor = Editor("a\nb\nc")
    assert isinstance(editor.render(Constraints(width=20)), Surface)
    assert editor.render(Constraints(width=20)) == editor.render(Constraints(width=20))
    assert editor.render(Constraints(width=20, max_height=2)).height == 2


def test_a_truncated_field_keeps_the_buffer_wrap_geometry():
    field = Input("hello world")
    assert field.render(Constraints(width=8, max_height=1)).height == 1
    # The budget shapes the returned rows only: the buffer's visual geometry
    # still comes from the constrained width, so the second wrapped row exists
    # for the click mapping even though it was not painted.
    assert field.click(1, 0) is True
    assert field.cursor == (0, 6)


def test_a_truncated_editor_render_is_byte_identical_to_the_width_render():
    editor = Editor("a\nb\nc")
    narrow = editor.render(Constraints(width=20, max_height=2))
    assert narrow.rows == tuple(editor.render(Constraints(width=20)))[:2]
    assert editor.render(Constraints(width=20)) == editor.render(Constraints(width=20))


def test_editor_wrap_defaults_to_word_and_keeps_the_current_bytes():
    text = "the quick brown fox"
    assert Editor(text).wrap is WrapMode.WORD
    assert Editor(text).render(Constraints(width=10)) == Editor(
        text, wrap=WrapMode.WORD
    ).render(Constraints(width=10))
    # The default guard trims an over-wide cluster exactly like ELLIPSIS.
    assert Editor("\u65e5").render(Constraints(width=1)) == Editor(
        "\u65e5", wrap=WrapMode.ELLIPSIS
    ).render(Constraints(width=1))


def test_editor_wrap_selects_the_final_row_guard():
    assert Editor("\u65e5").render(Constraints(width=1))[0].text == "\u2026"
    assert (
        Editor("\u65e5", wrap=WrapMode.CLIP).render(Constraints(width=1))[0].text == ""
    )
    # OVERFLOW keeps the logical row whole and hands its natural width out.
    overflow = Editor("abc", wrap=WrapMode.OVERFLOW)
    assert overflow.wrap is WrapMode.OVERFLOW
    surface = overflow.render(Constraints(width=2))
    assert surface.width == 3 and surface[0].text == "abc"


def test_editor_overflow_renders_logical_lines_at_their_natural_width():
    long_line = "value=" + "x" * 200
    editor = Editor(long_line + "\nsecond", wrap=WrapMode.OVERFLOW)
    surface = editor.render(Constraints(width=80))
    assert surface.width == len(long_line)
    assert [row.text for row in surface] == [long_line, "second"]
    assert all(row.width <= surface.width for row in surface)
    # The cursor stays on the logical line: at its end the block is the
    # reverse-video space, one cell past the text.
    editor.end()
    surface = editor.render(Constraints(width=80))
    assert surface[0].text == long_line + " "
    assert editor.cursor_position(80) == (0, len(long_line))


def test_editor_overflow_moves_between_logical_lines():
    editor = Editor("abc\nlong line\nz", wrap=WrapMode.OVERFLOW)
    assert editor.move_down() is True and editor.cursor == (1, 0)
    editor.end()
    assert editor.cursor == (1, 9)
    assert editor.move_down() is True
    assert editor.cursor == (2, 1)  # clamped to the shorter line's end
    assert editor.move_up() is True and editor.cursor == (1, 1)
    assert editor.select_up() is True and editor.selected_text == "bc\nl"
    assert editor.move_up() is False and editor.selected_text == ""


def test_editor_overflow_click_maps_logical_rows_and_columns():
    editor = Editor("abc\ndefgh", wrap=WrapMode.OVERFLOW)
    assert editor.click(1, 3) is True
    assert editor.cursor == (1, 3)
    assert editor.click(2, 0) is False


def test_editor_overflow_keeps_the_mask_and_selection_on_logical_rows():
    editor = Editor("secret\nmore", mask="\u2022", wrap=WrapMode.OVERFLOW)
    assert editor.select_all() is True
    surface = editor.render(Constraints(width=4))
    assert surface.width == 6
    # The cursor blocks the end of the selected last line, so its text is
    # one reverse-video cell longer than the masked content.
    assert [row.text for row in surface] == ["\u2022" * 6, "\u2022" * 4 + " "]
    assert "s" not in "".join(row.text for row in surface)


def test_the_editor_default_wrap_still_wraps_within_the_width():
    editor = Editor("x" * 200)
    surface = editor.render(Constraints(width=80))
    assert surface.width == 80
    assert surface.height > 1
    assert all(row.width <= 80 for row in surface)


def test_editor_wrap_is_part_of_the_revision():
    assert Editor("abc").revision() != Editor("abc", wrap=WrapMode.CLIP).revision()
    editor = Editor("abc", wrap=WrapMode.WORD)
    editor.wrap = WrapMode.CLIP
    assert editor.wrap is WrapMode.CLIP
    assert editor.revision() == Editor("abc", wrap=WrapMode.CLIP).revision()


def test_input_defaults_to_the_overflow_single_line_guard():
    assert Input().wrap is WrapMode.OVERFLOW
    # Two columns hold the wide glyph and its cursor block; one column cannot
    # hold both, so the row is the cursor's own cell (no ellipsis marker).
    assert Input("\u65e5", prompt="").render(Constraints(width=2))[0].text == "\u65e5"
    assert Input("\u65e5", prompt="").render(Constraints(width=1))[0].text == " "


# -- single-line overflow: the W2.5b default ---------------------------------


@pytest.mark.parametrize("width", [20, 40])
def test_a_long_input_stays_one_row(width):
    field = Input("x" * 200)
    assert field.render(Constraints(width=width)).height == 1
    park(field, 200)
    surface = field.render(Constraints(width=width))
    assert surface.height == 1
    assert all(len(row.text) <= width for row in surface)


def test_the_input_cursor_at_the_end_stays_visible():
    field = Input("abcdefghij", prompt="", styles=CARET_STYLES)
    park(field, 10)
    row = field.render(Constraints(width=5))[0]
    assert row.text == "ghij "
    caret = DEFAULT_THEME.text.base.merge(INJECTED)
    assert row.segments[-1].text == " " and row.segments[-1].style == caret
    assert field.cursor_position(5) == (0, 4)


def test_home_and_end_move_the_horizontal_window():
    field = Input("abcdefghij", prompt="")
    park(field, 10)
    assert field.render(Constraints(width=5))[0].text == "ghij "
    field.home()
    assert field.render(Constraints(width=5))[0].text == "abcde"
    field.end()
    assert field.render(Constraints(width=5))[0].text == "ghij "


def test_a_long_placeholder_stays_one_row_without_a_cursor():
    field = Input("", placeholder="a very long hint that cannot fit")
    surface = field.render(Constraints(width=10))
    assert surface.height == 1
    assert surface[0].text == "\u276f a very l"
    assert all(seg.style.reverse is False for seg in surface[0].segments)


def test_a_masked_input_is_one_row_and_keeps_the_caret_on_the_mask():
    field = Input("secret", mask="\u2022", prompt="")
    park(field, 6)
    surface = field.render(Constraints(width=4))
    assert surface.height == 1
    assert surface[0].text == "\u2022\u2022\u2022 "
    assert "s" not in surface[0].text
    assert field.cursor_position(4) == (0, 3)


def test_a_prompt_wider_than_the_field_shows_only_the_prompt():
    field = Input("hello", prompt="verylongprompt")
    surface = field.render(Constraints(width=5))
    assert surface.height == 1
    assert surface[0].text == "veryl"


def test_newlines_paint_one_cell_and_keep_the_character_offsets():
    field = Input("ab\ncd", prompt="", styles=CARET_STYLES)
    park(field, 4)  # on the 'd' after the folded break
    row = field.render(Constraints(width=4))[0]
    assert row.text == "b cd"
    assert field.cursor == (0, 4)
    caret = DEFAULT_THEME.text.base.merge(INJECTED)
    assert row.segments[1].text == "d" and row.segments[1].style == caret


def test_a_crlf_pair_keeps_both_character_offsets():
    field = Input("ab\r\ncd", prompt="")
    field.focused = False
    assert field.render(Constraints(width=10))[0].text == "ab  cd"
    field.focused = True
    park(field, 6)
    assert field.render(Constraints(width=4))[0].text == " cd "
    assert field.cursor_position(4) == (0, 3)


def test_an_input_can_opt_back_into_the_shared_wrap_guard():
    field = Input("\u65e5", prompt="")
    assert field.render(Constraints(width=1))[0].text == " "
    field.wrap = WrapMode.ELLIPSIS
    assert field.wrap is WrapMode.ELLIPSIS
    assert field.render(Constraints(width=1))[0].text == "\u2026"
    assert Input("abc").revision() != Input("abc", wrap=WrapMode.CLIP).revision()
