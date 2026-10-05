"""Tests for mocode_tui.core.lines.

Contracts (the module docstring + COMPONENTS.md): a ``Line`` is one immutable
visual row of styled ``Segment``s; ``width`` goes through ``visible_width``
(never ``len``); ``fit(width)`` truncates with a one-column ``…`` whose style
inherits the truncated run; ``pad_to`` pads with plain spaces; ``+``
concatenates; ``Line.filled`` is the band/padding primitive; ``wrap_line``
shares the kernel break rule (spaces preferred, hard breaks, tabs become one
space) and keeps styles across breaks.
"""

import pytest

from mocode_tui.core.lines import Line, Segment, wrap_line
from mocode_tui.core.style import ACCENT, MUTED, SUCCESS, Style


def test_line_views():
    assert Line().segments == ()
    assert Line().text == "" and Line().width == 0 and Line().styled() == ""
    line = Line.from_text("hello")
    assert (line.text, line.width) == ("hello", 5)
    assert line.segments == (Segment("hello", Style()),)
    assert Line((Segment("ab"), Segment("日本"))).width == 6  # wcwidth, not len
    assert Line((Segment("a", ACCENT), Segment("b", MUTED))).styled() == (
        ACCENT.prefix() + "a" + MUTED.prefix() + "b" + "\x1b[0m"
    )


def test_line_is_immutable_and_comparable_by_segments():
    line = Line.from_text("x")
    with pytest.raises(AttributeError):
        line.text = "y"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        line.segments = ()  # type: ignore[misc]
    assert Line.from_text("a") == Line.from_text("a")
    assert hash(Line.from_text("a")) == hash(Line.from_text("a"))
    assert Line.from_text("a") != Line.from_text("a", ACCENT)  # styles count
    assert len({Line.from_text("a"), Line.from_text("a"), Line.from_text("b")}) == 2


def test_fit_returns_self_or_truncates_with_the_marker():
    line = Line.from_text("abc")
    assert line.fit(3) is line and line.fit(10) is line
    fitted = Line.from_text("abcdef").fit(4)
    assert fitted.text == "abc…" and fitted.width == 4
    assert fitted.segments == (Segment("abc…", Style()),)
    assert Line.from_text("abc").fit(1).text == "…"
    assert Line.from_text("abc").fit(0).text == ""
    assert Line.from_text("abc").fit(-2).text == ""
    wide = Line.from_text("日本語").fit(4)
    assert wide.text == "日…" and wide.width <= 4


def test_fit_marker_inherits_the_truncated_run_style():
    line = Line((Segment("abcdef", ACCENT),))
    fitted = line.fit(4)
    assert fitted.segments == (Segment("abc…", ACCENT),)
    assert fitted.styled() == ACCENT.prefix() + "abc…" + "\x1b[0m"


def test_pad_to_appends_plain_spaces():
    padded = Line.from_text("ab").pad_to(5)
    assert padded.text == "ab   " and padded.width == 5
    assert padded.segments == (Segment("ab", Style()), Segment("   ", Style()))
    assert Line((Segment("a", ACCENT),)).pad_to(3).segments == (
        Segment("a", ACCENT),
        Segment("  ", Style()),
    )
    line = Line.from_text("ab")
    assert line.pad_to(2) is line and line.pad_to(0) is line


def test_filled_is_the_band_primitive():
    assert Line.filled(0) == Line() and Line.filled(-4) == Line()
    row = Line.filled(3, SUCCESS)
    assert row.segments == (Segment("   ", SUCCESS),)
    assert row.styled() == SUCCESS.prefix() + "   " + "\x1b[0m"


def test_add_concatenates_and_keeps_styles():
    combined = Line.from_text("ab") + Line.from_text("cd")
    assert combined.text == "abcd" and combined.width == 4
    assert Line((Segment("a", ACCENT),)) + Line((Segment("b", MUTED),)) == Line(
        (Segment("a", ACCENT), Segment("b", MUTED))
    )
    with pytest.raises(TypeError):
        Line.from_text("a") + "b"  # type: ignore[operator]


def test_wrap_line_shares_the_kernel_break_rule():
    assert wrap_line(Line(), 10) == [Line()]
    assert wrap_line(Line.from_text("abc"), 0) == [Line()]
    assert wrap_line(Line.from_text("hello world"), 5) == [
        Line.from_text("hello"),
        Line.from_text("world"),
    ]
    # Styles survive across breaks, including hard breaks.
    assert wrap_line(Line((Segment("hello world", ACCENT),)), 5) == [
        Line((Segment("hello", ACCENT),)),
        Line((Segment("world", ACCENT),)),
    ]
    assert wrap_line(Line.from_text("abcdef"), 3) == [
        Line.from_text("abc"),
        Line.from_text("def"),
    ]
    assert wrap_line(Line.from_text("日本語"), 5) == [Line.from_text("日本"), Line.from_text("語")]


def test_wrap_line_tab_rule_and_whitespace():
    rows = wrap_line(Line.from_text("a\tb"), 10)
    assert rows == [Line.from_text("a b")] and rows[0].width == 3
    assert wrap_line(Line.from_text("  ab  "), 10) == [Line.from_text("ab")]
    assert wrap_line(Line.from_text("   "), 10) == [Line()]
