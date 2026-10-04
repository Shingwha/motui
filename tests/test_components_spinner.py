"""Tests for mocode_tui.components.spinner (Spinner).

Contract: braille frame cycling around a label; ``advance()`` steps the cycle
and ``render`` draws ``frame + " " + text`` (COMPONENTS.md).  The driver, not
the component, decides when to advance.
"""

from mocode_tui.components.spinner import DEFAULT_FRAMES, Spinner


def test_default_render_at_width_80():
    spinner = Spinner("working")
    assert [row.text for row in spinner.render(80)] == [f"{DEFAULT_FRAMES[0]} working"]


def test_advance_steps_the_cycle_and_wraps():
    spinner = Spinner("x")
    spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[1]
    for _ in range(len(DEFAULT_FRAMES) - 1):
        spinner.advance()
    assert spinner.frame == DEFAULT_FRAMES[0]  # wrapped around


def test_empty_frames_render_the_label_only():
    spinner = Spinner("idle", frames=())
    assert spinner.render(20)[0].text == "idle"
    spinner.advance()  # no-op, must not raise
    assert spinner.render(20)[0].text == "idle"


def test_narrow_width_guard():
    row = Spinner("a very long label").render(6)[0]
    assert row.width == 6  # fit, not wrapped
    assert row.text.endswith("\u2026")
