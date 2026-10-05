"""Tests for mocode_tui.chrome: the Toasts overlay and its controller.

The stack is driven headlessly against a real :class:`~mocode_tui.app.TUI`:
a document of plain rows on a recording screen, the bands read off the
painted rows (a toast splices its band into the frame rows at its corner
rectangle), and the documented ``_clock`` seam for the expiry ticker.  The
geometry is pinned as row texts over the cases the spec names: all four
corners, the stack order and its blank separator, the width clamp and the
fit guard, the empty state, and -- for the controller -- TTL expiry,
``max_shown`` eviction, click-to-dismiss and ``detach``.
"""

import pytest

from _doubles import Rows

from mocode_tui.chrome import Toasts
from mocode_tui.core.events import Key, MouseEvent, Paste
from mocode_tui.core.style import Style
from mocode_tui.core.text import Text
from mocode_tui.core.theme import Theme
from mocode_tui.testing import headless_tui

# --- helpers ------------------------------------------------------------------


def stack(tui, **knobs) -> Toasts:
    """A Toasts attached to an already-painted ``tui``."""
    toasts = Toasts(tui, **knobs)
    tui.paint()
    return toasts


def rows(width: int, height: int) -> list[str]:
    """The painted row texts of a headless ``width``x``height`` frame."""
    return [f"r{index}" for index in range(height)]


def document(tui, texts):
    """Fill ``tui``'s document with ``texts`` and paint."""
    tui.add(Rows(*texts))
    tui.paint()


def press(x: int, y: int) -> MouseEvent:
    """A left-button press report at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y)


def motion(x: int, y: int) -> MouseEvent:
    """A motion report at the 0-based cell (no button state of its own)."""
    return MouseEvent("left", button=0, x=x, y=y, kind="motion")


def release(x: int, y: int) -> MouseEvent:
    """A left-button release report at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y, kind="release")


def clocked(tui, **knobs) -> tuple[Toasts, list[float]]:
    """A Toasts on ``tui`` with the documented ``_clock`` seam installed.

    The seam is set *before the first frame*, so the pump paints on the
    injected clock -- a ``_last_paint`` left on the real clock would freeze
    the throttle.  The caller advances ``now[0]`` and fires the pump with
    ``tui._tick``.
    """
    now = [1000.0]
    tui._clock = lambda: now[0]
    toasts = Toasts(tui, **knobs)
    tui.paint()
    return toasts, now


def advance(tui, now: list[float], seconds: float) -> None:
    """Move the injected clock and fire the pump once at the new reading."""
    now[0] += seconds
    tui._tick(now[0])


# --- T1: the overlay ------------------------------------------------------------


@pytest.mark.parametrize(
    ("corner", "affected", "expected"),
    [
        ("top-left", 0, "hi        "),  # the band covers the document's head
        ("top-right", 0, "r0      hi"),
        ("bottom-left", 3, "hi        "),
        ("bottom-right", 3, "r3      hi"),
    ],
)
def test_each_corner_anchors_the_band(corner, affected, expected):
    tui = headless_tui(10, 4)
    document(tui, rows(10, 4))
    stack(tui, corner=corner).show("hi")
    tui.paint()
    assert tui.rows[affected].text == expected
    # every other row is the document's own, untouched
    others = [index for index in range(4) if index != affected]
    assert [tui.rows[index].text for index in others] == [
        rows(10, 4)[index] for index in others
    ]


def test_the_stack_reads_newest_at_the_corner_with_one_blank_row_between():
    tui = headless_tui(10, 5)
    document(tui, rows(10, 5))
    toasts = stack(tui)
    toasts.show("old")
    toasts.show("new")
    tui.paint()
    assert tui.rows[0].text == "r0     new"  # the newest sits at the corner
    assert tui.rows[2].text == "r2     old"  # one blank row between neighbours
    assert tui.rows[1].text == "r1"  # the separator is the document's own row


def test_a_multi_row_component_band_covers_each_of_its_rows():
    tui = headless_tui(10, 4)
    document(tui, rows(10, 4))
    stack(tui, corner="bottom-right").show(Rows("one", "two"))
    tui.paint()
    assert tui.rows[2].text == "r2     one"  # the component's own row order
    assert tui.rows[3].text == "r3     two"  # the stack grew up from the bottom edge
    assert tui.rows[1].text == "r1"


def test_a_narrow_frame_clamps_the_band_to_half_its_width():
    tui = headless_tui(20, 3)
    toasts = stack(tui)
    toasts.show("x" * 30)  # one long word: hard-broken at the clamp
    tui.paint()
    # ceiling = min(40, 20 // 2) = 10: ten columns of text per row, wrapped
    assert tui.rows[0].text == " " * 10 + "x" * 10
    assert tui.rows[1].text == " " * 10 + "x" * 10
    assert tui.rows[2].text == " " * 10 + "x" * 10


def test_a_wide_frame_clamps_the_band_to_forty_columns():
    tui = headless_tui(80, 3)
    toasts = stack(tui)
    toasts.show("y" * 90)
    tui.paint()
    # ceiling = min(40, 80 // 2) = 40 -- never more than half the frame
    assert tui.rows[0].text == " " * 40 + "y" * 40
    assert tui.rows[1].text == " " * 40 + "y" * 40
    assert tui.rows[2].text == " " * 40 + "y" * 10 + " " * 30


def test_a_short_toast_band_is_only_as_wide_as_its_content():
    tui = headless_tui(80, 1)
    toasts = stack(tui)
    toasts.show("hi")
    tui.paint()
    assert tui.rows[0].text == " " * 78 + "hi"


def test_a_component_that_overruns_its_width_is_fit_to_the_band():
    tui = headless_tui(20, 1)
    toasts = stack(tui)
    toasts.show(Rows("z" * 50))  # Rows ignores its width: the fit guard cuts it
    tui.paint()
    assert tui.rows[0].text == " " * 10 + "z" * 9 + "…"


def test_an_empty_stack_paints_nothing():
    tui = headless_tui(10, 3)
    document(tui, rows(10, 3))
    before = [row.text for row in tui.rows]
    stack(tui)
    tui.paint()
    assert [row.text for row in tui.rows] == before


def test_a_frame_too_narrow_to_host_a_column_paints_nothing():
    tui = headless_tui(1, 2)
    document(tui, ["a", "b"])
    toasts = stack(tui)
    toasts.show("hi")
    tui.paint()
    assert [row.text for row in tui.rows] == ["a", "b"]


def test_a_toast_rides_the_retile_that_rebuilds_the_frame():
    tui = headless_tui(20, 3)
    document(tui, rows(20, 3))
    toasts = stack(tui, corner="bottom-right")
    toasts.show("stay")
    tui.screen.width = 30  # the terminal resized; the next paint retiles the frame
    tui.paint()
    assert tui.rows[2].text == "r2" + " " * 24 + "stay"  # the band moved with the edge


@pytest.mark.parametrize(
    ("knobs", "show_style", "expected"),
    [
        ({"style": Style(fg="#111111")}, None, Style(fg="#111111")),
        ({}, Style(fg="#222222"), Style(fg="#222222")),  # a toast's own wins
        (
            {"style": Style(fg="#111111")},
            Style(fg="#222222"),
            Style(fg="#222222"),
        ),
        (
            {"theme": Theme(toast=Style(fg="#333333"))},
            None,
            Style(fg="#333333"),
        ),
        (
            {"style": Style(fg="#111111"), "theme": Theme(toast=Style(fg="#333333"))},
            None,
            Style(fg="#111111"),
        ),
    ],
)
def test_the_band_resolves_a_toasts_style_then_the_controllers(
    knobs, show_style, expected
):
    tui = headless_tui(10, 1)
    toasts = stack(tui, **knobs)
    toasts.show("hi", style=show_style)
    tui.paint()
    assert tui.rows[0].segments[-1].style == expected


def test_the_band_paints_underneath_a_components_own_styles():
    tui = headless_tui(10, 6)
    toasts = stack(tui, style=Style(bg="#123456"))
    tui.paint()
    toasts.show(Text("red", style=Style(fg="red")))  # a color of its own: kept
    toasts.show(Text("dim", style=Style(italic=True)))  # an attribute: merged
    toasts.show(Rows("ab", ""))  # a short row and a blank row: both filled
    tui.paint()
    band = Style(bg="#123456")  # an explicit style is the whole band (charter)
    # The newest toast is two rows tall: "ab" over the band, then a blank row
    # that reads as a solid band row (the first segment of each row is the
    # untouched base the band does not cover).
    assert tui.rows[0].segments[1].style == band
    assert tui.rows[1].text == " " * 8 + "  "
    assert tui.rows[1].segments[-1].style == band
    # The middle toast: an attribute-only run shows the band through.
    assert tui.rows[3].segments[1].style == band.merge(Style(italic=True))
    # The oldest toast: a run with a color of its own stays absolute.
    assert tui.rows[5].segments[1].style == Style(fg="red")


def test_construct_attaches_the_overlay_and_detach_is_reported_clean():
    tui = headless_tui(10, 2)
    document(tui, rows(10, 2))
    toasts = stack(tui)
    assert toasts in tui._frame.overlays
    assert repr(toasts) == "Toasts(corner='top-right', shown=0)"
    toasts.show("hi")
    assert repr(toasts) == "Toasts(corner='top-right', shown=1)"


def test_an_unknown_corner_raises():
    tui = headless_tui(10, 2)
    with pytest.raises(ValueError):
        Toasts(tui, corner="middle")




# --- T2: the controller ----------------------------------------------------------


@pytest.mark.parametrize(
    ("ttl", "shown", "spent", "expected"),
    [
        (4.0, 3, 0.5, 2),  # the oldest toast's ttl has passed
        (4.0, 3, 1.5, 2),  # the second is not due yet
        (4.0, 3, 2.5, 1),  # two toasts came due, the newest is live
        (4.0, 3, 6.0, 0),  # the whole stack expired
        (1.0, 2, 0.75, 1),  # a shorter ttl: the oldest is due
        (1.0, 2, 2.0, 0),  # and the newer one follows
    ],
)
def test_the_ticker_drops_the_toasts_whose_ttl_has_passed(
    ttl, shown, spent, expected
):
    tui = headless_tui(10, 8)  # an empty document: every painted row is a toast
    toasts, now = clocked(tui, ttl=ttl)
    for index in range(shown):
        if index:
            now[0] += ttl / 2  # stagger the shows: each toast lives its own ttl
        toasts.show(f"t{index}")
    tui.paint()
    assert len([row for row in tui.rows if row.text.strip()]) == shown
    advance(tui, now, spent)
    tui.paint()
    assert len([row for row in tui.rows if row.text.strip()]) == expected


def test_the_expired_toasts_leave_the_frame_at_the_next_paint():
    tui = headless_tui(10, 4)
    document(tui, rows(10, 4))
    toasts, now = clocked(tui, ttl=4.0)
    toasts.show("gone")
    tui.paint()
    assert tui.rows[0].text == "r0    gone"
    advance(tui, now, 5.0)
    tui.paint()
    assert [row.text for row in tui.rows] == rows(10, 4)  # the band is gone


def test_the_ticker_stands_down_once_the_last_toast_expires():
    tui = headless_tui(10, 2)
    toasts, now = clocked(tui, ttl=1.0)
    toasts.show("bye")
    advance(tui, now, 1.5)  # the tick drops it and cancels the ticker
    assert tui._tick(now[0]) is None  # no periodic callback left on the pump
    toasts.show("again")  # a later show arms the one ticker afresh
    assert toasts.handle(press(9, 0)) is True  # the band is live and dismissible
    advance(tui, now, 1.5)
    assert tui._tick(now[0]) is None


@pytest.mark.parametrize(
    ("max_shown", "shown", "expected"),
    [
        (3, 2, ["r0      m1", "r2      m0"]),  # the whole stack fits
        (3, 4, ["r0      m3", "r2      m2", "r4      m1"]),  # the oldest went
    ],
)
def test_max_shown_evicts_the_oldest_toasts(max_shown, shown, expected):
    tui = headless_tui(10, 8)
    document(tui, rows(10, 8))
    toasts = stack(tui, max_shown=max_shown)
    for index in range(shown):
        toasts.show(f"m{index}")
    tui.paint()
    painted = [tui.rows[row].text for row in range(0, 2 * len(expected), 2)]
    assert painted == expected


def test_a_press_inside_a_toast_drops_that_toast_only():
    tui = headless_tui(10, 4)
    document(tui, rows(10, 4))
    toasts = stack(tui)
    toasts.show("one")
    toasts.show("two")
    tui.paint()
    # the newest toast covers row 0, columns 7-9; the older one row 2
    assert toasts.handle(press(8, 0)) is True
    tui.paint()
    # the survivor takes the corner the dismissed toast vacated
    assert tui.rows[0].text == "r0     one"
    assert tui.rows[2].text == "r2"

    # a press inside the survivor's band empties the stack
    assert toasts.handle(press(9, 0)) is True
    tui.paint()
    assert [row.text for row in tui.rows] == rows(10, 4)


def test_a_press_outside_every_toast_passes_through():
    tui = headless_tui(10, 4)
    document(tui, rows(10, 4))
    toasts = stack(tui)
    toasts.show("keep")  # a four-wide band: columns 6-9 of row 0
    tui.paint()
    assert toasts.handle(press(0, 0)) is False  # the document is under the pointer
    assert toasts.handle(press(5, 0)) is False  # one column short of the band
    tui.paint()
    assert tui.rows[0].text == "r0    keep"


def test_a_press_inside_a_bottom_corner_toast_drops_it():
    tui = headless_tui(10, 3)
    document(tui, rows(10, 3))
    toasts = stack(tui, corner="bottom-left")
    toasts.show("bye")
    tui.paint()
    assert tui.rows[2].text == "bye       "  # the band anchors at the left edge
    assert toasts.handle(press(1, 2)) is True
    tui.paint()
    assert tui.rows[2].text == "r2"


@pytest.mark.parametrize(
    "event",
    [
        Key("a", "a"),
        Paste("pasted"),
        MouseEvent("middle", button=1, x=8, y=0),
        MouseEvent("right", button=2, x=8, y=0),
        MouseEvent("wheel_up", button=0, x=8, y=0),
        MouseEvent("wheel_down", button=1, x=8, y=0),
        motion(8, 0),  # a motion is not a press: toasts have no drag
        release(8, 0),  # a release with no press of its own is the host's
    ],
)
def test_handle_passes_everything_the_dismiss_does_not_own(event):
    tui = headless_tui(10, 2)
    document(tui, rows(10, 2))
    toasts = stack(tui)
    toasts.show("stay")  # a four-wide band: columns 6-9 of row 0
    tui.paint()
    assert toasts.handle(event) is False
    assert toasts.handle(press(7, 0)) is True  # the band is still there


def test_the_string_sugar_wraps_a_text_and_a_component_shows_as_is():
    tui = headless_tui(10, 4)
    toasts = stack(tui)
    toasts.show("plain")  # a str: wrapped in a Text
    toasts.show(Rows("raw"))  # a Component: shown as it renders
    tui.paint()
    assert tui.rows[0].text == " " * 7 + "raw"  # the newest sits at the corner
    assert tui.rows[2].text == " " * 5 + "plain"


def test_a_per_show_ttl_overrides_the_controllers():
    tui = headless_tui(10, 4)
    toasts, now = clocked(tui, ttl=10.0)
    toasts.show("short", ttl=1.0)
    toasts.show("long")
    tui.paint()
    assert tui.rows[0].text == " " * 6 + "long"
    assert tui.rows[2].text == " " * 5 + "short"
    advance(tui, now, 2.0)  # the per-show ttl came due first
    tui.paint()
    assert tui.rows[0].text == " " * 6 + "long"  # the survivor takes the corner
    assert tui.rows[2].text == ""


def test_detach_drops_the_stack_cancels_the_ticker_and_stays_detached():
    tui = headless_tui(10, 2)
    document(tui, rows(10, 2))
    toasts, now = clocked(tui, ttl=1.0)
    toasts.show("gone")
    tui.paint()
    toasts.detach()
    tui.paint()
    assert [row.text for row in tui.rows] == rows(10, 2)  # the band left the frame
    toasts.show("ignored")  # a detached controller stays detached
    tui.paint()
    assert [row.text for row in tui.rows] == rows(10, 2)
    assert toasts.handle(press(8, 0)) is False
    advance(tui, now, 5.0)
    assert tui._tick(now[0]) is None  # the ticker is gone
    toasts.detach()  # idempotent


def test_the_controller_stays_attached_through_a_retile():
    tui = headless_tui(20, 3)
    document(tui, rows(20, 3))
    toasts = stack(tui, corner="bottom-right")
    toasts.show("stay")
    tui.screen.width = 30  # the terminal resized; the next paint retiles
    tui.paint()
    assert tui.rows[2].text == "r2" + " " * 24 + "stay"
    assert toasts.handle(press(29, 2)) is True  # the band moved with the edge
    tui.paint()
    assert tui.rows[2].text == "r2"
