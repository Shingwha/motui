"""Tests for mocode_tui.app (the TUI driver) and mocode_tui.testing.

Contracts (DESIGN.md / README.md): the ``add``/``get``/``remove``/``print``
facade invalidates the frame on every mutation; ``read_key()`` absorbs every
event in the ``scroll_keys`` table (rebindable, deletable) and returns
everything else -- button presses included, for the host to hit-test --
``None`` on a non-live screen even with a source attached; ``await
tui.keys.read()`` is the documented escape hatch; ``hit_test()`` maps a mouse
report's 0-based coordinates to the block and 0-based cell under them and
misses blank rows; ``run()`` brackets ``enter``/``leave`` on a live screen
including on exceptions, ``stop()`` and ``KeyboardInterrupt``; a non-live run
stays silent and dumps the final screen as plain text with trailing blank
rows trimmed; ``headless_tui``/``snapshot`` drive a real driver without a
terminal.
"""

import asyncio
import io

import pytest

from mocode_tui.core.ansi import enter_alt_screen, leave_alt_screen
from mocode_tui.app import TUI
from mocode_tui.core.block import BlockState
from mocode_tui.core.text import Text
from mocode_tui.core.events import Key, MouseEvent, Paste, ScriptedKeys
from mocode_tui.core.lines import Line
from mocode_tui.core.screen import HeadlessScreen, TerminalScreen
from mocode_tui.core.style import MUTED
from mocode_tui.testing import headless_tui, snapshot


class Rows:
    """Component rendering one row per given text."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(t) for t in self.texts]


def _lines(n: int) -> Rows:
    return Rows(*[f"r{i}" for i in range(n)])


def _piped_tui() -> tuple[TUI, io.StringIO]:
    """A TUI on a non-live (piped) screen the test itself holds."""
    stream = io.StringIO()
    return TUI(screen=TerminalScreen(stream)), stream


def _enter_leave(tui: TUI) -> tuple[int, int]:
    output = tui.screen.output
    return output.find(enter_alt_screen()), output.find(leave_alt_screen())


# --- document facade -----------------------------------------------------------


def test_add_get_remove_and_pin():
    tui = headless_tui()
    first = tui.add(Text("one"))
    second = tui.add(Text("footer"), pin="bottom")
    assert first.id == "b0" and second.pin == "bottom"
    assert tui.get("b0") is first
    assert tui.remove("b0") is first and len(tui.document) == 1
    with pytest.raises(KeyError):
        tui.get("b0")


def test_print_appends_a_muted_system_block():
    tui = headless_tui()
    block = tui.print("hello")
    assert isinstance(block.component, Text)
    assert block.component.text == "hello" and block.component.style == MUTED
    assert block.state is BlockState.OPEN
    assert tui.get(block.id) is block


def test_mutations_invalidate_the_frame():
    tui = headless_tui(80, 10)
    tui.paint()
    painted = len(tui.screen.output)
    tui.add(Text("x"))
    tui.paint()
    assert len(tui.screen.output) > painted  # the added block repainted
    painted = len(tui.screen.output)
    tui.remove("b0")
    tui.paint()
    assert len(tui.screen.output) > painted  # the removal repainted too


def test_scroll_facade_moves_the_window():
    tui = headless_tui(80, 10)
    tui.add(_lines(30))
    tui.paint()
    assert [row.text for row in tui.rows] == [f"r{i}" for i in range(20, 30)]
    tui.scroll_up(3)
    tui.paint()
    assert [row.text for row in tui.rows] == [
        *(f"r{i}" for i in range(17, 26)),
        "─ more below ─",
    ]
    tui.scroll_to_bottom()
    tui.paint()
    assert len(tui.rows) == 10
    assert [row.text for row in tui.rows] == [f"r{i}" for i in range(20, 30)]


# --- read_key ------------------------------------------------------------------


async def test_read_key_intercepts_page_keys_and_returns_the_rest():
    tui = headless_tui(
        80, 10, script=[Key("page_up"), Key("a", "a"), Key("page_down"), Paste("p"), None]
    )
    tui.add(_lines(30))
    tui.paint()
    before = [row.text for row in tui.rows]

    assert await tui.read_key() == Key("a", "a")  # page_up was consumed
    tui.paint()
    after_page_up = [row.text for row in tui.rows]
    assert after_page_up != before  # the intercepted page_up scrolled

    assert await tui.read_key() == Paste("p")  # page_down was consumed
    tui.paint()
    assert [row.text for row in tui.rows] != after_page_up

    assert await tui.read_key() is None  # EOF


async def test_read_key_intercepts_the_wheel_by_the_table_count():
    tui = headless_tui(
        80, 10, script=[MouseEvent("wheel_up", button=0, x=1, y=1), Key("a", "a"), None]
    )
    tui.add(_lines(30))
    tui.paint()
    assert await tui.read_key() == Key("a", "a")  # the wheel event was consumed
    tui.paint()
    # The absorbed wheel_up scrolled three rows: the table's default.
    assert [row.text for row in tui.rows] == [
        *(f"r{i}" for i in range(17, 26)),
        "─ more below ─",
    ]


async def test_scroll_keys_table_is_customizable():
    tui = headless_tui(
        80,
        10,
        script=[MouseEvent("wheel_down", button=1, x=4, y=7), MouseEvent("wheel_up"), None],
    )
    tui.add(_lines(30))
    tui.paint()
    tui.scroll_up(5)
    tui.paint()

    tui.scroll_keys["wheel_down"] = 1  # one row per notch, not the default three
    del tui.scroll_keys["wheel_up"]  # unbound: the event comes back untouched

    # The rebound wheel_down is absorbed on its way through (one row, not
    # three); the unbound wheel_up is handed back to the caller.
    assert await tui.read_key() == MouseEvent("wheel_up")
    tui.paint()
    assert [row.text for row in tui.rows] == [
        *(f"r{i}" for i in range(16, 25)),
        "─ more below ─",
    ]
    assert await tui.read_key() is None  # EOF


async def test_read_key_escape_hatch_reads_the_raw_source():
    tui = headless_tui(80, 10, script=[Key("page_up")])
    assert await tui.keys.read() == Key("page_up")  # no interception here


async def test_read_key_hands_button_presses_to_the_host_for_hit_testing():
    tui = headless_tui(
        80, 6, script=[MouseEvent("left", button=0, x=0, y=0), Key("a", "a"), None]
    )
    body = tui.add(_lines(10))
    tui.paint()
    event = await tui.read_key()  # a press is not in scroll_keys: it comes back
    assert event == MouseEvent("left", button=0, x=0, y=0)
    hit = tui.hit_test(event.x, event.y)  # the host resolves it against the frame
    assert hit is not None and hit.block is body and hit.row == 4 and hit.col == 0
    assert await tui.read_key() == Key("a", "a")
    assert await tui.read_key() is None


async def test_read_key_without_a_source_returns_none():
    assert await TUI(screen=HeadlessScreen()).read_key() is None


async def test_read_key_on_a_non_live_screen_returns_none():
    tui = TUI(screen=TerminalScreen(io.StringIO()), keys=ScriptedKeys([Key("a", "a")]))
    assert await tui.read_key() is None


# --- mouse hit test -------------------------------------------------------------


def test_hit_test_resolves_report_coordinates_into_a_block():
    tui = headless_tui(80, 6)
    body = tui.add(_lines(10))  # b0: r0..r9 in the scrollable body
    foot = tui.add(Rows("foot"), pin="bottom")  # b1: the bottom fixed region
    tui.paint()
    # Screen rows (0-based): r5..r9 above the pinned footer's one row.
    hit = tui.hit_test(2, 0)  # 0-based (col 2, row 0) -> screen row 0 = b0 row 5
    assert hit is not None and hit.block is body and hit.row == 5 and hit.col == 2
    hit = tui.hit_test(0, 5)  # the footer's only row, column 0
    assert hit is not None and hit.block is foot and hit.row == 0 and hit.col == 0


def test_hit_test_misses_blank_fill_out_of_range_and_removed_blocks():
    tui = headless_tui(80, 4)
    tui.add(Rows("only"))
    tui.paint()
    assert tui.hit_test(0, 2) is None  # blank fill below the content
    assert tui.hit_test(0, 98) is None  # below the screen of the last layout
    tui.remove("b0")  # the ownership table is stale until the next layout
    assert tui.hit_test(0, 0) is None


def test_hit_test_before_any_layout_misses():
    tui = headless_tui(80, 6)
    tui.add(Text("x"))
    assert tui.hit_test(0, 0) is None  # no layout has run yet


def test_hit_test_on_the_more_below_marker_keeps_the_covered_row():
    tui = headless_tui(80, 4)
    body = tui.add(_lines(10))
    tui.paint()
    tui.scroll_up(1)  # the window shows r5..r8, the marker painted over r8
    tui.paint()
    hit = tui.hit_test(0, 3)  # screen row 3, where the marker sits
    assert hit is not None and hit.block is body and hit.row == 8


# --- pump: throttle and every --------------------------------------------------


def test_throttle_delays_the_flush_until_the_window_elapses():
    tui = headless_tui()
    now = [1000.0]
    tui._clock = lambda: now[0]  # the documented clock seam

    assert tui._tick(now[0]) is None  # the initial frame flushes immediately
    painted = len(tui.screen.output)

    tui.add(Text("x"))
    assert tui._tick(now[0]) == pytest.approx(tui.throttle)  # the window has not elapsed
    assert len(tui.screen.output) == painted  # nothing painted yet

    now[0] += 0.050  # comfortably past the throttle
    assert tui._tick(now[0]) is None  # now it flushes
    assert len(tui.screen.output) > painted


def test_every_runs_on_schedule_and_can_be_cancelled():
    tui = headless_tui()
    now = [1000.0]
    tui._clock = lambda: now[0]
    tui._tick(now[0])  # the initial frame

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
    assert await tui.keys.read() is None  # and closed again by teardown


# --- run: non-live dump --------------------------------------------------------


async def test_non_live_run_is_silent_and_dumps_the_final_screen():
    tui, stream = _piped_tui()
    seen: list[str] = []

    async def body(app):
        app.add(Text("hello"))
        app.add(Text("world"))
        seen.append(stream.getvalue())  # nothing written during the run

    await tui.run(body)
    assert seen == [""]
    dumped = stream.getvalue()
    assert dumped == "hello\nworld\n"
    assert enter_alt_screen() not in dumped and leave_alt_screen() not in dumped


async def test_non_live_dump_trims_trailing_blank_rows():
    tui, stream = _piped_tui()

    async def body(app):
        app.add(Text("only line"))

    await tui.run(body)
    assert stream.getvalue() == "only line\n"


async def test_non_live_dump_of_an_empty_document_writes_nothing():
    tui, stream = _piped_tui()

    async def body(app):
        app.add(Text("   "))

    await tui.run(body)
    assert stream.getvalue() == ""


async def test_non_live_run_dumps_before_re_raising():
    tui, stream = _piped_tui()

    async def body(app):
        app.add(Text("partial"))
        raise RuntimeError("late failure")

    with pytest.raises(RuntimeError, match="late failure"):
        await tui.run(body)
    assert stream.getvalue() == "partial\n"


async def test_non_live_dump_puts_the_pinned_footer_last():
    tui, stream = _piped_tui()

    async def body(app):
        app.add(Text("body"))
        app.add(Text("footer"), pin="bottom")

    await tui.run(body)
    lines = stream.getvalue().splitlines()
    assert lines[0] == "body" and lines[-1] == "footer"


# --- testing helpers -----------------------------------------------------------


def test_snapshot_renders_block_stanzas():
    tui = headless_tui(80, 24)
    tui.add(Text("first\nsecond"))
    footer = tui.add(Text("foot"), pin="bottom")
    footer.seal()
    text = snapshot(tui)
    assert text.startswith("[b0 | open]\n  |first\n  |second\n")
    assert "[b1 | sealed,bottom]" in text
    assert text.splitlines()[-1].startswith("  |")


def test_headless_tui_wires_a_recording_screen_and_scripted_keys():
    tui = headless_tui(80, 24, script=[Key("x", "x")])
    assert isinstance(tui.screen, HeadlessScreen)
    assert tui.screen.live is True and tui.interactive is False
