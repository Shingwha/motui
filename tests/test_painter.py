"""Tests for mocode_tui.painter."""

import io

from mocode_tui.ansi import clear_line, cursor_position
from mocode_tui.block import Document
from mocode_tui.lines import Line
from mocode_tui.painter import Painter
from mocode_tui.screen import HeadlessScreen, TerminalScreen
from mocode_tui import screen as screen_mod


class Rows:
    """Component rendering one row per given text; records render calls."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.calls: list[int] = []

    def render(self, width: int) -> list[Line]:
        self.calls.append(width)
        return [Line.from_text(t) for t in self.texts]


class SpyScreen(HeadlessScreen):
    """Headless screen that also records write/flush call sequences."""

    def __init__(self, width: int = 80, height: int = 24) -> None:
        super().__init__(width, height)
        self.writes: list[str] = []
        self.flush_calls = 0

    def write(self, s: str) -> None:
        self.writes.append(s)
        super().write(s)

    def flush(self) -> None:
        self.flush_calls += 1
        super().flush()


def _many(n: int) -> list[str]:
    return [f"r{i}" for i in range(n)]


# --- frames ----------------------------------------------------------------------


def test_rows_are_empty_before_the_first_flush():
    doc = Document()
    doc.add(Rows("a"))
    painter = Painter(doc, HeadlessScreen())
    assert painter.rows() == []


def test_first_frame_erases_and_paints_every_row():
    doc = Document()
    doc.add(Rows("a", "b", "c"))
    screen = SpyScreen(height=6)
    painter = Painter(doc, screen)
    painter.flush()
    assert screen.output.startswith("\x1b[2J")
    assert screen.output.count("\x1b[2J") == 1
    assert screen.writes == [screen.output]  # one joined write per frame
    assert screen.flush_calls == 1
    expected = ["a", "b", "c", "", "", ""]
    for i, text in enumerate(expected):
        assert f"\x1b[{i + 1};1H" + clear_line() + Line.from_text(text).styled() in screen.output
    assert [row.text for row in painter.rows()] == expected


def test_unchanged_frame_is_zero_bytes_and_makes_no_calls():
    doc = Document()
    doc.add(Rows("a", "b", "c"))
    screen = SpyScreen(height=6)
    painter = Painter(doc, screen)
    painter.flush()
    painted = len(screen.output)
    writes, flushes = len(screen.writes), screen.flush_calls
    painter.flush()
    painter.flush()
    assert len(screen.output) == painted  # zero new bytes
    assert len(screen.writes) == writes
    assert screen.flush_calls == flushes


def test_single_row_change_writes_only_that_row():
    doc = Document()
    block = doc.add(Rows("x"))
    screen = SpyScreen(height=4)
    painter = Painter(doc, screen)
    painter.flush()
    before = screen.output
    block.set_component(Rows("X"))
    painter.flush()
    delta = screen.output[len(before) :]
    assert delta == f"\x1b[1;1H" + clear_line() + Line.from_text("X").styled()
    assert "\x1b[2J" not in delta
    assert delta.count(";1H") == 1  # no other row sequences


def test_row_becoming_empty_is_still_cleared():
    doc = Document()
    block = doc.add(Rows("x"))
    screen = SpyScreen(height=4)
    painter = Painter(doc, screen)
    painter.flush()
    before = screen.output
    block.set_component(Rows(""))
    painter.flush()
    delta = screen.output[len(before) :]
    assert Line.from_text("").styled() == ""
    assert delta == f"\x1b[1;1H" + clear_line()


def test_size_change_repaints_everything_and_rows_track_the_new_size():
    doc = Document()
    doc.add(Rows("a"))
    screen = SpyScreen(width=80, height=4)
    painter = Painter(doc, screen)
    painter.flush()
    before = screen.output
    screen.height = 10  # taller screen
    painter.flush()
    delta = screen.output[len(before) :]
    assert delta.startswith("\x1b[2J")
    assert delta.count("\x1b[2J") == 1
    assert len(painter.rows()) == 10
    before = screen.output
    screen.width = 100  # wider screen, same height
    painter.flush()
    delta = screen.output[len(before) :]
    assert delta.startswith("\x1b[2J")
    assert len(painter.rows()) == 10


def test_throttle_parameter_is_accepted_for_api_stability():
    doc = Document()
    doc.add(Rows("a"))
    painter = Painter(doc, HeadlessScreen(height=3), throttle=0.25)
    painter.flush()
    assert [row.text for row in painter.rows()] == ["a", "", ""]


# --- non-live -----------------------------------------------------------------------


def test_non_live_screen_stays_silent_but_rows_are_current(monkeypatch):
    monkeypatch.setattr(screen_mod, "terminal_size", lambda: (80, 5))
    stream = io.StringIO()
    doc = Document()
    doc.add(Rows(*_many(8)))
    painter = Painter(doc, TerminalScreen(stream))
    assert painter._screen.live is False
    painter.flush()
    painter.flush()
    assert stream.getvalue() == ""  # not a single byte at runtime
    assert [row.text for row in painter.rows()] == ["r3", "r4", "r5", "r6", "r7"]


def test_non_live_resize_stays_silent_but_rows_follow_the_new_size(monkeypatch):
    monkeypatch.setattr(screen_mod, "terminal_size", lambda: (80, 5))
    stream = io.StringIO()
    doc = Document()
    doc.add(Rows(*_many(8)))
    painter = Painter(doc, TerminalScreen(stream))
    painter.flush()
    monkeypatch.setattr(screen_mod, "terminal_size", lambda: (100, 4))
    painter.flush()
    assert stream.getvalue() == ""
    assert len(painter.rows()) == 4
    assert [row.text for row in painter.rows()] == ["r4", "r5", "r6", "r7"]


# --- scrolling ----------------------------------------------------------------------


def test_scroll_up_moves_the_window_into_the_diff():
    doc = Document()
    doc.add(Rows(*_many(30)))
    screen = SpyScreen(height=8)
    painter = Painter(doc, screen)
    painter.flush()
    assert [row.text for row in painter.rows()] == _many(30)[22:]
    before = screen.output
    painter.scroll_up(5)
    painter.flush()
    delta = screen.output[len(before) :]
    assert "\x1b[2J" not in delta  # a scroll is a plain row diff
    scrolled = [f"r{i}" for i in range(17, 24)] + ["─ more below ─"]
    assert [row.text for row in painter.rows()] == scrolled
    for i, row in enumerate(painter.rows()):
        assert f"\x1b[{i + 1};1H" + clear_line() + row.styled() in delta


def test_scroll_down_clamps_and_scroll_to_bottom_restores_the_tail():
    doc = Document()
    doc.add(Rows(*_many(30)))
    screen = SpyScreen(height=8)
    painter = Painter(doc, screen)
    painter.flush()
    painter.scroll_up(100)
    painter.flush()
    assert [row.text for row in painter.rows()] == [f"r{i}" for i in range(7)] + [
        "─ more below ─"
    ]
    painter.scroll_down(100)
    painter.flush()
    assert [row.text for row in painter.rows()] == _many(30)[22:]
    painter.scroll_up(2)
    painter.flush()
    assert [row.text for row in painter.rows()] == [f"r{i}" for i in range(20, 27)] + [
        "─ more below ─"
    ]
    painter.scroll_to_bottom()
    painter.flush()
    assert [row.text for row in painter.rows()] == _many(30)[22:]


# --- pinned footer -------------------------------------------------------------------


def test_pinned_footer_occupies_the_bottom_rows():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("p1", "p2"), pinned=True)
    screen = SpyScreen(height=8)
    painter = Painter(doc, screen)
    painter.flush()
    rows = painter.rows()
    assert len(rows) == 8
    assert [row.text for row in rows[:6]] == [f"r{i}" for i in range(4, 10)]
    assert [row.text for row in rows[6:]] == ["p1", "p2"]


def test_pinned_rows_stay_put_while_the_window_scrolls():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("p1", "p2"), pinned=True)
    screen = SpyScreen(height=8)
    painter = Painter(doc, screen)
    painter.flush()
    painter.scroll_up(3)
    painter.flush()
    rows = painter.rows()
    assert [row.text for row in rows[:6]] == [f"r{i}" for i in range(1, 6)] + ["─ more below ─"]
    assert [row.text for row in rows[6:]] == ["p1", "p2"]


# --- cursor anchor (IME) ------------------------------------------------------------


def test_frame_ends_with_the_cursor_anchor():
    doc = Document()
    doc.add(Rows("a"))
    screen = SpyScreen(height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(2, 3)  # 0-based -> one-based (3,4)
    painter.flush()
    assert screen.output.endswith(cursor_position(3, 4))
    assert screen.writes == [screen.output]  # the anchor joins the frame write


def test_anchor_follows_the_diff_on_a_changed_frame():
    doc = Document()
    block = doc.add(Rows("x"))
    screen = SpyScreen(height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(1, 1)
    painter.flush()
    before = screen.output
    block.set_component(Rows("X"))
    painter.flush()
    delta = screen.output[len(before) :]
    assert delta == f"\x1b[1;1H" + clear_line() + Line.from_text("X").styled() + cursor_position(2, 2)


def test_unchanged_frame_with_an_unchanged_anchor_stays_zero_bytes():
    doc = Document()
    doc.add(Rows("a", "b"))
    screen = SpyScreen(height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(0, 0)
    painter.flush()
    painted = len(screen.output)
    writes, flushes = len(screen.writes), screen.flush_calls
    painter.flush()
    painter.flush()
    assert len(screen.output) == painted  # the same anchor is not repeated
    assert len(screen.writes) == writes
    assert screen.flush_calls == flushes


def test_unchanged_frame_with_a_moved_anchor_writes_the_anchor_alone():
    doc = Document()
    doc.add(Rows("a", "b"))
    screen = SpyScreen(height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(0, 0)
    painter.flush()
    before = screen.output
    painter.set_cursor_anchor(2, 2)
    painter.flush()
    assert screen.output[len(before) :] == cursor_position(3, 3)  # zero row writes


def test_out_of_screen_anchor_clamps_into_the_screen():
    doc = Document()
    doc.add(Rows("a"))
    screen = SpyScreen(width=20, height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(9, 30)
    painter.flush()
    assert screen.output.endswith(cursor_position(4, 20))


def test_size_change_repaints_and_keeps_the_anchor():
    doc = Document()
    doc.add(Rows("a"))
    screen = SpyScreen(width=80, height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(2, 2)
    painter.flush()
    before = screen.output
    screen.height = 10
    painter.flush()
    delta = screen.output[len(before) :]
    assert delta.startswith("\x1b[2J")
    assert delta.endswith(cursor_position(3, 3))  # still pinned, not cleared


def test_non_live_screen_never_receives_the_anchor(monkeypatch):
    monkeypatch.setattr(screen_mod, "terminal_size", lambda: (80, 5))
    stream = io.StringIO()
    doc = Document()
    doc.add(Rows(*_many(8)))
    painter = Painter(doc, TerminalScreen(stream))
    assert painter._screen.live is False
    painter.set_cursor_anchor(2, 2)
    painter.flush()
    painter.flush()
    assert stream.getvalue() == ""  # not a single byte at runtime
    assert [row.text for row in painter.rows()] == ["r3", "r4", "r5", "r6", "r7"]
