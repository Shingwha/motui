"""SelectionGesture: drag ranges, copy-on-select, auto-scroll and click counts."""

from __future__ import annotations

import base64
import re

from motui.interaction import SelectionGesture, copy_on_select
from motui.core import Selection
from motui.core.events import KeyEvent, MouseEvent, PasteEvent
from tests.testing import (
    Clock,
    Rows,
    headless_tui,
    many,
    marked,
    motion,
    press,
    release,
    tick,
    wheel,
)

_OSC52 = re.compile(r"\x1b\]52;c;([A-Za-z0-9+/=]*)\x07")


def osc52(output: str) -> list[str]:
    """Every clipboard payload the stream carries, base64-decoded."""
    return [base64.b64decode(match).decode() for match in _OSC52.findall(output)]


def drive(rows: list[str], *, on_end=copy_on_select, **knobs):
    """A painted one-block document, a gesture, and its finished selections."""
    ends: list[Selection] = []

    def collect(app, selection: Selection) -> None:
        ends.append(selection)
        if on_end is not None:
            on_end(app, selection)

    tui = headless_tui(80, 8)
    tui.add(Rows(*rows))
    clock = Clock(1000.0).install(tui)
    tui.paint()
    gesture = SelectionGesture(tui, on_end=collect, **knobs)
    return tui, gesture, clock, ends


def edge_drag(body: int = 200, *, height: int = 10, scroll_up: int = 20, **knobs):
    """A long document scrolled up, a gesture over it, and the clock seam."""
    ends: list[Selection] = []
    tui = headless_tui(80, height)
    tui.add(Rows(*many(body)))
    clock = Clock(1000.0).install(tui)
    tui.paint()
    tui.scroll_up(scroll_up)
    tui.paint()
    gesture = SelectionGesture(
        tui, on_end=lambda app, selection: ends.append(selection), **knobs
    )
    return tui, gesture, clock, ends


# -- press, drag, release ----------------------------------------------------


def test_a_drag_extends_the_head_and_the_release_finalizes_once():
    tui, gesture, _, ends = drive(["alpha", "beta", "gamma"])
    assert gesture.handle(press(2, 0)) is True
    assert gesture.handle(motion(4, 2, "left")) is True
    assert gesture.handle(release(4, 2)) is True
    expected = Selection.between(("b0", 0, 2), ("b0", 2, 4))
    assert tui.selection == expected
    assert ends == [expected]


def test_a_drag_across_blocks_lands_the_head_in_the_next_block():
    tui = headless_tui(80, 8)
    tui.add(Rows("alpha"))
    tui.add(Rows("beta"))
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(
        tui, on_end=lambda app, selection: ends.append(selection)
    )
    gesture.handle(press(1, 0))
    gesture.handle(motion(2, 1, "left"))
    gesture.handle(release(2, 1))
    expected = Selection.between(("b0", 0, 1), ("b1", 0, 2))
    assert tui.selection == expected
    assert ends == [expected]


def test_the_default_on_end_copies_the_extracted_range_as_osc52():
    tui, gesture, _, _ = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2, "left"))
    gesture.handle(release(4, 2))
    assert osc52(tui.screen.output) == ["pha\nbeta\ngamm"]


def test_on_end_none_selects_without_an_effect():
    tui, gesture, _, ends = drive(["alpha", "beta"], on_end=None)
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 1, "left"))
    gesture.handle(release(4, 1))
    assert tui.selection == Selection.between(("b0", 0, 2), ("b0", 1, 4))
    assert osc52(tui.screen.output) == []
    assert ends == [tui.selection]


def test_a_click_clears_the_selection_and_never_fires_on_end():
    tui, gesture, _, ends = drive(["alpha", "beta", "gamma"])
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 1, 1)))
    tui.paint()
    assert marked(tui)[:2] == ["alpha", "b"]

    gesture.handle(press(0, 0))
    gesture.handle(release(0, 0))
    assert tui.selection is None
    assert ends == []
    assert osc52(tui.screen.output) == []


def test_the_highlight_stays_after_the_drag_and_yields_to_the_next_press():
    tui, gesture, _, _ = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2, "left"))
    gesture.handle(release(4, 2))
    tui.paint()
    assert marked(tui) == ["pha", "beta", "gamm", "", "", "", "", ""]

    gesture.handle(press(0, 0))
    tui.paint()
    assert not any(marked(tui))


def test_a_reflow_mid_drag_ends_the_drag_cleanly():
    tui, gesture, _, ends = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2, "left"))
    tui.screen.width = 40
    tui.paint()
    assert tui.selection is None
    gesture.handle(motion(4, 2, "left"))
    gesture.handle(release(4, 2))
    assert ends == []


def test_detach_drops_the_in_flight_drag():
    tui, gesture, _, ends = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2, "left"))
    gesture.detach()
    assert gesture.handle(release(4, 2)) is True
    assert ends == []


def test_a_drag_to_the_bottom_edge_scrolls_and_extends_the_head():
    tui, gesture, clock, _ = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    assert tui.selection.anchors == (("b0", offset + 9, 0),) * 2
    gesture.handle(motion(0, 9, "left"))
    tick(tui, clock, 10)
    assert tui.viewport.offset == offset + 20
    assert tui.selection.anchors[1] == ("b0", offset + 29, 0)
    tui.paint()
    assert marked(tui) == [f"r{row}" for row in range(190, 199)] + [""]


def test_a_press_on_the_edge_row_arms_the_ticker_without_a_motion():
    tui, gesture, clock, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    tick(tui, clock, 10)
    assert tui.viewport.offset == offset + 20
    assert tui.selection.anchors[1] == ("b0", offset + 29, 0)
    gesture.handle(release(0, 9))
    assert len(ends) == 1


def test_the_ticker_stands_down_at_the_document_end():
    tui, gesture, clock, ends = edge_drag()
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9, "left"))
    tick(tui, clock, 10)
    assert tui.viewport.offset == 190
    assert tui.selection.anchors[1] == ("b0", 199, 0)

    tick(tui, clock, 5)
    assert tui.viewport.offset == 190
    assert tui.tick(clock()) is None

    assert gesture.handle(wheel(0, 9, "down")) is True
    assert tui.viewport.offset == 190
    assert tui.selection.anchors[1] == ("b0", 199, 0)

    gesture.handle(release(0, 9))
    assert ends == [Selection.between(("b0", 179, 0), ("b0", 199, 0))]


def test_a_drag_away_from_the_edge_stops_the_ticker():
    tui, gesture, clock, _ = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9, "left"))
    tick(tui, clock, 2)
    assert tui.viewport.offset == offset + 4

    gesture.handle(motion(0, 5, "left"))
    tick(tui, clock, 5)
    assert tui.viewport.offset == offset + 4
    assert tui.selection.anchors[1] == ("b0", offset + 9, 0)


def test_the_release_stops_the_ticker_and_finalizes():
    tui, gesture, clock, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9, "left"))
    tick(tui, clock, 1)
    gesture.handle(release(0, 9))
    assert ends == [Selection.between(("b0", offset + 9, 0), ("b0", offset + 11, 0))]

    tick(tui, clock, 5)
    assert tui.viewport.offset == offset + 2


def test_detach_stops_the_ticker():
    tui, gesture, clock, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9, "left"))
    tick(tui, clock, 2)
    gesture.detach()
    tick(tui, clock, 5)
    assert tui.viewport.offset == offset + 4
    assert ends == []


def test_a_reflow_mid_drag_stops_the_ticker():
    tui, gesture, clock, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9, "left"))
    tick(tui, clock, 1)
    tui.screen.width = 40
    tui.paint()
    assert tui.selection is None
    tick(tui, clock, 5)
    assert tui.viewport.offset == offset + 2
    assert ends == []


def test_the_top_edge_scrolls_back_and_extends_upward():
    tui, gesture, clock, _ = edge_drag()
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 0, "left"))
    assert tui.selection.anchors[1] == ("b0", 170, 0)
    tick(tui, clock, 10)
    assert tui.viewport.offset == 150
    assert tui.selection.anchors == (("b0", 179, 0), ("b0", 150, 0))


def test_holding_the_other_edge_flips_the_scroll_direction():
    tui, gesture, clock, _ = edge_drag()
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9, "left"))
    tick(tui, clock, 2)
    down = tui.viewport.offset
    gesture.handle(motion(0, 0, "left"))
    tick(tui, clock, 1)
    assert tui.viewport.offset == down - 2


def test_the_head_walk_crosses_a_block_boundary():
    tui = headless_tui(80, 4)
    tui.add(Rows(*many(100)))
    tui.add(Rows(*many(100)))
    clock = Clock(1000.0).install(tui)
    tui.paint()
    tui.scroll_up(100)
    tui.paint()
    gesture = SelectionGesture(tui, on_end=None)
    gesture.handle(press(0, 3))
    assert tui.selection.anchors == (("b0", 99, 0), ("b0", 99, 0))
    gesture.handle(motion(0, 3, "left"))
    tick(tui, clock, 1)
    assert tui.viewport.offset == 98
    assert tui.selection.anchors == (("b0", 99, 0), ("b1", 1, 0))


def test_a_wheel_during_a_drag_co_extends_the_head():
    tui, gesture, _, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 5))
    assert gesture.handle(wheel(0, 5, "down")) is True
    assert tui.viewport.offset == offset + 3
    assert tui.selection.anchors == (("b0", 175, 0), ("b0", 178, 0))
    assert gesture.handle(wheel(0, 5, "up")) is True
    assert tui.viewport.offset == offset
    assert tui.selection.anchors == (("b0", 175, 0), ("b0", 175, 0))
    assert ends == []


def test_a_second_press_at_the_same_cell_selects_the_word():
    tui, gesture, clock, ends = drive(["hello world", "second row"])
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    assert tui.selection is None and ends == []

    clock.advance(0.2)
    assert gesture.handle(press(1, 0)) is True
    word = Selection.between(("b0", 0, 0), ("b0", 0, 5))
    assert tui.selection == word
    assert ends == [word]
    assert osc52(tui.screen.output) == ["hello"]

    assert gesture.handle(release(1, 0)) is True
    assert tui.selection == word and ends == [word]
    tui.paint()
    assert marked(tui)[0] == "hello"

    gesture.handle(press(3, 0))
    tui.paint()
    assert not any(marked(tui))


def test_a_third_press_selects_the_row():
    tui, gesture, clock, ends = drive(["hello world", "second row"])
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    clock.advance(0.2)
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    clock.advance(0.2)
    assert gesture.handle(press(1, 0)) is True
    word = Selection.between(("b0", 0, 0), ("b0", 0, 5))
    line = Selection.between(("b0", 0, 0), ("b0", 0, 11))
    assert tui.selection == line
    assert ends == [word, line]
    assert osc52(tui.screen.output) == ["hello", "hello world"]

    tui.paint()
    assert marked(tui)[:2] == ["hello world", ""]


def test_a_fourth_press_restarts_the_click_count():
    tui, gesture, clock, ends = drive(["hello world"])
    word = Selection.between(("b0", 0, 0), ("b0", 0, 5))
    line = Selection.between(("b0", 0, 0), ("b0", 0, 11))
    for _ in range(3):
        gesture.handle(press(1, 0))
        gesture.handle(release(1, 0))
        clock.advance(0.2)
    assert ends == [word, line]

    gesture.handle(press(1, 0))
    assert tui.selection.anchors == (("b0", 0, 1),) * 2
    gesture.handle(release(1, 0))
    clock.advance(0.2)
    gesture.handle(press(1, 0))
    assert tui.selection == word
    assert ends == [word, line, word]


def test_a_word_select_never_arms_the_ticker():
    tui = headless_tui(80, 10)
    tui.add(Rows(*many(200)))
    clock = Clock(1000.0).install(tui)
    tui.paint()
    tui.scroll_up(20)
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(
        tui, on_end=lambda app, selection: ends.append(selection)
    )
    offset = tui.viewport.offset
    gesture.handle(press(1, 9))
    gesture.handle(release(1, 9))
    clock.advance(0.2)
    gesture.handle(press(1, 9))
    assert ends == [Selection.between(("b0", 179, 0), ("b0", 179, 4))]
    tick(tui, clock, 5)
    assert tui.viewport.offset == offset


def test_a_press_anchors_the_cell_the_hit_resolves():
    tui, gesture, _, _ = drive(["alpha", "beta", "gamma"])
    for x, y, expected in (
        (0, 0, ("b0", 0, 0)),
        (7, 0, ("b0", 0, 7)),
        (79, 1, ("b0", 1, 79)),
        (0, 2, ("b0", 2, 0)),
    ):
        gesture.handle(press(x, y))
        assert tui.selection.anchors == (expected, expected)


def test_either_drag_direction_covers_the_same_range():
    for start, end in (((2, 0), (4, 2)), ((4, 2), (2, 0))):
        tui, gesture, _, ends = drive(["alpha", "beta", "gamma"])
        gesture.handle(press(*start))
        gesture.handle(motion(*end, "left"))
        gesture.handle(release(*end))
        assert tui.selection == Selection.between(
            ("b0", start[1], start[0]), ("b0", end[1], end[0])
        )
        assert len(ends) == 1


def test_handle_passes_everything_the_gesture_does_not_own():
    tui, gesture, _, _ = drive(["alpha"])
    for event in (
        KeyEvent("a", "a"),
        PasteEvent("pasted"),
        MouseEvent("middle", x=0, y=0),
        MouseEvent("right", x=0, y=0),
        wheel(0, 0, "down"),
        motion(0, 0),
        MouseEvent("middle", x=0, y=0, kind="release"),
        MouseEvent("left", x=0, y=0, kind="other"),
    ):
        assert gesture.handle(event) is False
    assert tui.selection is None


def test_the_word_run_is_the_maximal_non_whitespace_stretch():
    cases = (
        ("hello world", 1, (0, 5)),
        ("hello world", 8, (6, 11)),
        ("hello world", 5, None),
        ("\u4e2d\u6587 abc", 0, (0, 4)),
        ("\u4e2d\u6587 abc", 4, None),
        ("hi", 10, (0, 2)),
    )
    for text, col, expected in cases:
        tui, gesture, clock, ends = drive([text])
        gesture.handle(press(col, 0))
        gesture.handle(release(col, 0))
        clock.advance(0.2)
        gesture.handle(press(col, 0))
        if expected is None:
            assert tui.selection.anchors == (("b0", 0, col),) * 2
            assert ends == []
        else:
            word = Selection.between(("b0", 0, expected[0]), ("b0", 0, expected[1]))
            assert tui.selection == word
            assert ends == [word]


def test_the_scroll_knobs_set_the_tick_size_and_period():
    for scroll_rows, scroll_tick in ((1, 0.04), (2, 0.05), (5, 0.2)):
        tui, gesture, clock, _ = edge_drag(
            scroll_rows=scroll_rows, scroll_tick=scroll_tick
        )
        offset = tui.viewport.offset
        gesture.handle(press(0, 9))
        gesture.handle(motion(0, 9, "left"))
        clock.advance(scroll_tick / 2)
        tui.tick(clock())
        assert tui.viewport.offset == offset
        tick(tui, clock, 3, scroll_tick)
        assert tui.viewport.offset == offset + 3 * scroll_rows
