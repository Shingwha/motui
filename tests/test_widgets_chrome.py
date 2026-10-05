"""Tests for mocode_tui.widgets.chrome (Notice / Divider / Panel).

Contracts (COMPONENTS.md):
* ``Notice`` -- one message row; ``warn``/``error`` prepend a styled label,
  an unknown level degrades to ``info``; truncated, never wrapped.
* ``Divider`` -- a full-width rule from one repeated ``char``; a ``label``
  embeds ``char*2 + " " + label + " " + char*fill``, over-wide labels are
  ellipsize'd to ``width - 4``, and ``label``/``label_style`` are mutable.
* ``Panel`` -- a child inside a single-line box, optional titled top border.
Styles round-trip from the constructor: no default color is pinned.
"""

import pytest
from dataclasses import replace

from mocode_tui.core.text import Text, ellipsize_tail
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.chrome import Divider, Notice, Panel

from _doubles import texts

#: Injected styles: they flow back out of the render equal.
WARN = Style(fg="#abcdef")
ERROR = Style(fg="#123456")
RULE = Style(fg="#fedcba")


@pytest.mark.parametrize("level, label", [("info", ""), ("verbose", "")])  # unknown -> info
def test_a_plain_notice_is_one_bare_row(level, label):
    assert Notice("hello", level=level).render(80) == [Line.from_text("hello")]


@pytest.mark.parametrize("level, label", [("warn", "WARNING: "), ("error", "ERROR: ")])
def test_a_leveled_notice_prefixes_the_message_with_the_themes_label(level, label):
    theme = replace(DEFAULT_THEME, warning=WARN, error=ERROR)
    row = Notice("careful", level=level, theme=theme).render(80)[0]
    assert row.text == label + "careful"
    assert row.segments[0] == Segment(label, WARN if level == "warn" else ERROR)


def test_a_narrow_notice_truncates_instead_of_wrapping():
    row = Notice("a very long warning message", level="warn").render(10)[0]
    assert row.text == "WARNING: \u2026"
    assert row.width == 10


@pytest.mark.parametrize(
    "divider, width, span",
    [
        (Divider(), 10, "\u2500" * 10),  # the full painting width by default
        (Divider(max_width=10), 40, "\u2500" * 10),  # a cap paints a shorter row
        (Divider(char="\u65e5"), 9, "\u65e5" * 4),  # a wide char fills 4 whole columns at a time
        (Divider(max_width=80), 12, "\u2500" * 12),  # a cap beyond the width changes nothing
    ],
)
def test_a_rule_fills_the_width_with_one_repeated_char(divider, width, span):
    rows = divider.render(width)
    assert [row.text for row in rows] == [span]
    assert rows[0].width <= width
    assert rows[0].segments[0].style == DEFAULT_THEME.border  # uncolored by default


def test_an_injected_border_style_round_trips():
    row = Divider(style=RULE).render(10)[0]
    assert row.segments == (Segment("\u2500" * 10, RULE),)


def test_a_divider_embeds_the_label_between_rule_segments():
    row = Divider(label="Working", label_style=RULE).render(20)[0]
    assert row.text == "\u2500\u2500 Working " + "\u2500" * 9
    assert row.width == 20
    assert row.segments == (
        Segment("\u2500\u2500", DEFAULT_THEME.border),
        Segment(" ", DEFAULT_THEME.border),
        Segment("Working", RULE),  # the label carries its own injected style
        Segment(" ", DEFAULT_THEME.border),
        Segment("\u2500" * 9, DEFAULT_THEME.border),
    )


@pytest.mark.parametrize("divider", [Divider(), Divider(max_width=16)])
def test_a_label_is_mutable_and_ellipsized_when_over_wide(divider):
    span = 16 if divider.max_width else 10
    divider.label = "a very long working label"  # a host re-labels one divider in place
    row = divider.render(span)[0]
    # Locate the label by text: with an uncolored border the rule segments
    # share the label's (no-)style, so style is no longer a discriminator.
    assert ellipsize_tail("a very long working label", span - 4) in [seg.text for seg in row.segments]
    assert row.width == span


def test_a_label_too_wide_for_the_capped_width_degrades_to_the_pure_rule():
    # width < 4 leaves no room for a label: the pure rule, like an empty label.
    for width in range(0, 4):
        assert Divider(label="Working").render(width) == Divider().render(width)
    assert Divider().render(0) == [Line()]
    assert Divider().render(-3) == [Line()]
    assert Divider(max_width=0).render(10)[0].text == ""
    # A wide char leaves the columns ragged; the final fit keeps the row honest.
    for width in (5, 9, 16):
        assert Divider(char="\u65e5", label="Working").render(width)[0].width <= width


def test_a_cap_is_a_plain_attribute_a_host_can_move():
    divider = Divider(max_width=6)
    assert divider.render(40)[0].text == "\u2500" * 6
    divider.max_width = None
    assert divider.render(12)[0].text == "\u2500" * 12


def test_panel_frames_the_child_with_an_optional_title():
    assert texts(Panel(Text("hi")), 12) == [
        "\u250c" + "\u2500" * 10 + "\u2510",
        "\u2502 hi       \u2502",
        "\u2514" + "\u2500" * 10 + "\u2518",
    ]
    titled = Panel(Text("body"), title="Info").render(20)
    assert titled[0].text.startswith("\u250c\u2500 Info \u2500")
    assert titled[0].text.endswith("\u2510")
    assert titled[0].width == 20


def test_panel_below_four_columns_degrades_to_the_bare_child():
    assert texts(Panel(Text("hello world")), 3) == ["hel", "lo", "wor", "ld"]
    assert Panel(Text("x")).render(1) == [Line.from_text("x")]
