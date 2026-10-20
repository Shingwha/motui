"""Tests for motui.kernel.screen.

``TerminalScreen`` is live iff the stream is a tty and the VT probe succeeds,
decided once at construction; ``HeadlessScreen`` records and resizes; ``copy``
emits OSC 52 on live screens only, the headless one records it.  The
enter/leave bracket carries the mouse and paste reporting pairs, each gated
by its own constructor switch.
"""

import pytest

from motui.kernel import ansi
from motui.kernel import screen as screen_module
from motui.kernel.screen import HeadlessScreen, TerminalScreen


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
    assert (screen.width, screen.height, screen.live, screen.output) == (80, 24, True, "")
    screen.write("a")
    screen.write("")
    screen.write("bc")
    assert screen.output == "abc"
    screen.flush()  # a no-op: the recording buffer is the output
    assert screen.output == "abc"


def test_the_default_bracket_pins_its_exact_bytes():
    # The default enter/leave bytes, literal: 1000 + 1002 + 1006 out, all
    # four modes (1006/1003/1002/1000) back off on the leave path -- 1003
    # rides it since pointer W2 so no mode can be left on, even one the
    # hover path never set.
    screen = HeadlessScreen()
    screen.enter()
    screen.leave()
    assert screen.output == (
        "\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1002h\x1b[?1006h\x1b[?2004h"
        "\x1b[?2004l\x1b[?1006l\x1b[?1003l\x1b[?1002l\x1b[?1000l"
        "\x1b[?25h\x1b[?1049l"
    )


def test_headless_hover_records_the_1003_motion_mode():
    screen = HeadlessScreen(hover=True)
    screen.enter()
    assert "1003h" in screen.output
    assert "1002h" not in screen.output
    screen.leave()
    assert "1003l" in screen.output


def test_focus_events_are_off_by_default_and_ride_the_bracket_when_on():
    # Off: the default bracket (pinned above) gains no 1004 byte at all.
    default = HeadlessScreen()
    default.enter()
    default.leave()
    assert "1004h" not in default.output and "1004l" not in default.output
    # On: DECSET 1004 is the last enable and the first disable -- the strict
    # reverse of the enter order, so no reporting mode can be left on.
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


def test_a_live_terminal_screen_sends_the_focus_pair_when_switched_on(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream, focus_events=True)
    screen.enter()
    screen.leave()
    assert stream.data == (
        ansi.enter_alt_screen()
        + ansi.hide_cursor()
        + ansi.enable_mouse_tracking()
        + ansi.enable_bracketed_paste()
        + ansi.enable_focus_events()
        + ansi.disable_focus_events()
        + ansi.disable_bracketed_paste()
        + ansi.disable_mouse_tracking()
        + ansi.show_cursor()
        + ansi.leave_alt_screen()
    )


def test_a_live_terminal_screen_hover_records_the_1003_motion_mode(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream, hover=True)
    screen.enter()
    screen.leave()
    assert "\x1b[?1003h" in stream.data
    assert "\x1b[?1002h" not in stream.data
    assert "\x1b[?1003l" in stream.data


@pytest.mark.parametrize(
    "kwargs, present, absent",
    [
        ({"mouse": False}, ansi.enable_bracketed_paste(), ansi.enable_mouse_tracking()),
        ({"paste": False}, ansi.enable_mouse_tracking(), ansi.enable_bracketed_paste()),
    ],
)
def test_headless_switches_drop_the_pair_they_gate(kwargs, present, absent):
    screen = HeadlessScreen(**kwargs)
    screen.enter()
    screen.leave()
    assert present in screen.output
    assert absent not in screen.output
    assert ansi.enter_alt_screen() in screen.output and ansi.leave_alt_screen() in screen.output


@pytest.mark.parametrize(
    "kwargs, present, absent",
    [
        ({"mouse": False}, ansi.enable_bracketed_paste(), ansi.enable_mouse_tracking()),
        ({"paste": False}, ansi.enable_mouse_tracking(), ansi.enable_bracketed_paste()),
    ],
)
def test_a_live_terminal_screen_drops_the_pair_its_switch_turns_off(
    monkeypatch, kwargs, present, absent
):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream, **kwargs)
    screen.enter()
    screen.leave()
    assert present in stream.data
    assert absent not in stream.data


def test_a_live_terminal_screen_sends_the_full_enter_leave_bracket(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
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


def test_a_live_screen_copies_the_osc52_bytes_and_flushes(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
    assert screen.live is True
    assert screen.copy_to_clipboard("copied text") is True
    assert stream.data == ansi.copy_clipboard("copied text")
    assert stream.flushes == 1  # the clipboard primitive pushes its own bytes


def test_a_non_live_screen_copies_nothing_and_reports_false():
    stream = FakeStream()  # isatty() is False: a pipe or a file
    screen = TerminalScreen(stream)
    assert screen.copy_to_clipboard("copied text") is False
    assert stream.data == ""  # not a single escape byte
    assert stream.flushes == 0


def test_the_headless_screen_records_the_copy_and_reports_true():
    screen = HeadlessScreen()
    assert screen.copy_to_clipboard("copied text") is True
    assert screen.output == ansi.copy_clipboard("copied text")


def test_both_screens_declare_size_encoding_and_close():
    terminal = TerminalScreen(FakeStream())
    assert terminal.size == (terminal.width, terminal.height)
    assert terminal.encoding is None or isinstance(terminal.encoding, str)
    terminal.close()

    headless = HeadlessScreen(21, 7)
    assert headless.size == (21, 7)
    assert headless.encoding == "utf-8"
    headless.close()  # idempotent and side-effect free


def test_headless_color_mode_is_a_definite_truecolor_unless_asked_otherwise():
    # Not the environment probe a live terminal runs: a test's bytes never
    # depend on the machine it runs on.
    assert HeadlessScreen().color_mode == "truecolor"
    assert HeadlessScreen(color_mode="256").color_mode == "256"
    assert HeadlessScreen(color_mode="none").color_mode == "none"


def test_a_terminal_screen_resolves_auto_once_at_construction(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    monkeypatch.setattr(screen_module, "detect_color_mode", lambda: "256")
    stream = FakeStream(isatty=True)
    screen = TerminalScreen(stream)
    assert screen.color_mode == "256"  # "auto" probed the environment
    monkeypatch.setattr(screen_module, "detect_color_mode", lambda: "none")
    screen.refresh_size()
    assert screen.color_mode == "256"  # decided once, like liveness
    assert TerminalScreen(stream, color_mode="16").color_mode == "16"  # taken as given
