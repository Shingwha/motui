"""Tests for mocode_tui.core.painter.

Contracts (DESIGN.md): ``flush()`` paints one frame -- a full repaint prefixed
by ``\\x1b[2J`` on a (re)size or the first frame, otherwise a per-row
cursor-addressed rewrite of only the rows that differ from the previous frame;
an unchanged frame writes zero bytes; a non-live screen stays completely
silent while ``rows()`` still reports the logical target.  ``rows()`` always
returns exactly ``screen.height`` rows.
"""

from mocode_tui.core.ansi import clear_line, clear_screen, cursor_position
from mocode_tui.core.block import Document
from mocode_tui.core.lines import Line
from mocode_tui.core.painter import Painter

MORE_BELOW = "─ more below ─"


class Rows:
    """Component rendering one row per given text."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(t) for t in self.texts]


class Recorder:
    """Screen double: records every write, settable size, switchable liveness."""

    def __init__(self, width: int = 80, height: int = 24, *, live: bool = True) -> None:
        self.width = width
        self.height = height
        self.live = live
        self.writes: list[str] = []
        self.flushes = 0

    def write(self, s: str) -> None:
        self.writes.append(s)

    def flush(self) -> None:
        self.flushes += 1

    def refresh_size(self) -> None:
        pass  # the size only changes when a test moves it

    @property
    def output(self) -> str:
        return "".join(self.writes)

    def delta(self) -> str:
        """Everything written since the last delta() call."""
        if not hasattr(self, "_mark"):
            self._mark = 0  # the first call captures everything written so far
        fresh = "".join(self.writes[self._mark :])
        self._mark = len(self.writes)
        return fresh


def _many(n: int) -> list[str]:
    return [f"r{i}" for i in range(n)]


def test_rows_are_empty_before_the_first_flush():
    painter = Painter(Document(), Recorder())
    assert painter.rows() == []  # nothing has been painted yet


def test_first_frame_erases_and_paints_every_row():
    doc = Document()
    doc.add(Rows("a", "b", "c"))
    screen = Recorder(height=6)
    painter = Painter(doc, screen)
    painter.flush()
    frame = screen.delta()
    assert frame.startswith(clear_screen())
    assert frame.count(clear_screen()) == 1  # only the first frame
    assert len(screen.writes) == 1  # one joined write per frame
    assert screen.flushes == 1
    assert [row.text for row in painter.rows()] == ["a", "b", "c", "", "", ""]


def test_unchanged_frame_writes_zero_bytes():
    doc = Document()
    doc.add(Rows("a", "b", "c"))
    screen = Recorder(height=6)
    painter = Painter(doc, screen)
    painter.flush()
    screen.delta()
    painter.flush()
    painter.flush()
    assert screen.delta() == ""  # zero new bytes
    assert len(screen.writes) == 1 and screen.flushes == 1


def test_single_row_change_writes_only_that_row():
    doc = Document()
    block = doc.add(Rows("x"))
    screen = Recorder(height=4)
    painter = Painter(doc, screen)
    painter.flush()
    screen.delta()
    block.set_component(Rows("X"))
    painter.flush()
    delta = screen.delta()
    assert clear_screen() not in delta  # a content change is a plain row diff
    assert delta.count(";1H") == 1  # exactly one row rewrite
    assert Line.from_text("X").styled() in delta


def test_row_becoming_empty_is_still_cleared():
    doc = Document()
    block = doc.add(Rows("x"))
    screen = Recorder(height=4)
    painter = Painter(doc, screen)
    painter.flush()
    screen.delta()
    block.set_component(Rows(""))
    painter.flush()
    # A row whose styled() is empty still gets the positioning and the erase:
    # stale content from an earlier frame must be cleared.
    assert screen.delta() == "\x1b[1;1H" + clear_line()


def test_size_change_forces_a_full_repaint():
    doc = Document()
    doc.add(Rows("a"))
    screen = Recorder(width=80, height=4)
    painter = Painter(doc, screen)
    painter.flush()
    screen.delta()
    screen.height = 10  # a taller screen
    painter.flush()
    assert screen.delta().startswith(clear_screen())
    assert len(painter.rows()) == 10
    screen.width = 100  # a wider screen, same height
    painter.flush()
    assert screen.delta().startswith(clear_screen())
    assert len(painter.rows()) == 10


def test_non_live_screen_stays_silent_but_rows_are_current():
    doc = Document()
    doc.add(Rows(*_many(8)))
    screen = Recorder(width=80, height=5, live=False)
    painter = Painter(doc, screen)
    painter.flush()
    painter.flush()
    assert screen.writes == []  # not a single byte at runtime
    assert [row.text for row in painter.rows()] == ["r3", "r4", "r5", "r6", "r7"]


def test_cursor_anchor_joins_the_frame_and_clamps_into_the_screen():
    doc = Document()
    doc.add(Rows("a"))
    screen = Recorder(width=20, height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(9, 30)  # 0-based, outside the screen
    painter.flush()
    assert screen.delta().endswith(cursor_position(4, 20))  # clamped to the last cell


def test_moved_anchor_alone_writes_only_the_anchor_escape():
    doc = Document()
    doc.add(Rows("a", "b"))
    screen = Recorder(height=4)
    painter = Painter(doc, screen)
    painter.set_cursor_anchor(0, 0)
    painter.flush()
    screen.delta()
    painter.set_cursor_anchor(2, 2)
    painter.flush()
    assert screen.delta() == cursor_position(3, 3)  # zero row writes
    painter.flush()  # an unchanged frame with an unchanged anchor stays silent
    assert screen.delta() == ""


def test_scroll_is_a_plain_row_diff_with_the_more_below_row():
    doc = Document()
    doc.add(Rows(*_many(30)))
    screen = Recorder(height=8)
    painter = Painter(doc, screen)
    painter.flush()
    screen.delta()
    painter.scroll_up(5)
    painter.flush()
    delta = screen.delta()
    assert clear_screen() not in delta  # a scroll is a plain row diff
    assert [row.text for row in painter.rows()] == [*(f"r{i}" for i in range(17, 24)), MORE_BELOW]
    painter.scroll_to_bottom()
    painter.flush()
    assert [row.text for row in painter.rows()] == _many(30)[22:]


def test_pinned_footer_occupies_the_bottom_rows():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("p1", "p2"), pin="bottom")
    screen = Recorder(height=8)
    painter = Painter(doc, screen)
    painter.flush()
    rows = painter.rows()
    assert len(rows) == 8
    assert [row.text for row in rows[:6]] == [f"r{i}" for i in range(4, 10)]
    assert [row.text for row in rows[6:]] == ["p1", "p2"]
