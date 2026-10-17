"""Tests for motui.core.painter.

``paint(layout)`` fully repaints on a (re)size or the first frame, otherwise
rewrites only changed rows; a non-live screen stays silent but ``rows`` current.
Every non-empty frame leaves as one write -- the joined rows bracketed by the
synchronized-update pair (DECSET 2026) -- and one flush; an unchanged frame
stays zero bytes, and ``sync=False`` drops the bracket.
"""

from _doubles import RecordingScreen, Rows, many

import pytest

from motui.core.ansi import (
    CLEAR_LINE,
    begin_sync_update,
    clear_screen,
    cursor_position,
    end_sync_update,
)
from motui.core.block import Document
from motui.core.lines import Line, Segment
from motui.core.painter import Painter
from motui.core.style import RESET, Style
from motui.core.viewport import MORE_BELOW, Viewport


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
    # The frame is bracketed by the DECSET 2026 pair: one write, one flush,
    # the same payload the painter always joined.
    assert frame.startswith(begin_sync_update() + clear_screen())
    assert frame.endswith(end_sync_update())
    assert frame.count(clear_screen()) == 1  # only the first frame
    assert len(screen.writes) == 1  # one joined write per frame
    assert screen.flushes == 1
    assert [row.text for row in painter.rows] == ["a", "b", "c", "", "", ""]


def test_sync_false_paints_the_old_unbracketed_bytes():
    doc = Document()
    doc.add(Rows("a"))
    screen = RecordingScreen(height=4)
    view = Viewport(doc)
    painter = Painter(screen, sync=False)
    _paint(painter, view, screen)
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
    assert screen.delta() == ""  # zero new bytes: no writes, no sync pair either
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
    assert screen.delta() == (
        begin_sync_update() + "\x1b[1;1H" + CLEAR_LINE + end_sync_update()
    )


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
    assert begin_sync_update() + clear_screen() in screen.delta()
    assert len(painter.rows) == 10
    screen.width = 100  # a wider screen, same height
    _paint(painter, view, screen)
    assert begin_sync_update() + clear_screen() in screen.delta()
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
    # The clamped anchor is the payload's epilogue; the sync pair wraps it.
    assert screen.delta().endswith(cursor_position(4, 20) + end_sync_update())


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
    # Zero row writes: the anchor alone, still inside the sync wrapper.
    assert screen.delta() == (
        begin_sync_update() + cursor_position(3, 3) + end_sync_update()
    )
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


def test_frames_counts_every_paint_call_including_unchanged_frames():
    doc = Document()
    doc.add(Rows("a"))
    screen = RecordingScreen(height=4)
    view = Viewport(doc)
    painter = Painter(screen)
    assert painter.frames == 0  # nothing painted yet
    _paint(painter, view, screen)
    assert painter.frames == 1
    screen.delta()
    _paint(painter, view, screen)  # zero bytes: still a frame
    assert screen.delta() == ""
    assert painter.frames == 2
    _paint(painter, view, screen)
    assert painter.frames == 3


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


class _BlueRow:
    """Component double rendering one blue row (a color to downgrade)."""

    def render(self, width: int) -> list[Line]:
        return [Line((Segment("x", Style(fg="#58a6ff")),))]


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("truecolor", Style(fg="#58a6ff").prefix() + "x" + RESET),
        ("256", "\x1b[38;5;75m" + "x" + RESET),
        ("16", "\x1b[94m" + "x" + RESET),
        ("none", "x" + RESET),
    ],
)
def test_rows_render_under_the_screens_color_mode(mode, expected):
    doc = Document()
    doc.add(_BlueRow())
    screen = RecordingScreen(width=20, height=1)
    screen.color_mode = mode  # a screen's declared capability
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    assert expected in screen.delta()
    if mode != "truecolor":
        # The downgrade is fresh bytes; the truecolor form is gone.
        assert Style(fg="#58a6ff").prefix() not in screen.delta()


def test_a_screen_declaring_no_color_mode_is_painted_truecolor():
    # The protocol's optional attribute: a screen that names no mode gets the
    # cached rendering, exactly as before the capability story existed.
    assert not hasattr(RecordingScreen(), "color_mode")
    doc = Document()
    doc.add(_BlueRow())
    screen = RecordingScreen(width=20, height=1)
    view = Viewport(doc)
    painter = Painter(screen)
    _paint(painter, view, screen)
    assert Style(fg="#58a6ff").prefix() + "x" + RESET in screen.delta()
