"""Tests for motui.interaction.scrollbar (Scrollbar): the strip and its gesture.

One test file per source file: this module carries the pane chrome -- the
Scrollbar's strip geometry and its drag/page ticker (the split's private
divider rides the same chrome budget and is exercised through the driver's
own split in ``tests/test_app.py``).  The bar is driven headlessly against a
real :class:`~motui.app.TUI`: nothing sleeps (the documented ``clock`` seam
and a recording screen stand in for time and terminal) and every geometry is
pinned as painted row text.

The frame overlays -- Stats, Toasts and the Tooltip -- live in
``tests/test_overlays.py``.
"""

import pytest

from _doubles import Rows, many

from motui import Key, MouseEvent, Paste, Style, Theme, TUI
from motui.interaction import Scrollbar
from motui.kernel import glyphs
from motui.kernel.lines import Text
from motui.testing import headless_tui


# === Scrollbar =====================================================================


# --- helpers ------------------------------------------------------------------


def strip_texts(tui, width: int = 1) -> list[str]:
    """The strip's row texts: the bar's columns at the pane's right edge."""
    return [row.text[tui.screen.width - width :] for row in tui.rows]


def bar(tui, **knobs) -> Scrollbar:
    """A Scrollbar attached to an already-painted ``tui``."""
    strip = Scrollbar(tui, **knobs)
    tui.paint()
    return strip


def scrolled(total: int, height: int, offset: int) -> object:
    """A headless TUI over ``total`` rows, the window scrolled to ``offset``.

    The fresh viewport sticks to the bottom (offset ``total - height``), so
    scrolling up the difference lands the window exactly at ``offset``.
    """
    tui = headless_tui(20, height)
    tui.add(Rows(*many(total)))
    tui.paint()
    tui.scroll_up(total - height - offset)
    tui.paint()
    return tui


def press(x: int, y: int) -> MouseEvent:
    """A left-button press report at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y)


def motion(x: int, y: int) -> MouseEvent:
    """A motion report with the left button held at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y, kind="motion")


def release(x: int, y: int) -> MouseEvent:
    """A left-button release report at the 0-based cell."""
    return MouseEvent("left", button=0, x=x, y=y, kind="release")


def tick(tui, now: list[float], count: int = 1, seconds: float = 0.05) -> None:
    """Fire the pump ``count`` times, ``seconds`` of clock apart."""
    for _ in range(count):
        now[0] += seconds
        tui.tick(now[0])


# --- T1: the geometry ------------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "height", "offset", "expected"),
    [
        (100, 10, 0, "█░░░░░░░░░"),  # the top of the document
        (100, 10, 45, "░░░░█░░░░░"),  # the acceptance case: round(45*9/90)
        (100, 10, 85, "░░░░░░░░█░"),  # a half rounds to the even integer
        (100, 10, 86, "░░░░░░░░░█"),
        (100, 10, 90, "░░░░░░░░░█"),  # the maximum offset: the bottom
        (1000, 10, 400, "░░░░█░░░░░"),  # a long document: the thumb is one cell
        (11, 2, 4, "█░"),  # a tiny strip: round(4/9) == 0
        (11, 2, 5, "░█"),  # a tiny strip: round(5/9) == 1
        (5, 10, 0, "░░░░░░░░░░"),  # a document shorter than the window: no thumb
        (0, 10, 0, "░░░░░░░░░░"),  # an empty document: no thumb
    ],
)
def test_the_strip_paints_the_thumb_the_geometry_maps(
    total: int, height: int, offset: int, expected: str
):
    tui = scrolled(total, height, offset)
    bar(tui)
    assert "".join(strip_texts(tui)) == expected


def test_the_strip_runs_the_panes_whole_height_pinned_footer_included():
    """The thumb maps the window over the body; the track is the whole pane."""
    tui = headless_tui(20, 10)
    tui.add(Rows(*many(100)))
    tui.add(Rows("foot one", "foot two"), id="foot", pin="bottom")
    tui.paint()  # a fresh viewport sticks to the bottom: offset 92, window 8
    bar(tui)
    assert "".join(strip_texts(tui)) == "░░░░░░░░░█"
    assert tui.rows[9].text[19] == "█"  # the pinned footer row carries the strip too


def test_the_strip_remembers_the_layout_it_mapped_and_follows_a_scroll():
    """The strip memo (T3): the bar's paint is a pure function of the laid-out
    state, so the same layout answers the very rows again -- and a frame that
    moved nothing writes nothing -- while a scroll resolves the thumb afresh:
    the memo cannot serve the strip the offset before painted."""
    tui = scrolled(100, 10, 45)  # the geometry's own case: the thumb at row 4
    bar(tui)
    layout = tui.frame.pane_layout("primary")
    chrome = tui.frame.pane("primary").chrome[0]
    first = chrome.paint(layout, 10)
    assert "".join(row.text for row in first) == "░░░░█░░░░░"
    again = chrome.paint(layout, 10)
    assert [row is other for row, other in zip(first, again)] == [True] * 10
    assert first is not again  # a fresh list every call: the caller owns its rows
    before = tui.screen.output
    tui.paint()
    assert tui.screen.output == before  # nothing moved: zero bytes, memo and all
    tui.scroll_up(45)  # offset 0: the thumb rides the first strip row
    tui.paint()
    moved = chrome.paint(tui.frame.pane_layout("primary"), 10)
    assert "".join(row.text for row in moved) == "█░░░░░░░░░"
    assert moved != first  # the old strip is gone, not remembered


def test_the_bar_budgets_its_column_and_the_pane_rewraps_beside_it():
    """Chrome reserves, never overlaps: the content wraps at the reduced width."""
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    assert [row.text for row in tui.rows] == ["0123456789", ""]
    bar(tui)
    assert [row.text for row in tui.rows] == ["012345678░", "9        ░"]


def test_a_two_column_strip_paints_two_wide_rows_and_wraps_at_two_less():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    bar(tui, size=2)
    assert [row.text for row in tui.rows] == ["01234567░░", "89      ░░"]


@pytest.mark.parametrize(
    ("total", "min_thumb", "expected"),
    [
        (100, 1, "░░░█░░░░░░"),  # the default: the one cell the document allows
        (100, 3, "░░███░░░░░"),
        (100, 5, "░░█████░░░"),
        (100, 10, "██████████"),  # longer than the strip: clamped to it
        (100, 0, "░░░█░░░░░░"),  # zero still allows the one computed cell
        (1000, 0, "░░░░░░░░░░"),  # a long document shaves the thumb away
    ],
)
def test_min_thumb_sets_the_shortest_thumb(total: int, min_thumb: int, expected: str):
    tui = scrolled(total, 10, 30)
    bar(tui, min_thumb=min_thumb)
    assert "".join(strip_texts(tui)) == expected


@pytest.mark.parametrize(
    ("knobs", "track", "thumb"),
    [
        (
            {"style": Style(fg="#111111"), "thumb_style": Style(fg="#222222")},
            "#111111",
            "#222222",
        ),
        (
            {
                "theme": Theme(
                    scrollbar=Style(fg="#333333"), scrollbar_thumb=Style(fg="#444444")
                )
            },
            "#333333",
            "#444444",
        ),
        (
            {
                "style": Style(fg="#111111"),
                "thumb_style": Style(fg="#222222"),
                "theme": Theme(
                    scrollbar=Style(fg="#333333"),
                    scrollbar_thumb=Style(fg="#444444"),
                ),
            },
            "#111111",
            "#222222",
        ),
    ],
)
def test_the_styles_resolve_explicit_then_theme_then_default(knobs, track, thumb):
    tui = scrolled(100, 10, 45)  # the thumb sits at strip row 4
    bar(tui, **knobs)
    assert tui.rows[0].segments[-1].style.fg == track
    assert tui.rows[4].segments[-1].style.fg == thumb


def test_the_default_glyphs_are_the_vocabularys_track_and_thumb():
    """The shipped strip still paints ``glyphs.TRACK`` / ``glyphs.THUMB``."""
    tui = scrolled(100, 10, 45)
    bar(tui)
    assert "".join(strip_texts(tui)) == f"{glyphs.TRACK * 4}{glyphs.THUMB}{glyphs.TRACK * 5}"


def test_custom_glyphs_paint_the_strip():
    """``track`` / ``thumb`` are content: the host picks both cells."""
    tui = scrolled(100, 10, 45)
    bar(tui, track=".", thumb="#")
    assert "".join(strip_texts(tui)) == "....#....."
    # A two-column strip repeats the chosen glyph per budgeted cell.
    wide = scrolled(100, 10, 45)
    bar(wide, size=2, track="=", thumb="X")
    assert [row.text[-2:] for row in wide.rows] == ["=="] * 4 + ["XX"] + ["=="] * 5


def test_the_strip_memo_keys_the_glyphs_and_repaints_a_re_glyphed_bar():
    """The strip memo names the glyphs: a re-glyphed bar never reuses a row."""
    tui = scrolled(100, 10, 45)
    strip = bar(tui, track=".", thumb="#")
    layout = tui.frame.pane_layout("primary")
    chrome = tui.frame.pane("primary").chrome[0]
    first = chrome.paint(layout, 10)
    assert "".join(row.text for row in first) == "....#....."
    again = chrome.paint(layout, 10)
    assert [row is other for row, other in zip(first, again)] == [True] * 10
    # The glyphs are constructor input, so a live bar only changes them by
    # construction -- but the key must carry them all the same: a strip
    # remembering the old cells would paint them over the new glyphs.
    strip._track, strip._thumb = "-", "+"
    changed = chrome.paint(layout, 10)
    assert "".join(row.text for row in changed) == "----+-----"
    assert changed[0] is not first[0]


def test_an_empty_glyph_paints_the_reserved_column_empty():
    """``""`` seats nothing: the column stays budgeted, the cells paint blank.

    A scrollbar has no useful "disabled" state, so the empty glyph takes the
    closest semantics to ``size=0``: the budget is unchanged (the pane keeps
    wrapping beside the bar) and nothing is painted in it.
    """
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    bar(tui, track="", thumb="")
    assert [row.text for row in tui.rows] == ["012345678 ", "9         "]
    assert [row.text[tui.screen.width - 1 :] for row in tui.rows] == [" ", " "]


def test_construct_registers_the_strip_and_detach_gives_the_column_back():
    tui = headless_tui(10, 3)
    tui.add(Text("0123456789"))
    tui.paint()
    strip = bar(tui)
    assert [row.text for row in tui.rows] == [
        "012345678░",
        "9        ░",
        "         ░",
    ]
    strip.detach()
    tui.paint()
    # the budget is released: the document re-wraps at the pane's full width
    assert [row.text for row in tui.rows] == ["0123456789", "", ""]
    strip.detach()  # idempotent: nothing is registered twice


def test_the_pane_knob_selects_a_pane_by_id_and_an_unknown_id_raises():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    bar(tui, pane="primary")  # the driver's primary pane, named explicitly
    assert [row.text for row in tui.rows] == ["012345678░", "9        ░"]
    with pytest.raises(ValueError):
        Scrollbar(tui, pane="nowhere")


# --- T2: the gesture --------------------------------------------------------------


def driven(total: int, height: int, offset: int, **knobs) -> tuple:
    """A scrolled pane, an attached bar, and the clock seam.

    Returns ``(tui, bar, now)`` with the documented ``clock`` seam
    installed *before the first frame*, so the pump paints on the
    injected clock -- a ``_last_paint`` left on the real clock would
    freeze the throttle.  The caller advances ``now[0]`` and fires the
    pump with ``tui.tick``.
    """
    tui = headless_tui(20, height)
    tui.add(Rows(*many(total)))
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.paint()
    tui.scroll_up(total - height - offset)
    tui.paint()
    bar = Scrollbar(tui, **knobs)
    tui.paint()
    return tui, bar, now


@pytest.mark.parametrize(
    ("total", "offset", "press_row", "motion_row", "expected"),
    [
        (100, 45, 4, 4, 45),  # the anchor: a grab moves nothing until the pointer does
        (100, 45, 4, 7, 75),  # 3 strip rows is 30 document rows (scroll/track = 10)
        (100, 45, 4, 2, 25),
        (100, 45, 4, 0, 5),  # 4 rows back is 40: 45 - 40, clamped at neither end
        (100, 45, 4, 9, 90),  # clamped at the document end
        (20, 5, 4, 6, 9),  # a longer thumb: 2 strip rows is 4 document rows
    ],
)
def test_a_drag_maps_the_pointer_row_to_the_offset(
    total: int, offset: int, press_row: int, motion_row: int, expected: int
):
    tui, bar, _ = driven(total, 10, offset)
    assert bar.handle(press(19, press_row)) is True
    assert bar.handle(motion(19, motion_row)) is True
    assert tui.viewport.offset == expected


def test_a_drag_repaints_the_thumb_where_the_offset_now_maps():
    tui, bar, _ = driven(100, 10, 45)
    bar.handle(press(19, 4))
    bar.handle(motion(19, 7))
    assert tui.viewport.offset == 75
    tui.paint()
    assert "".join(strip_texts(tui)) == "░░░░░░░░█░"


def test_a_drag_follows_the_pointer_past_the_strip_column():
    tui, bar, _ = driven(100, 10, 45)
    bar.handle(press(19, 4))
    assert bar.handle(motion(0, 7)) is True  # the pointer left the column
    assert tui.viewport.offset == 75


def test_a_drag_routes_the_painted_strip_cells_beside_a_stacked_separator():
    # The split's divider stacks outermost (by name), one column outside the
    # bar -- so the pane's outermost column is the separator's, and the
    # routing that guessed "outermost = the bar" consumed presses one cell
    # right of the strip the compositor painted: the visible track did not
    # drag at all.  The strip is the kernel's grant of the bar's own chrome,
    # the very cells the strip paints.
    tui = headless_tui(30, 10)
    tui.add(Rows(*many(100)))
    tui.paint()
    tui.scroll_up(100 - 10 - 45)
    bar = Scrollbar(tui)  # registered before the split, the demo's order
    tui.split("vertical", ratios=(2, 1))  # the separator stacks outside the bar
    tui.paint()
    left = tui.frame.pane("primary")
    assert left.rect.width == 20  # 18 viewport + the bar's column + the separator
    assert "█" in "".join(row.text[18] for row in tui.rows)  # the thumb paints at 18
    assert bar.handle(press(19, 4)) is False  # the separator's column is not the bar's
    assert bar.handle(press(18, 4)) is True  # the painted thumb cell is
    assert bar.handle(motion(18, 7)) is True
    assert left.viewport.offset == 75


def test_a_press_on_the_track_pages_down_and_repeats_while_held():
    tui, bar, now = driven(100, 10, 45)
    assert bar.handle(press(19, 9)) is True  # below the thumb at strip row 4
    assert tui.viewport.offset == 55  # one page: the window's own height
    tick(tui, now, 1)
    assert tui.viewport.offset == 65
    tick(tui, now, 3)  # 75, 85, then clamped at 90
    assert tui.viewport.offset == 90
    tick(tui, now, 5)  # the page that could not move stands the ticker down
    assert tui.viewport.offset == 90
    assert tui.tick(now[0]) is None  # no periodic callback left on the pump


def test_a_press_above_the_thumb_pages_up_and_stops_at_the_top():
    tui, bar, now = driven(100, 10, 45)
    assert bar.handle(press(19, 0)) is True
    assert tui.viewport.offset == 35
    tick(tui, now, 4)  # 25, 15, 5, then clamped at 0
    assert tui.viewport.offset == 0
    tick(tui, now, 3)
    assert tui.viewport.offset == 0


def test_a_press_on_an_unscrollable_strip_is_consumed_and_stands_down():
    tui, bar, now = driven(5, 10, 0)  # the document fits: no thumb, nothing to page
    assert bar.handle(press(19, 2)) is True
    tick(tui, now, 3)
    assert tui.viewport.offset == 0


def test_the_release_stops_the_held_page():
    tui, bar, now = driven(100, 10, 45)
    bar.handle(press(19, 9))
    tick(tui, now, 1)
    assert tui.viewport.offset == 65
    assert bar.handle(release(19, 9)) is True
    tick(tui, now, 5)
    assert tui.viewport.offset == 65


def test_a_pointer_that_leaves_the_strip_stands_the_held_page_down():
    tui, bar, now = driven(100, 10, 45)
    bar.handle(press(19, 9))
    tick(tui, now, 1)
    assert tui.viewport.offset == 65
    assert bar.handle(motion(0, 9)) is True  # consumed, but out of the strip
    assert bar.handle(release(0, 9)) is True  # the press was ours, so its release is
    tick(tui, now, 5)
    assert tui.viewport.offset == 65


def test_detach_stops_the_ticker_and_unregisters_the_bar():
    tui, bar, now = driven(100, 10, 45)
    bar.handle(press(19, 9))
    tick(tui, now, 1)
    bar.detach()
    assert tui.viewport.offset == 65
    tick(tui, now, 5)
    assert tui.viewport.offset == 65  # the ticker is gone
    tui.paint()
    assert strip_texts(tui) == [""] * 10  # the column is content again
    assert bar.handle(press(19, 9)) is False  # a detached bar stays detached


def test_detach_ends_an_in_flight_drag():
    tui, bar, _ = driven(100, 10, 45)
    bar.handle(press(19, 4))
    bar.handle(motion(19, 7))
    assert tui.viewport.offset == 75
    bar.detach()
    assert bar.handle(motion(19, 2)) is False
    assert tui.viewport.offset == 75


def test_the_bar_rides_a_resize_that_rebuilds_the_frame():
    tui, bar, _ = driven(100, 10, 45)
    tui.screen.width = 30  # the terminal resized; the next paint retiles the frame
    tui.paint()
    # The retile carried the chrome (the overlay registry's ride-along,
    # made symmetric for chrome): no event was needed to keep the strip.
    assert "".join(strip_texts(tui)) == "░░░░█░░░░░"
    assert bar.handle(press(29, 4)) is True  # the strip moved with the pane edge
    bar.handle(motion(29, 6))
    tui.paint()
    assert tui.viewport.offset > 45  # the anchored drag scrolled the pane


def test_a_bar_attached_before_the_first_paint_rides_the_retile():
    tui = headless_tui(20, 10)
    tui.add(Rows(*many(100)))
    bar = Scrollbar(tui)  # attached before the driver has painted once
    tui.paint()  # the placeholder rectangle is retiled on this first paint
    # No event ever fired: the strip is there because the rebuild carried it.
    assert "".join(strip_texts(tui)) == "░░░░░░░░░█"  # the window sits at offset 90
    assert bar.handle(Key("a", "a")) is False  # a key passes the bar straight through


@pytest.mark.parametrize(
    "event",
    [
        Key("a", "a"),
        Paste("pasted"),
        MouseEvent("middle", button=1, x=19, y=4),
        MouseEvent("right", button=2, x=19, y=4),
        MouseEvent("wheel_up", button=0, x=19, y=4),
        MouseEvent("wheel_down", button=1, x=19, y=4),
        MouseEvent("left", button=0, x=0, y=4),  # outside the strip column
        MouseEvent("left", button=0, x=19, y=4, kind="motion"),  # motion, no press
        MouseEvent("left", button=0, x=19, y=4, kind="release"),  # release, no press
        MouseEvent("left", button=0, x=19, y=4, kind="other"),
    ],
)
def test_handle_passes_everything_the_bar_does_not_own(event):
    tui, bar, _ = driven(100, 10, 45)
    assert bar.handle(event) is False
    assert tui.viewport.offset == 45

