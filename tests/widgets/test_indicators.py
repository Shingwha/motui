"""ProgressBar, Slider and Spinner: determinate and stepped value indicators."""

from dataclasses import replace

import pytest

from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import ProgressBar, Slider, Spinner

from tests.testing import texts


@pytest.mark.parametrize(
    "fraction, expected",
    [(0.0, "[\u2591\u2591\u2591\u2591\u2591\u2591]"), (1.0, "[\u2588\u2588\u2588\u2588\u2588\u2588]")],
)
def test_progress_bar_fills_its_track_by_fraction(fraction, expected):
    assert texts(ProgressBar(fraction, width_chars=6), 20) == [expected]
    half = texts(ProgressBar(0.5, width_chars=6), 20)[0]
    assert half == "[\u2588\u2588\u2588\u2591\u2591\u2591]"


def test_progress_bar_clamps_and_can_lead_with_a_label():
    bar = ProgressBar(1.4, width_chars=4)
    assert bar.fraction == 1.0
    bar.fraction = -2
    assert bar.fraction == 0.0
    assert texts(ProgressBar(1.0, label="done", width_chars=4), 20) == ["done [\u2588\u2588\u2588\u2588]"]


def test_progress_bar_styles_the_filled_and_empty_runs():
    row = ProgressBar(0.5, width_chars=4).render(20)[0]
    assert row.segments[2].style == DEFAULT_THEME.status.success
    assert row.segments[3].style == DEFAULT_THEME.text.faint


def test_slider_renders_its_track_and_value():
    assert texts(Slider(5, maximum=10), 14) == ["[\u2501\u2501\u2501\u2501\u2501\u25cf\u2501\u2501\u2501\u2501] 5"]
    assert texts(Slider(0, maximum=10), 14) == ["[\u25cf\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501] 0"]
    assert texts(Slider(10, maximum=10), 14) == ["[\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u25cf] 10"]


def test_slider_clamps_and_snaps_onto_the_step_grid():
    slider = Slider(7, maximum=10, step=3)
    assert slider.value == 6
    slider.value = 100
    assert slider.value == 9
    slider.step = 2
    assert slider.value == 10
    slider.minimum = 4
    assert slider.value == 10
    assert Slider(5, minimum=10, maximum=2).value == 10


def test_slider_move_steps_and_clamps_and_clears_a_pending_value():
    slider = Slider(5, maximum=10)
    assert slider.activate() is True
    assert slider.move(1) is True and slider.value == 6
    assert slider.take_result() is None
    assert slider.move(99) is True and slider.value == 10
    assert slider.move(1) is False
    assert slider.move(-99) is True and slider.value == 0


def test_slider_click_maps_the_track_to_the_value():
    slider = Slider(0, maximum=10)
    slider.render(14)
    assert slider.click(0, 1) is True and slider.value == 0
    assert slider.click(0, 11) is True and slider.value == 10
    assert slider.click(1, 1) is False


def test_slider_activate_takes_the_value_once_and_disabled_refuses():
    slider = Slider(4)
    assert slider.activate() is True and slider.take_result() == 4
    assert slider.take_result() is None
    dead = Slider(4, disabled=True, disabled_style=Style(italic=True))
    assert dead.move(1) is False and dead.click(0, 1) is False
    assert dead.activate() is False and dead.take_result() is None
    assert dead.render(14)[0].segments[0].style.italic is True


def test_slider_hover_and_focus_merge_their_bands():
    theme = replace(
        DEFAULT_THEME,
        surfaces=replace(DEFAULT_THEME.surfaces, hover=Style(underline=True)),
        controls=replace(DEFAULT_THEME.controls, focus=Style(bold=True)),
    )
    slider = Slider(2, theme=theme)
    plain = slider.render(14)
    assert slider.hover_at(0, 0) is True
    assert all(seg.style.underline for seg in slider.render(14)[0].segments)
    assert slider.hover_at(1, 0) is True
    assert slider.render(14) == plain
    slider.focused = True
    assert all(seg.style.bold for seg in slider.render(14)[0].segments)


def test_spinner_advances_through_its_frames_and_wraps():
    spinner = Spinner(" working", frames=("a", "b"))
    assert texts(spinner, 20) == ["a working"]
    spinner.advance()
    assert texts(spinner, 20) == ["b working"]
    spinner.advance()
    assert texts(spinner, 20) == ["a working"]
    empty = Spinner("x", frames=())
    empty.advance()
    assert texts(empty, 20) == ["x"]
