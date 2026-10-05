"""Tests for mocode_tui.widgets.input (Input).

Contracts (COMPONENTS.md): a prompt-led field with a reverse-video block
cursor; the prompt shows on the first visual row only and continuation rows
indent by its width; an empty focused field shows a dim placeholder; up/down
follow the wrapped rows; no row ever exceeds the width.
"""

from mocode_tui.widgets.input import Input
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import ACCENT, CURSOR, DIM, NONE


def test_default_render_at_width_80():
    field = Input()
    field.insert("hello")
    rows = field.render(80)
    assert rows[0].text == "\u276e hello "  # trailing reverse-video space is the cursor
    assert rows[0].segments[0] == Segment("\u276e ", ACCENT)
    assert Input().render(80)[0].segments[1] == Segment(" ", DIM.merge(CURSOR))  # empty + focused


def test_editing_insert_backspace_delete_clear():
    field = Input()
    assert field.backspace() is False and field.delete() is False  # empty
    field.insert("ac")
    field.move_left()
    field.insert("b")
    assert field.text == "abc" and field.cursor == 2
    assert field.delete() is True and field.text == "ab" and field.cursor == 2
    assert field.backspace() is True and field.text == "a"
    field.clear()
    assert field.text == "" and field.cursor == 0


def test_cursor_movement_left_right_home_end():
    field = Input()
    field.insert("ab\ncd")
    field.move_left()
    assert field.cursor == 4  # between "c" and "d"
    assert field.home() is True and field.cursor == 3  # start of the logical line "cd"
    assert field.home() is False  # already home
    assert field.end() is True and field.cursor == 5
    assert field.end() is False  # already at the line end
    assert field.move_left() is True and field.cursor == 4
    assert Input().move_left() is False  # nothing to move through


def test_up_and_down_follow_the_wrapped_rows():
    field = Input()
    field.insert("abcdefgh")  # wraps to "abcd" / "efgh" at width 6 (inner 4)
    field.render(6)
    field.cursor = 1  # column 1 of the first visual row
    assert field.move_down() is True and field.cursor == 5
    assert field.move_up() is True and field.cursor == 1
    assert field.move_up() is False  # top visual row


def test_cursor_restyles_the_character_under_it():
    field = Input()
    field.insert("abc")
    field.cursor = 1
    assert field.render(20)[0].segments == (
        Segment("\u276e ", ACCENT),
        Segment("a", NONE),
        Segment("b", CURSOR),
        Segment("c", NONE),
    )
    # A full row is exactly full: the cursor space is skipped, no overflow.
    full = Input()
    full.insert("abc")
    assert full.render(5)[0].segments == (Segment("\u276e ", ACCENT), Segment("abc", NONE))


def test_placeholder_and_focus():
    row = Input(placeholder="hint").render(30)[0]
    assert row.text == "\u276e hint"  # the block cursor paints over the first char
    assert row.segments[1] == Segment("h", DIM.merge(CURSOR))
    focused_off = Input(focused=False)
    focused_off.insert("abc")
    assert focused_off.render(20)[0].segments == (
        Segment("\u276e ", ACCENT),
        Segment("abc", NONE),
    )


def test_narrow_width_guard():
    field = Input()
    field.insert("the quick brown fox jumps")
    for width in (1, 3, 8):
        assert all(row.width <= width for row in field.render(width))
    multiline = Input()
    multiline.insert("a\nbb\nccc")
    rows = multiline.render(6)
    assert [row.text for row in rows] == ["\u276e a", "  bb", "  ccc "]  # prompt once, then indent


def test_cursor_position_reports_the_block_cursor_cell():
    field = Input()
    field.insert("abcdefgh")  # width 6: "\u276e abcd" / "  efgh"
    field.cursor = 5
    assert field.cursor_position(6) == (1, 3)  # row 1, past the two-wide indent
    field.cursor = 1
    assert field.cursor_position(6) == (0, 3)
    assert Input().cursor_position(10) == (0, 2)  # the prompt-width column
