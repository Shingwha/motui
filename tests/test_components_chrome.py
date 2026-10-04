"""Tests for mocode_tui.components.chrome (Notice / Divider / Panel)."""

from mocode_tui.components.chrome import Divider, Notice, Panel
from mocode_tui.components.text import Text
from mocode_tui.lines import Line, Segment
from mocode_tui.style import BORDER, ERROR, NONE, WARNING


# --- Notice -------------------------------------------------------------------


def test_notice_info_is_bare():
    assert Notice("hello").render(20) == [Line.from_text("hello")]


def test_notice_warn_and_error_prefixes():
    assert Notice("careful", level="warn").render(30) == [
        Line((Segment("WARNING: ", WARNING), Segment("careful")))
    ]
    assert Notice("boom", level="error").render(30) == [
        Line((Segment("ERROR: ", ERROR), Segment("boom")))
    ]


def test_notice_prefix_and_text_share_one_row():
    row = Notice("boom", level="error").render(30)[0]
    assert row.text == "ERROR: boom"
    assert [seg.style for seg in row.segments] == [ERROR, NONE]


def test_notice_text_is_plain():
    row = Notice("boom", level="error").render(30)[0]
    assert row.segments[1] == Segment("boom")


def test_notice_unknown_level_degrades_to_info():
    assert Notice("hmm", level="verbose").render(20) == [Line.from_text("hmm")]


def test_notice_truncates_to_width():
    row = Notice("a very long warning message", level="warn").render(10)[0]
    assert row.text == "WARNING: \u2026"
    assert row.width == 10


# --- Divider ------------------------------------------------------------------


def test_divider_fills_width():
    assert Divider().render(10) == [Line.from_text("\u2500" * 10, BORDER)]


def test_divider_wide_char_stays_within_width():
    row = Divider(char="\u65e5").render(9)[0]
    assert row.text == "\u65e5" * 4
    assert row.width == 8 <= 9


def test_divider_degenerate_widths():
    assert Divider().render(0) == [Line()]
    assert Divider().render(-3) == [Line()]
    assert Divider(char="\u65e5").render(1) == [Line()]  # char wider than the row


# --- Panel --------------------------------------------------------------------


def test_panel_frames_child_and_pads_to_inner_width():
    rows = Panel(Text("hi")).render(12)
    assert [row.width for row in rows] == [12, 12, 12]
    assert rows[0].text == "\u250c" + "\u2500" * 10 + "\u2510"
    assert rows[1].text == "\u2502 hi       \u2502"
    assert rows[2].text == "\u2514" + "\u2500" * 10 + "\u2518"


def test_panel_title_embedded_in_top_border():
    rows = Panel(Text("body"), title="Info").render(20)
    assert rows[0].text.startswith("\u250c\u2500 Info \u2500")
    assert rows[0].text.endswith("\u2510")
    assert rows[0].width == 20
    assert rows[1].text.startswith("\u2502 body")


def test_panel_title_truncated_not_broken_layout():
    rows = Panel(Text("x"), title="a rather long panel title").render(14)
    assert rows[0].width == 14
    assert rows[0].text.startswith("\u250c\u2500 ")
    assert "\u2026" in rows[0].text


def test_panel_border_carries_style():
    rows = Panel(Text("x")).render(8)
    assert rows[0].segments == (Segment("\u250c" + "\u2500" * 6 + "\u2510", BORDER),)
    assert rows[1].segments[0].style == BORDER


def test_panel_multi_row_child_all_aligned():
    rows = Panel(Text("a\nbbb")).render(10)
    assert [row.width for row in rows] == [10] * 4
    assert rows[1].text == "\u2502 a      \u2502"
    assert rows[2].text == "\u2502 bbb    \u2502"


def test_panel_narrow_width_degrades_to_bare_child():
    rows = Panel(Text("hello world")).render(3)
    assert [row.text for row in rows] == ["hel", "lo", "wor", "ld"]
    assert all(row.width <= 3 for row in rows)


def test_panel_zero_width_does_not_crash():
    assert Panel(Text("x")).render(0) == [Line()]
    assert Panel(Text("x")).render(1) == [Line.from_text("x")]
