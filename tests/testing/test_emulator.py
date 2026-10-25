"""The paint-frame emulator: escapes in, a cell grid out."""

from __future__ import annotations

from motui.kernel import Style
from motui.kernel import Pos
from motui.testing import Emulator
from tests.testing import Rows, headless_tui


def row_text(em: Emulator, row: int) -> str:
    """The visible glyphs of one grid row, placeholders included as nothing."""
    return "".join(cell.char for cell in em.grid[row])


def test_cup_places_text_at_the_addressed_cell():
    em = Emulator(10, 3)
    em.feed("\x1b[2;3Hhello")
    assert em.cell(2, 1).char == "h"
    assert em.cell(6, 1).char == "o"
    assert em.cursor == Pos(x=7, y=1)
    assert em.text() == "\n  hello"


def test_sgr_tracks_attributes_and_the_extended_color_forms():
    em = Emulator(10, 2)
    em.feed("\x1b[1;31mA")
    style = em.sgr_at(0, 0)
    assert style.bold and style.fg == "red"
    em.feed("\x1b[0mB")
    assert em.sgr_at(1, 0) == Style()
    em.feed("\x1b[38;2;1;2;3;48;5;196;3;4;7;9mC")
    style = em.sgr_at(2, 0)
    assert style.fg == (1, 2, 3)
    assert style.bg == (255, 0, 0)
    assert style.italic and style.underline and style.reverse and style.strike
    em.feed("\x1b[22;23;24;27;29;39;49mD")
    assert em.sgr_at(3, 0) == Style()
    em.feed("\x1b[91;104mE")
    style = em.sgr_at(4, 0)
    assert style.fg == "bright_red" and style.bg == "bright_blue"


def test_el_clears_to_the_end_of_the_row_and_2j_clears_the_screen():
    em = Emulator(10, 3)
    em.feed("abcdef")
    em.feed("\x1b[1;4H\x1b[K")
    assert em.text() == "abc"
    em.feed("\x1b[2J")
    assert em.text() == ""
    assert all(cell.char == " " for row in em.grid for cell in row)


def test_a_line_wider_than_the_screen_wraps_at_the_right_edge():
    em = Emulator(20, 4)
    em.feed("A" * 40)
    assert row_text(em, 0) == "A" * 20
    assert row_text(em, 1) == "A" * 20
    assert row_text(em, 2).strip() == ""
    assert em.cursor == Pos(x=0, y=2)


def test_wide_glyphs_own_two_cells_and_combining_marks_join_the_previous_cell():
    em = Emulator(10, 2)
    em.feed("中a")
    assert em.cell(0, 0).char == "中"
    assert em.cell(1, 0).char == ""
    assert em.cell(2, 0).char == "a"
    assert em.text() == "中a"
    em.feed("\r\x1b[2;1H😀")
    assert em.cell(0, 1).char == "😀"
    assert em.cell(1, 1).char == ""
    em.feed("\r\x1b[1;1He\u0301")
    assert em.cell(0, 0).char == "e\u0301"
    assert em.cell(2, 0).char == "a"


def test_feed_accepts_arbitrary_splits_including_inside_a_utf8_glyph():
    frame = "\x1b[?2026h\x1b[2;2H\x1b[31m中文\x1b[0m\x1b[K\x1b[?2026l"
    whole = Emulator(10, 3)
    whole.feed(frame)

    pieces = len(frame) // 3
    split = Emulator(10, 3)
    for chunk in (frame[:pieces], frame[pieces : 2 * pieces], frame[2 * pieces :]):
        split.feed(chunk)

    assert split.grid == whole.grid
    assert split.cursor == whole.cursor
    assert split.text() == whole.text() == "\n 中文"

    data = "中文".encode()
    cut = data.index("文".encode()[0]) + 1  # inside the second glyph's bytes
    raw = Emulator(10, 2)
    raw.feed(data[:cut])
    raw.feed(data[cut:])
    assert raw.text() == "中文"


def test_alt_screen_clears_and_homes_and_the_mode_escapes_are_ignored():
    em = Emulator(10, 3)
    em.feed("\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1003h\x1b[?1006h")
    em.feed("\x1b[?2004h\x1b[?1004hxy")
    assert em.text() == "xy"
    em.feed("\x1b[?1049l")
    assert em.text() == ""
    assert em.cursor == Pos()
    em.feed("\x1b[?2026h\x1b[1;1Hz\x1b[?2026l")
    assert em.text() == "z"


def test_osc8_records_the_link_and_an_empty_url_closes_it():
    em = Emulator(20, 2)
    em.feed("\x1b]8;;https://example.test\x1b\\link\x1b]8;;\x1b\\plain")
    assert em.cell(0, 0).link == "https://example.test"
    assert em.cell(3, 0).link == "https://example.test"
    assert em.cell(4, 0).link is None
    em.feed("\x1b]2;title\x07!")
    assert em.text() == "linkplain!"


def test_resize_keeps_the_top_left_block_and_clamps_the_cursor():
    em = Emulator(5, 3)
    em.feed("abc")
    em.resize(8, 4)
    assert em.text() == "abc"
    assert em.cell(7, 3).char == " "
    em.resize(2, 2)
    assert em.text() == "ab"
    assert em.cursor == Pos(x=1, y=0)


def test_a_real_painter_frame_rebuilds_the_text_the_tui_lays_out():
    tui = headless_tui(20, 6)
    tui.add(Rows("alpha", "beta"))
    tui.paint()
    em = Emulator(20, 6)
    em.feed(tui.screen.output)
    expected = [row.text.rstrip() for row in tui.rows]
    while expected and not expected[-1]:
        expected.pop()
    assert em.text() == "\n".join(expected)
    assert em.text().splitlines()[0] == "alpha"
