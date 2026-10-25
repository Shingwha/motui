"""ProgressBar, Slider and Spinner: determinate and stepped value indicators."""

from dataclasses import replace

import pytest

from motui.kernel.cell import Surface
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import ProgressBar, Slider, Spinner

from tests.testing import key, texts


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
    row = ProgressBar(0.5, width_chars=4).render(Constraints(width=20))[0]
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
    assert slider.on_action("activate") is True
    assert slider.move(1) is True and slider.value == 6
    assert slider.take() is None
    assert slider.move(99) is True and slider.value == 10
    assert slider.move(1) is False
    assert slider.move(-99) is True and slider.value == 0


def test_slider_click_maps_the_track_to_the_value():
    slider = Slider(0, maximum=10)
    slider.render(Constraints(width=14))
    assert slider.on_click(Pos(x=1, y=0)) is True and slider.value == 0
    assert slider.on_click(Pos(x=11, y=0)) is True and slider.value == 10
    assert slider.on_click(Pos(x=1, y=1)) is False


def test_slider_activate_takes_the_value_once_and_disabled_refuses():
    slider = Slider(4)
    assert slider.on_action("activate") is True and slider.take() == 4
    assert slider.take() is None
    dead = Slider(
        4,
        disabled=True,
        styles=Styles(text=replace(DEFAULT_THEME.text, faint=Style(italic=True))),
    )
    assert dead.move(1) is False and dead.on_click(Pos(x=1, y=0)) is False
    assert dead.on_action("activate") is False and dead.take() is None
    assert dead.render(Constraints(width=14))[0].segments[0].style.italic is True


def test_slider_hover_and_focus_merge_their_bands():
    theme = replace(
        DEFAULT_THEME,
        surfaces=replace(DEFAULT_THEME.surfaces, hover=Style(underline=True)),
        controls=replace(DEFAULT_THEME.controls, focus=Style(bold=True)),
    )
    slider = Slider(2, theme=theme)
    plain = slider.render(Constraints(width=14))
    assert slider.on_hover(Pos(x=0, y=0)) is True
    assert all(seg.style.underline for seg in slider.render(Constraints(width=14))[0].segments)
    assert slider.on_hover(Pos(x=0, y=1)) is True
    assert slider.render(Constraints(width=14)) == plain
    slider.focused = True
    assert all(seg.style.bold for seg in slider.render(Constraints(width=14))[0].segments)


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


# -- the 2.0 render contract -------------------------------------------------


def test_the_indicators_take_constraints_and_honour_the_height_budget():
    for component in (ProgressBar(0.5, width_chars=4), Slider(5), Spinner("x")):
        assert isinstance(component.render(Constraints(width=14)), Surface)
        assert component.render(Constraints(width=14)) == component.render(Constraints(width=14))
        assert list(component.render(Constraints(width=14, max_height=0))) == []
        assert component.render(Constraints(width=14, max_height=1)).height == 1


def test_a_zero_height_slider_render_still_seeds_the_click_geometry():
    slider = Slider(0, maximum=10)
    slider.render(Constraints(width=14, max_height=0))
    assert slider.on_click(Pos(x=11, y=0)) is True and slider.value == 10


def test_an_unbounded_progress_bar_still_follows_the_constrained_width():
    surface = ProgressBar(1.0).render(Constraints(width=10))
    assert [row.text for row in surface] == ["[" + "\u2588" * 8 + "]"]


# -- the 2.0 capabilities and hooks -------------------------------------------


def test_only_the_slider_declares_interactive_capabilities():
    slider = Slider(5)
    assert (slider.focusable, slider.clickable, slider.hoverable, slider.activatable) == (
        True,
        True,
        True,
        True,
    )
    for quiet in (ProgressBar(0.5), Spinner("x")):
        assert quiet.focusable is False
        assert quiet.clickable is False
        assert quiet.hoverable is False
        assert quiet.activatable is False


def test_slider_on_key_steps_and_confirms():
    slider = Slider(5, maximum=10)

    assert slider.on_key(key("left")) is True and slider.value == 4
    assert slider.on_key(key("down")) is True and slider.value == 5
    assert slider.on_key(key("enter")) is True
    assert slider.take() == 5
    assert slider.on_key(key("x", "x")) is False


def test_slider_on_key_declines_at_the_range_end_and_when_disabled():
    at_end = Slider(10, maximum=10)
    assert at_end.on_key(key("right")) is False

    dead = Slider(5, disabled=True)
    assert dead.on_key(key("left")) is False
    assert dead.on_key(key("enter")) is False


def test_slider_on_click_maps_the_track():
    slider = Slider(0, maximum=10)
    slider.render(Constraints(width=14))

    assert slider.on_click(Pos(y=0, x=11)) is True and slider.value == 10
    assert slider.on_click(Pos(y=1, x=1)) is False


def test_slider_on_action_activates_and_moves():
    slider = Slider(5, maximum=10)

    assert slider.on_action("activate") is True
    assert slider.take() == 5
    assert slider.on_action("next") is True and slider.value == 6
    assert slider.on_action("unknown") is False
    # The move cleared the pending value instead of leaving a stale one.
    assert slider.take() is None
