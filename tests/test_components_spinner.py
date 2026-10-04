"""Tests for mocode_tui.components.spinner (Spinner)."""

from mocode_tui.components.spinner import DEFAULT_FRAMES, Spinner
from mocode_tui.style import NONE


def test_default_frames_are_one_column_each():
    assert len(DEFAULT_FRAMES) >= 2
    from mocode_tui.text import visible_width

    assert all(visible_width(frame) == 1 for frame in DEFAULT_FRAMES)


def test_starts_at_first_frame():
    spinner = Spinner("working")
    assert spinner.frame == DEFAULT_FRAMES[0]


def test_advance_steps_and_wraps_around():
    spinner = Spinner("x")
    spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[1]
    for _ in range(len(DEFAULT_FRAMES) - 1):
        spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[0]  # wrapped


def test_render_shows_frame_space_text():
    spinner = Spinner("working")
    assert [row.text for row in spinner.render(40)] == [f"{DEFAULT_FRAMES[0]} working"]
    spinner.advance()
    assert [row.text for row in spinner.render(40)] == [f"{DEFAULT_FRAMES[1]} working"]


def test_render_without_text_is_frame_only():
    spinner = Spinner()
    assert [row.text for row in spinner.render(10)] == [DEFAULT_FRAMES[0]]


def test_custom_frames_cycle():
    spinner = Spinner("go", frames=("|", "/", "-", "\\"))
    assert spinner.render(20)[0].text == "| go"
    spinner.advance()
    spinner.advance()
    assert spinner.render(20)[0].text == "- go"


def test_empty_frames_render_text_only():
    spinner = Spinner("idle", frames=())
    assert spinner.render(20)[0].text == "idle"
    spinner.advance()  # no-op, must not raise
    assert spinner.render(20)[0].text == "idle"


def test_render_fits_width():
    spinner = Spinner("a very long label")
    row = spinner.render(6)[0]
    assert row.width == 6
    assert row.text == f"{DEFAULT_FRAMES[0]} a v\u2026"


def test_frame_segment_is_unstyled():
    row = Spinner("t").render(20)[0]
    assert row.segments[0].style == NONE
