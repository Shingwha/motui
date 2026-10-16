"""Tests for mocode_tui.gesture: the gesture, the policy tier.

The gesture is driven headlessly against a real :class:`~mocode_tui.app.TUI`:
a document of plain rows on a recording screen, ``press``/``motion``/``release``
:class:`~mocode_tui.core.events.MouseEvent` reports injected through
``handle``, and the documented ``clock`` seam for the timed behaviors.  The
helpers here are the mouse-report shorthands and an OSC 52 payload extractor
-- the OSC 52 bytes are decoded back, never matched against a re-derivation.
"""

import base64
import re

import pytest

from _doubles import Rows, many

from mocode_tui.core.events import Key, MouseEvent, Paste
from mocode_tui.core.selection import Selection
from mocode_tui.gesture import SelectionGesture, copy_on_select
from mocode_tui.testing import headless_tui

# --- helpers ------------------------------------------------------------------


def press(x: int, y: int) -> MouseEvent:
    """A left-button press report at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y)


def motion(x: int, y: int) -> MouseEvent:
    """A motion report with the left button held at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y, kind="motion")


def release(x: int, y: int) -> MouseEvent:
    """A left-button release report at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y, kind="release")


_OSC52 = re.compile(r"\x1b\]52;c;([A-Za-z0-9+/=]*)\x07")


def osc52(output: str) -> list[str]:
    """The clipboard payloads a stream carries, base64-decoded."""
    return [base64.b64decode(match).decode() for match in _OSC52.findall(output)]


def marked(tui) -> list[str]:
    """Per row: the text of the pieces the overlay marked, ``""`` when none.

    A piece counts as marked when it carries SELECTION's attributes --
    ``reverse`` -- which no default style in this file carries.
    """
    return [
        "".join(seg.text for seg in row.segments if seg.style.reverse)
        for row in tui.rows
    ]


def drive(rows: list[str], *, on_end=copy_on_select):
    """A laid-out one-block document, a gesture over it, and its ``ends`` log.

    Returns ``(tui, gesture, ends)``: every finished selection is appended to
    ``ends`` and then handed to ``on_end`` -- the default shipped policy
    included, so the OSC 52 write and the log both happen.  ``on_end=None``
    logs without an effect.
    """
    ends: list[Selection] = []

    def end(app, selection: Selection) -> None:
        ends.append(selection)
        if on_end is not None:
            on_end(app, selection)

    tui = headless_tui(80, 8)
    tui.add(Rows(*rows))
    tui.paint()
    gesture = SelectionGesture(tui, on_end=end)
    return tui, gesture, ends


#: The default ``scroll_tick``: one autoscroll tick of the clock.
TICK = 0.05


def edge_drag(body: int = 200, *, height: int = 10, scroll_up: int = 20, **knobs):
    """A 200-row document scrolled up, a gesture over it, and the clock seam.

    Returns ``(tui, gesture, now, ends)`` with the documented ``clock`` seam
    installed *before the first frame*, so the pump paints on the injected
    clock -- a ``_last_paint`` left on the real clock would freeze the
    throttle and leave the hit test reading the previous layout.  The caller
    advances ``now[0]`` by one ``scroll_tick`` and calls ``tui.tick`` to fire
    one autoscroll tick.  ``height`` is the screen and ``scroll_up`` how far
    the window sits from the bottom, so the drag has room to run; ``knobs``
    forward the gesture's scroll settings.
    """
    ends: list[Selection] = []
    tui = headless_tui(80, height)
    tui.add(Rows(*many(body)))
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.paint()
    tui.scroll_up(scroll_up)
    tui.paint()
    gesture = SelectionGesture(tui, on_end=lambda app, sel: ends.append(sel), **knobs)
    return tui, gesture, now, ends


def tick(tui, now: list[float], count: int = 1, seconds: float = TICK) -> None:
    """Fire the pump ``count`` times, ``seconds`` of clock apart (``tick`` seam)."""
    for _ in range(count):
        now[0] += seconds
        tui.tick(now[0])


# --- T1: press / drag / release / clear ----------------------------------------


def test_a_press_anchors_the_reported_cell():
    tui, gesture, _ = drive(["alpha", "beta", "gamma"])
    assert gesture.handle(press(0, 0)) is True
    assert tui.selection is not None
    assert tui.selection.anchors == (("b0", 0, 0), ("b0", 0, 0))


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (0, 0, ("b0", 0, 0)),
        (7, 0, ("b0", 0, 7)),  # past the row's text: columns clamp lazily (D8)
        (79, 1, ("b0", 1, 79)),  # the screen edge, where the hit test clamps
        (0, 2, ("b0", 2, 0)),
    ],
)
def test_a_press_anchors_the_cell_the_hit_test_resolves(
    x: int, y: int, expected: tuple[str, int, int]
):
    tui, gesture, _ = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(x, y))
    assert tui.selection is not None
    assert tui.selection.anchors == (expected, expected)


def test_a_drag_extends_the_head_and_the_release_finalizes_once():
    tui, gesture, ends = drive(["alpha", "beta", "gamma"])
    assert gesture.handle(press(2, 0)) is True
    assert gesture.handle(motion(4, 2)) is True
    assert gesture.handle(release(4, 2)) is True
    expected = Selection.between(("b0", 0, 2), ("b0", 2, 4))
    assert tui.selection == expected
    assert ends == [expected]  # exactly once


@pytest.mark.parametrize(("start", "end"), [((2, 0), (4, 2)), ((4, 2), (2, 0))])
def test_either_drag_direction_covers_the_same_range(start, end):
    tui, gesture, ends = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(*start))
    gesture.handle(motion(*end))
    gesture.handle(release(*end))
    expected = Selection.between(("b0", start[1], start[0]), ("b0", end[1], end[0]))
    assert tui.selection == expected
    assert ends == [expected]


def test_a_drag_across_blocks_lands_the_head_in_the_next_block():
    tui = headless_tui(80, 8)
    tui.add(Rows("alpha"))  # b0: one row
    tui.add(Rows("beta"))  # b1: the next block, one row
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(tui, on_end=lambda app, selection: ends.append(selection))
    gesture.handle(press(1, 0))
    gesture.handle(motion(2, 1))
    gesture.handle(release(2, 1))
    expected = Selection.between(("b0", 0, 1), ("b1", 0, 2))
    assert tui.selection == expected
    assert ends == [expected]


def test_the_default_on_end_copies_the_extracted_range_as_osc52():
    tui, gesture, _ = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2))
    gesture.handle(release(4, 2))
    assert osc52(tui.screen.output) == ["pha\nbeta\ngamm"]


def test_copy_on_select_extracts_and_writes_the_clipboard_bytes():
    tui = headless_tui(80, 8)
    tui.add(Rows("alpha", "beta"))
    tui.paint()
    copy_on_select(tui, Selection.between(("b0", 0, 1), ("b0", 1, 2)))
    assert osc52(tui.screen.output) == ["lpha\nbe"]


def test_on_end_none_selects_without_any_effect():
    tui, gesture, ends = drive(["alpha", "beta", "gamma"], on_end=None)
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2))
    gesture.handle(release(4, 2))
    assert tui.selection == Selection.between(("b0", 0, 2), ("b0", 2, 4))
    assert osc52(tui.screen.output) == []
    assert ends == [Selection.between(("b0", 0, 2), ("b0", 2, 4))]


def test_a_click_clears_the_selection_and_never_fires_on_end():
    tui, gesture, ends = drive(["alpha", "beta", "gamma"])
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 1, 1)))
    tui.paint()
    assert marked(tui)[:2] == ["alpha", "b"]

    gesture.handle(press(0, 0))
    gesture.handle(release(0, 0))
    assert tui.selection is None  # cleared, not left at zero width
    assert ends == []
    assert osc52(tui.screen.output) == []


def test_the_highlight_stays_after_the_drag_and_yields_to_the_next_press():
    tui, gesture, _ = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2))
    gesture.handle(release(4, 2))
    tui.paint()
    assert marked(tui) == ["pha", "beta", "gamm", "", "", "", "", ""]

    gesture.handle(press(0, 0))  # the next press retires it
    tui.paint()
    assert not any(marked(tui))


def test_a_second_press_reanchors_the_drag():
    tui, gesture, ends = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2))
    gesture.handle(press(0, 0))  # a fresh drag, mid-flight
    gesture.handle(motion(2, 2))
    gesture.handle(release(2, 2))
    expected = Selection.between(("b0", 0, 0), ("b0", 2, 2))
    assert tui.selection == expected
    assert ends == [expected]  # the abandoned drag never fired


def test_a_press_off_the_content_clears_and_anchors_nothing():
    tui, gesture, ends = drive(["alpha", "beta", "gamma"])
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 0, 3)))
    tui.paint()

    assert gesture.handle(press(0, 5)) is True  # below the content: blank fill
    assert gesture.handle(release(0, 5)) is True
    assert tui.selection is None
    assert ends == []
    assert osc52(tui.screen.output) == []


def test_a_motion_off_the_content_keeps_the_head():
    tui, gesture, _ = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2))
    assert gesture.handle(motion(0, 7)) is True  # blank fill: still a drag motion
    gesture.handle(release(0, 7))
    assert tui.selection == Selection.between(("b0", 0, 2), ("b0", 2, 4))


def test_a_reflow_mid_drag_ends_the_drag_cleanly():
    tui = headless_tui(80, 8)
    tui.add(Rows("alpha", "beta", "gamma"))
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(tui, on_end=lambda app, selection: ends.append(selection))
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2))
    tui.screen.width = 40  # the terminal resized; the next paint reflows (D8)
    tui.paint()
    assert tui.selection is None  # the reflow cleared it on the frame
    gesture.handle(motion(4, 2))
    gesture.handle(release(4, 2))
    assert ends == []  # the abandoned drag never fired


def test_detach_drops_the_in_flight_drag():
    tui, gesture, ends = drive(["alpha", "beta", "gamma"])
    gesture.handle(press(2, 0))
    gesture.handle(motion(4, 2))
    gesture.detach()
    assert gesture.handle(release(4, 2)) is True  # consumed, but finalizes nothing
    assert ends == []


@pytest.mark.parametrize(
    "event",
    [
        Key("a", "a"),
        Paste("pasted"),
        MouseEvent("middle", button=1, x=0, y=0),
        MouseEvent("right", button=2, x=0, y=0),
        MouseEvent("wheel_down", button=1, x=0, y=0),
        MouseEvent("wheel_up", button=0, x=0, y=0),
        MouseEvent("left", button=0, x=0, y=0, kind="motion"),  # motion, no drag
        MouseEvent("middle", button=1, x=0, y=0, kind="release"),
        MouseEvent("left", button=0, x=0, y=0, kind="other"),
    ],
)
def test_handle_passes_everything_the_gesture_does_not_own(event):
    tui, gesture, _ = drive(["alpha"])
    assert gesture.handle(event) is False
    assert tui.selection is None


def test_a_press_resolves_the_document_row_the_layout_shows():
    tui = headless_tui(80, 10)
    tui.add(Rows(*many(9)))  # 9 rows on a 10-row screen: every row is on screen
    tui.paint()
    gesture = SelectionGesture(tui)
    gesture.handle(press(1, 1))
    assert tui.selection is not None
    assert tui.selection.anchors == (("b0", 1, 1), ("b0", 1, 1))


# --- T2: edge auto-scroll and the wheel -----------------------------------------


def test_a_drag_to_the_bottom_edge_autoscrolls_and_extends_the_head():
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset
    bottom = 9  # the viewport's last screen row (no pinned rows here)
    gesture.handle(press(0, bottom))
    assert tui.selection.anchors == (("b0", offset + bottom, 0),) * 2
    gesture.handle(motion(0, bottom))  # lands on the edge row: arms the ticker
    tick(tui, now, 10)
    assert tui.viewport.offset == offset + 10 * 2
    assert tui.selection.anchors[1] == ("b0", offset + bottom + 20, 0)
    tui.paint()
    # The highlight followed the head: the rows now in range are the painted ones.
    assert marked(tui) == [f"r{row}" for row in range(190, 199)] + [""]


def test_a_press_on_the_edge_row_arms_the_ticker_without_any_motion():
    # The pointer can reach the edge before the button goes down; a stationary
    # press there emits no motion, so the press itself must arm the ticker.
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    tick(tui, now, 10)  # no motion was ever sent
    assert tui.viewport.offset == offset + 10 * 2
    assert tui.selection.anchors[1] == ("b0", offset + 9 + 20, 0)
    gesture.handle(release(0, 9))
    assert len(ends) == 1  # the press-armed drag finalizes like any other


def test_the_ticker_stands_down_at_the_document_end():
    tui, gesture, now, ends = edge_drag()
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9))
    tick(tui, now, 10)
    assert tui.viewport.offset == 190  # 200 rows on a 10-row screen
    assert tui.selection.anchors[1] == ("b0", 199, 0)

    tick(tui, now, 5)  # more time changes nothing: the ticker stood down
    assert tui.viewport.offset == 190
    assert tui.selection.anchors[1] == ("b0", 199, 0)
    assert tui.tick(now[0]) is None  # no periodic callback left on the pump

    # A wheel at the end moves nothing either: the head cannot leave the range.
    assert gesture.handle(MouseEvent("wheel_down", button=1, x=0, y=9)) is True
    assert tui.viewport.offset == 190
    assert tui.selection.anchors[1] == ("b0", 199, 0)

    gesture.handle(release(0, 9))
    assert ends == [Selection.between(("b0", 179, 0), ("b0", 199, 0))]


def test_a_drag_away_from_the_edge_stops_the_ticker():
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9))
    tick(tui, now, 2)
    assert tui.viewport.offset == offset + 4

    gesture.handle(motion(0, 5))  # edge-exit: the head lands on the cell under the pointer
    tick(tui, now, 5)
    assert tui.viewport.offset == offset + 4
    assert tui.selection.anchors[1] == ("b0", offset + 4 + 5, 0)  # row 179


def test_the_release_stops_the_ticker_and_finalizes_the_drag():
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9))
    tick(tui, now, 1)
    head_row = offset + 9 + 2
    gesture.handle(release(0, 9))
    assert ends == [Selection.between(("b0", offset + 9, 0), ("b0", head_row, 0))]

    tick(tui, now, 5)
    assert tui.viewport.offset == offset + 2
    assert tui.selection.anchors[1] == ("b0", head_row, 0)


def test_detach_stops_the_ticker():
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9))
    tick(tui, now, 2)
    gesture.detach()
    tick(tui, now, 5)
    assert tui.viewport.offset == offset + 4
    assert ends == []


def test_a_reflow_mid_drag_stops_the_ticker():
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9))
    tick(tui, now, 1)
    tui.screen.width = 40  # the terminal resized; the next paint reflows (D8)
    tui.paint()
    assert tui.selection is None
    tick(tui, now, 5)
    assert tui.viewport.offset == offset + 2  # frozen: the drag ended cleanly
    assert ends == []


def test_the_top_edge_scrolls_back_and_extends_the_head_upward():
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset  # 170
    gesture.handle(press(0, 9))  # anchor at document row 179
    gesture.handle(motion(0, 0))  # head at the row screen row 0 shows: 170
    assert tui.selection.anchors[1] == ("b0", 170, 0)
    tick(tui, now, 10)
    assert tui.viewport.offset == 150
    assert tui.selection.anchors == (("b0", 179, 0), ("b0", 150, 0))


def test_a_hold_on_one_edge_then_the_other_flips_the_scroll_direction():
    tui, gesture, now, ends = edge_drag()
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9))
    tick(tui, now, 2)
    down = tui.viewport.offset
    gesture.handle(motion(0, 0))  # the pointer now holds the top edge
    tick(tui, now, 1)
    assert tui.viewport.offset == down - 2


def test_the_head_walk_crosses_a_block_boundary_into_the_next_block():
    tui = headless_tui(80, 4)
    tui.add(Rows(*many(100)))  # b0: document rows 0..99
    tui.add(Rows(*many(100)))  # b1: document rows 100..199
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.paint()
    tui.scroll_up(100)  # offset 96: the window shows document rows 96..99
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(tui, on_end=lambda app, sel: ends.append(sel))
    gesture.handle(press(0, 3))  # anchor at b0's last row
    assert tui.selection.anchors == (("b0", 99, 0), ("b0", 99, 0))
    gesture.handle(motion(0, 3))  # still the edge row: the ticker arms
    tick(tui, now, 1)
    # Scrolling 2 rows moves the content under the edge row 2 document rows:
    # from b0's row 99 into b1's row 1 -- one walk, no re-hit_test (D4).
    assert tui.viewport.offset == 98
    assert tui.selection.anchors == (("b0", 99, 0), ("b1", 1, 0))


def test_the_edge_zone_stops_at_the_pinned_footer():
    tui = headless_tui(80, 8)
    tui.add(Rows(*many(200)))
    tui.add(Rows("foot one", "foot two"), id="foot", pin="bottom")
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.paint()
    tui.scroll_up(10)  # the window holds body rows 184..189; rows 6,7 are pinned
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(tui, on_end=lambda app, sel: ends.append(sel))
    offset = tui.viewport.offset  # 184
    gesture.handle(press(0, 5))  # the viewport's last screen row
    gesture.handle(motion(0, 5))
    tick(tui, now, 1)
    assert tui.viewport.offset == offset + 2
    assert tui.selection.anchors[1] == ("b0", offset + 5 + 2, 0)

    gesture.handle(motion(0, 6))  # into the pinned footer: edge-exit, no scroll
    assert tui.selection.anchors[1] == ("foot", 0, 0)
    tick(tui, now, 5)
    assert tui.viewport.offset == offset + 2


def test_a_wheel_during_a_drag_co_extends_the_head_by_the_same_rows():
    tui, gesture, now, ends = edge_drag()
    offset = tui.viewport.offset
    gesture.handle(press(0, 5))  # anchor at document row 175
    assert gesture.handle(MouseEvent("wheel_down", button=1, x=0, y=5)) is True
    assert tui.viewport.offset == offset + 3
    assert tui.selection.anchors == (("b0", 175, 0), ("b0", 178, 0))
    assert gesture.handle(MouseEvent("wheel_up", button=0, x=0, y=5)) is True
    assert tui.viewport.offset == offset
    assert tui.selection.anchors == (("b0", 175, 0), ("b0", 175, 0))
    assert ends == []  # the wheel extends; only the release finalizes


def test_a_wheel_binding_the_host_removed_passes_through_mid_drag():
    tui, gesture, now, ends = edge_drag()
    del tui.scroll_keys["wheel_down"]  # the documented host knob
    gesture.handle(press(0, 5))
    assert gesture.handle(MouseEvent("wheel_down", button=1, x=0, y=5)) is False
    assert tui.viewport.offset == 170
    assert tui.selection.anchors[1] == ("b0", 175, 0)


@pytest.mark.parametrize(("scroll_rows", "scroll_tick"), [(1, 0.04), (2, 0.05), (5, 0.2)])
def test_the_scroll_knobs_set_the_tick_size_and_the_period(scroll_rows, scroll_tick):
    tui, gesture, now, ends = edge_drag(scroll_rows=scroll_rows, scroll_tick=scroll_tick)
    offset = tui.viewport.offset
    gesture.handle(press(0, 9))
    gesture.handle(motion(0, 9))
    now[0] += scroll_tick / 2  # half a period: the ticker has not fired yet
    tui.tick(now[0])
    assert tui.viewport.offset == offset
    tick(tui, now, 3, scroll_tick)
    assert tui.viewport.offset == offset + 3 * scroll_rows
    assert tui.selection.anchors[1] == ("b0", offset + 9 + 3 * scroll_rows, 0)


def clocked(rows: list[str], *, on_end=copy_on_select, **knobs):
    """``drive`` with the documented ``clock`` seam installed before the frame.

    Returns ``(tui, gesture, now, ends)``; the caller moves time through
    ``now[0]`` and fires the pump with ``tui.tick``.
    """
    ends: list[Selection] = []

    def end(app, selection: Selection) -> None:
        ends.append(selection)
        if on_end is not None:
            on_end(app, selection)

    tui = headless_tui(80, 8)
    tui.add(Rows(*rows))
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.paint()
    gesture = SelectionGesture(tui, on_end=end, **knobs)
    return tui, gesture, now, ends


# --- T3: the click count -- word select, then line select ------------------------


def test_a_second_press_at_the_same_cell_selects_the_word_run():
    tui, gesture, now, ends = clocked(["hello world", "second row"])
    gesture.handle(press(1, 0))  # the first click anchors ...
    gesture.handle(release(1, 0))  # ... and clears: a click never fires on_end
    assert tui.selection is None
    assert ends == []

    now[0] += 0.2  # inside the double-click window
    assert gesture.handle(press(1, 0)) is True
    word = Selection.between(("b0", 0, 0), ("b0", 0, 5))
    assert tui.selection == word
    assert ends == [word]  # fired once, at the press
    assert osc52(tui.screen.output) == ["hello"]

    assert gesture.handle(release(1, 0)) is True  # the release finalizes nothing
    assert tui.selection == word
    assert ends == [word]

    tui.paint()
    assert marked(tui)[0] == "hello"
    gesture.handle(press(3, 0))  # the next press retires it, like any selection
    tui.paint()
    assert not any(marked(tui))


@pytest.mark.parametrize(
    ("text", "col", "expected"),
    [
        ("hello world", 1, (0, 5)),
        ("hello world", 4, (0, 5)),
        ("hello world", 8, (6, 11)),
        ("hello world", 10, (6, 11)),
        ("hello world", 5, None),  # the separator: no run to select
        ("a  b", 0, (0, 1)),
        ("a  b", 1, None),
        ("a  b", 3, (3, 4)),
        ("中文 abc", 0, (0, 4)),  # CJK: the run covers both wide characters
        ("中文 abc", 3, (0, 4)),
        ("中文 abc", 4, None),  # the space after them
        ("中文 abc", 6, (5, 8)),
        ("hi", 10, (0, 2)),  # past the row's text: the last column, clamped
    ],
)
def test_the_word_run_is_the_maximal_non_whitespace_stretch(text, col, expected):
    tui, gesture, now, ends = clocked([text])
    gesture.handle(press(col, 0))
    gesture.handle(release(col, 0))
    now[0] += 0.2
    gesture.handle(press(col, 0))
    if expected is None:
        # no run at that cell: the press degrades to a plain anchor, so the
        # release that follows clears and on_end never fires
        assert tui.selection.anchors == (("b0", 0, col), ("b0", 0, col))
        assert ends == []
    else:
        word = Selection.between(("b0", 0, expected[0]), ("b0", 0, expected[1]))
        assert tui.selection == word
        assert ends == [word]


def test_a_second_press_outside_the_window_is_a_plain_press():
    tui, gesture, now, ends = clocked(["hello world"])
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    now[0] += 0.5  # past the default 0.35s window
    gesture.handle(press(1, 0))
    assert tui.selection.anchors == (("b0", 0, 1), ("b0", 0, 1))
    assert ends == []


def test_a_second_press_at_another_cell_is_a_plain_press():
    tui, gesture, now, ends = clocked(["hello world"])
    gesture.handle(press(1, 0))
    now[0] += 0.1
    gesture.handle(press(8, 0))  # a different cell, inside the window
    assert tui.selection.anchors == (("b0", 0, 8), ("b0", 0, 8))
    assert ends == []


def test_the_double_click_knob_widens_the_window():
    tui, gesture, now, ends = clocked(["hello world"], double_click_seconds=1.0)
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    now[0] += 0.6  # past the default window, inside this one
    gesture.handle(press(1, 0))
    assert tui.selection == Selection.between(("b0", 0, 0), ("b0", 0, 5))


def test_a_third_press_in_the_window_selects_the_line():
    tui, gesture, now, ends = clocked(["hello world", "second row"])
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    now[0] += 0.2
    gesture.handle(press(1, 0))  # the second press: the word
    gesture.handle(release(1, 0))
    now[0] += 0.2
    assert gesture.handle(press(1, 0)) is True  # still inside the window: the line
    word = Selection.between(("b0", 0, 0), ("b0", 0, 5))
    line = Selection.between(("b0", 0, 0), ("b0", 0, 11))
    assert tui.selection == line
    assert ends == [word, line]  # fired once each, at their own press
    assert osc52(tui.screen.output) == ["hello", "hello world"]

    assert gesture.handle(release(1, 0)) is True  # the release finalizes nothing
    assert tui.selection == line
    assert ends == [word, line]

    tui.paint()
    assert marked(tui)[:2] == ["hello world", ""]  # the line spares the row below it


def test_the_line_select_is_the_hit_blocks_own_row():
    """A click at one block's row selects that row -- never its neighbour's."""
    tui = headless_tui(80, 8)
    tui.add(Rows("first block"))
    tui.add(Rows("second block"))
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(tui, on_end=lambda app, sel: ends.append(sel))
    line = Selection.between(("b1", 0, 0), ("b1", 0, 12))
    word = Selection.between(("b1", 0, 0), ("b1", 0, 6))
    for _ in range(3):
        gesture.handle(press(3, 1))  # the second block's row, one screen row down
        gesture.handle(release(3, 1))
        now[0] += 0.2
    assert tui.selection == line
    assert ends == [word, line]  # the word fired on the second press
    tui.paint()
    assert marked(tui)[:2] == ["", "second block"]  # the first block stayed clear


def test_a_fourth_press_restarts_the_click_count():
    tui, gesture, now, ends = clocked(["hello world"])
    word = Selection.between(("b0", 0, 0), ("b0", 0, 5))
    line = Selection.between(("b0", 0, 0), ("b0", 0, 11))
    for _ in range(3):  # click, word, line -- each inside the window
        gesture.handle(press(1, 0))
        gesture.handle(release(1, 0))
        now[0] += 0.2
    assert ends == [word, line]
    gesture.handle(press(1, 0))  # the fourth: the count starts over
    assert tui.selection.anchors == (("b0", 0, 1), ("b0", 0, 1))
    assert ends == [word, line]
    gesture.handle(release(1, 0))  # the zero-width click clears
    now[0] += 0.2
    gesture.handle(press(1, 0))  # the fifth: the word again
    assert tui.selection == word
    assert ends == [word, line, word]


def test_a_third_press_outside_the_window_is_a_plain_press():
    tui, gesture, now, ends = clocked(["hello world"])
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    now[0] += 0.2
    gesture.handle(press(1, 0))  # the word, inside the window
    assert tui.selection == Selection.between(("b0", 0, 0), ("b0", 0, 5))
    now[0] += 0.5  # past the default 0.35s window since that press
    gesture.handle(press(1, 0))
    assert tui.selection.anchors == (("b0", 0, 1), ("b0", 0, 1))
    assert ends == [Selection.between(("b0", 0, 0), ("b0", 0, 5))]


def test_a_third_press_at_another_cell_is_a_plain_press():
    tui, gesture, now, ends = clocked(["hello world"])
    gesture.handle(press(1, 0))
    gesture.handle(release(1, 0))
    now[0] += 0.2
    gesture.handle(press(1, 0))  # the word at the first cell
    now[0] += 0.2
    gesture.handle(press(8, 0))  # a different cell: the count is per cell
    assert tui.selection.anchors == (("b0", 0, 8), ("b0", 0, 8))
    assert ends == [Selection.between(("b0", 0, 0), ("b0", 0, 5))]


def test_a_triple_click_on_whitespace_still_selects_the_line():
    tui, gesture, now, ends = clocked(["a  b"])
    for _ in range(2):  # the second press has no word run: it degrades
        gesture.handle(press(1, 0))
        gesture.handle(release(1, 0))
        now[0] += 0.2
    assert ends == []
    gesture.handle(press(1, 0))  # the third: the whole line, whitespace included
    line = Selection.between(("b0", 0, 0), ("b0", 0, 4))
    assert tui.selection == line
    assert ends == [line]


def test_a_word_select_never_arms_the_autoscroll_ticker():
    tui = headless_tui(80, 10)
    tui.add(Rows(*many(200)))
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.paint()
    tui.scroll_up(20)
    tui.paint()
    ends: list[Selection] = []
    gesture = SelectionGesture(tui, on_end=lambda app, sel: ends.append(sel))
    offset = tui.viewport.offset
    gesture.handle(press(1, 9))  # the bottom edge row: a drag motion would arm here
    gesture.handle(release(1, 9))
    now[0] += 0.2
    gesture.handle(press(1, 9))  # the word select instead
    assert ends == [Selection.between(("b0", 179, 0), ("b0", 179, 4))]  # "r179"
    tick(tui, now, 5)
    assert tui.viewport.offset == offset  # no ticker was ever armed
