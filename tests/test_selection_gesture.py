"""Tests for mocode_tui.selection: the gesture, the policy tier.

The gesture is driven headlessly against a real :class:`~mocode_tui.app.TUI`:
a document of plain rows on a recording screen, ``press``/``motion``/``release``
:class:`~mocode_tui.core.events.MouseEvent` reports injected through
``handle``, and the documented ``_clock`` seam for the timed behaviors.  The
helpers here are the mouse-report shorthands and an OSC 52 payload extractor
-- the OSC 52 bytes are decoded back, never matched against a re-derivation.
"""

import base64
import re

import pytest

from _doubles import Rows, many

from mocode_tui.core.events import Key, MouseEvent, Paste
from mocode_tui.core.selection import Selection
from mocode_tui.selection import SelectionGesture, copy_on_select
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
    ``reverse+dim`` -- which no default style in this file carries.
    """
    return [
        "".join(seg.text for seg in row.segments if seg.style.reverse and seg.style.dim)
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
