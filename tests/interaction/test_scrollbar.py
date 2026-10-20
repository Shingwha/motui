"""Scrollbar: the strip geometry, the thumb drag, track paging and lifecycle."""

from __future__ import annotations

import pytest

from motui.interaction import Scrollbar
from motui.kernel import Style, Theme
from motui.kernel import glyphs
from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent
from motui.kernel.lines import Text
from tests.testing import Clock, Rows, headless_tui, key, many, motion, press, release


def strip_texts(tui, width: int = 1) -> list[str]:
    return [row.text[tui.screen.width - width :] for row in tui.rows]


def bar(tui, **knobs) -> Scrollbar:
    strip = Scrollbar(tui, **knobs)
    tui.paint()
    return strip


def scrolled(total: int, height: int, offset: int):
    tui = headless_tui(20, height)
    tui.add(Rows(*many(total)))
    tui.paint()
    tui.scroll_up(total - height - offset)
    tui.paint()
    return tui


def driven(total: int, height: int, offset: int, **knobs):
    tui = headless_tui(20, height)
    tui.add(Rows(*many(total)))
    clock = Clock(1000.0).install(tui)
    tui.paint()
    tui.scroll_up(total - height - offset)
    tui.paint()
    strip = Scrollbar(tui, **knobs)
    tui.paint()
    return tui, strip, clock


def tick(tui, clock: Clock, count: int = 1, seconds: float = 0.05) -> None:
    for _ in range(count):
        clock.advance(seconds)
        tui.tick(clock())


# -- geometry ----------------------------------------------------------------


@pytest.mark.parametrize(
    "total,height,offset,expected",
    [
        (100, 10, 0, "\u2588\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591"),
        (100, 10, 45, "\u2591\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591"),
        (100, 10, 85, "\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2588\u2591"),
        (100, 10, 90, "\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2588"),
        (1000, 10, 400, "\u2591\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591"),
        (11, 2, 4, "\u2588\u2591"),
        (11, 2, 5, "\u2591\u2588"),
        (5, 10, 0, "\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591"),
        (0, 10, 0, "\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591"),
    ],
)
def test_the_strip_paints_the_thumb_the_geometry_maps(total, height, offset, expected):
    tui = scrolled(total, height, offset)
    bar(tui)
    assert "".join(strip_texts(tui)) == expected


def test_the_strip_runs_the_whole_pane_height_including_a_pinned_footer():
    tui = headless_tui(20, 10)
    tui.add(Rows(*many(100)))
    tui.add(Rows("foot one", "foot two"), id="foot", pin="bottom")
    tui.paint()
    bar(tui)
    assert "".join(strip_texts(tui)) == "\u2591" * 9 + "\u2588"
    assert tui.rows[9].text[19] == "\u2588"


def test_the_bar_budgets_its_column_and_the_pane_rewraps_beside_it():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    assert [row.text for row in tui.rows] == ["0123456789", ""]
    bar(tui)
    assert [row.text for row in tui.rows] == ["012345678\u2591", "9        \u2591"]


def test_a_two_column_strip_paints_two_wide_rows():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    bar(tui, size=2)
    assert [row.text for row in tui.rows] == [
        "01234567\u2591\u2591",
        "89      \u2591\u2591",
    ]


@pytest.mark.parametrize(
    "min_thumb,expected",
    [
        (1, "\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591\u2591"),
        (3, "\u2591\u2591\u2588\u2588\u2588\u2591\u2591\u2591\u2591\u2591"),
        (10, "\u2588" * 10),
        (0, "\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591\u2591"),
    ],
)
def test_min_thumb_sets_the_shortest_thumb(min_thumb: int, expected: str):
    tui = scrolled(100, 10, 30)
    bar(tui, min_thumb=min_thumb)
    assert "".join(strip_texts(tui)) == expected


def test_a_very_long_document_shaves_the_thumb_away():
    tui = scrolled(1000, 10, 30)
    bar(tui, min_thumb=0)
    assert "".join(strip_texts(tui)) == "\u2591" * 10


@pytest.mark.parametrize(
    "knobs,track,thumb",
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
def test_the_styles_resolve_explicit_then_theme(knobs, track, thumb):
    tui = scrolled(100, 10, 45)
    bar(tui, **knobs)
    assert tui.rows[0].segments[-1].style.fg == track
    assert tui.rows[4].segments[-1].style.fg == thumb


def test_the_default_glyphs_are_the_vocabularys_track_and_thumb():
    tui = scrolled(100, 10, 45)
    bar(tui)
    assert "".join(strip_texts(tui)) == (
        f"{glyphs.TRACK * 4}{glyphs.THUMB}{glyphs.TRACK * 5}"
    )


def test_custom_glyphs_paint_the_strip():
    tui = scrolled(100, 10, 45)
    bar(tui, track=".", thumb="#")
    assert "".join(strip_texts(tui)) == "....#....."

    wide = scrolled(100, 10, 45)
    bar(wide, size=2, track="=", thumb="X")
    assert [row.text[-2:] for row in wide.rows] == ["=="] * 4 + ["XX"] + ["=="] * 5


def test_an_empty_glyph_paints_the_reserved_column_empty():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    bar(tui, track="", thumb="")
    assert [row.text for row in tui.rows] == ["012345678 ", "9         "]


# -- lifecycle ---------------------------------------------------------------


def test_construct_registers_the_strip_and_detach_gives_the_column_back():
    tui = headless_tui(10, 3)
    tui.add(Text("0123456789"))
    tui.paint()
    strip = bar(tui)
    assert [row.text for row in tui.rows] == [
        "012345678\u2591",
        "9        \u2591",
        "         \u2591",
    ]
    strip.detach()
    tui.paint()
    assert [row.text for row in tui.rows] == ["0123456789", "", ""]
    strip.detach()


def test_the_pane_knob_selects_a_pane_and_an_unknown_id_raises():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    bar(tui, pane="primary")
    assert [row.text for row in tui.rows] == ["012345678\u2591", "9        \u2591"]
    with pytest.raises(ValueError):
        Scrollbar(tui, pane="nowhere")


# -- the gesture -------------------------------------------------------------


@pytest.mark.parametrize(
    "total,offset,press_row,motion_row,expected",
    [
        (100, 45, 4, 4, 45),
        (100, 45, 4, 7, 75),
        (100, 45, 4, 2, 25),
        (100, 45, 4, 9, 90),
        (20, 5, 4, 6, 9),
    ],
)
def test_a_drag_maps_the_pointer_row_to_the_offset(
    total, offset, press_row, motion_row, expected
):
    tui, strip, _ = driven(total, 10, offset)
    assert strip.handle(press(19, press_row)) is True
    assert strip.handle(motion(19, motion_row, "left")) is True
    assert tui.viewport.offset == expected


def test_a_drag_repaints_the_thumb_where_the_offset_now_maps():
    tui, strip, _ = driven(100, 10, 45)
    strip.handle(press(19, 4))
    strip.handle(motion(19, 7, "left"))
    assert tui.viewport.offset == 75
    tui.paint()
    assert "".join(strip_texts(tui)) == "\u2591" * 8 + "\u2588\u2591"


def test_a_drag_follows_the_pointer_past_the_strip_column():
    tui, strip, _ = driven(100, 10, 45)
    strip.handle(press(19, 4))
    assert strip.handle(motion(0, 7, "left")) is True
    assert tui.viewport.offset == 75


def test_a_drag_routes_the_painted_strip_beside_a_stacked_separator():
    tui = headless_tui(30, 10)
    tui.add(Rows(*many(100)))
    tui.paint()
    tui.scroll_up(100 - 10 - 45)
    strip = Scrollbar(tui)
    tui.split("vertical", ratios=(2, 1))
    tui.paint()
    left = tui.frame.pane("primary")
    assert left.rect.width == 20
    assert "\u2588" in "".join(row.text[18] for row in tui.rows)
    assert strip.handle(press(19, 4)) is False
    assert strip.handle(press(18, 4)) is True
    assert strip.handle(motion(18, 7, "left")) is True
    assert left.viewport.offset == 75


def test_a_track_press_pages_down_and_repeats_while_held():
    tui, strip, clock = driven(100, 10, 45)
    assert strip.handle(press(19, 9)) is True
    assert tui.viewport.offset == 55
    tick(tui, clock, 1)
    assert tui.viewport.offset == 65
    tick(tui, clock, 3)
    assert tui.viewport.offset == 90
    tick(tui, clock, 5)
    assert tui.viewport.offset == 90
    assert tui.tick(clock()) is None


def test_a_track_press_above_the_thumb_pages_up_and_stops_at_the_top():
    tui, strip, clock = driven(100, 10, 45)
    assert strip.handle(press(19, 0)) is True
    assert tui.viewport.offset == 35
    tick(tui, clock, 4)
    assert tui.viewport.offset == 0
    tick(tui, clock, 3)
    assert tui.viewport.offset == 0


def test_a_press_on_an_unscrollable_strip_is_consumed_and_stands_down():
    tui, strip, clock = driven(5, 10, 0)
    assert strip.handle(press(19, 2)) is True
    tick(tui, clock, 3)
    assert tui.viewport.offset == 0


def test_the_release_stops_the_held_page():
    tui, strip, clock = driven(100, 10, 45)
    strip.handle(press(19, 9))
    tick(tui, clock, 1)
    assert tui.viewport.offset == 65
    assert strip.handle(release(19, 9)) is True
    tick(tui, clock, 5)
    assert tui.viewport.offset == 65


def test_a_pointer_leaving_the_strip_stands_the_held_page_down():
    tui, strip, clock = driven(100, 10, 45)
    strip.handle(press(19, 9))
    tick(tui, clock, 1)
    assert strip.handle(motion(0, 9, "left")) is True
    assert strip.handle(release(0, 9)) is True
    tick(tui, clock, 5)
    assert tui.viewport.offset == 65


def test_detach_stops_the_ticker_and_unregisters_the_bar():
    tui, strip, clock = driven(100, 10, 45)
    strip.handle(press(19, 9))
    tick(tui, clock, 1)
    strip.detach()
    assert tui.viewport.offset == 65
    tick(tui, clock, 5)
    assert tui.viewport.offset == 65
    tui.paint()
    assert strip_texts(tui) == [""] * 10
    assert strip.handle(press(19, 9)) is False


def test_detach_ends_an_in_flight_drag():
    tui, strip, _ = driven(100, 10, 45)
    strip.handle(press(19, 4))
    strip.handle(motion(19, 7, "left"))
    assert tui.viewport.offset == 75
    strip.detach()
    assert strip.handle(motion(19, 2, "left")) is False
    assert tui.viewport.offset == 75


def test_the_bar_rides_a_resize():
    tui, strip, _ = driven(100, 10, 45)
    tui.screen.width = 30
    tui.paint()
    assert "".join(strip_texts(tui)) == "\u2591\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591"
    assert strip.handle(press(29, 4)) is True
    strip.handle(motion(29, 6, "left"))
    tui.paint()
    assert tui.viewport.offset > 45


def test_a_bar_attached_before_the_first_paint_rides_the_retile():
    tui = headless_tui(20, 10)
    tui.add(Rows(*many(100)))
    strip = Scrollbar(tui)
    tui.paint()
    assert "".join(strip_texts(tui)) == "\u2591" * 9 + "\u2588"
    assert strip.handle(KeyEvent("a", "a")) is False


@pytest.mark.parametrize(
    "event",
    [
        key("a", "a"),
        PasteEvent("pasted"),
        MouseEvent("middle", x=19, y=4),
        MouseEvent("wheel_up", x=19, y=4, kind="wheel"),
        MouseEvent("left", x=0, y=4),
        MouseEvent("left", x=19, y=4, kind="motion"),
        MouseEvent("left", x=19, y=4, kind="release"),
    ],
)
def test_handle_passes_everything_the_bar_does_not_own(event):
    tui, strip, _ = driven(100, 10, 45)
    assert strip.handle(event) is False
    assert tui.viewport.offset == 45
