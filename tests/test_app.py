"""Tests for mocode_tui.app (the TUI driver) and mocode_tui.testing."""

import asyncio
import io

import pytest

from mocode_tui.ansi import enter_alt_screen, leave_alt_screen
from mocode_tui.app import TUI
from mocode_tui.block import BlockState
from mocode_tui.components.input import Input
from mocode_tui.components.text import Text
from mocode_tui.keys import Key, Paste, ScriptedKeys
from mocode_tui.lines import Line
from mocode_tui.screen import HeadlessScreen, TerminalScreen
from mocode_tui.style import MUTED
from mocode_tui.testing import headless_tui, snapshot


class Rows:
    """Component rendering one row per given text."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(t) for t in self.texts]


def _lines(n: int) -> Rows:
    return Rows(*[f"r{i}" for i in range(n)])


def _piped_tui() -> TUI:
    """A TUI on a non-live (piped) screen: the dump contract applies."""
    return TUI(screen=TerminalScreen(io.StringIO()))


def _enter_leave(tui: TUI) -> tuple[int, int]:
    output = tui.screen.output
    return output.find(enter_alt_screen()), output.find(leave_alt_screen())


# --- construction --------------------------------------------------------------


def test_defaults_use_a_terminal_screen():
    tui = TUI()
    assert isinstance(tui.screen, TerminalScreen)
    assert tui.throttle == 0.030


def test_interactive_override_wins_over_the_derived_value():
    assert headless_tui().interactive is False
    assert TUI(screen=HeadlessScreen(), interactive=True).interactive is True


def test_a_non_live_screen_is_never_interactive():
    assert _piped_tui().interactive is False


# --- document facade -----------------------------------------------------------


def test_add_get_remove_and_auto_ids():
    tui = headless_tui()
    first = tui.add(Text("one"))
    second = tui.add(Text("two"), id="named")
    assert first.id == "b0"
    assert second.id == "named"
    assert tui.get("b0") is first
    assert tui.get("named") is second
    assert len(tui.document) == 2
    removed = tui.remove("b0")
    assert removed is first
    assert len(tui.document) == 1
    with pytest.raises(KeyError):
        tui.get("b0")


def test_add_accepts_pinned_blocks():
    tui = headless_tui()
    block = tui.add(Text("footer"), pinned=True)
    assert block.pinned is True
    assert tui.document.blocks()[0].pinned is True


def test_print_appends_a_muted_system_block():
    tui = headless_tui()
    block = tui.print("hello")
    assert isinstance(block.component, Text)
    assert block.component.text == "hello"
    assert block.component.style == MUTED
    assert block.state is BlockState.OPEN
    assert tui.get(block.id) is block


def test_document_mutations_invalidate_the_frame():
    tui = headless_tui()
    tui.flush()
    assert tui._dirty is False
    tui.add(Text("x"))
    assert tui._dirty is True
    tui.flush()
    tui.remove(tui.document.blocks()[0].id)
    assert tui._dirty is True


# --- scroll facade -------------------------------------------------------------


def test_scroll_facade_moves_the_rows_window():
    tui = headless_tui(80, 10)
    tui.add(_lines(30))
    tui.flush()
    assert [row.text for row in tui.rows()] == [f"r{i}" for i in range(20, 30)]

    tui.scroll_up(3)
    tui.flush()
    # Scrolled away from the bottom, the viewport's last row is the marker.
    assert [row.text for row in tui.rows()] == [
        *(f"r{i}" for i in range(17, 26)),
        "─ more below ─",
    ]

    tui.scroll_down(1)
    tui.flush()
    assert [row.text for row in tui.rows()] == [
        *(f"r{i}" for i in range(18, 27)),
        "─ more below ─",
    ]

    tui.scroll_to_bottom()
    tui.flush()
    assert [row.text for row in tui.rows()] == [f"r{i}" for i in range(20, 30)]


def test_rows_are_exactly_screen_height():
    tui = headless_tui(80, 7)
    tui.add(Text("a"))
    tui.flush()
    assert len(tui.rows()) == 7


# --- read_key ------------------------------------------------------------------


async def test_read_key_intercepts_page_keys_and_returns_the_rest():
    tui = headless_tui(
        80, 10, script=[Key("page_up"), Key("a", "a"), Key("page_down"), Paste("p"), None]
    )
    tui.add(_lines(30))
    tui.flush()
    before = [row.text for row in tui.rows()]

    assert await tui.read_key() == Key("a", "a")  # page_up was consumed
    tui.flush()
    after_page_up = [row.text for row in tui.rows()]
    assert after_page_up != before  # the intercepted page_up scrolled

    assert await tui.read_key() == Paste("p")  # page_down was consumed
    tui.flush()
    after_page_down = [row.text for row in tui.rows()]
    assert after_page_down != after_page_up

    assert await tui.read_key() is None  # EOF


async def test_read_key_escape_hatch_reads_the_raw_source():
    tui = headless_tui(80, 10, script=[Key("page_up")])
    assert await tui.keys.read() == Key("page_up")  # no interception here


async def test_read_key_without_a_source_returns_none():
    tui = TUI(screen=HeadlessScreen())
    assert await tui.read_key() is None


async def test_read_key_on_a_non_live_screen_returns_none():
    tui = TUI(screen=TerminalScreen(io.StringIO()), keys=ScriptedKeys([Key("a", "a")]))
    assert await tui.read_key() is None


# --- pump: throttle and every --------------------------------------------------


def test_tick_throttles_the_flush():
    tui = headless_tui()
    now = [1000.0]
    tui._clock = lambda: now[0]

    assert tui._tick(now[0]) is None  # the initial frame flushes immediately
    painted = len(tui.screen.output)
    assert painted > 0

    tui.add(Text("x"))
    assert tui._tick(now[0]) == pytest.approx(0.030)  # throttle not elapsed
    assert len(tui.screen.output) == painted  # nothing painted yet

    now[0] += 0.050  # comfortably past the throttle
    assert tui._tick(now[0]) is None  # now it flushes
    assert len(tui.screen.output) > painted


def test_tick_returns_none_when_nothing_is_pending():
    tui = headless_tui()
    tui._clock = lambda: 1000.0
    assert tui._tick(1000.0) is None
    assert tui._tick(1000.0) is None


def test_every_runs_on_schedule_and_can_be_cancelled():
    tui = headless_tui()
    now = [1000.0]
    tui._clock = lambda: now[0]
    assert tui._tick(now[0]) is None  # the initial frame

    calls: list[int] = []
    handle = tui.every(0.5, lambda: calls.append(1))
    assert tui._tick(now[0]) == pytest.approx(0.5)

    now[0] += 0.5
    assert tui._tick(now[0]) == pytest.approx(0.5)
    assert calls == [1]

    handle.cancel()
    assert handle.cancelled is True
    now[0] += 5.0
    assert tui._tick(now[0]) is None
    assert calls == [1]


def test_every_callback_can_invalidate_and_trigger_a_flush():
    tui = headless_tui()
    now = [1000.0]
    tui._clock = lambda: now[0]
    block = tui.add(Text(""))
    tui._tick(now[0])  # the initial frame
    painted = len(tui.screen.output)

    def grow() -> None:
        block.component.text += "x"  # new content for the next frame
        tui.invalidate()

    handle = tui.every(0.010, grow)
    now[0] += 0.010
    assert tui._tick(now[0]) == pytest.approx(0.010)  # dirty, throttle pending
    assert len(tui.screen.output) == painted

    now[0] += 0.050  # the throttle elapses
    tui._tick(now[0])
    assert len(tui.screen.output) > painted  # the new content was painted
    handle.cancel()


def test_tick_reports_the_earlier_of_flush_and_every():
    tui = headless_tui()
    now = [1000.0]
    tui._clock = lambda: now[0]
    tui._tick(now[0])
    tui.every(5.0, lambda: None)
    tui.add(Text("x"))
    assert tui._tick(now[0]) == pytest.approx(0.030)  # flush due before the callback


async def test_pump_loop_paints_and_exits_on_stop():
    tui = headless_tui(80, 5)
    tui.add(Text("hello"))
    task = asyncio.create_task(tui._pump())
    await asyncio.sleep(0)  # one loop turn: the pump ticks once
    assert tui.screen.output  # a frame was painted
    tui.stop()
    await asyncio.wait_for(task, timeout=5)


# --- run: lifecycle ------------------------------------------------------------


async def test_run_enters_and_leaves_the_alt_screen():
    tui = headless_tui(80, 6)

    async def body(app):
        app.add(Text("hi"))

    await tui.run(body)
    enter_at, leave_at = _enter_leave(tui)
    assert enter_at >= 0 and leave_at > enter_at
    assert tui.screen.output.endswith(leave_alt_screen())


async def test_run_leaves_the_alt_screen_when_the_body_raises():
    tui = headless_tui(80, 6)

    async def body(app):
        app.add(Text("hi"))
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await tui.run(body)
    enter_at, leave_at = _enter_leave(tui)
    assert enter_at >= 0 and leave_at > enter_at


async def test_run_leaves_the_alt_screen_when_stopped():
    tui = headless_tui(80, 6)

    async def body(app):
        app.add(Text("hi"))
        await asyncio.sleep(0)  # let the pump paint
        app.stop()

    await tui.run(body)
    enter_at, leave_at = _enter_leave(tui)
    assert enter_at >= 0 and leave_at > enter_at
    assert tui.screen.output


async def test_run_swallows_keyboard_interrupt_as_a_stop():
    tui = headless_tui(80, 6)

    async def body(app):
        app.add(Text("hi"))
        raise KeyboardInterrupt

    await tui.run(body)  # no exception escapes
    _, leave_at = _enter_leave(tui)
    assert leave_at >= 0


async def test_run_attaches_and_closes_raw_keys_when_interactive_and_live():
    tui = TUI(screen=HeadlessScreen(80, 6), interactive=True)
    seen: list[object] = []

    async def body(app):
        seen.append(app.keys)

    await tui.run(body)
    assert seen[0] is not None  # a raw source was attached for the session
    assert tui._owns_keys is False  # and closed again


# --- run: non-live dump --------------------------------------------------------


async def test_non_live_run_is_silent_and_dumps_the_final_screen():
    tui = _piped_tui()
    stream = tui.screen._stream
    seen: list[str] = []

    async def body(app):
        app.add(Text("hello"))
        app.add(Text("world"))
        seen.append(stream.getvalue())  # nothing written during the run

    await tui.run(body)
    assert seen == [""]
    assert stream.getvalue() == "hello\nworld\n"
    assert enter_alt_screen() not in stream.getvalue()
    assert leave_alt_screen() not in stream.getvalue()


async def test_non_live_dump_trims_trailing_blank_rows():
    tui = _piped_tui()

    async def body(app):
        app.add(Text("only line"))

    await tui.run(body)
    assert tui.screen._stream.getvalue() == "only line\n"


async def test_non_live_dump_of_an_empty_document_writes_nothing():
    tui = _piped_tui()

    async def body(app):
        app.add(Text("   "))

    await tui.run(body)
    assert tui.screen._stream.getvalue() == ""


async def test_non_live_run_dumps_before_re_raising():
    tui = _piped_tui()

    async def body(app):
        app.add(Text("partial"))
        raise RuntimeError("late failure")

    with pytest.raises(RuntimeError, match="late failure"):
        await tui.run(body)
    assert tui.screen._stream.getvalue() == "partial\n"


async def test_non_live_dump_puts_the_pinned_footer_last():
    tui = _piped_tui()

    async def body(app):
        app.add(Text("body"))
        app.add(Text("footer"), pinned=True)

    await tui.run(body)
    lines = tui.screen._stream.getvalue().splitlines()
    assert lines[0] == "body"
    assert lines[-1] == "footer"
    assert tui.screen._stream.getvalue().endswith("\n")


# --- testing helpers -----------------------------------------------------------


def test_snapshot_renders_block_stanzas():
    tui = headless_tui(80, 24)
    tui.add(Text("first\nsecond"))
    footer = tui.add(Input(), pinned=True)
    footer.seal()
    text = snapshot(tui)
    assert text.startswith("[b0 | open]\n  |first\n  |second\n")
    assert "[b1 | sealed,pinned]" in text
    assert text.splitlines()[-1].startswith("  |")  # the footer's rendered row


def test_headless_tui_script_drives_read_key():
    tui = headless_tui(80, 24, script=[Key("x", "x")])
    assert tui.screen.live is True
    assert tui.interactive is False
