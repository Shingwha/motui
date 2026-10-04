"""Tests for mocode_tui.screen.

Contracts (DESIGN.md): ``TerminalScreen`` is live iff ``stream.isatty()`` and
the VT probe succeeds, decided once at construction -- a non-live screen's
``enter``/``leave`` are empty writes so a piped run stays pure text.
``HeadlessScreen`` is live by construction, records every written byte in
order, and has settable ``width``/``height`` so a test can simulate a resize.
"""

from mocode_tui import ansi
from mocode_tui.screen import HeadlessScreen, Screen, TerminalScreen


class FakeStream:
    """Minimal stream double: records writes, counts flushes, fakes isatty."""

    def __init__(self, *, isatty: bool = False) -> None:
        self.data = ""
        self.flushes = 0
        self.ttys = isatty

    def write(self, s: str) -> int:
        self.data += s
        return len(s)

    def flush(self) -> None:
        self.flushes += 1

    def isatty(self) -> bool:
        return self.ttys


def test_both_screens_satisfy_the_protocol():
    assert isinstance(HeadlessScreen(), Screen)
    assert isinstance(TerminalScreen(FakeStream()), Screen)


def test_headless_defaults_and_records_every_byte():
    screen = HeadlessScreen()
    assert (screen.width, screen.height, screen.live, screen.output) == (80, 24, True, "")
    screen.write("a")
    screen.write("")
    screen.write("bc")
    assert screen.output == "abc"
    screen.flush()  # a no-op: the recording buffer is the output
    assert screen.output == "abc"


def test_headless_simulates_a_resize_by_setting_dimensions():
    screen = HeadlessScreen()
    screen.width, screen.height = 132, 43
    assert (screen.width, screen.height) == (132, 43)
    screen.refresh_size()  # no-op: the fixed size never changes on its own
    assert (screen.width, screen.height) == (132, 43)


def test_headless_records_the_real_enter_leave_brackets():
    screen = HeadlessScreen()
    screen.enter()
    assert screen.output.startswith(ansi.enter_alt_screen() + ansi.hide_cursor())
    screen.leave()
    assert screen.output.endswith(ansi.leave_alt_screen())
    assert ansi.enter_alt_screen() in screen.output and screen.output.count(
        ansi.leave_alt_screen()
    ) == 1


def test_non_live_pipe_screen_stays_silent():
    stream = FakeStream()  # isatty() is False: a pipe or a file
    screen = TerminalScreen(stream)
    assert screen.live is False
    screen.enter()
    screen.leave()
    assert stream.data == ""  # not a single escape byte


def test_liveness_is_decided_once_at_construction():
    stream = FakeStream()  # a pipe
    screen = TerminalScreen(stream)
    assert screen.live is False
    stream.ttys = True  # the stream attaches to a terminal after construction
    screen.refresh_size()
    assert screen.live is False  # the construction-time decision stands


def test_terminal_write_and_flush_forward_to_the_stream():
    stream = FakeStream()
    screen = TerminalScreen(stream)
    screen.write("hello")
    screen.flush()
    assert stream.data == "hello" and stream.flushes == 1
