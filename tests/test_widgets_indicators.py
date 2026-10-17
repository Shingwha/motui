"""Tests for motui.widgets.indicators (ProgressBar / Slider / Spinner).

The value indicators, each asserted as its own contract: the determination a
bar clamps and paints, the stepped grid a slider's value lives on with the
three doors into its ``chosen``, and the frame cycle a spinner walks -- plus
the row-level ``hover_at`` marking that must render zero extra bytes when it
cleared and the focus band that must be told apart from the plain render.
The spinner renders no rows of its own (a host paints ``frame``), so its
tests read the state directly.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.kernel import Component
from motui.kernel.block import Activable, Clickable
from motui.kernel.lines import Segment
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import ProgressBar, Slider, Spinner
from motui.widgets.indicators import DEFAULT_FRAMES

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
PLAIN = Style(fg="#123456")
HOVER = Style(italic=True)
FOCUS = Style(underline=True)
DONE = Style(fg="#abcdef")
TODO = Style(fg="#123456")


# --- ProgressBar ---------------------------------------------------------------


def _row(bar, width=10):
    rows = bar.render(width)
    assert len(rows) == 1  # a progress bar is exactly one row
    return rows[0]


@pytest.mark.parametrize(
    "fraction, track",
    [(0.0, "\u2591" * 4), (0.5, "\u2588\u2588\u2591\u2591"), (1.0, "\u2588" * 4)],
)
def test_the_track_fills_to_the_fraction(fraction, track):
    assert _row(ProgressBar(fraction, width_chars=4), width=20).text == f"[{track}]"


@pytest.mark.parametrize(
    "value, fraction, track",
    [
        (1.5, 1.0, "\u2588" * 4),  # clamped on construction
        (-0.2, 0.0, "\u2591" * 4),
        (0.75, 0.75, "\u2588\u2588\u2588\u2591"),
    ],
)
def test_fraction_clamps_on_construction_and_assignment(value, fraction, track):
    bar = ProgressBar(value, width_chars=4)
    assert bar.fraction == fraction
    bar.fraction = 2.0
    assert bar.fraction == 1.0
    bar.fraction = value
    assert _row(bar, width=20).text == f"[{track}]"  # a mutation re-renders


def test_label_prefixes_the_track():
    assert _row(ProgressBar(0.5, label="load"), width=10).text == "load [\u2588\u2588\u2591]"
    assert _row(ProgressBar(1.0, label="done"), width=10).text == "done [\u2588\u2588\u2588]"


def test_width_chars_pins_the_track_width():
    assert _row(ProgressBar(0.5, width_chars=4), width=40).text == "[\u2588\u2588\u2591\u2591]"
    # a pinned track (or label) wider than the painting width truncates with an ellipsis
    row = _row(ProgressBar(1.0, width_chars=6, label="x"), width=2)
    assert row.text == "x\u2026" and row.width == 2
    assert _row(ProgressBar(0.5, width_chars=30), width=8).width == 8
    # degenerate widths: the kernel fit pins, composed with the single fit call
    assert _row(ProgressBar(0.5), width=0).text == ""
    assert _row(ProgressBar(0.5), width=1).text == "\u2026"


def test_the_row_round_trips_the_injected_styles():
    # The one pinned five-segment golden: explicit styles and theme fields
    # both flow back out of the render equal.
    explicit = ProgressBar(0.5, width_chars=4, done_style=DONE, todo_style=TODO)
    assert _row(explicit, width=20).segments == (
        Segment(""),
        Segment("["),
        Segment("\u2588\u2588", DONE),
        Segment("\u2591\u2591", TODO),
        Segment("]"),
    )
    theme = replace(DEFAULT_THEME, success=DONE, dim=TODO)
    themed = ProgressBar(0.5, width_chars=4, theme=theme)
    assert _row(themed, width=20).segments == (
        Segment(""),
        Segment("["),
        Segment("\u2588\u2588", DONE),
        Segment("\u2591\u2591", TODO),
        Segment("]"),
    )


# --- Slider ---------------------------------------------------------------------


def test_slider_renders_the_track_and_the_value():
    slider = Slider(5)
    row = slider.render(14)[0]
    assert row.text == "[=====-----] 5"  # key + label + 2 brackets leave a 10-cell track
    assert row.segments[1] == Segment("=====", DEFAULT_THEME.accent)
    assert row.segments[2] == Segment("-----", DEFAULT_THEME.dim)
    assert isinstance(slider, Component)
    assert slider.render(30)[0].text == "[=============-------------] 5"  # the track follows width


def test_slider_clamps_and_snaps_to_the_step_grid():
    assert Slider(99, maximum=10).value == 10
    assert Slider(-5).value == 0
    slider = Slider(7, minimum=0, maximum=10, step=3)  # grid: 0, 3, 6, 9
    assert slider.value == 6  # 7 snaps down to the nearest grid point
    slider.value = 10
    assert slider.value == 9  # the largest grid point not past maximum
    slider.value = 100
    assert slider.value == 9
    slider.value = -100
    assert slider.value == 0
    assert Slider(5, minimum=7, maximum=7).value == 7  # an empty range pins the value


def test_slider_move_steps_clamps_and_clears_a_stale_choice():
    slider = Slider(4)
    assert slider.move(1) is True and slider.value == 5
    slider.chosen = 5  # the host read once and reset
    assert slider.move(1) is True and slider.value == 6 and slider.chosen is None
    assert slider.move(9) is True and slider.value == 10  # clamped at the top
    assert slider.move(1) is False  # already there: nothing moved
    assert slider.move(-99) is True and slider.value == 0
    assert slider.move(-1) is False
    stepped = Slider(0, minimum=0, maximum=9, step=3)
    assert stepped.move(1) is True and stepped.value == 3  # whole steps of the grid


def test_slider_click_maps_the_column_onto_the_value():
    slider = Slider(5)
    assert isinstance(slider, Clickable)
    slider.render(14)  # the track spans cells 1..10
    assert slider.click(0, 1) is True and slider.value == 0  # the track's first cell
    slider.render(14)
    assert slider.click(0, 6) is True and slider.value == 5  # the track's middle
    slider.render(14)
    assert slider.click(0, 11) is True and slider.value == 10  # the closing bracket
    slider.render(14)
    assert slider.click(0, 0) is True and slider.value == 0  # the opening bracket
    slider.render(14)
    assert slider.click(0, 99) is True and slider.value == 10  # past the row
    slider.render(14)
    assert slider.click(0, 6) is True  # a hit even when the value already sat there
    slider.chosen = 5
    assert slider.click(0, 6) is True and slider.chosen is None  # a click clears the pick
    for row in (-1, 1, 9):
        before = slider.value
        assert slider.click(row, 3) is False and slider.value == before


def test_slider_click_before_the_first_render_uses_the_default_width():
    slider = Slider(0)
    assert slider.click(0, 1) is True  # the 80-column default geometry
    assert slider.value == 0
    assert slider.click(0, 79) is True and slider.value == 10  # deep into the track's tail


def test_slider_activate_confirms_the_value_and_reads_once():
    slider = Slider(4, minimum=0, maximum=20)
    slider.move(2)
    assert isinstance(slider, Activable)
    assert slider.activate() is True and slider.chosen == 6
    slider.chosen = None
    assert slider.value == 6  # confirming changes nothing


def test_slider_marks_the_row_and_clears_back():
    slider = Slider(5, filled_style=SELECTED, empty_style=PLAIN, hover_style=HOVER)
    plain = slider.render(14)
    assert slider.hover_at(0, 3) is True
    marked = slider.render(14)
    assert marked[0].segments[1].style == SELECTED.merge(HOVER)
    assert marked[0].segments[2].style == PLAIN.merge(HOVER)
    assert marked[0].text == plain[0].text  # the band never changes the text
    assert slider.hover_at(0, 99) is False  # the same row: nothing to repaint
    assert slider.hover_at(-1, -1) is True  # the pointer left
    assert slider.render(14) == plain  # byte-for-byte the un-hovered row
    assert slider.hover_at(1, 0) is False  # no second row: nothing to mark
    assert slider.render(14) == plain


def test_slider_focus_band_is_told_apart_from_the_plain_render():
    styles = dict(filled_style=SELECTED, empty_style=PLAIN, focus_style=FOCUS)
    plain = Slider(5, **styles).render(14)[0]
    focused = Slider(5, focused=True, **styles).render(14)[0]
    assert focused.segments[1].style == SELECTED.merge(FOCUS)
    assert focused.segments[3].style == FOCUS  # brackets too: the row is one band
    assert plain.segments[1].style == SELECTED


# --- Spinner -------------------------------------------------------------------


def test_advance_steps_the_cycle_and_wraps():
    spinner = Spinner("x")
    spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[1]
    for _ in range(len(DEFAULT_FRAMES) - 1):
        spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[0]  # wrapped around


def test_empty_frames_yield_an_empty_frame():
    spinner = Spinner("idle", frames=())
    assert spinner.frame == ""
    spinner.advance()  # no-op, must not raise
    assert spinner.frame == ""
