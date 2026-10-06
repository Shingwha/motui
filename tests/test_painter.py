"""Tests for mocode_tui.core.painter.

``paint(layout)`` fully repaints on a (re)size or the first frame, otherwise
rewrites only changed rows; a non-live screen stays silent but ``rows`` current.
"""

from _doubles import RecordingScreen, Rows, many

from mocode_tui.core.ansi import clear_line, clear_screen, cursor_position
from mocode_tui.core.block import Document
from mocode_tui.core.lines import Line
from mocode_tui.core.painter import Painter
from mocode_tui.core.viewport import MORE_BELOW, Viewport


def _paint(painter: Painter, view: Viewport, screen: RecordingScreen) -> None:
    """Lay the document out at the screen size and paint the frame."""
    painter.paint(view.layout(screen.width, screen.height))


def test_rows_are_empty_before_the_first_paint():
    painter = Painter(RecordingScreen())
    assert painter.rows == []  # nothing has been painted yet


def test_first_frame_erases_and_paints_every_row():
    doc = Document()
    doc.add(Rows("a", "b", "c"))
    screen = RecordingScreen(height=6)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    frame = screen.delta()
    assert frame.startswith(clear_screen())
    assert frame.count(clear_screen()) == 1  # only the first frame
    assert len(screen.writes) == 1  # one joined write per frame
    assert screen.flushes == 1
    assert [row.text for row in painter.rows] == ["a", "b", "c", "", "", ""]


def test_unchanged_frame_writes_zero_bytes():
    doc = Document()
    doc.add(Rows("a", "b", "c"))
    screen = RecordingScreen(height=6)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    _paint(painter, view, screen)
    _paint(painter, view, screen)
    assert screen.delta() == ""  # zero new bytes
    assert len(screen.writes) == 1 and screen.flushes == 1


def test_single_row_change_writes_only_that_row():
    doc = Document()
    doc.add(Rows("x"))
    screen = RecordingScreen(height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    doc.remove("b0")
    doc.add(Rows("X"))  # a fresh block renders the new content
    _paint(painter, view, screen)
    delta = screen.delta()
    assert clear_screen() not in delta  # a content change is a plain row diff
    assert delta.count(";1H") == 1  # exactly one row rewrite
    assert Line.from_text("X").styled() in delta


def test_row_becoming_empty_is_still_cleared():
    doc = Document()
    doc.add(Rows("x"))
    screen = RecordingScreen(height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    doc.remove("b0")
    doc.add(Rows(""))  # a fresh block rendering an empty row
    _paint(painter, view, screen)
    # A row whose styled() is empty still gets the positioning and the erase:
    # stale content from an earlier frame must be cleared.
    assert screen.delta() == "\x1b[1;1H" + clear_line()


def test_size_change_forces_a_full_repaint():
    doc = Document()
    doc.add(Rows("a"))
    screen = RecordingScreen(width=80, height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    screen.height = 10  # a taller screen
    _paint(painter, view, screen)
    assert screen.delta().startswith(clear_screen())
    assert len(painter.rows) == 10
    screen.width = 100  # a wider screen, same height
    _paint(painter, view, screen)
    assert screen.delta().startswith(clear_screen())
    assert len(painter.rows) == 10


def test_non_live_screen_stays_silent_but_rows_are_current():
    doc = Document()
    doc.add(Rows(*many(8)))
    screen = RecordingScreen(width=80, height=5, live=False)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    _paint(painter, view, screen)
    assert screen.writes == []  # not a single byte at runtime
    assert [row.text for row in painter.rows] == many(8)[3:]


def test_the_pinned_cursor_joins_the_frame_and_clamps_into_the_screen():
    doc = Document()
    doc.add(Rows("a"))
    screen = RecordingScreen(width=20, height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    painter.set_cursor(9, 30)  # 0-based, outside the screen
    _paint(painter, view, screen)
    assert screen.delta().endswith(cursor_position(4, 20))  # clamped to the last cell


def test_moved_cursor_alone_writes_only_the_cursor_escape():
    doc = Document()
    doc.add(Rows("a", "b"))
    screen = RecordingScreen(height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    painter.set_cursor(0, 0)
    _paint(painter, view, screen)
    screen.delta()
    painter.set_cursor(2, 2)
    _paint(painter, view, screen)
    assert screen.delta() == cursor_position(3, 3)  # zero row writes
    _paint(painter, view, screen)  # an unchanged frame with an unchanged cursor stays silent
    assert screen.delta() == ""


def test_scroll_is_a_plain_row_diff_with_the_more_below_row():
    doc = Document()
    doc.add(Rows(*many(30)))
    screen = RecordingScreen(height=8)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    view.scroll_up(5)
    _paint(painter, view, screen)
    delta = screen.delta()
    assert clear_screen() not in delta  # a scroll is a plain row diff
    assert [row.text for row in painter.rows] == [*many(30)[17:24], MORE_BELOW.text]
    view.scroll_to_bottom()
    _paint(painter, view, screen)
    assert [row.text for row in painter.rows] == many(30)[22:]


def test_pinned_footer_occupies_the_bottom_rows():
    doc = Document()
    doc.add(Rows(*many(10)))
    doc.add(Rows("p1", "p2"), pin="bottom")
    screen = RecordingScreen(height=8)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    rows = painter.rows
    assert len(rows) == 8
    assert [row.text for row in rows[:6]] == many(10)[4:]
    assert [row.text for row in rows[6:]] == ["p1", "p2"]
