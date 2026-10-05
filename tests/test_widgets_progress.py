"""Tests for mocode_tui.widgets.progress (ProgressBar).

Contracts (the W4 ticket + the COMPONENTS.md blueprint): a single-row
``[\\u2588\\u2588\\u2588\\u2591\\u2591\\u2591]`` track whose filled part is ``round(track * fraction)``;
``fraction`` clamps into ``[0, 1]`` on construction and assignment;
``label`` prefixes the track, ``width_chars`` pins the track width (``None``
fills the available width); the row always ``fit``\\ s back to ``width``.
The five-segment row is pinned once, as a round trip of the injected
styles -- never as a pinned default color.
"""

import pytest
from dataclasses import replace

from mocode_tui.core.block import Component
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.progress import ProgressBar

#: Injected styles: they flow back out of the render equal.
DONE = Style(fg="#abcdef")
TODO = Style(fg="#123456")


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


def test_narrow_widths_never_overflow():
    for width in (0, 1, 2, 3, 4, 5):
        assert _row(ProgressBar(0.5), width=width).width <= width
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


def test_is_a_component():
    assert isinstance(ProgressBar(0.4), Component)
