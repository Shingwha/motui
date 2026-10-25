"""Scrollbar: the strip geometry, the thumb drag, track paging and lifecycle."""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.app import Scrollbar, ScrollbarStyles
from motui.kernel import Axis, Style, Theme
from motui.kernel.document import Placement
from motui.kernel.events import MouseEvent, PasteEvent
from motui.kernel.frame import SEPARATOR_CHROME_NAME, Chrome
from motui.kernel.glyphs import GLYPHS
from motui.kernel.cell import Line, Surface
from motui.widgets import ScrollPanel
from motui.widgets.text import Text
from tests.testing import (
    Clock,
    Rows,
    headless_tui,
    key,
    many,
    motion,
    press,
    release,
    tick,
)


class Wide:
    """A component whose one row is 200 columns wide (an OVERFLOW producer)."""

    def render(self, c):
        return Surface.of([Line.from_text("x" * 200)], 200, pad=False)


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


# -- geometry ----------------------------------------------------------------


def test_the_strip_is_the_scrolling_window_between_pinned_regions():
    tui = headless_tui(20, 10)
    tui.add(Rows("head"), id="head", placement=Placement.TOP)
    tui.add(Rows(*many(100)))
    tui.add(Rows("foot one", "foot two"), id="foot", placement=Placement.BOTTOM)
    tui.paint()
    tui.viewport.scroll_up(tui.viewport.offset)  # detach the tail, show the top
    tui.paint()
    bar(tui)
    # The window is rows 1..7 (10 - 1 top - 2 bottom); the pinned rows keep
    # the column empty.  The thumb is one row at the window's top edge.
    strip = [row.text[19] for row in tui.rows]
    assert strip == [" ", "\u2588", *"\u2591" * 6, " ", " "]


def test_a_pane_filled_by_fixed_regions_paints_no_strip():
    tui = headless_tui(20, 10)
    tui.add(Rows(*many(12)), id="foot", placement=Placement.BOTTOM)
    tui.paint()
    strip = bar(tui)
    assert strip_texts(tui) == [" "] * 10
    assert strip.handle(press(19, 5)) is False


def test_a_press_over_a_pinned_region_is_not_the_bars():
    tui = headless_tui(20, 10)
    tui.add(Rows(*many(100)))
    tui.add(Rows("foot one", "foot two"), id="foot", placement=Placement.BOTTOM)
    tui.paint()
    strip = bar(tui)
    assert strip.handle(press(19, 8)) is False
    assert strip.handle(press(19, 9)) is False
    assert strip.handle(press(19, 4)) is True


def test_a_divider_and_a_bar_stack_on_a_shared_edge():
    tui = headless_tui(30, 10)
    tui.add(Rows(*many(100)))
    tui.add(Rows("foot one", "foot two"), id="foot", placement=Placement.BOTTOM)
    tui.paint()
    Scrollbar(tui)
    tui.split(Axis.X, weights=(2, 1), separator=False)
    left = tui.frame.pane("primary")
    # The separator stacks outermost whatever else sits on the edge, so the
    # divider owns the split's last column and the bar's window the one
    # beside it: a pane-scoped band spans every row, a body-scoped band the
    # window's rows only (the pinned footer keeps the column empty).
    left.add_chrome(
        Chrome(
            "right",
            1,
            lambda layout, length: [Line.from_text("|")] * length,
            name=SEPARATOR_CHROME_NAME,
        )
    )
    tui.paint()
    edge = [row.text[19] for row in tui.rows]
    inner = [row.text[18] for row in tui.rows]
    assert edge == ["|"] * 10
    assert inner == ["\u2591"] * 7 + ["\u2588"] + [" "] * 2


def test_the_bar_budgets_its_column_and_the_pane_rewraps_beside_it():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    assert [row.text for row in tui.rows] == ["0123456789", ""]
    bar(tui)
    assert [row.text for row in tui.rows] == ["012345678\u2591", "9        \u2591"]


def test_custom_glyphs_paint_the_strip():
    tui = scrolled(100, 10, 45)
    bar(tui, glyphs=replace(GLYPHS, bar_empty=".", bar_full="#"))
    assert "".join(strip_texts(tui)) == "....#....."

    wide = scrolled(100, 10, 45)
    bar(wide, size=2, glyphs=replace(GLYPHS, bar_empty="=", bar_full="X"))
    assert [row.text[-2:] for row in wide.rows] == ["=="] * 4 + ["XX"] + ["=="] * 5


def test_an_empty_glyph_paints_the_reserved_column_empty():
    tui = headless_tui(10, 2)
    tui.add(Text("0123456789"))
    tui.paint()
    bar(tui, glyphs=replace(GLYPHS, bar_empty="", bar_full=""))
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


def test_a_drag_routes_the_painted_strip_beside_a_stacked_separator():
    tui = headless_tui(30, 10)
    tui.add(Rows(*many(100)))
    tui.paint()
    tui.scroll_up(100 - 10 - 45)
    strip = Scrollbar(tui)
    tui.split(Axis.X, weights=(2, 1))
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


def test_the_bar_rides_a_resize():
    tui, strip, _ = driven(100, 10, 45)
    tui.screen.width = 30
    tui.paint()
    assert "".join(strip_texts(tui)) == "\u2591\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591"
    assert strip.handle(press(29, 4)) is True
    strip.handle(motion(29, 6, "left"))
    tui.paint()
    assert tui.viewport.offset > 45


def test_the_strip_paints_the_thumb_the_geometry_maps():
    cases = (
        (100, 10, 0, "\u2588" + "\u2591" * 9),
        (100, 10, 45, "\u2591" * 4 + "\u2588" + "\u2591" * 5),
        (100, 10, 90, "\u2591" * 9 + "\u2588"),
        (11, 2, 4, "\u2588\u2591"),
        (11, 2, 5, "\u2591\u2588"),
        (5, 10, 0, "\u2591" * 10),
        (0, 10, 0, "\u2591" * 10),
    )
    for total, height, offset, expected in cases:
        tui = scrolled(total, height, offset)
        bar(tui)
        assert "".join(strip_texts(tui)) == expected


def test_min_thumb_sets_the_shortest_thumb():
    for min_thumb, expected in (
        (1, "\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591\u2591"),
        (3, "\u2591\u2591\u2588\u2588\u2588\u2591\u2591\u2591\u2591\u2591"),
        (10, "\u2588" * 10),
        (0, "\u2591\u2591\u2591\u2588\u2591\u2591\u2591\u2591\u2591\u2591"),
    ):
        tui = scrolled(100, 10, 30)
        bar(tui, min_thumb=min_thumb)
        assert "".join(strip_texts(tui)) == expected


def test_the_styles_resolve_explicit_then_theme():
    cases = (
        (
            {
                "styles": ScrollbarStyles(
                    track=Style(fg="#111111"), thumb=Style(fg="#222222")
                )
            },
            "#111111",
            "#222222",
        ),
        (
            {
                "theme": Theme(
                    chrome=replace(
                        Theme().chrome,
                        scrollbar=Style(fg="#333333"),
                        scrollbar_thumb=Style(fg="#444444"),
                    )
                )
            },
            "#333333",
            "#444444",
        ),
    )
    for knobs, track_fg, thumb_fg in cases:
        tui = scrolled(100, 10, 45)
        bar(tui, **knobs)
        painted = {}
        for row in tui.rows:
            for segment in row.segments:
                if segment.text and segment.text[-1] in (
                    GLYPHS.bar_empty,
                    GLYPHS.bar_full,
                ):
                    painted[segment.text[-1]] = segment.style
        assert painted[GLYPHS.bar_empty].fg == track_fg
        assert painted[GLYPHS.bar_full].fg == thumb_fg


def test_a_drag_maps_the_pointer_row_to_the_offset():
    for total, offset, press_row, motion_row, expected in (
        (100, 45, 4, 4, 45),
        (100, 45, 4, 7, 75),
        (100, 45, 4, 9, 90),
        (20, 5, 4, 6, 9),
    ):
        tui, strip, _ = driven(total, 10, offset)
        assert strip.handle(press(19, press_row)) is True
        assert strip.handle(motion(19, motion_row, "left")) is True
        assert tui.viewport.offset == expected


def test_a_drag_maps_the_window_not_the_pane():
    # Window 8 of a 10-row pane at offset 8: the thumb is 3 rows of 5 travel
    # (not 3 of 7), so two strip rows are 6.4 document rows, not 4.6 -- the
    # old, pane-tall mapping would have answered 13 here, not 14.
    tui = headless_tui(20, 10)
    tui.add(Rows(*many(24)))
    tui.add(Rows("foot one", "foot two"), id="foot", placement=Placement.BOTTOM)
    tui.paint()
    tui.viewport.scroll_to(8)
    tui.paint()
    strip = bar(tui)
    assert strip.handle(press(19, 4)) is True
    assert strip.handle(motion(19, 6, "left")) is True
    assert tui.viewport.offset == 14


def test_handle_passes_everything_the_bar_does_not_own():
    for event in (
        key("a", "a"),
        PasteEvent("pasted"),
        MouseEvent("middle", x=19, y=4),
        MouseEvent("wheel_up", x=19, y=4, kind="wheel"),
        MouseEvent("left", x=0, y=4),
        MouseEvent("left", x=19, y=4, kind="motion"),
        MouseEvent("left", x=19, y=4, kind="release"),
    ):
        tui, strip, _ = driven(100, 10, 45)
        assert strip.handle(event) is False
        assert tui.viewport.offset == 45


def test_the_release_stops_the_held_page():
    tui, strip, clock = driven(100, 10, 45)
    strip.handle(press(19, 9))
    tick(tui, clock, 1)
    assert tui.viewport.offset == 65
    assert strip.handle(release(19, 9)) is True
    tick(tui, clock, 5)
    assert tui.viewport.offset == 65


# -- the horizontal bar (axis=Axis.X) ----------------------------------------


def test_a_horizontal_bar_paints_the_targets_x_geometry():
    tui = headless_tui(80, 6)
    panel = ScrollPanel(Wide(), axis="x", height=3)
    tui.add(panel)
    tui.paint()
    strip = Scrollbar(tui, axis=Axis.X)
    tui.paint()
    # 80-column viewport over 200 columns: a 32-cell thumb with 48 cells of
    # travel, at the left edge first and the right edge at the end.
    assert tui.rows[-1].text == "\u2588" * 32 + "\u2591" * 48
    assert panel.scroll_x_to_end() is True
    tui.paint()
    assert tui.rows[-1].text == "\u2591" * 48 + "\u2588" * 32
    strip.detach()


def test_the_horizontal_bar_resolves_an_explicit_or_unique_target():
    empty = headless_tui(20, 4)
    empty.add(Text("abc"))
    empty.paint()
    with pytest.raises(ValueError):
        Scrollbar(empty, axis=Axis.X)

    ambiguous = headless_tui(20, 4)
    ambiguous.add(ScrollPanel(Text("a"), axis="x"))
    ambiguous.add(ScrollPanel(Text("b"), axis="x"))
    ambiguous.paint()
    with pytest.raises(ValueError):
        Scrollbar(ambiguous, axis=Axis.X)

    # An explicit target answers even when it is not in the pane's document;
    # before its first render it has no extent, so the strip is plain track.
    target = ScrollPanel(Wide(), axis="x", height=1)
    tui = headless_tui(20, 4)
    tui.add(Text("abc"))
    tui.paint()
    strip = Scrollbar(tui, axis=Axis.X, target=target)
    tui.paint()
    assert tui.rows[-1].text == "\u2591" * 20
    strip.detach()


def test_the_horizontal_bar_declines_every_event():
    tui = headless_tui(20, 4)
    tui.add(ScrollPanel(Wide(), axis="x", height=1))
    tui.paint()
    strip = Scrollbar(tui, axis=Axis.X)
    tui.paint()
    for event in (
        press(0, 3),
        motion(0, 2, "left"),
        release(0, 3),
        key("a", "a"),
        MouseEvent("wheel_down", x=0, y=3, kind="wheel"),
    ):
        assert strip.handle(event) is False
    assert repr(strip).endswith("axis=x)")


def test_the_horizontal_bar_gives_its_row_back_on_detach():
    tui = headless_tui(20, 6)
    tui.add(Rows(*many(20)))
    tui.paint()
    strip = Scrollbar(tui, axis=Axis.X, target=ScrollPanel(Wide(), axis="x"))
    tui.paint()
    assert tui.rows[-1].text == "\u2591" * 20
    strip.detach()
    tui.paint()
    assert tui.rows[-1].text == "r19"
