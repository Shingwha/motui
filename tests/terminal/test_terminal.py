"""The terminal adapter: screen construction, the session bracket, reads and
clipboard forwarding.

A ``Terminal`` wraps exactly one screen and one event source.  The screen
choice is layered (explicit ``screen=`` over ``options.screen`` over a
constructed ``TerminalScreen``), the mouse mode maps to the screen switches,
and ``read_event`` is a pure read with ``None`` meaning EOF.
"""

from __future__ import annotations

import io

from motui.terminal import (
    Capability,
    HeadlessScreen,
    MouseMode,
    Terminal,
    TerminalOptions,
    ansi,
)
from motui.terminal import screen as screen_module
from tests.testing import ScriptedEvents, key


class FakeStream:
    """Minimal stream double: records writes, fakes isatty."""

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


def _terminal_for(stream: FakeStream, mode: MouseMode) -> Terminal:
    return Terminal(TerminalOptions(stream=stream, mouse=mode))


def test_an_explicit_screen_wins_over_the_options_screen():
    chosen = HeadlessScreen(10, 3)
    spare = HeadlessScreen(20, 4)
    terminal = Terminal(TerminalOptions(screen=spare), screen=chosen)
    assert terminal.screen is chosen


def test_the_options_screen_is_used_as_is():
    screen = HeadlessScreen(21, 7)
    terminal = Terminal(TerminalOptions(screen=screen))
    assert terminal.screen is screen
    assert terminal.size == (21, 7)
    assert terminal.live is True


def test_a_constructed_screen_maps_every_mouse_mode(monkeypatch):
    monkeypatch.setattr(screen_module, "enable_vt", lambda: True)
    for mode, motion, absent in (
        (MouseMode.MOVE, "1003h", "1002h"),
        (MouseMode.DRAG, "1002h", "1003h"),
        (MouseMode.BUTTON, "1002h", "1003h"),
    ):
        stream = FakeStream(isatty=True)
        terminal = _terminal_for(stream, mode)
        terminal.enter()
        terminal.leave()
        assert motion in stream.data and absent not in stream.data
        assert ansi.enable_bracketed_paste() in stream.data
    stream = FakeStream(isatty=True)
    terminal = _terminal_for(stream, MouseMode.OFF)
    terminal.enter()
    terminal.leave()
    assert "1000h" not in stream.data and "1002h" not in stream.data
    assert ansi.enable_bracketed_paste() in stream.data


def test_a_non_live_terminal_writes_no_session_bytes():
    stream = io.StringIO()
    terminal = Terminal(TerminalOptions(stream=stream, mouse=MouseMode.MOVE))
    assert terminal.live is False
    terminal.enter()
    terminal.leave()
    assert stream.getvalue() == ""


def test_enter_and_leave_forward_the_screen_bracket_in_order():
    screen = HeadlessScreen()
    terminal = Terminal(TerminalOptions(screen=screen))
    terminal.enter()
    terminal.leave()
    assert screen.output.startswith(ansi.enter_alt_screen())
    assert screen.output.endswith(ansi.leave_alt_screen())


async def test_read_event_reads_the_configured_source_then_eofs():
    terminal = Terminal(
        TerminalOptions(
            screen=HeadlessScreen(),
            input=ScriptedEvents([key("a", "a"), None]),
        )
    )
    assert await terminal.read_event() == key("a", "a")
    assert await terminal.read_event() is None


async def test_read_event_answers_none_without_a_source_and_after_attach():
    terminal = Terminal(TerminalOptions(screen=HeadlessScreen()))
    assert terminal.input is None
    assert await terminal.read_event() is None
    source = ScriptedEvents([key("b", "b")])
    terminal.attach(source)
    assert terminal.input is source
    assert await terminal.read_event() == key("b", "b")
    terminal.attach(None)
    assert await terminal.read_event() is None


def test_the_clipboard_forwards_to_the_screen():
    screen = HeadlessScreen()
    terminal = Terminal(TerminalOptions(screen=screen))
    assert terminal.clipboard.copy("copied text") is True
    assert screen.output == ansi.copy_clipboard("copied text")


def test_capability_samples_the_screen_on_demand():
    terminal = Terminal(TerminalOptions(screen=HeadlessScreen(21, 7, color_mode="256")))
    assert terminal.capability == Capability(
        color_mode="256", size=(21, 7), live=True, encoding="utf-8"
    )


def test_refresh_size_delegates_to_the_screen():
    screen = HeadlessScreen()
    calls: list[int] = []
    screen.refresh_size = lambda: calls.append(1)  # type: ignore[method-assign]
    Terminal(TerminalOptions(screen=screen)).refresh_size()
    assert calls == [1]


def test_close_closes_the_source_and_the_screen():
    class Source:
        closed = False

        async def read(self):
            return None

        def close(self) -> None:
            self.closed = True

    source = Source()
    screen = HeadlessScreen()
    closed: list[str] = []
    screen.close = lambda: closed.append("screen")  # type: ignore[method-assign]
    terminal = Terminal(TerminalOptions(screen=screen, input=source))
    terminal.close()
    assert source.closed is True
    assert terminal.input is None
    assert closed == ["screen"]


def test_the_terminal_reports_the_mouse_mode_in_its_repr():
    terminal = Terminal(TerminalOptions(screen=HeadlessScreen(), mouse=MouseMode.BUTTON))
    assert "mouse='button'" in repr(terminal)
