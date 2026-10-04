"""Tests for mocode_tui.components.input (Input)."""

from mocode_tui.components.input import Input
from mocode_tui.lines import Line, Segment
from mocode_tui.style import ACCENT, CURSOR, DIM, NONE


def _rows(input_: Input, width: int) -> list[str]:
    return [row.text for row in input_.render(width)]


# --- editing: insert / delete / clear ------------------------------------------


def test_insert_moves_cursor_to_end_of_paste():
    field = Input()
    field.insert("ab")
    assert field.text == "ab"
    assert field.cursor == 2


def test_insert_lands_at_cursor_position():
    field = Input()
    field.insert("ac")
    field.move_left()
    field.insert("b")
    assert field.text == "abc"
    assert field.cursor == 2


def test_insert_accepts_multiline():
    field = Input()
    field.insert("one\ntwo")
    assert field.text == "one\ntwo"
    assert field.cursor == 7


def test_newline_inserts_break():
    field = Input()
    field.insert("ab")
    field.newline()
    field.insert("cd")
    assert field.text == "ab\ncd"
    assert field.cursor == 5


def test_backspace_and_delete_boundaries():
    field = Input()
    assert field.backspace() is False  # empty
    assert field.delete() is False
    field.insert("abc")
    assert field.cursor == 3
    assert field.delete() is False  # at the end
    assert field.backspace() is True
    assert field.text == "ab" and field.cursor == 2
    field.move_left()
    assert field.delete() is True  # deletes the char at the cursor
    assert field.text == "a" and field.cursor == 1


def test_clear_resets_text_and_cursor():
    field = Input()
    field.insert("stuff")
    field.clear()
    assert field.text == "" and field.cursor == 0


# --- editing: cursor movement ---------------------------------------------------


def test_move_left_and_right_boundaries():
    field = Input()
    field.insert("ab")
    assert field.move_right() is False  # already at the end
    assert field.move_left() is True and field.cursor == 1
    assert field.move_left() is True and field.cursor == 0
    assert field.move_left() is False
    assert field.move_right() is True and field.cursor == 1


def test_home_and_end_stay_on_the_logical_line():
    field = Input()
    field.insert("ab\ncd")
    field.move_left()  # between c and d (cursor 5 -> 4)
    assert field.cursor == 4
    assert field.home() is True and field.cursor == 3  # start of "cd"
    assert field.home() is False  # already home
    assert field.end() is True and field.cursor == 5  # before the end of text
    assert field.end() is False
    field.home()
    field.move_up()
    field.end()  # end of the first logical line ("ab")
    assert field.cursor == 2


def test_move_up_and_down_keep_column_when_wrapped():
    field = Input()
    field.insert("abcdefgh")  # wraps to "abcd" / "efgh" at width 6 (inner 4)
    field.render(6)
    field.cursor = 1  # column 1 of the first visual row
    assert field.move_down() is True
    assert field.cursor == 5  # column 1 of the second visual row
    assert field.move_up() is True
    assert field.cursor == 1


def test_move_up_and_down_across_logical_lines():
    field = Input()
    field.insert("ab\ncd")
    field.render(20)
    field.cursor = 1
    assert field.move_down() is True
    assert field.cursor == 4  # column 1 of "cd"
    assert field.move_up() is True
    assert field.cursor == 1
    assert field.move_up() is False  # top visual row


def test_move_down_clamps_column_on_shorter_row():
    field = Input()
    field.insert("abcd\nxy")
    field.render(20)
    field.cursor = 3  # column 3 of "abcd"
    assert field.move_down() is True
    assert field.cursor == 7  # clamped to the end of "xy" (column 2)


def test_move_up_uses_last_width_before_first_render():
    field = Input()
    field.insert("x" * 90)  # 78 per row at the 80-column fallback (prompt is 2)
    field.cursor = 0
    field.move_down()
    assert field.cursor == 78
    field.move_up()
    assert field.cursor == 0


# --- rendering: prompt, placeholder, cursor ---------------------------------------


def test_prompt_only_on_first_row_continuation_rows_indent():
    field = Input()
    field.insert("ab\ncd")
    field.cursor = 0  # keep the trailing cursor space off the last row
    rows = _rows(field, 20)
    assert rows == ["\u276e ab", "  cd"]
    assert field.render(20)[1].segments[0] == Segment("  ")


def test_cursor_restyles_character_under_it():
    field = Input()
    field.insert("abc")
    field.cursor = 1
    row = field.render(20)[0]
    assert row.text == "\u276e abc"
    assert row.segments == (
        Segment("\u276e ", ACCENT),
        Segment("a", NONE),
        Segment("b", CURSOR),
        Segment("c", NONE),
    )


def test_cursor_at_row_end_appends_reverse_space():
    field = Input()
    field.insert("abc")
    row = field.render(20)[0]
    assert row.segments[-1] == Segment(" ", CURSOR)
    assert row.text == "\u276e abc "


def test_cursor_space_skipped_when_row_is_full():
    field = Input()
    field.insert("abc")  # width 5 -> inner 3, the single row is exactly full
    row = field.render(5)[0]
    assert row.text == "\u276e abc"
    assert row.width == 5
    assert row.segments == (Segment("\u276e ", ACCENT), Segment("abc", NONE))


def test_placeholder_shown_when_empty_and_focused():
    field = Input(placeholder="type here")
    row = field.render(30)[0]
    assert row.text == "\u276e type here"
    styles = {seg.text: seg.style for seg in row.segments}
    assert styles["type here".removeprefix("t")] == DIM
    assert row.segments[1].style == DIM.merge(CURSOR)  # cursor marks first char


def test_placeholder_with_cursor_and_dropped_when_text_present():
    field = Input(placeholder="hint")
    field.insert("x")
    assert _rows(field, 20) == ["\u276e x "]  # trailing space is the block cursor


def test_unfocused_field_renders_no_cursor():
    field = Input(focused=False)
    field.insert("abc")
    row = field.render(20)[0]
    assert row.text == "\u276e abc"
    assert row.segments == (Segment("\u276e ", ACCENT), Segment("abc", NONE))


# --- rendering: wrap and width invariants -----------------------------------------


def test_render_wraps_at_inner_width():
    field = Input()
    field.insert("abcdefgh")
    assert _rows(field, 6) == ["\u276e abcd", "  efgh"]


def test_multiline_paste_shape():
    field = Input()
    field.insert("a\nbb\nccc")
    field.cursor = len(field.text)
    rows = field.render(20)
    assert [row.text for row in rows] == ["\u276e a", "  bb", "  ccc "]
    assert rows[-1].segments[-1] == Segment(" ", CURSOR)  # cursor at the end


def test_rows_never_exceed_width():
    field = Input()
    field.insert("the quick brown fox jumps")
    for cursor in range(len(field.text) + 1):
        field.cursor = cursor
        for width in (1, 2, 3, 5, 8, 13, 40):
            rows = field.render(width)
            assert all(row.width <= width for row in rows), (cursor, width)


def test_cjk_text_rows_stay_within_width():
    field = Input()
    field.insert("\u65e5\u672c\u8a9e")
    rows = field.render(6)  # inner 4: two rows of two wide chars
    assert [row.text for row in rows] == ["\u276e \u65e5\u672c", "  \u8a9e "]
    assert all(row.width <= 6 for row in rows)


def test_empty_field_renders_prompt_and_cursor_space():
    assert _rows(Input(), 10) == ["\u276e  "]  # prompt + block-cursor space
    row = Input().render(10)[0]
    assert row.segments[1] == Segment(" ", DIM.merge(CURSOR))


def test_zero_and_tiny_widths_do_not_crash():
    field = Input()
    field.insert("abc")
    assert all(row.width <= 0 for row in field.render(0))
    assert all(row.width <= 1 for row in field.render(1))


def test_tab_insert_counts_as_one_column():
    field = Input()
    field.insert("a\tb")
    row = field.render(20)[0]
    assert row.text == "\u276e a b "  # tab became a space; trailing block cursor
    assert row.width == 6
