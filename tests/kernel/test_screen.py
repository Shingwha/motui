"""Screen surfaces: headless recording, the terminal enter/leave bracket,
clipboard forwarding and color mode.

``HeadlessScreen`` records every byte and is live by construction; a
``TerminalScreen`` is live only when the stream is a tty and the VT probe
succeeds, decided once at construction.  Both bracket a session with the
alternate screen and the reporting modes their switches enable.
"""

from __future__ import annotations

from motui.core import ansi
from motui.core import screen as screen_module
from motui.core.screen import HeadlessScreen, TerminalScreen


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


def test_headless_defaults_and_records_every_byte():
    screen = HeadlessScreen()
    assert (screen.width, screen.height, screen.live, screen.output) == (
        80,
        24,
        True,
        "",
    )
    screen.write("a")
    screen.write("")
    screen.write("bc")
    assert screen.output == "abc"
    screen.flush()
    assert screen.output == "abc"


def test_the_default_enter_leave_bracket():
    screen = HeadlessScreen()
    screen.enter()
    screen.leave()
    assert screen.output == (
        "\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1002h\x1b[?1006h\x1b[?2004h"
        "\x1b[?2004l\x1b[?1006l\x1b[?1003l\x1b[?1002l\x1b[?1000l"
        "\x1b[?25h\x1b[?1049l"
    )


def test_hover_records_the_1003_motion_mode():
    screen = HeadlessScreen(hover=True)
    screen.enter()
    assert "1003h" in screen.output
    assert "1002h" not in screen.output
    screen.leave()
    assert "1003l" in screen.output


def test_focus_events_are_off_by_default_and_ride_the_bracket_when_enabled():
    default = HeadlessScreen()
    default.enter()
    default.leave()
    assert "1004h" not in default.output and "1004l" not in default.output
    screen = HeadlessScreen(focus_events=True)
    screen.enter()
    assert screen.output == (
        ansi.enter_alt_screen()
        + ansi.hide_cursor()
        + ansi.enable_mouse_tracking()
        + ansi.enable_bracketed_paste()
        + ansi.enable_focus_events()
    )
    screen.leave()
    assert screen.output.endswith(
        ansi.disable_focus_events()
        + ansi.disable_bracketed_paste()
        + ansi.disable_mouse_tracking()
        + ansi.show_cursor()
        + ansi.leave_alt_screen()
    )


def test_switches_drop_the_reporting_pair_they_gate():
    for kwargs, present, absent in (
        ({"mouse": False}, ansi.enable_bracketed_paste(), ansi.enable_mouse_tracking()),
        ({"paste": False}, ansi.enable_mouse_tracking(), ansi.enable_bracketed_paste()),
    ):
        screen = HeadlessScreen(**kwargs)
        screen.enter()
        screen.leave()
        assert present in screen.output
        assert absent not in screen.output
        assert ansi.enter_alt_screen() in screen.output


def test_a_live_terminal_screen_sends_the_full_bracket(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
    assert screen.live is True
    screen.enter()
    screen.leave()
    assert stream.data == (
        ansi.enter_alt_screen()
        + ansi.hide_cursor()
        + ansi.enable_mouse_tracking()
        + ansi.enable_bracketed_paste()
        + ansi.disable_bracketed_paste()
        + ansi.disable_mouse_tracking()
        + ansi.show_cursor()
        + ansi.leave_alt_screen()
    )


def test_a_non_live_pipe_screen_stays_silent():
    stream = FakeStream()
    screen = TerminalScreen(stream)
    assert screen.live is False
    screen.enter()
    screen.leave()
    assert stream.data == ""


def test_liveness_is_decided_once_at_construction():
    stream = FakeStream()
    screen = TerminalScreen(stream)
    assert screen.live is False
    stream.ttys = True
    screen.refresh_size()
    assert screen.live is False


def test_a_live_screen_copies_the_osc52_bytes_and_flushes(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
    assert screen.copy_to_clipboard("copied text") is True
    assert stream.data == ansi.copy_clipboard("copied text")
    assert stream.flushes == 1


def test_a_non_live_screen_copies_nothing_and_reports_false():
    stream = FakeStream()
    assert TerminalScreen(stream).copy_to_clipboard("copied text") is False
    assert stream.data == "" and stream.flushes == 0


def test_the_headless_screen_records_the_copy():
    screen = HeadlessScreen()
    assert screen.copy_to_clipboard("copied text") is True
    assert screen.output == ansi.copy_clipboard("copied text")


def test_both_screens_declare_size_encoding_and_close():
    terminal = TerminalScreen(FakeStream())
    assert terminal.size == (terminal.width, terminal.height)
    terminal.close()
    headless = HeadlessScreen(21, 7)
    assert headless.size == (21, 7) and headless.encoding == "utf-8"
    headless.close()


def test_color_modes_are_declared_and_auto_resolves_once(monkeypatch):
    assert HeadlessScreen().color_mode == "truecolor"
    assert HeadlessScreen(color_mode="256").color_mode == "256"
    assert HeadlessScreen(color_mode="none").color_mode == "none"
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    monkeypatch.setattr(screen_module, "detect_color_mode", lambda: "256")
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
    assert screen.color_mode == "256"
    monkeypatch.setattr(screen_module, "detect_color_mode", lambda: "none")
    screen.refresh_size()
    assert screen.color_mode == "256"
    assert TerminalScreen(stream, color_mode="16").color_mode == "16"
