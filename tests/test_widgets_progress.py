"""Tests for mocode_tui.widgets.progress (ProgressBar).

Contracts (the W4 ticket + the COMPONENTS.md blueprint): a single-row
``[\\u2588\\u2588\\u2588\\u2591\\u2591\\u2591]`` track whose filled part is ``round(track * fraction)``;
``fraction`` clamps into ``[0, 1]`` on construction and assignment;
``label`` prefixes the track, ``width_chars`` pins the track width (``None``
fills the available width); the row always ``fit``\\ s back to ``width``.
"""

from mocode_tui.widgets.progress import ProgressBar
from mocode_tui.core.block import Component
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import DIM, SUCCESS, Style
from mocode_tui.core.theme import Theme


def _row(bar, width=10):
    rows = bar.render(width)
    assert len(rows) == 1  # a progress bar is exactly one row
    return rows[0]


def test_three_states_across_a_full_track():
    empty = _row(ProgressBar(0.0))
    assert empty.text == "[" + "\u2591" * 8 + "]"
    assert empty.segments == (
        Segment(""),
        Segment("["),
        Segment("", SUCCESS),
        Segment("\u2591" * 8, DIM),
        Segment("]"),
    )
    half = _row(ProgressBar(0.5))
    assert half.text == "[" + "\u2588" * 4 + "\u2591" * 4 + "]"
    full = _row(ProgressBar(1.0))
    assert full.text == "[" + "\u2588" * 8 + "]"
    assert full.segments == (
        Segment(""),
        Segment("["),
        Segment("\u2588" * 8, SUCCESS),
        Segment("", DIM),
        Segment("]"),
    )


def test_fraction_clamps_on_construction_and_assignment():
    assert ProgressBar(1.5).fraction == 1.0
    assert ProgressBar(-0.2).fraction == 0.0
    bar = ProgressBar(0.3)
    bar.fraction = 2.0
    assert bar.fraction == 1.0
    assert _row(bar).text == "[" + "\u2588" * 8 + "]"
    bar.fraction = -1.0
    assert _row(bar).text == "[" + "\u2591" * 8 + "]"


def test_fraction_mutation_rerenders():
    bar = ProgressBar(0.0)
    bar.fraction = 0.75
    assert _row(bar).text == "[" + "\u2588" * 6 + "\u2591" * 2 + "]"


def test_label_prefixes_the_track():
    row = _row(ProgressBar(0.5, label="load"))
    assert row.text == "load [\u2588\u2588\u2591]"  # 10 - 5 - 2 = 3 track columns
    row = _row(ProgressBar(1.0, label="done"))
    assert row.text == "done [\u2588\u2588\u2588]"


def test_width_chars_pins_the_track_width():
    bar = ProgressBar(0.5, width_chars=4)
    assert _row(bar, width=40).text == "[\u2588\u2588\u2591\u2591]"
    # a pinned track (or label) wider than the painting width truncates with an ellipsis
    row = _row(ProgressBar(1.0, width_chars=6, label="x"), width=2)
    assert row.text == "x\u2026" and row.width == 2
    assert _row(ProgressBar(0.5, width_chars=30), width=8).width == 8


def test_narrow_widths_never_overflow():
    for width in (0, 1, 2, 3, 4, 5):
        row = _row(ProgressBar(0.5), width=width)
        assert row.width <= width
    assert _row(ProgressBar(0.5), width=0).text == ""
    assert _row(ProgressBar(0.5), width=1).text == "\u2026"


def test_style_injection_and_theme_fallback():
    bar = ProgressBar(
        0.5,
        width_chars=4,
        done_style=Style(fg="red"),
        todo_style=Style(fg="blue"),
    )
    row = _row(bar, width=20)
    assert row.segments[2] == Segment("\u2588\u2588", Style(fg="red"))
    assert row.segments[3] == Segment("\u2591\u2591", Style(fg="blue"))

    theme = Theme(success=Style(fg="green"), dim=Style(fg="gray"))
    row = _row(ProgressBar(0.5, width_chars=4, theme=theme), width=20)
    assert row.segments[2] == Segment("\u2588\u2588", Style(fg="green"))
    assert row.segments[3] == Segment("\u2591\u2591", Style(fg="gray"))


def test_is_a_component():
    assert isinstance(ProgressBar(0.4), Component)
