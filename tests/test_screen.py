"""Tests for mocode_tui.screen."""

from mocode_tui import ansi
from mocode_tui import screen as screen_mod
from mocode_tui.screen import HeadlessScreen, Screen, TerminalScreen


class FakeStream:
    """Minimal stream double: records writes, counts flushes, fakes isatty."""

    def __init__(self, *, isatty: bool = False) -> None:
        self.data = ""
        self.flushes = 0
        self._isatty = isatty

    def write(self, s: str) -> int:
        self.data += s
        return len(s)

    def flush(self) -> None:
        self.flushes += 1

    def isatty(self) -> bool:
        return self._isatty


# --- Screen protocol -----------------------------------------------------------


def test_both_screens_satisfy_the_protocol():
    assert isinstance(HeadlessScreen(), Screen)
    assert isinstance(TerminalScreen(FakeStream()), Screen)


def test_protocol_declares_the_full_surface():
    for name in (
        "width",
        "height",
        "live",
        "enter",
        "leave",
        "write",
        "flush",
        "refresh_size",
    ):
        assert hasattr(Screen, name), name


# --- HeadlessScreen -------------------------------------------------------------


def test_headless_defaults():
    screen = HeadlessScreen()
    assert (screen.width, screen.height) == (80, 24)
    assert screen.live is True
    assert screen.output == ""


def test_headless_enter_leave_bytes_match_the_ansi_single_source():
    screen = HeadlessScreen()
    screen.enter()
    assert screen.output == ansi.enter_alt_screen() + ansi.hide_cursor()
    screen.leave()
    assert screen.output == (
        ansi.enter_alt_screen()
        + ansi.hide_cursor()
        + ansi.show_cursor()
        + ansi.leave_alt_screen()
    )


def test_headless_write_records_in_order():
    screen = HeadlessScreen()
    screen.write("a")
    screen.write("")
    screen.write("bc")
    assert screen.output == "abc"


def test_headless_clear_resets_the_recording():
    screen = HeadlessScreen()
    screen.enter()
    screen.write("x")
    screen.clear()
    assert screen.output == ""
    screen.write("y")
    assert screen.output == "y"


def test_headless_flush_is_a_noop():
    screen = HeadlessScreen()
    screen.write("x")
    screen.flush()
    assert screen.output == "x"


def test_headless_refresh_size_keeps_fixed_dimensions():
    screen = HeadlessScreen(width=100, height=30)
    screen.refresh_size()
    assert (screen.width, screen.height) == (100, 30)


def test_headless_dimensions_are_adjustable_for_resize_tests():
    screen = HeadlessScreen()
    screen.width, screen.height = 132, 43
    assert (screen.width, screen.height) == (132, 43)


# --- TerminalScreen -------------------------------------------------------------


def test_terminal_non_tty_stream_is_not_live_and_stays_silent():
    stream = FakeStream()  # isatty() is False by default
    screen = TerminalScreen(stream)
    assert screen.live is False
    screen.enter()
    screen.leave()
    assert stream.data == ""


def test_terminal_live_when_tty_and_vt_available(monkeypatch):
    monkeypatch.setattr(screen_mod, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
    assert screen.live is True
    screen.enter()
    assert stream.data == ansi.enter_alt_screen() + ansi.hide_cursor()
    screen.leave()
    assert stream.data == (
        ansi.enter_alt_screen()
        + ansi.hide_cursor()
        + ansi.show_cursor()
        + ansi.leave_alt_screen()
    )


def test_terminal_tty_without_vt_is_not_live(monkeypatch):
    monkeypatch.setattr(screen_mod, "enable_vt", lambda: False)
    screen = TerminalScreen(FakeStream(isatty=True))
    assert screen.live is False


def test_terminal_liveness_is_decided_once_at_construction(monkeypatch):
    monkeypatch.setattr(screen_mod, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
    stream._isatty = False  # the stream detaches after construction
    assert screen.live is True


def test_terminal_write_and_flush_forward_to_stream():
    stream = FakeStream()
    screen = TerminalScreen(stream)
    screen.write("hello")
    screen.flush()
    assert stream.data == "hello"
    assert stream.flushes == 1


def test_terminal_refresh_size_resamples_terminal_size(monkeypatch):
    monkeypatch.setattr(screen_mod, "terminal_size", lambda: (132, 43))
    screen = TerminalScreen(FakeStream())
    assert (screen.width, screen.height) == (132, 43)  # initial sample
    monkeypatch.setattr(screen_mod, "terminal_size", lambda: (100, 30))
    screen.refresh_size()
    assert (screen.width, screen.height) == (100, 30)


def test_terminal_defaults_to_stdout(monkeypatch):
    monkeypatch.setattr(screen_mod, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    monkeypatch.setattr(screen_mod.sys, "stdout", stream)
    screen = TerminalScreen()
    assert screen.live is True
    screen.enter()
    assert stream.data == ansi.enter_alt_screen() + ansi.hide_cursor()
