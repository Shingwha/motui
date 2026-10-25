"""The driver's public contract: document facade, scroll, events, docks, lifecycle."""

from __future__ import annotations

import asyncio
import io

import pytest

from motui.app import Runtime
from motui.app.runtime import Timer
from motui.kernel import DEFAULT_THEME, Rect, RowSpan
from motui.kernel.document import Placement, Sizing
from motui.kernel.geom import Axis
from motui.widgets.text import Text
from motui.terminal import HeadlessScreen, Terminal, TerminalOptions
from motui.terminal.ansi import copy_clipboard, enter_alt_screen, leave_alt_screen
from motui.terminal.screen import TerminalScreen
from tests.testing import (
    Clock,
    RecordingScreen,
    Rows,
    ScriptedEvents,
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
    pinned = tui.add(Text("footer"), placement=Placement.BOTTOM)
    assert first.id == "b0"
    assert tui.document.get(pinned.id).placement is Placement.BOTTOM
    assert tui.get("b0").widget.text == "one"

    system = tui.system("hello")
    component = tui.get(system.id).widget
    assert isinstance(component, Text)
    assert component.text == "hello"
    assert component.style == DEFAULT_THEME.text.muted

    assert tui.remove("b0").widget.text == "one"
    assert len(tui.document) == 2
    with pytest.raises(KeyError):
        tui.get("b0")


def test_fill_replaces_the_pane_and_paints_the_remaining_height():
    tui = headless_tui(10, 5)
    tui.add(Rows("head"))
    section = tui.fill(Rows("game"))
    assert section.sizing is Sizing.FILL
    assert section.widget is tui.document.get(section.id).widget
    assert tui.document.fills() == (section,)
    assert [block.id for block in tui.document.blocks()] == [section.id]
    tui.paint()
    assert rows(tui) == ["game", "", "", "", ""]


def test_fill_keeps_the_flow_the_document_already_holds():
    tui = headless_tui(10, 4)
    tui.add(Rows("head"))
    tui.add(Rows("game"), sizing=Sizing.FILL)
    tui.paint()
    assert rows(tui) == ["head", "game", "", ""]


def test_add_forwards_placement():
    tui = headless_tui(10, 4)
    tui.add(Rows("head"), placement=Placement.TOP)
    tui.add(Rows("body"))
    tui.paint()
    assert rows(tui) == ["head", "body", "", ""]
    assert tui.document.get("b0").placement is Placement.TOP


def test_add_and_system_target_the_main_document_not_focus():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X)
    tui.frame.focus(right)

    assert tui.add(Rows("body")).id == "b0"
    assert tui.system("note").id == "b1"
    assert [block.id for block in left.document.blocks()] == ["b0", "b1"]
    assert right.document.blocks() == ()

    assert tui.add(Rows("preview"), pane=right.id).id == "b2"
    assert [block.id for block in right.document.blocks()] == ["b2"]


def test_reveal_follows_the_block_owner_not_the_focused_pane():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X)
    block = tui.add(Rows(*many(20)), pane=right.id)
    tui.frame.focus(left)
    right.viewport.scroll_to(0)
    tui.paint()
    before = tui.viewport.offset

    assert tui.reveal(block.id, 19) is True
    assert right.viewport.offset > 0
    assert tui.viewport.offset == before


def test_duplicate_block_ids_are_rejected_across_the_frame():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X)
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
    left, right = tui.split(Axis.X)
    left.document.add(Rows("transcript"))
    right.document.add(Rows("preview"))
    assert right.document.blocks()[0].id == "b0"
    block = tui.add(Rows("child body"), pane=right.id)
    assert block.id == "b1"
    assert tui.pane(right.id) is right
    component = tui.get(block.id).widget
    assert component is right.document.get(block.id).widget
    assert tui.remove(block.id) is not None
    assert [held.id for held in right.document.blocks()] == ["b0"]


def test_pane_lookup_raises_for_an_unknown_id():
    tui = headless_tui()
    with pytest.raises(KeyError):
        tui.pane("nowhere")


# -- split and pane surface --------------------------------------------------


def test_split_keeps_the_document_in_the_first_child():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X, weights=(2, 1))
    left.document.add(Rows("transcript"))
    right.document.add(Rows("preview"))
    assert [pane.id for pane in tui.frame.panes] == ["primary", "pane-1"]
    assert left.document is tui.document
    assert right.document is not tui.document
    assert tui.frame.focused_pane is left
    tui.paint()
    assert rows(tui)[0].startswith("transcript")
    assert left.rect.width == 26 and right.rect.x == 26


def test_split_axes_divide_width_and_height():
    side_by_side = headless_tui(40, 6)
    left, right = side_by_side.split(Axis.X, weights=(2, 1))
    assert left.rect.width == 26 and right.rect.x == 26
    assert left.rect.height == right.rect.height == 6

    stacked = headless_tui(40, 6)
    top, bottom = stacked.split(Axis.Y, weights=(1, 2))
    assert top.rect.height == 2 and bottom.rect.y == 2
    assert top.rect.width == bottom.rect.width == 40


def test_split_weights_divide_the_cells_proportionally():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X, weights=(1, 2))
    assert left.rect.width == 13 and right.rect.width == 27


def test_split_rejects_a_legacy_string():
    legacy = "vertical"
    with pytest.raises(ValueError, match="split axis"):
        headless_tui(40, 6).split(legacy)  # type: ignore[arg-type]


def test_split_takes_an_explicit_pane_and_moves_no_focus():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X)
    top, bottom = tui.split(Axis.Y, pane=right.id)
    assert top.id == right.id and top.document is right.document
    assert bottom.document is not right.document
    assert tui.frame.focused_pane is left


def test_pane_ids_are_monotonic_and_never_reused():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X)
    assert (left.id, right.id) == ("primary", "pane-1")
    right.close()
    first, second = tui.split(Axis.X, pane="primary")
    assert first.id == "primary" and second.id == "pane-2"


def test_closing_a_child_returns_its_cells_and_the_focus():
    tui = headless_tui(40, 6)
    left, right = tui.split(Axis.X)
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


def _three_blocks(tui: Runtime) -> None:
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
    tui.add(Rows("status"), id="status", placement=Placement.BOTTOM)
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


async def test_read_event_returns_wheel_and_page_events_untouched():
    tui = headless_tui(
        80,
        10,
        script=[wheel(0, 0, "up"), key("page_up"), key("a", "a"), paste("p"), None],
    )
    tui.add(Rows(*many(30)))
    tui.paint()
    before = rows(tui)

    assert await tui.read_event() == wheel(0, 0, "up")
    assert await tui.read_event() == key("page_up")
    assert await tui.read_event() == key("a", "a")
    assert await tui.read_event() == paste("p")
    tui.paint()
    assert rows(tui) == before  # the raw read moved nothing
    assert await tui.read_event() is None


async def test_a_button_press_comes_back_for_the_host_to_hit_test():
    tui = headless_tui(80, 6, script=[press(0, 0), None])
    body = tui.add(Rows(*many(10)))
    tui.paint()
    event = await tui.read_event()
    assert event == press(0, 0)
    hit = tui.hit(event.x, event.y)
    assert hit is not None and hit.block.id == body.id and hit.row == 4 and hit.col == 0


def test_read_event_answers_none_without_a_source_or_on_a_non_live_screen():
    assert asyncio.run(
        Runtime(Terminal(TerminalOptions(screen=HeadlessScreen()))).read_event()
    ) is None
    tui = Runtime(
        Terminal(
            TerminalOptions(
                screen=TerminalScreen(io.StringIO()),
                input=ScriptedEvents([key("a", "a")]),
            )
        )
    )
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
    tui = Runtime(
        Terminal(TerminalOptions(screen=HeadlessScreen(), input=source)),
        interactive=False,
    )
    pending = asyncio.create_task(tui.read_event())
    tui.exit()
    assert await asyncio.wait_for(pending, 1) is None
    assert not source.closed  # closing the source belongs to teardown


# -- terminal wiring ---------------------------------------------------------


async def test_a_terminal_driver_reads_through_the_terminal_source():
    screen = HeadlessScreen(20, 4)
    source = ScriptedEvents([key("a", "a"), None])
    terminal = Terminal(TerminalOptions(screen=screen, input=source))
    tui = Runtime(terminal, interactive=False)

    assert tui.screen is screen
    assert tui.keys is source
    assert await tui.read_event() == key("a", "a")
    assert await tui.read_event() is None


def test_a_terminal_driver_on_a_non_live_screen_reads_nothing():
    terminal = Terminal(
        TerminalOptions(stream=io.StringIO(), input=ScriptedEvents([key("a", "a")]))
    )
    tui = Runtime(terminal, interactive=False)
    assert asyncio.run(tui.read_event()) is None


async def test_a_terminal_run_brackets_the_session_through_the_terminal():
    screen = HeadlessScreen(20, 3)
    tui = Runtime(
        Terminal(TerminalOptions(screen=screen)), interactive=False
    )

    async def body(app: Runtime) -> None:
        app.workspace.add(Text("hi"))

    await tui.run_session(body)
    output = screen.output
    assert output.find(enter_alt_screen()) >= 0
    assert output.find(leave_alt_screen()) > output.find(enter_alt_screen())


async def test_a_non_live_terminal_run_stays_silent_and_dumps_plain_text():
    stream = io.StringIO()
    tui = Runtime(
        Terminal(TerminalOptions(stream=stream)), interactive=False
    )
    seen: list[str] = []

    async def body(app: Runtime) -> None:
        app.workspace.add(Text("hello"))
        seen.append(stream.getvalue())

    await tui.run_session(body)
    assert seen == [""]
    assert stream.getvalue() == "hello\n"
    assert enter_alt_screen() not in stream.getvalue()


def test_the_runtime_takes_the_terminal_as_its_only_endpoint():
    chosen = HeadlessScreen(20, 5)
    source = ScriptedEvents(())
    tui = Runtime(
        Terminal(TerminalOptions(screen=chosen, input=source)),
        interactive=False,
    )
    assert tui.screen is chosen
    assert tui.keys is source
    with pytest.raises(TypeError):
        Runtime(**{"screen": chosen})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Runtime(
            Terminal(TerminalOptions(screen=chosen)), **{"keys": source}  # type: ignore[arg-type]
        )


def test_a_terminal_driver_copies_through_the_terminal_clipboard():
    screen = HeadlessScreen()
    tui = Runtime(Terminal(TerminalOptions(screen=screen)), interactive=False)
    assert tui.copy_to_clipboard("copied") is True
    assert screen.output == copy_clipboard("copied")


# -- lifecycle ---------------------------------------------------------------


async def test_exit_ends_run_async_and_a_second_session_starts_clean():
    tui = headless_tui(40, 3)

    asyncio.get_running_loop().call_soon(tui.exit)
    await tui.run_async()

    async def body(app: Runtime) -> None:
        app.workspace.add(Text("second run"))
        app.exit()

    await tui.run_session(body)
    tui.paint()
    assert rows(tui)[0] == "second run"


def test_run_is_a_synchronous_entry_that_returns_when_the_session_exits():
    screen = RecordingScreen(20, 3, live=True)
    tui = Runtime(
        Terminal(TerminalOptions(screen=screen, input=ScriptedEvents(()))),
        interactive=False,
    )
    tui.workspace.add(Text("hi"))
    # A host may end the session from inside the screen bracket; the sync
    # entry must still return once the session is over.
    screen.enter = lambda: (screen.__class__.enter(screen), tui.exit())
    tui.run()
    assert screen.entered == 1 and screen.left == 1


def test_run_brackets_enter_and_leave_on_every_exit_path():
    async def returns(app: Runtime) -> None:
        app.workspace.add(Text("hi"))

    async def stops(app: Runtime) -> None:
        app.workspace.add(Text("hi"))
        app.exit()

    async def raises(app: Runtime) -> None:
        app.workspace.add(Text("hi"))
        raise ValueError("boom")

    async def interrupts(app: Runtime) -> None:
        app.workspace.add(Text("hi"))
        raise KeyboardInterrupt

    async def run_one(body) -> Runtime:
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


async def test_a_frame_mutation_after_a_session_does_not_raise():
    tui = headless_tui()

    async def body(app: Runtime) -> None:
        app.exit()

    await tui.run_session(body)
    tui.frame.remove_overlay(tui.frame.overlays[0])
    tui.paint()
    assert tui.rows


def _piped_tui() -> tuple[Runtime, io.StringIO]:
    stream = io.StringIO()
    return Runtime(Terminal(TerminalOptions(screen=TerminalScreen(stream)))), stream


async def test_a_non_live_run_stays_silent_and_dumps_plain_text():
    tui, stream = _piped_tui()
    seen: list[str] = []

    async def body(app: Runtime) -> None:
        app.workspace.add(Text("hello"))
        app.workspace.add(Text("world"))
        seen.append(stream.getvalue())

    await tui.run_session(body)
    assert seen == [""]
    assert stream.getvalue() == "hello\nworld\n"
    assert enter_alt_screen() not in stream.getvalue()


async def test_a_non_live_dump_degrades_on_a_stream_that_cannot_carry_the_frame():
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    tui = Runtime(Terminal(TerminalOptions(screen=TerminalScreen(stream))))
    tui.workspace.add(Rows("\u2588 block"))

    async def body(app: Runtime) -> None:
        app.paint()

    await tui.run_session(body)
    written = stream.buffer.getvalue().decode("cp1252")
    assert "block" in written
    assert "\u2588" not in written


def test_snapshot_renders_one_stanza_per_block():
    tui = headless_tui(80, 24)
    tui.add(Text("first\nsecond"))
    tui.add(Text("foot"), placement=Placement.BOTTOM)
    text = snapshot(tui)
    assert text.startswith("[b0]\n  |first\n  |second\n")
    assert "[b1 | bottom]" in text
    assert text.splitlines()[-1].startswith("  |")


# -- protocol surface --------------------------------------------------------


def test_the_bottom_dock_reserves_rows_beneath_the_pane_area():
    tui = headless_tui(40, 6)
    dock = tui.dock(Rows("the dock"))
    assert tui.frame.dock("bottom") is dock and dock.id == "pane-1"
    tui.add(Rows("transcript"))
    tui.paint()
    assert rows(tui) == ["transcript", "", "", "", "", "the dock"]
    assert tui.frame.panes[0].rect == Rect(x=0, y=0, width=40, height=5)
    assert dock.rect == Rect(x=0, y=5, width=40, height=1)
    assert tui.frame.panes == (tui.frame.panes[0],)

    hit = tui.hit(4, 5)
    assert hit is not None and hit.block is dock.document.blocks()[0]
    assert tui.visible_range() == RowSpan(0, 4)
    assert tui.dock_region() == Rect(x=0, y=5, width=40, height=1)
    with pytest.raises(ValueError):
        tui.frame.focus(dock.id)
    with pytest.raises(RuntimeError):
        tui.dock(Rows("second"))
    with pytest.raises(ValueError):
        tui.dock(Rows("left"), placement=Placement.FLOW)

    assert tui.undock() is dock
    tui.paint()
    assert rows(tui) == ["transcript"] + [""] * 5


def test_top_and_bottom_docks_compose_and_an_empty_dock_keeps_no_rows():
    tui = headless_tui(20, 8)
    top = tui.dock(Rows("top one", "top two"), placement=Placement.TOP)
    bottom = tui.dock(Rows("bottom"), placement=Placement.BOTTOM, size=1)
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
    assert tui.frame.panes[0].rect == Rect(x=0, y=2, width=20, height=5)
    assert top.rect == Rect(x=0, y=0, width=20, height=2) and bottom.rect == Rect(x=0, y=7, width=20, height=1)
    assert tui.visible_range() == RowSpan(2, 6)
    assert tui.visible_range("primary") == RowSpan(2, 6)

    empty_tui = headless_tui(20, 6)
    empty_tui.add(Rows("body"))
    empty = empty_tui.dock(Rows())
    assert empty.rect == Rect(x=0, y=0, width=0, height=0)
    empty_tui.paint()
    assert rows(empty_tui) == ["body"] + [""] * 5


def test_dock_and_undock_accept_placements():
    tui = headless_tui(20, 6)
    top = tui.dock(Rows("top"), placement=Placement.TOP)
    bottom = tui.dock(Rows("foot"), placement=Placement.BOTTOM, size=1)

    assert tui.frame.dock("top") is top
    assert tui.frame.dock("bottom") is bottom
    assert tui.undock(Placement.BOTTOM) is bottom
    assert tui.undock(Placement.TOP) is top
    assert tui.frame.dock("top") is None and tui.frame.dock("bottom") is None

    with pytest.raises(ValueError, match="FLOW"):
        tui.dock(Rows("nope"), placement=Placement.FLOW)


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

    block = tui.document.get(tui.add(Text("")).id)
    calls: list[int] = []

    def grow() -> None:
        calls.append(1)
        block.widget.text += "x"
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


async def test_a_timer_registered_before_the_run_survives_enter():
    """A shell built before ``run_session`` keeps its animation beat."""
    tui = headless_tui()
    clock = Clock(1000.0).install(tui)
    calls: list[int] = []
    handle = tui.every(0.5, lambda: calls.append(1))

    async def body(tui: Runtime) -> None:
        clock.advance(0.5)
        tui.tick(clock())
        tui.exit()

    await tui.run_session(body)
    handle.cancel()
    assert calls == [1]


def test_a_direct_frame_split_is_painted_by_the_pump():
    tui = headless_tui(40, 6)
    clock = Clock(1000.0).install(tui)
    tui.add(Rows("left"))
    assert tui.tick(clock()) is None
    painted = len(tui.screen.output)

    tui.frame.pane("primary").split(Axis.X)
    clock.advance(0.05)
    tui.tick(clock())
    assert len(tui.screen.output) > painted
    assert [pane.id for pane in tui.frame.panes] == ["primary", "pane-1"]


# -- deadline timers ---------------------------------------------------------


def test_a_fifty_millisecond_timer_runs_nineteen_to_twenty_times_a_virtual_second():
    tui = headless_tui()
    tui._clock = lambda: 0.0
    calls: list[float] = []
    tui.every(0.05, lambda: calls.append(tui.clock()))

    tui.advance(1.0)

    assert 19 <= len(calls) <= 20
    assert calls[0] == pytest.approx(0.05)
    assert calls[-1] <= 1.0


def test_advance_replays_the_same_script_deterministically():
    def run() -> tuple[list[float], str]:
        tui = headless_tui(20, 3)
        tui._clock = lambda: 100.0
        calls: list[float] = []
        tui.every(0.05, lambda: calls.append(tui.clock()))
        tui.advance(1.3)
        return calls, tui.screen.output

    first, second = run(), run()
    assert first == second
    assert 25 <= len(first[0]) <= 26


def test_the_deadlines_do_not_drift_with_late_ticks():
    tui = headless_tui()
    tui._clock = lambda: 100.0
    timer = tui.every(0.05, lambda: None)
    assert timer.next_run == pytest.approx(100.05)

    tui._clock = lambda: 100.07
    tui.tick(100.07)
    # The deadline advanced by exactly one period, not by the late tick's time.
    assert timer.next_run == pytest.approx(100.10)


def test_skip_realigns_to_now_and_coalesce_preserves_the_phase():
    tui = headless_tui()
    tui._clock = lambda: 10.0
    skip_calls: list[float] = []
    skip = tui.every(0.05, lambda: skip_calls.append(tui.clock()), catch_up="skip")
    coalesce_calls: list[float] = []
    coalesce = tui.every(
        0.05, lambda: coalesce_calls.append(tui.clock()), catch_up="coalesce"
    )

    tui._clock = lambda: 10.17
    tui.tick(10.17)

    assert skip_calls == coalesce_calls == [10.17]
    assert skip.next_run == pytest.approx(10.22)  # now + period
    assert coalesce.next_run == pytest.approx(10.20)  # whole periods only


def test_cancelling_a_timer_stops_every_future_run():
    tui = headless_tui()
    tui._clock = lambda: 0.0
    calls: list[int] = []
    timer = tui.every(0.05, lambda: calls.append(1))
    timer.cancel()

    tui.advance(1.0)

    assert calls == []
    assert timer.cancelled is True


def test_timer_is_its_own_cancellable_handle_and_validates_its_configuration():
    tui = headless_tui()
    timer = tui.every(0.05, lambda: None)
    assert isinstance(timer, Timer)
    assert timer.cancelled is False
    with pytest.raises(ValueError, match="period must be positive"):
        tui.every(0.0, lambda: None)
    with pytest.raises(ValueError, match="catch_up"):
        tui.every(0.05, lambda: None, catch_up="later")
    with pytest.raises(ValueError, match="rate must be positive"):
        tui.animation(0.0, lambda: None)


def test_animation_schedules_one_draw_per_frame():
    tui = headless_tui()
    tui._clock = lambda: 0.0
    draws: list[int] = []
    timer = tui.animation(20, lambda: draws.append(1))
    assert timer.period == pytest.approx(0.05)

    tui.advance(1.0)

    assert 19 <= len(draws) <= 20


def test_invalidate_and_paint_now_are_the_20_names():
    tui = headless_tui(20, 3)
    clock = Clock(1000.0).install(tui)
    tui.add(Text("x"))
    tui.paint_now()
    painted = len(tui.screen.output)
    assert painted > 0

    tui.add(Text("y"))
    tui.invalidate()
    tui.tick(clock())
    assert len(tui.screen.output) == painted  # still inside the throttle
    clock.advance(tui.throttle + 0.01)
    tui.tick(clock())
    assert len(tui.screen.output) > painted
