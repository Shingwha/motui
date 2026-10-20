"""Frame overlays: the stats box, the toast stack and the pointer tooltip."""

from __future__ import annotations

import pytest

from motui import Button
from motui.interaction import Pointer, Stats, Toasts, Tooltip
from motui.kernel import HeadlessScreen, Style, Theme, Text
from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent
from motui.kernel.lines import Line
from motui.kernel.style import sgr_prefix
from tests.testing import Clock, Rows, headless_tui, key, many, press


# === Stats ==================================================================


def mounted(width: int = 40, height: int = 8):
    tui = headless_tui(width, height)
    tui.add(Button("Ship"))
    tui.paint()
    return tui, Stats(tui, pointer=Pointer(tui))


def box_rows(tui) -> list[str]:
    return [row.text.strip() for row in tui.rows[:3]]


def test_stats_registers_on_construction_and_detach_unregisters():
    tui = headless_tui(40, 8)
    before = len(tui.frame.overlays)
    stats = Stats(tui)
    assert len(tui.frame.overlays) == before + 1
    assert stats in tui.frame.overlays
    stats.detach()
    assert stats not in tui.frame.overlays
    stats.detach()
    assert stats not in tui.frame.overlays


def test_a_detached_stats_box_paints_nothing_again():
    tui, stats = mounted()
    tui.paint()
    assert "frames " in tui.rows[0].text
    stats.detach()
    tui.paint()
    assert "frames " not in "".join(row.text for row in tui.rows)
    assert " Ship " in tui.rows[0].text


def test_a_frame_with_no_room_for_the_box_stays_total():
    tui = headless_tui(0, 5)
    Stats(tui)
    tui.paint()
    assert all(not row.text for row in tui.rows)


def test_handle_counts_every_event_and_names_the_last_one():
    tui = headless_tui(40, 8)
    stats = Stats(tui)
    assert stats.events == 0 and stats.last == ""
    assert stats.handle(KeyEvent("c-g")) is True
    assert stats.handle(MouseEvent("left", x=1, y=2, kind="press")) is True
    assert stats.handle(PasteEvent("two\nlines")) is True
    assert stats.events == 3
    assert stats.last == "paste"


def test_the_box_paints_in_the_top_right_corner_with_every_reading():
    tui, stats = mounted()
    stats.handle(KeyEvent("c-g"))
    stats.handle(PasteEvent("no name"))
    stats.pointer.handle(MouseEvent("none", x=1, y=0, kind="motion"))
    tui.paint()

    lines = [row.text for row in tui.rows[:3]]
    frames = tui.painter.frames - 1
    assert lines[0].rstrip().endswith(f"frames {frames}    0.0 fps")
    assert lines[1].strip() == "events 2  last paste"
    assert lines[2].strip() == "hover Button (1, 0)"
    assert {len(line) for line in lines} == {40}


def test_the_box_reads_the_hovered_leaf_and_clears_to_placeholder():
    tui, stats = mounted()
    stats.pointer.handle(MouseEvent("none", x=1, y=0, kind="motion"))
    tui.paint()
    assert box_rows(tui)[2] == "hover Button (1, 0)"
    stats.pointer.clear()
    tui.paint()
    assert box_rows(tui)[2] == "hover --"


def test_a_host_can_point_the_box_at_a_rebuilt_pointer():
    tui, stats = mounted()
    fresh = Pointer(tui)
    stats.pointer = fresh
    fresh.handle(MouseEvent("none", x=1, y=0, kind="motion"))
    tui.paint()
    assert box_rows(tui)[2] == "hover Button (1, 0)"


def test_the_frame_rate_is_sampled_over_a_window_of_at_least_a_second():
    tui = headless_tui(40, 8)
    clock = Clock(100.0).install(tui)
    stats = Stats(tui)
    tui.paint()
    tui.paint()
    assert stats.fps == 0.0
    clock.advance(2.0)
    tui.paint()
    assert stats.fps == pytest.approx(1.0)
    clock.advance(0.5)
    tui.paint()
    assert stats.fps == pytest.approx(1.0)
    clock.advance(0.5)
    tui.paint()
    assert stats.fps == pytest.approx(2.0)


def test_the_stats_band_follows_a_theme_change():
    tui, stats = mounted()
    band = Style(bg="#123456")
    stats.set_theme(Theme(toast=band))
    marker = len(tui.screen.output)
    tui.paint()
    assert sgr_prefix(band, "truecolor") in tui.screen.output[marker:]


# === Toasts =================================================================


def stack(tui, **knobs) -> Toasts:
    toasts = Toasts(tui, **knobs)
    tui.paint()
    return toasts


def document(tui, texts) -> None:
    tui.add(Rows(*texts))
    tui.paint()


def clocked(tui, **knobs) -> tuple[Toasts, Clock]:
    clock = Clock(1000.0).install(tui)
    toasts = Toasts(tui, **knobs)
    tui.paint()
    return toasts, clock


def advance(tui, clock: Clock, seconds: float) -> None:
    clock.advance(seconds)
    tui.tick(clock())


@pytest.mark.parametrize(
    "corner,affected,expected",
    [
        ("top-left", 0, "hi        "),
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
    others = [index for index in range(4) if index != affected]
    assert [tui.rows[index].text for index in others] == [
        many(4)[index] for index in others
    ]


def test_the_stack_reads_newest_at_the_corner_with_a_blank_row_between():
    tui = headless_tui(10, 5)
    document(tui, many(5))
    toasts = stack(tui)
    toasts.show("old")
    toasts.show("new")
    tui.paint()
    assert tui.rows[0].text == "r0     new"
    assert tui.rows[2].text == "r2     old"
    assert tui.rows[1].text == "r1"


def test_a_multi_row_component_band_covers_each_of_its_rows():
    tui = headless_tui(10, 4)
    document(tui, many(4))
    stack(tui, corner="bottom-right").show(Rows("one", "two"))
    tui.paint()
    assert tui.rows[2].text == "r2     one"
    assert tui.rows[3].text == "r3     two"
    assert tui.rows[1].text == "r1"


def test_a_band_clamps_to_half_a_narrow_frame_and_to_forty_columns():
    narrow = headless_tui(20, 3)
    stack(narrow).show("x" * 30)
    narrow.paint()
    assert [row.text for row in narrow.rows] == [" " * 10 + "x" * 10] * 3

    wide = headless_tui(80, 3)
    stack(wide).show("y" * 90)
    wide.paint()
    assert wide.rows[0].text == " " * 40 + "y" * 40
    assert wide.rows[2].text == " " * 40 + "y" * 10 + " " * 30


def test_a_short_band_is_only_as_wide_as_its_content():
    tui = headless_tui(80, 1)
    stack(tui).show("hi")
    tui.paint()
    assert tui.rows[0].text == " " * 78 + "hi"


def test_a_component_overrunning_its_width_is_fit_to_the_band():
    tui = headless_tui(20, 1)
    stack(tui).show(Rows("z" * 50))
    tui.paint()
    assert tui.rows[0].text == " " * 10 + "z" * 9 + "\u2026"


def test_an_empty_stack_and_a_frame_too_narrow_paint_nothing():
    tui = headless_tui(10, 3)
    document(tui, many(3))
    before = [row.text for row in tui.rows]
    stack(tui)
    tui.paint()
    assert [row.text for row in tui.rows] == before

    narrow = headless_tui(1, 2)
    document(narrow, ["a", "b"])
    toasts = stack(narrow)
    toasts.show("hi")
    narrow.paint()
    assert [row.text for row in narrow.rows] == ["a", "b"]


def test_a_toast_rides_a_retile():
    tui = headless_tui(20, 3)
    document(tui, many(3))
    toasts = stack(tui, corner="bottom-right")
    toasts.show("stay")
    tui.screen.width = 30
    tui.paint()
    assert tui.rows[2].text == "r2" + " " * 24 + "stay"


@pytest.mark.parametrize(
    "knobs,show_style,expected",
    [
        ({"style": Style(fg="#111111")}, None, Style(fg="#111111")),
        ({}, Style(fg="#222222"), Style(fg="#222222")),
        ({"theme": Theme(toast=Style(fg="#333333"))}, None, Style(fg="#333333")),
        ({"style": Style(fg="#111111"), "theme": Theme(toast=Style(fg="#333333"))}, None, Style(fg="#111111")),
    ],
)
def test_the_band_resolves_a_toasts_style_then_the_controllers(knobs, show_style, expected):
    tui = headless_tui(10, 1)
    toasts = stack(tui, **knobs)
    toasts.show("hi", style=show_style)
    tui.paint()
    assert tui.rows[0].segments[-1].style == expected


def test_the_band_paints_underneath_a_components_own_styles():
    tui = headless_tui(10, 6)
    toasts = stack(tui, style=Style(bg="#123456"))
    toasts.show(Text("red", style=Style(fg="red")))
    toasts.show(Text("dim", style=Style(italic=True)))
    toasts.show(Rows("ab", ""))
    tui.paint()
    band = Style(bg="#123456")
    assert tui.rows[0].segments[1].style == band
    assert tui.rows[1].text == " " * 8 + "  "
    assert tui.rows[1].segments[-1].style == band
    assert tui.rows[3].segments[1].style == band.merge(Style(italic=True))
    assert tui.rows[5].segments[1].style == Style(fg="red")


def test_an_unknown_corner_raises():
    with pytest.raises(ValueError):
        Toasts(headless_tui(10, 2), corner="middle")


@pytest.mark.parametrize(
    "ttl,shown,spent,expected",
    [
        (4.0, 3, 0.5, 2),
        (4.0, 3, 2.5, 1),
        (4.0, 3, 6.0, 0),
        (1.0, 2, 0.75, 1),
    ],
)
def test_the_ticker_drops_toasts_whose_ttl_has_passed(ttl, shown, spent, expected):
    tui = headless_tui(10, 8)
    toasts, clock = clocked(tui, ttl=ttl)
    for index in range(shown):
        if index:
            clock.advance(ttl / 2)
        toasts.show(f"t{index}")
    tui.paint()
    assert len([row for row in tui.rows if row.text.strip()]) == shown
    advance(tui, clock, spent)
    tui.paint()
    assert len([row for row in tui.rows if row.text.strip()]) == expected


def test_an_expired_toast_leaves_the_next_frame_and_the_ticker_stands_down():
    tui = headless_tui(10, 2)
    toasts, clock = clocked(tui, ttl=1.0)
    toasts.show("bye")
    advance(tui, clock, 1.5)
    tui.paint()
    assert not any(row.text.strip() for row in tui.rows)
    assert tui.tick(clock()) is None

    toasts.show("again")
    assert toasts.handle(press(9, 0)) is True
    advance(tui, clock, 1.5)
    assert tui.tick(clock()) is None


@pytest.mark.parametrize(
    "max_shown,shown,expected",
    [
        (3, 2, ["r0      m1", "r2      m0"]),
        (3, 4, ["r0      m3", "r2      m2", "r4      m1"]),
    ],
)
def test_max_shown_evicts_the_oldest(max_shown, shown, expected):
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
    assert toasts.handle(press(8, 0)) is True
    tui.paint()
    assert tui.rows[0].text == "r0     one"
    assert tui.rows[2].text == "r2"

    assert toasts.handle(press(9, 0)) is True
    tui.paint()
    assert [row.text for row in tui.rows] == many(4)


def test_a_press_outside_every_toast_passes_through():
    tui = headless_tui(10, 4)
    document(tui, many(4))
    toasts = stack(tui)
    toasts.show("keep")
    tui.paint()
    assert toasts.handle(press(0, 0)) is False
    assert toasts.handle(press(5, 0)) is False
    tui.paint()
    assert tui.rows[0].text == "r0    keep"


def test_a_bottom_left_toast_is_dismissible():
    tui = headless_tui(10, 3)
    document(tui, many(3))
    toasts = stack(tui, corner="bottom-left")
    toasts.show("bye")
    tui.paint()
    assert tui.rows[2].text == "bye       "
    assert toasts.handle(press(1, 2)) is True
    tui.paint()
    assert tui.rows[2].text == "r2"


@pytest.mark.parametrize(
    "event",
    [
        key("a", "a"),
        PasteEvent("pasted"),
        MouseEvent("right", x=8, y=0),
        MouseEvent("wheel_up", x=8, y=0, kind="wheel"),
        MouseEvent("left", x=8, y=0, kind="motion"),
        MouseEvent("left", x=8, y=0, kind="release"),
    ],
)
def test_handle_passes_everything_the_dismiss_does_not_own(event):
    tui = headless_tui(10, 2)
    document(tui, many(2))
    toasts = stack(tui)
    toasts.show("stay")
    tui.paint()
    assert toasts.handle(event) is False
    assert toasts.handle(press(7, 0)) is True


def test_a_string_wraps_in_text_and_a_component_shows_as_is():
    tui = headless_tui(10, 4)
    toasts = stack(tui)
    toasts.show("plain")
    toasts.show(Rows("raw"))
    tui.paint()
    assert tui.rows[0].text == " " * 7 + "raw"
    assert tui.rows[2].text == " " * 5 + "plain"


def test_a_per_show_ttl_overrides_the_controllers():
    tui = headless_tui(10, 4)
    toasts, clock = clocked(tui, ttl=10.0)
    toasts.show("short", ttl=1.0)
    toasts.show("long")
    tui.paint()
    assert tui.rows[0].text == " " * 6 + "long"
    assert tui.rows[2].text == " " * 5 + "short"
    advance(tui, clock, 2.0)
    tui.paint()
    assert tui.rows[0].text == " " * 6 + "long"
    assert tui.rows[2].text == ""


def test_detach_drops_the_stack_cancels_the_ticker_and_stays_detached():
    tui = headless_tui(10, 2)
    document(tui, many(2))
    toasts, clock = clocked(tui, ttl=1.0)
    toasts.show("gone")
    tui.paint()
    toasts.detach()
    assert all(held is not toasts for held in tui.frame.overlays)
    tui.paint()
    assert [row.text for row in tui.rows] == many(2)
    toasts.show("ignored")
    tui.paint()
    assert [row.text for row in tui.rows] == many(2)
    assert toasts.handle(press(8, 0)) is False
    advance(tui, clock, 5.0)
    assert tui.tick(clock()) is None
    toasts.detach()


def test_a_controller_attached_before_the_first_paint_rides_the_retile():
    tui = headless_tui(20, 3)
    document(tui, many(3))
    toasts = Toasts(tui, corner="bottom-left")
    tui.paint()
    toasts.show("here")
    tui.paint()
    assert tui.rows[2].text == "here" + " " * 16
    assert toasts.handle(press(0, 2)) is True


# === Tooltip ================================================================


class Leaf:
    """A hoverable leaf with an optional hint."""

    def __init__(self, *, rows: int = 1, has_hint: bool = True, hint: object = None) -> None:
        self.hover = False
        self.rows = rows
        if has_hint:
            self.hint = hint

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(f"leaf{i}") for i in range(self.rows)]


def mounted_tip(leaf, *, width: int = 30, height: int = 6, theme=None):
    tui = headless_tui(width, height)
    tui.add(leaf)
    tui.paint()
    pointer = Pointer(tui)
    tooltip = Tooltip(tui, pointer, theme=theme)
    return tui, pointer, tooltip


def rows_text(tui) -> list[str]:
    return [row.text for row in tui.rows]


def test_a_hint_paints_a_one_row_band_under_the_pointer():
    leaf = Leaf(rows=2, hint="press enter to ship")
    tui, pointer, _ = mounted_tip(leaf)
    pointer.handle(MouseEvent("none", x=2, y=1, kind="motion"))
    tui.paint()
    assert tui.rows[0].text == "leaf0"
    assert tui.rows[1].text == "leaf1"
    assert tui.rows[2].text.rstrip() == "  press enter to ship"


@pytest.mark.parametrize(
    "leaf",
    [
        Leaf(has_hint=False),
        Leaf(hint=""),
        Leaf(hint=5),
        Leaf(hint=None),
    ],
)
def test_a_leaf_without_a_usable_hint_paints_nothing(leaf):
    tui, pointer, _ = mounted_tip(leaf)
    before = rows_text(tui)
    pointer.handle(MouseEvent("none", x=2, y=0, kind="motion"))
    tui.paint()
    assert rows_text(tui) == before


def test_a_pointer_that_never_moved_paints_nothing():
    leaf = Leaf(rows=2, hint="hidden")
    tui, _, _ = mounted_tip(leaf)
    tui.paint()
    assert [row.text for row in tui.rows[:3]] == ["leaf0", "leaf1", ""]


def test_moving_off_the_leaf_takes_the_band_away():
    leaf = Leaf(hint="here")
    tui, pointer, _ = mounted_tip(leaf, height=4)
    pointer.handle(MouseEvent("none", x=2, y=0, kind="motion"))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "  here"
    pointer.handle(MouseEvent("none", x=2, y=3, kind="motion"))
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", "", ""]


def test_the_band_flips_above_a_pointer_on_the_last_row():
    leaf = Leaf(rows=3, hint="<<flip>>")
    tui, pointer, _ = mounted_tip(leaf, height=3)
    pointer.handle(MouseEvent("none", x=1, y=1, kind="motion"))
    tui.paint()
    assert "<<flip>>" in tui.rows[2].text
    tui.screen.height = 2
    pointer.handle(MouseEvent("none", x=1, y=1, kind="motion"))
    tui.paint()
    assert "<<flip>>" in tui.rows[0].text
    assert "<<flip>>" not in tui.rows[1].text


def test_the_band_is_clamped_into_the_frames_width():
    leaf = Leaf(hint="nineteen characters")
    tui, pointer, _ = mounted_tip(leaf, width=20, height=3)
    pointer.handle(MouseEvent("none", x=18, y=0, kind="motion"))
    tui.paint()
    assert tui.rows[1].text == " nineteen characters"[:20]
    assert len(tui.rows[1].text) == 20


def test_a_hint_wider_than_a_narrow_frame_is_fit_to_it():
    leaf = Leaf(hint="a long hint")
    tui, pointer, _ = mounted_tip(leaf, width=1, height=2)
    pointer.handle(MouseEvent("none", x=0, y=0, kind="motion"))
    tui.paint()
    assert len(tui.rows[1].text) == 1


def test_the_band_paints_with_the_themes_toast_style():
    leaf = Leaf(hint="hi")
    band = Style(fg="#333333")
    tui, pointer, _ = mounted_tip(leaf, theme=Theme(toast=band))
    pointer.handle(MouseEvent("none", x=0, y=0, kind="motion"))
    tui.paint()
    assert band in [seg.style for seg in tui.rows[1].segments]


def test_detach_unregisters_the_tooltip_and_stops_the_paint():
    leaf = Leaf(hint="gone")
    tui, pointer, tooltip = mounted_tip(leaf, height=3)
    pointer.handle(MouseEvent("none", x=0, y=0, kind="motion"))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "gone"
    tooltip.detach()
    assert all(held is not tooltip for held in tui.frame.overlays)
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", ""]
    tooltip.detach()


def test_a_hint_changed_under_a_live_pointer_shows_on_the_next_frame():
    leaf = Leaf(hint="old")
    tui, pointer, _ = mounted_tip(leaf, height=4)
    pointer.handle(MouseEvent("none", x=0, y=0, kind="motion"))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "old"
    leaf.hint = "new"
    tui.paint()
    assert tui.rows[1].text.rstrip() == "new"


def test_a_host_repoints_the_band_by_mounting_the_new_pointers_tooltip():
    leaf = Leaf(hint="left pane")
    tui, pointer, tooltip = mounted_tip(leaf, height=3)
    pointer.handle(MouseEvent("none", x=0, y=0, kind="motion"))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "left pane"
    tooltip.detach()
    fresh = Pointer(tui)
    Tooltip(tui, fresh)
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", ""]
    fresh.handle(MouseEvent("none", x=0, y=0, kind="motion"))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "left pane"
