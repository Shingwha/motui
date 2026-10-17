"""Tests for motui.chrome: the Scrollbar, Stats, Toasts and Tooltip overlays.

One test file per source file: this module carries all four of
:mod:`motui.chrome`'s exports, in the order ``chrome.__all__`` names them.
Each overlay is driven headlessly against a real :class:`~motui.app.TUI` --
the Scrollbar's strip geometry and its drag/page ticker, the Stats box's
readings under a replaced clock, the Toasts stack's corners, clamps, TTL and
dismiss routing, and the Tooltip's band (hint, flip, clamp, repoint).
Nothing sleeps: the documented ``clock`` seam and a recording screen stand in
for time and terminal, and every geometry is pinned as painted row text.

The four banners below mark the sections as they were written, one per
overlay; the doubles they share open the first banner, and each overlay's own
helpers stay with it.
"""

import pytest

from _doubles import Rows, many

from motui import Button, Key, MouseEvent, Paste, Pointer, Style, Theme, TUI
from motui.chrome import Scrollbar, Stats, Toasts, Tooltip
from motui.kernel import HeadlessScreen
from motui.kernel.lines import Line, Text
from motui.kernel.style import sgr_prefix
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


# === Stats =========================================================================


def _mounted(width: int = 40, height: int = 8):
    """A headless TUI with one Button block and a mounted Stats overlay."""
    tui = TUI(screen=HeadlessScreen(width, height), interactive=False)
    tui.add(Button("Ship"))
    tui.paint()
    return tui, Stats(tui, pointer=Pointer(tui))


def _box_rows(tui: TUI) -> list[str]:
    """The three box rows' stripped text (the box is the first three rows)."""
    return [row.text.strip() for row in tui.rows[:3]]


# --- lifecycle -----------------------------------------------------------------


def test_constructing_registers_the_overlay_and_detach_unregisters_it():
    """The Tooltip contract: constructed mounted, detach() idempotent."""
    tui = TUI(screen=HeadlessScreen(40, 8), interactive=False)
    before = len(tui.frame.overlays)
    stats = Stats(tui)
    assert len(tui.frame.overlays) == before + 1
    assert stats in tui.frame.overlays
    stats.detach()
    assert stats not in tui.frame.overlays
    assert len(tui.frame.overlays) == before
    stats.detach()  # idempotent: the registry is not charged twice
    assert stats not in tui.frame.overlays


def test_a_detached_overlay_paints_nothing_again():
    """After detach the corner is the pane's own again (the zero-byte case)."""
    tui, stats = _mounted()
    tui.paint()
    assert "frames " in tui.rows[0].text
    stats.detach()
    tui.paint()
    assert "frames " not in "".join(row.text for row in tui.rows)
    assert " Ship " in tui.rows[0].text


def test_a_frame_with_no_room_for_the_box_stays_total():
    """A screen with no column cannot host the box: painting never raises."""
    tui = TUI(screen=HeadlessScreen(0, 5), interactive=False)
    Stats(tui)
    tui.paint()
    assert all(not row.text for row in tui.rows)


# --- the readings ---------------------------------------------------------------


def test_handle_counts_every_event_and_names_the_last_one():
    """Every event counts -- key, mouse report, paste -- and answers True."""
    tui = TUI(screen=HeadlessScreen(40, 8), interactive=False)
    stats = Stats(tui)
    assert stats.events == 0 and stats.last == ""  # nothing counted yet
    assert stats.handle(Key("c-g")) is True  # the repaint cue, never a claim
    assert stats.handle(MouseEvent("left", button=0, x=1, y=2, kind="press")) is True
    assert stats.handle(Paste("two\nlines")) is True
    assert stats.events == 3
    assert stats.last == "paste"  # a paste carries no name of its own


def test_the_box_paints_in_the_top_right_corner_with_every_reading():
    """Three rows, flush right, carrying frames/fps, events/last and hover."""
    tui, stats = _mounted()
    stats.handle(Key("c-g"))
    stats.handle(Paste("no name of its own"))
    stats.pointer.handle(MouseEvent("none", button=0, x=1, y=0, kind="motion"))
    tui.paint()

    lines = [row.text for row in tui.rows[:3]]
    frames = tui.painter.frames - 1  # the frame being painted is not counted yet
    assert lines[0].rstrip().endswith(f"frames {frames}    0.0 fps")  # padded to the box
    assert lines[1].strip() == "events 2  last paste"
    assert lines[2].strip() == "hover Button (1, 0)"

    # Flush right: one left edge for the box, and every row ends at the edge.
    offsets = {len(line) - len(line.lstrip()) for line in lines[1:]}
    assert len(offsets) == 1
    assert {len(line) for line in lines} == {40}


def test_the_box_reads_the_hovered_leaf_and_the_pointer_cell():
    """The hover row follows the pointer's live state, cleared to ``--``."""
    tui, stats = _mounted()
    stats.pointer.handle(MouseEvent("none", button=0, x=1, y=0, kind="motion"))
    tui.paint()
    assert _box_rows(tui)[2] == "hover Button (1, 0)"
    stats.pointer.clear()  # a pane switch, a blur: the hover is gone
    tui.paint()
    assert _box_rows(tui)[2] == "hover --"


def test_a_host_can_point_the_overlay_at_a_rebuilt_pointer():
    """The demo rebuilds its pointer per page: the box follows the new one."""
    tui, stats = _mounted()
    fresh = Pointer(tui)
    stats.pointer = fresh  # the retarget the demo's page switch performs
    fresh.handle(MouseEvent("none", button=0, x=1, y=0, kind="motion"))
    tui.paint()
    assert _box_rows(tui)[2] == "hover Button (1, 0)"


def test_the_frame_rate_is_sampled_over_a_window_of_at_least_a_second():
    """The session's own arithmetic, driven by a replaced clock.

    Frames painted: one per ``paint()`` call, counted at composition time,
    so each line below reads the count *before* its own frame.
    """
    tui = TUI(screen=HeadlessScreen(40, 8), interactive=False)
    now = [100.0]
    tui.clock = lambda: now[0]  # the documented seam: a test replaces the clock
    stats = Stats(tui)
    tui.paint()
    tui.paint()  # two frames before the window opens
    assert stats.fps == 0.0
    now[0] = 102.0
    tui.paint()  # the window opens: 2 frames over 2 s
    assert stats.fps == pytest.approx(1.0)
    now[0] = 102.5
    tui.paint()  # half a second since the sample: too short a window to read
    assert stats.fps == pytest.approx(1.0)
    now[0] = 103.0
    tui.paint()  # a full second since the sample: 2 more frames over 1 s
    assert stats.fps == pytest.approx(2.0)


def test_the_band_follows_a_theme_change():
    """``set_theme`` repaints the box on the theme's ``toast`` band."""
    tui, stats = _mounted()
    band = Style(bg="#123456")
    stats.set_theme(Theme(toast=band))
    marker = len(tui.screen.output)
    tui.paint()
    assert sgr_prefix(band, "truecolor") in tui.screen.output[marker:]


# === Toasts ========================================================================


# --- helpers ------------------------------------------------------------------


def stack(tui, **knobs) -> Toasts:
    """A Toasts attached to an already-painted ``tui``."""
    toasts = Toasts(tui, **knobs)
    tui.paint()
    return toasts


def document(tui, texts):
    """Fill ``tui``'s document with ``texts`` and paint."""
    tui.add(Rows(*texts))
    tui.paint()


def clocked(tui, **knobs) -> tuple[Toasts, list[float]]:
    """A Toasts on ``tui`` with the documented ``clock`` seam installed.

    The seam is set *before the first frame*, so the pump paints on the
    injected clock -- a ``_last_paint`` left on the real clock would freeze
    the throttle.  The caller advances ``now[0]`` and fires the pump with
    ``tui.tick``.
    """
    now = [1000.0]
    tui.clock = lambda: now[0]
    toasts = Toasts(tui, **knobs)
    tui.paint()
    return toasts, now


def advance(tui, now: list[float], seconds: float) -> None:
    """Move the injected clock and fire the pump once at the new reading."""
    now[0] += seconds
    tui.tick(now[0])


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
    document(tui, many(4))
    stack(tui, corner=corner).show("hi")
    tui.paint()
    assert tui.rows[affected].text == expected
    # every other row is the document's own, untouched
    others = [index for index in range(4) if index != affected]
    assert [tui.rows[index].text for index in others] == [
        many(4)[index] for index in others
    ]


def test_the_stack_reads_newest_at_the_corner_with_one_blank_row_between():
    tui = headless_tui(10, 5)
    document(tui, many(5))
    toasts = stack(tui)
    toasts.show("old")
    toasts.show("new")
    tui.paint()
    assert tui.rows[0].text == "r0     new"  # the newest sits at the corner
    assert tui.rows[2].text == "r2     old"  # one blank row between neighbours
    assert tui.rows[1].text == "r1"  # the separator is the document's own row


def test_a_multi_row_component_band_covers_each_of_its_rows():
    tui = headless_tui(10, 4)
    document(tui, many(4))
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
    document(tui, many(3))
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
    document(tui, many(3))
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
    document(tui, many(4))
    toasts, now = clocked(tui, ttl=4.0)
    toasts.show("gone")
    tui.paint()
    assert tui.rows[0].text == "r0    gone"
    advance(tui, now, 5.0)
    tui.paint()
    assert [row.text for row in tui.rows] == many(4)  # the band is gone


def test_the_ticker_stands_down_once_the_last_toast_expires():
    tui = headless_tui(10, 2)
    toasts, now = clocked(tui, ttl=1.0)
    toasts.show("bye")
    advance(tui, now, 1.5)  # the tick drops it and cancels the ticker
    assert tui.tick(now[0]) is None  # no periodic callback left on the pump
    toasts.show("again")  # a later show arms the one ticker afresh
    assert toasts.handle(press(9, 0)) is True  # the band is live and dismissible
    advance(tui, now, 1.5)
    assert tui.tick(now[0]) is None


@pytest.mark.parametrize(
    ("max_shown", "shown", "expected"),
    [
        (3, 2, ["r0      m1", "r2      m0"]),  # the whole stack fits
        (3, 4, ["r0      m3", "r2      m2", "r4      m1"]),  # the oldest went
    ],
)
def test_max_shown_evicts_the_oldest_toasts(max_shown, shown, expected):
    tui = headless_tui(10, 8)
    document(tui, many(8))
    toasts = stack(tui, max_shown=max_shown)
    for index in range(shown):
        toasts.show(f"m{index}")
    tui.paint()
    painted = [tui.rows[row].text for row in range(0, 2 * len(expected), 2)]
    assert painted == expected


def test_a_press_inside_a_toast_drops_that_toast_only():
    tui = headless_tui(10, 4)
    document(tui, many(4))
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
    assert [row.text for row in tui.rows] == many(4)


def test_a_press_outside_every_toast_passes_through():
    tui = headless_tui(10, 4)
    document(tui, many(4))
    toasts = stack(tui)
    toasts.show("keep")  # a four-wide band: columns 6-9 of row 0
    tui.paint()
    assert toasts.handle(press(0, 0)) is False  # the document is under the pointer
    assert toasts.handle(press(5, 0)) is False  # one column short of the band
    tui.paint()
    assert tui.rows[0].text == "r0    keep"


def test_a_press_inside_a_bottom_corner_toast_drops_it():
    tui = headless_tui(10, 3)
    document(tui, many(3))
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
    document(tui, many(2))
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
    document(tui, many(2))
    toasts, now = clocked(tui, ttl=1.0)
    toasts.show("gone")
    tui.paint()
    toasts.detach()
    # The documented frame seam (chrome.py's module docstring): the
    # unregister is real -- no inert overlay rides the registry.
    assert all(held is not toasts for held in tui.frame.overlays)
    tui.paint()
    assert [row.text for row in tui.rows] == many(2)  # the band left the frame
    toasts.show("ignored")  # a detached controller stays detached
    tui.paint()
    assert [row.text for row in tui.rows] == many(2)
    assert toasts.handle(press(8, 0)) is False
    advance(tui, now, 5.0)
    assert tui.tick(now[0]) is None  # the ticker is gone
    toasts.detach()  # idempotent


def test_the_controller_stays_attached_through_a_retile():
    tui = headless_tui(20, 3)
    document(tui, many(3))
    toasts = stack(tui, corner="bottom-right")
    toasts.show("stay")
    tui.screen.width = 30  # the terminal resized; the next paint retiles
    tui.paint()
    assert tui.rows[2].text == "r2" + " " * 24 + "stay"
    assert toasts.handle(press(29, 2)) is True  # the band moved with the edge
    tui.paint()
    assert tui.rows[2].text == "r2"


def test_a_controller_attached_before_the_first_paint_rides_the_retile():
    tui = headless_tui(20, 3)
    document(tui, many(3))
    toasts = Toasts(tui, corner="bottom-left")  # attached before the first paint
    tui.paint()  # the placeholder rectangle is retiled on this first paint
    toasts.show("here")
    tui.paint()
    # No event ever fired: the band is there because the rebuild carried the
    # overlay registration across, the way it carries the selection overlay's.
    assert tui.rows[2].text == "here" + " " * 16
    assert toasts.handle(press(0, 2)) is True  # the routing follows the band


# === Tooltip =======================================================================


# --- helpers ------------------------------------------------------------------


class Leaf:
    """A hoverable leaf: rows of text, and a ``hint`` when one is asked for."""

    def __init__(self, *, rows: int = 1, hint: object = None, has_hint: bool = True):
        self.hover = False
        self.rows = rows
        if has_hint:
            self.hint = hint

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(f"leaf{i}") for i in range(self.rows)]


def hover_motion(x: int, y: int) -> MouseEvent:
    """The button-free motion a 1003 host sees (the decoder's normalized 35)."""
    return MouseEvent("none", button=0, x=x, y=y, kind="motion")


def mounted(leaf, *, width: int = 30, height: int = 6, theme=None):
    """A painted TUI with ``leaf`` mounted, a Pointer over it, and a Tooltip."""
    tui = headless_tui(width, height)
    tui.add(leaf)
    tui.paint()
    pointer = Pointer(tui)
    tooltip = Tooltip(tui, pointer, theme=theme)
    return tui, pointer, tooltip


def rows_text(tui) -> list[str]:
    return [row.text for row in tui.rows]


# --- the paint -------------------------------------------------------------------


def test_a_hint_paints_a_one_row_band_under_the_pointers_cell():
    leaf = Leaf(rows=2, hint="press enter to ship")
    tui, pointer, _ = mounted(leaf)
    pointer.handle(hover_motion(2, 1))  # over the leaf's second row
    tui.paint()
    assert tui.rows[1].text == "leaf1"  # the pointer's own row is spared
    assert tui.rows[2].text.rstrip() == "  press enter to ship"
    assert tui.rows[0].text == "leaf0"


@pytest.mark.parametrize(
    "leaf",
    [
        Leaf(has_hint=False),  # no hint attribute at all
        Leaf(hint=""),  # an empty hint is no hint
        Leaf(hint=5),  # a non-str hint is not read as one
        Leaf(hint=None),  # nor is None
    ],
)
def test_a_leaf_without_a_usable_hint_paints_nothing(leaf):
    tui, pointer, _ = mounted(leaf)
    before = rows_text(tui)
    pointer.handle(hover_motion(2, 0))
    tui.paint()
    assert rows_text(tui) == before


def test_a_pointer_that_never_moved_paints_nothing():
    leaf = Leaf(rows=2, hint="hidden")
    tui, _, _ = mounted(leaf)
    tui.paint()
    assert [row.text for row in tui.rows[:3]] == ["leaf0", "leaf1", ""]


def test_moving_off_the_leaf_takes_the_band_away():
    leaf = Leaf(hint="here")
    tui, pointer, _ = mounted(leaf, height=4)
    pointer.handle(hover_motion(2, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "  here"
    pointer.handle(hover_motion(2, 3))  # a blank cell: nothing is hovered any more
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", "", ""]


def test_the_band_flips_above_a_pointer_on_the_last_row():
    leaf = Leaf(rows=3, hint="<<flip>>")
    tui, pointer, _ = mounted(leaf, height=3)
    pointer.handle(hover_motion(1, 1))  # room below: the band goes there
    tui.paint()
    assert "<<flip>>" in tui.rows[2].text
    tui.screen.height = 2  # the pointer's row is the last one now
    pointer.handle(hover_motion(1, 1))
    tui.paint()
    assert "<<flip>>" in tui.rows[0].text  # the band flipped above it
    assert "<<flip>>" not in tui.rows[1].text


def test_the_band_is_clamped_into_the_frames_width():
    leaf = Leaf(hint="nineteen characters")
    tui, pointer, _ = mounted(leaf, width=20, height=3)
    pointer.handle(hover_motion(18, 0))  # near the right edge: the band clamps left
    tui.paint()
    assert tui.rows[1].text == " nineteen characters"[:20]
    assert len(tui.rows[1].text) == 20


def test_a_hint_wider_than_a_narrow_frame_is_fit_to_it():
    leaf = Leaf(hint="a long hint")
    tui, pointer, _ = mounted(leaf, width=1, height=2)
    pointer.handle(hover_motion(0, 0))
    tui.paint()
    assert len(tui.rows[1].text) == 1  # never wider than the frame


# --- the band's style ---------------------------------------------------------------


def test_the_band_paints_with_the_themes_toast_style():
    leaf = Leaf(hint="hi")
    band = Style(fg="#333333")
    tui, pointer, _ = mounted(leaf, theme=Theme(toast=band))
    pointer.handle(hover_motion(0, 0))
    tui.paint()
    assert band in [seg.style for seg in tui.rows[1].segments]


# --- the lifecycle ------------------------------------------------------------------


def test_detach_unregisters_the_overlay_and_stops_the_paint():
    leaf = Leaf(hint="gone")
    tui, pointer, tooltip = mounted(leaf, height=3)
    assert any(held is tooltip for held in tui.frame.overlays)
    pointer.handle(hover_motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "gone"  # the band is live
    tooltip.detach()
    assert all(held is not tooltip for held in tui.frame.overlays)
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", ""]  # the band left the frame
    tooltip.detach()  # idempotent


def test_a_hint_changed_under_a_live_pointer_shows_on_the_next_frame():
    leaf = Leaf(hint="old")
    tui, pointer, _ = mounted(leaf, height=4)
    pointer.handle(hover_motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "old"
    leaf.hint = "new"  # the leaf restyles itself; the overlay caches nothing
    tui.paint()
    assert tui.rows[1].text.rstrip() == "new"


def test_a_host_repoints_the_band_by_mounting_the_new_pointers_tooltip():
    """The demo's own rule: a page switch mounts a fresh pair."""
    leaf = Leaf(hint="left pane")
    tui, pointer, tooltip = mounted(leaf, height=3)
    pointer.handle(hover_motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "left pane"
    tooltip.detach()  # the retarget: the old pointer's band goes with it
    fresh = Pointer(tui)
    Tooltip(tui, fresh)
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", ""]  # the fresh pointer saw no motion
    fresh.handle(hover_motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "left pane"
