"""Tests for mocode_tui.widgets.chrome (Notice / Divider / Panel).

Contracts (COMPONENTS.md):
* ``Notice`` -- one message row; ``warn``/``error`` prepend a styled label,
  an unknown level degrades to ``info``; truncated, never wrapped.
* ``Divider`` -- a full-width rule from one repeated ``char``; a ``label``
  embeds ``char*2 + " " + label + " " + char*fill``, over-wide labels are
  ellipsize'd to ``width - 4``, and ``label``/``label_style`` are mutable.
* ``Panel`` -- a child inside a single-line box, optional titled top border.
"""

import pytest

from mocode_tui.widgets.chrome import Divider, Notice, Panel
from mocode_tui.widgets.text import Text
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import ACCENT, BORDER, ERROR, NONE, WARNING
from mocode_tui.core.text import ellipsize_tail


def test_notice_levels_and_degradation():
    assert Notice("hello").render(80) == [Line.from_text("hello")]
    assert Notice("hmm", level="verbose").render(80) == [Line.from_text("hmm")]  # unknown -> info
    row = Notice("careful", level="warn").render(80)[0]
    assert row.text == "WARNING: careful"
    assert row.segments[0] == Segment("WARNING: ", WARNING)
    row = Notice("boom", level="error").render(80)[0]
    assert row.segments[0] == Segment("ERROR: ", ERROR)
    # Truncated, never wrapped.
    narrow = Notice("a very long warning message", level="warn").render(10)[0]
    assert narrow.text == "WARNING: \u2026"
    assert narrow.width == 10


def test_divider_fills_the_width_with_the_default_char():
    assert Divider().render(10) == [Line.from_text("\u2500" * 10, BORDER)]


def test_divider_label_embeds_between_rule_segments():
    row = Divider(label="Working").render(20)[0]
    assert row.text == "\u2500\u2500 Working " + "\u2500" * 9
    assert row.width == 20
    assert row.segments == (
        Segment("\u2500\u2500", BORDER),
        Segment(" ", BORDER),
        Segment("Working", NONE),
        Segment(" ", BORDER),
        Segment("\u2500" * 9, BORDER),
    )
    styled = Divider(label="Working", label_style=ACCENT).render(20)[0]
    assert styled.segments[2] == Segment("Working", ACCENT)
    assert all(seg.style == BORDER for seg in (styled.segments[0], styled.segments[-1]))


def test_divider_label_is_mutable_and_ellipsized_when_over_wide():
    divider = Divider()
    divider.label = "Working"  # a host re-labels one divider in place
    assert divider.render(10)[0].text == "\u2500\u2500 Worki\u2026 "
    row = Divider(label="a very long working label").render(16)[0]
    label = next(seg for seg in row.segments if seg.style == NONE)
    assert label.text == ellipsize_tail("a very long working label", 16 - 4)


def test_divider_narrow_width_guard():
    # width < 4 leaves no room for a label: the pure rule, like an empty label.
    for width in range(0, 4):
        assert Divider(label="Working").render(width) == Divider().render(width)
    assert Divider().render(0) == [Line()]
    assert Divider().render(-3) == [Line()]
    # A wide char leaves the columns ragged; the final fit keeps the row honest.
    for width in (5, 9, 16):
        row = Divider(char="\u65e5", label="Working").render(width)[0]
        assert row.width <= width


def test_divider_max_width_caps_the_span_left_aligned():
    row = Divider(max_width=10).render(40)[0]
    assert row.text == "\u2500" * 10
    assert row.width == 10  # a short row is legal; the painter clears the tail
    # A cap at or beyond the width changes nothing (None = full width).
    assert Divider(max_width=80).render(12) == [Line.from_text("\u2500" * 12, BORDER)]
    assert Divider(max_width=None).render(12) == Divider().render(12)
    # The label branch budgets (ellipsize, fill) from the capped width.
    row = Divider(label="Working", max_width=12).render(40)[0]
    assert row.text == "\u2500\u2500 Working \u2500"
    assert row.width == 12
    long = Divider(label="a very long working label", max_width=16).render(40)[0]
    label = next(seg for seg in long.segments if seg.style == NONE)
    assert label.text == ellipsize_tail("a very long working label", 16 - 4)
    # A degenerate cap paints an empty row rather than raising.
    assert Divider(max_width=0).render(10)[0].text == ""
    # The cap is a plain attribute: a host re-caps one divider in place.
    divider = Divider()
    divider.max_width = 6
    assert divider.render(40)[0].text == "\u2500" * 6


def test_panel_frames_the_child_with_an_optional_title():
    rows = Panel(Text("hi")).render(12)
    assert [row.text for row in rows] == [
        "\u250c" + "\u2500" * 10 + "\u2510",
        "\u2502 hi       \u2502",
        "\u2514" + "\u2500" * 10 + "\u2518",
    ]
    titled = Panel(Text("body"), title="Info").render(20)
    assert titled[0].text.startswith("\u250c\u2500 Info \u2500")
    assert titled[0].text.endswith("\u2510")
    assert titled[0].width == 20


def test_panel_narrow_width_degrades_to_the_bare_child():
    rows = Panel(Text("hello world")).render(3)
    assert [row.text for row in rows] == ["hel", "lo", "wor", "ld"]
    assert all(row.width <= 3 for row in rows)
    assert Panel(Text("x")).render(1) == [Line.from_text("x")]
