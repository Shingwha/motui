"""The driver's public contract: document facade, scroll, events, docks, lifecycle."""

from __future__ import annotations

import asyncio
import io

import pytest

from motui.app import TUI
from motui.kernel import (
    MUTED,
    HeadlessScreen,
    Rect,
    RowRange,
    Text,
)
from motui.kernel.ansi import enter_alt_screen, leave_alt_screen
from motui.kernel.block import BlockState
from motui.kernel.screen import TerminalScreen
from motui.kernel.viewport import Viewport
from motui.testing import ScriptedEvents
from tests.testing import (
    Clock,
    RecordingScreen,
    Rows,
    headless_tui,
    key,
    many,
    paste,
    press,
    rows,
    snapshot,
    wheel,
)


# -- document facade ---------------------------------------------------------


def test_add_get_remove_and_system_address_blocks():
    tui = headless_tui()
    first = tui.add(Text("one"))
    pinned = tui.add(Text("footer"), pin="bottom")
    assert first.id == "b0" and pinned.pin == "bottom"
    assert tui.get("b0") is first

    block = tui.system("hello")
    assert isinstance(block.component, Text)
    assert block.component.text == "hello"
    assert block.component.style == MUTED
    assert block.state is BlockState.OPEN
    assert tui.get(block.id) is block

    assert tui.remove("b0") is first
    assert len(tui.document) == 2
    with pytest.raises(KeyError):
        tui.get("b0")


def test_a_mutation_reaches_the_next_paint():
    tui = headless_tui(80, 10)
    tui.paint()
    painted = len(tui.screen.output)
    tui.add(Text("x"))
    tui.paint()
    assert len(tui.screen.output) > painted
    painted = len(tui.screen.output)
    tui.remove("b0")
    tui.paint()
    assert len(tui.screen.output) > painted


def test_duplicate_block_ids_are_rejected_across_the_frame():
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical")
    tui.add(Rows("explicit"), id="dup")
    with pytest.raises(ValueError, match="duplicate block id"):
        tui.add(Rows("same document"), id="dup")
    with pytest.raises(ValueError, match="duplicate block id"):
        tui.add(Rows("other document"), id="dup", pane=right.id)

    # A document can be handed a duplicate directly; driver reads refuse to pick.
    left.document.add(Rows("collision"), id="same")
    right.document.add(Rows("collision"), id="same")
    with pytest.raises(ValueError, match="multiple panes"):
        tui.get("same")
    with pytest.raises(ValueError, match="multiple panes"):
        tui.remove("same")


def test_block_ids_are_allocated_across_the_whole_frame():
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical")
    left.document.add(Rows("transcript"))
    right.document.add(Rows("preview"))
    assert right.document.blocks()[0].id == "b0"
    block = tui.add(Rows("child body"), pane=right.id)
    assert block.id == "b1"
    assert tui.pane(right.id) is right
    assert tui.get(block.id) is block
    assert tui.remove(block.id) is block
    assert [held.id for held in right.document.blocks()] == ["b0"]


def test_pane_lookup_raises_for_an_unknown_id():
    tui = headless_tui()
    with pytest.raises(KeyError):
        tui.pane("nowhere")


# -- split and pane surface --------------------------------------------------


def test_split_keeps_the_document_in_the_first_child():
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical", ratios=(2, 1))
    left.document.add(Rows("transcript"))
    right.document.add(Rows("preview"))
    assert [pane.id for pane in tui.frame.panes] == ["primary", "pane-1"]
    assert left.document is tui.document
    assert right.document is not tui.document
    assert tui.frame.focused_pane is left
    tui.paint()
    assert rows(tui)[0].startswith("transcript")
    assert left.rect.width == 26 and right.rect.x == 26


def test_split_takes_an_explicit_pane_and_moves_no_focus():
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical")
    top, bottom = tui.split("horizontal", pane=right.id)
    assert top.id == right.id and top.document is right.document
    assert bottom.document is not right.document
    assert tui.frame.focused_pane is left


def test_pane_ids_are_monotonic_and_never_reused():
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical")
    assert (left.id, right.id) == ("primary", "pane-1")
    right.close()
    first, second = tui.split("vertical", pane="primary")
    assert first.id == "primary" and second.id == "pane-2"


def test_closing_a_child_returns_its_cells_and_the_focus():
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical")
    left.document.add(Rows("transcript"))
    right.document.add(Rows("preview"))
    tui.paint()
    right.focus()
    right.close()
    tui.paint()
    assert [pane.id for pane in tui.frame.panes] == ["primary"]
    assert tui.frame.pane("pane-1") is None
    assert tui.frame.focused_pane is tui.frame.pane("primary")
    assert rows(tui) == ["transcript"] + [""] * 5
    assert tui.frame.focused_pane.document is tui.document


async def test_a_button_press_focuses_the_pane_under_it():
    tui = headless_tui(40, 6, script=[press(30, 0), None])
    left, right = tui.split("vertical")
    tui.paint()
    assert tui.frame.focused_pane is left
    assert await tui.read_event() == press(30, 0)
    assert tui.frame.focused_pane is right


async def test_a_wheel_scrolls_the_pane_under_the_pointer_without_moving_focus():
    tui = headless_tui(40, 6, script=[wheel(4, 0, "up"), wheel(30, 0, "up"), None])
    left, right = tui.split("vertical")
    left.document.add(Rows(*many(40)))
    right.document.add(Rows(*many(40)))
    right.focus()
    tui.paint()
    left_before, right_before = left.viewport.offset, right.viewport.offset
    assert await tui.read_event() is None  # both wheels were absorbed
    assert left.viewport.offset == left_before - 3
    assert right.viewport.offset == right_before - 3
    assert tui.frame.focused_pane is right


def test_the_focus_policy_is_replaceable():
    tui = headless_tui(40, 6)
    left, _ = tui.split("vertical")
    seen: list[object] = []
    event = press(30, 0)
    tui.focus_policy = lambda app, item: seen.append(item) or None
    tui.focus_policy(tui, event)
    assert tui.frame.focused_pane is left and seen == [event]


# -- scroll facade -----------------------------------------------------------


def test_scroll_facade_moves_the_focused_window():
    tui = headless_tui(80, 10)
    tui.add(Rows(*many(30)))
    tui.paint()
    assert rows(tui) == many(30)[20:]
    tui.scroll_up(3)
    tui.paint()
    assert rows(tui) == many(30)[17:27]
    tui.scroll_to_bottom()
    tui.paint()
    assert rows(tui) == many(30)[20:]


def _three_blocks(tui: TUI) -> None:
    for name, prefix in (("head", "h"), ("body", "b"), ("tail", "t")):
        tui.add(Rows(*(f"{prefix}{i}" for i in range(10))), id=name)


def test_reveal_leaves_a_visible_target_alone_and_centers_the_rest():
    tui = headless_tui(40, 10)
    _three_blocks(tui)
    tui.paint()
    assert tui.viewport.offset == 20
    tui.scroll_up(1 << 20)
    tui.paint()
    assert tui.viewport.offset == 0

    assert tui.reveal("head", 9) is True
    assert tui.viewport.offset == 0

    assert tui.reveal("tail", 0) is True
    assert tui.viewport.offset == 15
    tui.paint()
    assert rows(tui) == [f"b{i}" for i in range(5, 10)] + [f"t{i}" for i in range(5)]

    assert tui.reveal("body", 0) is True
    assert tui.viewport.offset == 5
    tui.paint()
    assert rows(tui) == [f"h{i}" for i in range(5, 10)] + [
        f"b{i}" for i in range(5)
    ]


def test_reveal_answers_false_and_clamps_rows_and_fixed_regions():
    tui = headless_tui(40, 10)
    assert tui.reveal("head", 0) is False  # no composition yet
    _three_blocks(tui)
    tui.add(Rows("status"), id="status", pin="bottom")
    tui.paint()
    assert tui.viewport.offset == 21

    assert tui.reveal("status", 0) is True
    assert tui.viewport.offset == 21
    assert tui.reveal("ghost", 0) is False
    assert tui.viewport.offset == 21

    tui.scroll_up(1 << 20)
    tui.paint()
    assert tui.reveal("body", 100) is True
    assert tui.viewport.offset == 15
    tui.paint()
    assert "b9" in rows(tui)


# -- read_event --------------------------------------------------------------


async def test_read_event_absorbs_scroll_keys_and_returns_the_rest():
    tui = headless_tui(
        80,
        10,
        script=[wheel(0, 0, "up"), key("page_up"), key("a", "a"), paste("p"), None],
    )
    tui.add(Rows(*many(30)))
    tui.paint()
    assert rows(tui) == many(30)[20:]

    assert await tui.read_event() == key("a", "a")
    assert await tui.read_event() == paste("p")
    tui.paint()
    assert rows(tui) == many(30)[16:26]
    assert await tui.read_event() is None


async def test_scroll_keys_table_is_customizable_per_driver():
    tui = headless_tui(
        80, 10, script=[wheel(0, 0, "down"), wheel(0, 0, "up"), None]
    )
    tui.add(Rows(*many(30)))
    tui.paint()
    tui.scroll_up(5)
    tui.paint()
    assert rows(tui) == many(30)[15:25]

    tui.scroll_keys["wheel_down"] = 1
    del tui.scroll_keys["wheel_up"]
    assert await tui.read_event() == wheel(0, 0, "up")
    tui.paint()
    assert rows(tui) == many(30)[16:26]


async def test_a_button_press_comes_back_for_the_host_to_hit_test():
    tui = headless_tui(80, 6, script=[press(0, 0), None])
    body = tui.add(Rows(*many(10)))
    tui.paint()
    event = await tui.read_event()
    assert event == press(0, 0)
    hit = tui.hit(event.x, event.y)
    assert hit is not None and hit.block is body and hit.row == 4 and hit.col == 0


def test_read_event_answers_none_without_a_source_or_on_a_non_live_screen():
    assert asyncio.run(TUI(screen=HeadlessScreen()).read_event()) is None
    tui = TUI(screen=TerminalScreen(io.StringIO()), keys=ScriptedEvents([key("a", "a")]))
    assert asyncio.run(tui.read_event()) is None


class _BlockingSource:
    """An event source that answers only when the session ends."""

    def __init__(self) -> None:
        self.closed = False
        self.gate = asyncio.Event()

    async def read(self):
        await self.gate.wait()
        return None

    def close(self) -> None:
        self.closed = True
        self.gate.set()


async def test_exit_unblocks_a_pending_read_event_immediately():
    source = _BlockingSource()
    tui = TUI(screen=HeadlessScreen(), keys=source, interactive=False)
    pending = asyncio.create_task(tui.read_event())
    tui.exit()
    assert await asyncio.wait_for(pending, 1) is None
    assert not source.closed  # closing the source belongs to teardown


# -- lifecycle ---------------------------------------------------------------


async def test_exit_ends_run_async_and_a_second_session_starts_clean():
    tui = headless_tui(40, 3)

    asyncio.get_running_loop().call_soon(tui.exit)
    await tui.run_async()

    async def body(app: TUI) -> None:
        app.add(Text("second run"))
        app.exit()

    await tui.run_session(body)
    tui.paint()
    assert rows(tui)[0] == "second run"


def test_run_is_a_synchronous_entry_that_returns_when_the_session_exits():
    screen = RecordingScreen(20, 3, live=True)
    tui = TUI(screen=screen, keys=ScriptedEvents(()), interactive=False)
    tui.add(Text("hi"))
    # A host may end the session from inside the screen bracket; the sync
    # entry must still return once the session is over.
    screen.enter = lambda: (screen.__class__.enter(screen), tui.exit())
    tui.run()
    assert screen.entered == 1 and screen.left == 1


def test_run_brackets_enter_and_leave_on_every_exit_path():
    async def returns(app: TUI) -> None:
        app.add(Text("hi"))

    async def stops(app: TUI) -> None:
        app.add(Text("hi"))
        app.exit()

    async def raises(app: TUI) -> None:
        app.add(Text("hi"))
        raise ValueError("boom")

    async def interrupts(app: TUI) -> None:
        app.add(Text("hi"))
        raise KeyboardInterrupt

    async def run_one(body) -> TUI:
        tui = headless_tui(80, 6)
        if body is raises:
            with pytest.raises(ValueError, match="boom"):
                await tui.run_session(body)
        else:
            await tui.run_session(body)
        return tui

    for body in (returns, stops, raises, interrupts):
        tui = asyncio.run(run_one(body))
        output = tui.screen.output
        assert output.find(enter_alt_screen()) < output.find(leave_alt_screen())
        assert output.endswith(leave_alt_screen())


async def test_entering_a_session_repaints_a_frame_painted_before_it():
    screen = RecordingScreen(20, 3, live=True)
    tui = TUI(screen=screen, keys=ScriptedEvents(()), interactive=True)
    tui.add(Rows("hello"))
    tui.paint()
    screen.delta()

    async def body(app: TUI) -> None:
        app.paint()

    await tui.run_session(body)
    assert screen.entered == 1
    assert "hello" in screen.delta()


async def test_a_frame_mutation_after_a_session_does_not_raise():
    tui = headless_tui()

    async def body(app: TUI) -> None:
        app.exit()

    await tui.run_session(body)
    tui.frame.remove_overlay(tui.frame.overlays[0])
    tui.paint()
    assert tui.rows


async def test_the_run_attaches_and_closes_a_raw_source_when_interactive():
    tui = TUI(screen=HeadlessScreen(80, 6), interactive=True)
    seen: list[object] = []

    async def body(app: TUI) -> None:
        seen.append(app.keys)

    await tui.run_session(body)
    source = seen[0]
    assert source is not None
    assert await source.read() is None
    assert tui.keys is None


# -- non-live dump and snapshot ----------------------------------------------


def _piped_tui() -> tuple[TUI, io.StringIO]:
    stream = io.StringIO()
    return TUI(screen=TerminalScreen(stream)), stream


async def test_a_non_live_run_stays_silent_and_dumps_plain_text():
    tui, stream = _piped_tui()
    seen: list[str] = []

    async def body(app: TUI) -> None:
        app.add(Text("hello"))
        app.add(Text("world"))
        seen.append(stream.getvalue())

    await tui.run_session(body)
    assert seen == [""]
    assert stream.getvalue() == "hello\nworld\n"
    assert enter_alt_screen() not in stream.getvalue()


async def test_a_non_live_dump_puts_the_pinned_footer_last():
    tui, stream = _piped_tui()

    async def body(app: TUI) -> None:
        app.add(Text("body"))
        app.add(Text("footer"), pin="bottom")

    await tui.run_session(body)
    lines = stream.getvalue().splitlines()
    assert lines[0] == "body" and lines[-1] == "footer"


async def test_a_non_live_dump_degrades_on_a_stream_that_cannot_carry_the_frame():
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    tui = TUI(screen=TerminalScreen(stream))
    tui.add(Rows("\u2588 block"))

    async def body(app: TUI) -> None:
        app.paint()

    await tui.run_session(body)
    written = stream.buffer.getvalue().decode("cp1252")
    assert "block" in written
    assert "\u2588" not in written


def test_snapshot_renders_one_stanza_per_block():
    tui = headless_tui(80, 24)
    tui.add(Text("first\nsecond"))
    footer = tui.add(Text("foot"), pin="bottom")
    footer.seal()
    text = snapshot(tui)
    assert text.startswith("[b0 | open]\n  |first\n  |second\n")
    assert "[b1 | sealed,bottom]" in text
    assert text.splitlines()[-1].startswith("  |")


# -- protocol surface --------------------------------------------------------


def test_set_title_writes_the_osc2_bytes_on_a_non_live_screen():
    tui, stream = _piped_tui()
    tui.set_title("hello \u00b7 world")
    assert stream.getvalue() == "\x1b]2;hello \u00b7 world\x07"


def test_set_cursor_shape_writes_decscusr_and_an_unknown_shape_raises():
    tui = TUI(screen=HeadlessScreen(20, 2), interactive=False)
    tui.set_cursor_shape("beam")
    assert tui.screen.output == "\x1b[6 q"
    with pytest.raises(KeyError):
        tui.set_cursor_shape("bar")
    assert tui.screen.output == "\x1b[6 q"


# -- dock --------------------------------------------------------------------


def test_the_bottom_dock_reserves_rows_beneath_the_pane_area():
    from motui.kernel import Document

    document = Document()
    document.add(Rows("the dock"), pin="bottom")
    tui = headless_tui(40, 6)
    dock = tui.dock(Viewport(document))
    assert tui.frame.dock("bottom") is dock and dock.id == "pane-1"
    tui.add(Rows("transcript"))
    tui.paint()
    assert rows(tui) == ["transcript", "", "", "", "", "the dock"]
    assert tui.frame.panes[0].rect == Rect(0, 0, 40, 5)
    assert dock.rect == Rect(0, 5, 40, 1)
    assert tui.frame.panes == (tui.frame.panes[0],)

    hit = tui.hit(4, 5)
    assert hit is not None and hit.block is document.blocks()[0]
    assert tui.visible_range() == RowRange(0, 4)
    assert tui.dock_region() == Rect(0, 5, 40, 1)
    with pytest.raises(ValueError):
        tui.frame.focus(dock.id)
    with pytest.raises(RuntimeError):
        tui.dock(Viewport(Document()))
    with pytest.raises(ValueError):
        tui.dock(Viewport(Document()), edge="left")

    assert tui.undock() is dock
    tui.paint()
    assert rows(tui) == ["transcript"] + [""] * 5


def test_top_and_bottom_docks_compose_and_an_empty_dock_keeps_no_rows():
    from motui.kernel import Document

    top_document = Document()
    top_document.add(Rows("top one", "top two"))
    bottom_document = Document()
    bottom_document.add(Rows("bottom"))
    tui = headless_tui(20, 8)
    top = tui.dock(Viewport(top_document), edge="top")
    bottom = tui.dock(Viewport(bottom_document), edge="bottom", size=1)
    tui.add(Rows("body"))
    tui.paint()
    assert rows(tui) == [
        "top one",
        "top two",
        "body",
        "",
        "",
        "",
        "",
        "bottom",
    ]
    assert tui.frame.panes[0].rect == Rect(0, 2, 20, 5)
    assert top.rect == Rect(0, 0, 20, 2) and bottom.rect == Rect(0, 7, 20, 1)
    assert tui.visible_range() == RowRange(2, 6)
    assert tui.visible_range("primary") == RowRange(2, 6)

    empty_tui = headless_tui(20, 6)
    empty_tui.add(Rows("body"))
    empty = empty_tui.dock(Viewport(Document()))
    assert empty.rect == Rect(0, 0, 0, 0)
    empty_tui.paint()
    assert rows(empty_tui) == ["body"] + [""] * 5


async def test_a_wheel_over_a_dock_scrolls_the_focused_pane():
    from motui.kernel import Document

    document = Document()
    document.add(Rows("dock"), pin="bottom")
    tui = headless_tui(40, 6, script=[wheel(4, 5, "up"), None])
    tui.dock(Viewport(document))
    tui.add(Rows(*many(40)))
    tui.paint()
    before = tui.viewport.offset
    assert await tui.read_event() is None
    assert tui.viewport.offset == before - 3


# -- pump --------------------------------------------------------------------


def test_the_pump_paints_on_the_throttle_and_runs_scheduled_callbacks():
    tui = headless_tui()
    clock = Clock(1000.0).install(tui)
    assert tui.tick(clock()) is None
    painted = len(tui.screen.output)

    tui.add(Text("x"))
    assert tui.tick(clock()) == pytest.approx(tui.throttle)
    assert len(tui.screen.output) == painted

    clock.advance(0.05)
    assert tui.tick(clock()) is None
    assert len(tui.screen.output) > painted

    block = tui.add(Text(""))
    calls: list[int] = []

    def grow() -> None:
        calls.append(1)
        block.component.text += "x"
        tui.refresh()

    handle = tui.every(0.010, grow)
    painted = len(tui.screen.output)
    clock.advance(0.010)
    assert tui.tick(clock()) == pytest.approx(0.010)
    assert calls == [1]
    assert len(tui.screen.output) == painted  # the throttle has not elapsed

    clock.advance(0.05)
    tui.tick(clock())
    assert len(tui.screen.output) > painted
    handle.cancel()


def test_every_runs_on_schedule_and_can_be_cancelled():
    tui = headless_tui()
    clock = Clock(1000.0).install(tui)
    tui.tick(clock())

    calls: list[int] = []
    handle = tui.every(0.5, lambda: calls.append(1))
    assert tui.tick(clock()) == pytest.approx(0.5)
    clock.advance(0.5)
    assert tui.tick(clock()) == pytest.approx(0.5)
    assert calls == [1]

    handle.cancel()
    assert handle.cancelled is True
    clock.advance(5.0)
    assert tui.tick(clock()) is None
    assert calls == [1]


def test_a_direct_frame_split_is_painted_by_the_pump():
    tui = headless_tui(40, 6)
    clock = Clock(1000.0).install(tui)
    tui.add(Rows("left"))
    assert tui.tick(clock()) is None
    painted = len(tui.screen.output)

    tui.frame.pane("primary").split("vertical")
    clock.advance(0.05)
    tui.tick(clock())
    assert len(tui.screen.output) > painted
    assert [pane.id for pane in tui.frame.panes] == ["primary", "pane-1"]
