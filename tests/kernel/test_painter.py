"""Painter row-diff rendering: first frame, unchanged frames, row diffs,
resize, non-live silence and the cursor anchor.

A first frame (or one after a size change) erases and repaints every row; a
frame at the same size rewrites only the rows that changed, so an unchanged
frame is zero bytes.  Each non-empty frame leaves as one write bracketed by
the synchronized-update pair (unless disabled) and one flush.
"""

from __future__ import annotations

from motui.kernel.ansi import (
    CLEAR_LINE,
    begin_sync_update,
    clear_screen,
    cursor_position,
    end_sync_update,
)
from motui.kernel.block import Document
from motui.kernel.lines import Line, Segment
from motui.kernel.painter import Painter
from motui.kernel.style import RESET, Style
from motui.kernel.viewport import ScreenLayout, Viewport
from tests.testing import RecordingScreen, Rows, many


def _paint(painter: Painter, view: Viewport, screen: RecordingScreen) -> None:
    painter.paint(view.layout(screen.width, screen.height))


def test_rows_are_normalized_to_the_screen_height():
    screen = RecordingScreen(width=10, height=4, live=False)
    painter = Painter(screen)
    painter.paint(ScreenLayout(rows=(Line.from_text("one"),), body_rows=()))
    assert [row.text for row in painter.rows] == ["one", "", "", ""]
    painter.paint(
        ScreenLayout(rows=tuple(Line.from_text(str(i)) for i in range(6)), body_rows=())
    )
    assert [row.text for row in painter.rows] == ["0", "1", "2", "3"]


def test_first_frame_erases_and_paints_every_row():
    doc = Document()
    doc.add(Rows("a", "b", "c"))
    screen = RecordingScreen(height=6)
    painter = Painter(screen)
    _paint(painter, Viewport(doc), screen)
    frame = screen.delta()
    assert frame.startswith(begin_sync_update() + clear_screen())
    assert frame.endswith(end_sync_update())
    assert frame.count(clear_screen()) == 1
    assert len(screen.writes) == 1 and screen.flushes == 1
    assert [row.text for row in painter.rows] == ["a", "b", "c", "", "", ""]


def test_sync_false_emits_the_unbracketed_bytes():
    doc = Document()
    doc.add(Rows("a"))
    screen = RecordingScreen(height=4)
    painter = Painter(screen, sync=False)
    _paint(painter, Viewport(doc), screen)
    frame = screen.delta()
    assert begin_sync_update() not in frame and end_sync_update() not in frame
    assert frame == clear_screen() + "".join(
        cursor_position(i + 1, 1) + CLEAR_LINE + row.styled()
        for i, row in enumerate(painter.rows)
    )
    assert len(screen.writes) == 1 and screen.flushes == 1


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
    assert screen.delta() == ""
    assert len(screen.writes) == 1 and screen.flushes == 1


def test_a_single_changed_row_is_rewritten():
    doc = Document()
    doc.add(Rows("x"))
    screen = RecordingScreen(height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    doc.remove("b0")
    doc.add(Rows("X"))
    _paint(painter, view, screen)
    delta = screen.delta()
    assert clear_screen() not in delta
    assert delta.count(";1H") == 1
    assert Line.from_text("X").styled() in delta


def test_a_row_becoming_empty_is_still_cleared():
    doc = Document()
    doc.add(Rows("x"))
    screen = RecordingScreen(height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    doc.remove("b0")
    doc.add(Rows(""))
    _paint(painter, view, screen)
    assert screen.delta() == (
        begin_sync_update() + "\x1b[1;1H" + CLEAR_LINE + end_sync_update()
    )


def test_a_size_change_forces_a_full_repaint():
    doc = Document()
    doc.add(Rows("a"))
    screen = RecordingScreen(width=80, height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    screen.delta()
    screen.height = 10
    _paint(painter, view, screen)
    assert begin_sync_update() + clear_screen() in screen.delta()
    assert len(painter.rows) == 10
    screen.width = 100
    _paint(painter, view, screen)
    assert begin_sync_update() + clear_screen() in screen.delta()


def test_non_live_screen_stays_silent_but_rows_are_current():
    doc = Document()
    doc.add(Rows(*many(8)))
    screen = RecordingScreen(width=80, height=5, live=False)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    _paint(painter, view, screen)
    assert screen.writes == []
    assert [row.text for row in painter.rows] == many(8)[3:]


def test_the_pinned_cursor_joins_the_frame_and_clamps_into_the_screen():
    doc = Document()
    doc.add(Rows("a"))
    screen = RecordingScreen(width=20, height=4)
    painter = Painter(screen)
    painter.set_cursor(9, 30)
    _paint(painter, Viewport(doc), screen)
    assert screen.delta().endswith(cursor_position(4, 20) + end_sync_update())


def test_a_moved_cursor_alone_writes_only_the_cursor_escape():
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
    assert screen.delta() == (
        begin_sync_update() + cursor_position(3, 3) + end_sync_update()
    )
    _paint(painter, view, screen)
    assert screen.delta() == ""


def test_rows_render_under_the_screens_color_mode():
    cases = [
        ("truecolor", Style(fg="#58a6ff").prefix() + "x" + RESET),
        ("256", "\x1b[38;5;75m" + "x" + RESET),
        ("16", "\x1b[94m" + "x" + RESET),
        ("none", "x" + RESET),
    ]
    for mode, expected in cases:
        doc = Document()
        doc.add(_BlueRow())
        screen = RecordingScreen(width=20, height=1)
        screen.color_mode = mode
        painter = Painter(screen)
        _paint(painter, Viewport(doc), screen)
        assert expected in screen.delta()
        if mode != "truecolor":
            assert Style(fg="#58a6ff").prefix() not in screen.delta()


class _BlueRow:
    def render(self, width: int) -> list[Line]:
        return [Line((Segment("x", Style(fg="#58a6ff")),))]


def test_a_screen_declaring_no_color_mode_is_painted_truecolor():
    assert not hasattr(RecordingScreen(), "color_mode")
    doc = Document()
    doc.add(_BlueRow())
    screen = RecordingScreen(width=20, height=1)
    painter = Painter(screen)
    _paint(painter, Viewport(doc), screen)
    assert Style(fg="#58a6ff").prefix() + "x" + RESET in screen.delta()
