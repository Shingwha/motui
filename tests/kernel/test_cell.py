"""The immutable row model: Segment and Line values, their sizing,
combination, styling and cutting operations.

A Line is one visual row of styled segments; every operation returns a new
value and carries the inline payloads (link/action) along.  Cutting works in
two offset spaces -- character offsets (slice_line/wrap_line) and display
columns (cut_line) -- and both respect grapheme clusters.
"""

from __future__ import annotations

import pytest

from motui.kernel.cell import (
    Line,
    Segment,
    Surface,
    action_at,
    cut_line,
    fuse,
    overlay,
    rest,
    slice_line,
    wrap_line,
)
from motui.kernel.document import Document
from motui.kernel.layout import Viewport
from motui.kernel.style import NONE, RESET, Style
from motui.kernel.text import WrapMode
from motui.terminal.paint import Painter
from motui.terminal.render import styled_line
from motui.terminal.screen import HeadlessScreen
from tests.testing import Rows

ACCENT = Style(fg="#58a6ff", bold=True)
MUTED = Style(fg="#8b949e")
SUCCESS = Style(fg="#4bb563")

NASTY = [
    "\u26a0\ufe0f Blocked",
    "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466",
    "e\u0301e\u0301e\u0301",
    "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8",
    "a\tb\tc",
    "\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f end",
    "caf\u00e9 \U0001F600 \u4e2d\u6587",
    "x\U0001F468\u200D\U0001F469\u200Dy",
]


def test_an_empty_line_has_no_segments_or_width():
    line = Line()
    assert line.segments == ()
    assert line.text == "" and line.width == 0 and styled_line(line) == ""


def test_line_views_report_text_and_display_width():
    line = Line.from_text("hello")
    assert (line.text, line.width) == ("hello", 5)
    assert line.segments == (Segment("hello", Style()),)
    assert Line((Segment("ab"), Segment("\u65e5\u672c"))).width == 6


def test_styled_puts_a_reset_before_every_segment():
    line = Line((Segment("a", ACCENT), Segment("b", MUTED)))
    assert styled_line(line) == (
        ACCENT.prefix() + "a" + RESET + MUTED.prefix() + "b" + RESET
    )


def test_zero_width_segments_paint_nothing():
    assert styled_line(Line((Segment("", ACCENT), Segment("a", Style())))) == "a" + RESET
    assert styled_line(Line((Segment("", ACCENT),))) == ""


def test_styled_with_resolves_each_segment_for_the_mode():
    blue = Style(fg="#58a6ff")
    row = Line([Segment("", Style(dim=True)), Segment("x", Style()), Segment("y", blue)])
    assert styled_line(row, "256") == "x" + RESET + "\x1b[38;5;75my" + RESET
    assert styled_line(row, "16") == "x" + RESET + "\x1b[94my" + RESET
    assert styled_line(row, "none") == "x" + RESET + "y" + RESET
    assert styled_line(row, "truecolor") == styled_line(row)
    assert styled_line(Line(), "none") == ""


def test_line_is_immutable():
    line = Line.from_text("x")
    with pytest.raises(AttributeError):
        line.text = "y"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        line.segments = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        del line.text  # type: ignore[misc]


def test_line_equality_and_hash_follow_the_segments():
    assert Line.from_text("a") == Line.from_text("a")
    assert hash(Line.from_text("a")) == hash(Line.from_text("a"))
    assert Line.from_text("a") != Line.from_text("a", ACCENT)
    assert len({Line.from_text("a"), Line.from_text("a"), Line.from_text("b")}) == 2


def test_segment_link_counts_for_equality_and_action_does_not():
    plain = Segment("t", ACCENT)
    assert (plain.link, plain.action) == (None, None)
    assert Segment("t", ACCENT, link="a") != Segment("t", ACCENT, link="b")
    assert Segment("t", ACCENT, link="a") != plain
    assert Segment("t", ACCENT, action="a") == Segment("t", ACCENT, action="b")
    assert Segment("t", ACCENT, action="a").with_style(MUTED) == Segment(
        "t", MUTED, action="a"
    )


def test_styled_wraps_a_link_segment_in_the_osc8_pair():
    row = Line(
        [
            Segment("see ", Style()),
            Segment("docs", ACCENT, link="https://example.invalid"),
            Segment(" now", Style()),
        ]
    )
    link = ACCENT.prefix() + "\x1b]8;;https://example.invalid\x1b\\docs\x1b]8;;\x1b\\"
    assert styled_line(row) == "see " + RESET + link + RESET + " now" + RESET
    assert row.text == "see docs now" and row.width == 12
    plain_link = "\x1b]8;;https://example.invalid\x1b\\docs\x1b]8;;\x1b\\"
    assert styled_line(row, "none") == (
        "see " + RESET + "\x1b[1m" + plain_link + RESET + " now" + RESET
    )
    assert styled_line(row, "truecolor") == styled_line(row)


def test_slice_line_keeps_styles_and_payloads():
    payload = {"link": "https://example.invalid", "action": "open"}
    row = Line([Segment("a "), Segment("link", ACCENT, **payload), Segment(" z")])
    assert slice_line(row, 2, 6).segments == (Segment("link", ACCENT, **payload),)
    assert slice_line(row, 0, 2).segments == (Segment("a ", Style()),)
    assert slice_line(row, 2, 2) == Line()


def test_cut_line_cuts_by_display_columns():
    row = Line.from_text("abcdef")
    assert cut_line(row, 1, 4).text == "bcd"
    assert cut_line(row, 1, 4).width == 3
    assert cut_line(row, 0, 99).text == "abcdef"
    assert cut_line(row, 4, 4) == Line()


def test_cut_line_never_halves_a_cluster():
    row = Line.from_text("A\u26a0\ufe0fB")
    assert cut_line(row, 0, 2).width == 1
    assert cut_line(Line.from_text("a\u754cb"), 0, 2).text == "a"
    assert cut_line(Line.from_text("\u2764\U000E0100x"), 0, 1).text == "\u2764\U000E0100"
    assert cut_line(Line.from_text("\u2764\U000E0100x"), 1, 2).text == "x"


def test_cut_line_pieces_tile_the_row():
    for text in NASTY:
        row = Line.from_text(text)
        plain = text.replace("\t", " ")
        for column in range(row.width + 1):
            left, right = cut_line(row, 0, column), cut_line(row, column, row.width)
            assert left.text + right.text == plain, (text, column)
            assert left.width + right.width == row.width


def test_wrap_line_shares_the_break_rule():
    assert wrap_line(Line(), 10) == [Line()]
    assert wrap_line(Line.from_text("abc"), 0) == [Line()]
    assert wrap_line(Line.from_text("hello world"), 5) == [
        Line.from_text("hello"),
        Line.from_text("world"),
    ]
    assert wrap_line(Line.from_text("abcdef"), 3) == [
        Line.from_text("abc"),
        Line.from_text("def"),
    ]
    assert wrap_line(Line.from_text("\u65e5\u672c\u8a9e"), 5) == [
        Line.from_text("\u65e5\u672c"),
        Line.from_text("\u8a9e"),
    ]


def test_wrap_line_keeps_styles_across_breaks():
    assert wrap_line(Line((Segment("hello world", ACCENT),)), 5) == [
        Line((Segment("hello", ACCENT),)),
        Line((Segment("world", ACCENT),)),
    ]


def test_wrap_line_normalizes_tabs_and_drops_whitespace():
    rows = wrap_line(Line.from_text("a\tb"), 10)
    assert rows == [Line.from_text("a b")] and rows[0].width == 3
    assert wrap_line(Line.from_text("  ab  "), 10) == [Line.from_text("ab")]
    assert wrap_line(Line.from_text("   "), 10) == [Line()]


def test_ellipsis_clip_returns_the_line_itself_when_it_fits():
    row = Line.from_text("abc")
    assert row.clip(WrapMode.ELLIPSIS, 3) is row
    assert row.clip(WrapMode.ELLIPSIS, 10) is row


def test_ellipsis_clip_truncates_with_the_marker():
    fitted = Line.from_text("abcdef").clip(WrapMode.ELLIPSIS, 4)
    assert fitted.text == "abc\u2026" and fitted.width == 4
    assert fitted.segments == (Segment("abc\u2026", Style()),)
    assert Line.from_text("abc").clip(WrapMode.ELLIPSIS, 1).text == "\u2026"
    assert Line.from_text("abc").clip(WrapMode.ELLIPSIS, 0).text == ""
    assert Line.from_text("abc").clip(WrapMode.ELLIPSIS, -2).text == ""
    assert Line.from_text("\u65e5\u672c\u8a9e").clip(WrapMode.ELLIPSIS, 4).text == "\u65e5\u2026"


def test_ellipsis_clip_marker_inherits_the_kept_run_style():
    fitted = Line((Segment("abcdef", ACCENT),)).clip(WrapMode.ELLIPSIS, 4)
    assert fitted.segments == (Segment("abc\u2026", ACCENT),)
    assert styled_line(fitted) == ACCENT.prefix() + "abc\u2026" + RESET


def test_ellipsis_clip_postcondition_holds_for_nasty_rows():
    for text in NASTY:
        row = Line.from_text(text)
        for width in range(row.width + 3):
            assert row.clip(WrapMode.ELLIPSIS, width).width <= width, (text, width)


#: Width/character matrix for the five modes: ASCII, CJK, emoji, combining
#: marks, a ZWJ family, whitespace and the empty row.
REFLOW_TEXTS = [
    "abcdef",
    "hello world and more",
    "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8",
    "e\u0301e\u0301e\u0301",
    "\U0001F600x\U0001F600y",
    "caf\u00e9 \u4e2d\u6587 \U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466",
    "  ",
    "",
]

SINGLE_ROW_MODES = (WrapMode.ELLIPSIS, WrapMode.CLIP, WrapMode.OVERFLOW)
MULTI_ROW_MODES = (WrapMode.WORD, WrapMode.CHAR)


@pytest.mark.parametrize("mode", tuple(WrapMode))
@pytest.mark.parametrize("width", [0, 1, 2, 3, 7])
@pytest.mark.parametrize("text", REFLOW_TEXTS)
def test_reflow_obeys_the_row_contract(mode: WrapMode, width: int, text: str) -> None:
    rows = Line.from_text(text).reflow(mode, width)
    assert rows
    if mode in MULTI_ROW_MODES:
        assert len(rows) >= 1
    else:
        assert len(rows) == 1
    if mode is WrapMode.OVERFLOW:
        assert rows == [Line.from_text(text)]
    else:
        assert all(row.width <= width for row in rows), (
            text,
            width,
            mode,
            [row.text for row in rows],
        )


def test_reflow_word_matches_the_shared_break_rule() -> None:
    line = Line.from_text("hello world")
    assert [row.text for row in line.reflow(WrapMode.WORD, 5)] == ["hello", "world"]
    assert [row.text for row in line.reflow(WrapMode.WORD, 3)] == [
        "hel",
        "lo",
        "wor",
        "ld",
    ]
    assert line.clip(WrapMode.WORD, 5).text == "hello"


def test_reflow_char_breaks_between_cells_only() -> None:
    line = Line.from_text("\u65e5\u672c\u8a9e")
    assert [row.text for row in line.reflow(WrapMode.CHAR, 4)] == ["\u65e5\u672c", "\u8a9e"]
    # A cluster wider than the width owns its row and is then trimmed to fit.
    assert [row.text for row in line.reflow(WrapMode.CHAR, 1)] == [
        "\u2026",
        "\u2026",
        "\u2026",
    ]
    assert line.clip(WrapMode.CHAR, 4).text == "\u65e5\u672c"


def test_reflow_keeps_styles_and_payloads_across_rows() -> None:
    line = Line(
        (
            Segment("red green", ACCENT, link="u", action="a"),
            Segment(" tail", MUTED),
        )
    )
    rows = line.reflow(WrapMode.WORD, 5)
    assert [row.text for row in rows] == ["red", "green", "tail"]
    assert rows[0].segments == (Segment("red", ACCENT, link="u"),)
    assert rows[0].segments[0].action == "a"
    assert rows[1].segments == (Segment("green", ACCENT, link="u"),)
    assert rows[1].segments[0].action == "a"
    assert rows[2].segments == (Segment("tail", MUTED),)


def test_clip_mode_cuts_without_a_marker() -> None:
    assert Line.from_text("abcdef").clip(WrapMode.CLIP, 3).text == "abc"
    assert Line.from_text("\u65e5\u672c\u8a9e").clip(WrapMode.CLIP, 3).text == "\u65e5"
    assert Line.from_text("abc").clip(WrapMode.CLIP, 0).text == ""
    assert Line.from_text("abc").clip(WrapMode.CLIP, 10).text == "abc"


def test_overflow_keeps_the_row_whole() -> None:
    line = Line.from_text("abcdef")
    assert line.clip(WrapMode.OVERFLOW, 2) is line
    assert line.clip(WrapMode.OVERFLOW, 0) is line


def test_reflow_rejects_an_unknown_mode() -> None:
    with pytest.raises(ValueError):
        Line.from_text("abc").reflow(object(), 3)  # type: ignore[arg-type]


def test_reflow_zero_width_yields_one_empty_row() -> None:
    for mode in (m for m in WrapMode if m is not WrapMode.OVERFLOW):
        rows = Line.from_text("abc").reflow(mode, 0)
        assert rows == [Line()], mode


def test_fill_pads_with_plain_spaces_by_default():
    padded = Line.from_text("ab").fill(5, NONE)
    assert padded.text == "ab   " and padded.width == 5
    assert padded.segments == (Segment("ab", Style()), Segment("   ", Style()))
    row = Line.from_text("ab")
    assert row.fill(2, NONE) is row
    assert row.fill(5, Style()).segments == padded.segments


def test_fill_merges_a_band_under_the_content():
    band = Style(bg="#123456")
    row = Line((Segment("hi", ACCENT), Segment("!", MUTED)))
    assert row.fill(6, band).segments == (
        Segment("hi", band.merge(ACCENT)),
        Segment("!", band.merge(MUTED)),
        Segment("   ", band),
    )
    assert Line.from_text("hi").fill(5, band).segments == (
        Segment("hi", band),
        Segment("   ", band),
    )


def test_fill_never_truncates():
    row = Line.from_text("abcdef")
    assert row.fill(3, SUCCESS).text == "abcdef"
    assert row.fill(10, SUCCESS).text == "abcdef    "


def test_fill_and_filled_degenerate_widths():
    assert Line.from_text("abc").fill(0, SUCCESS) == Line()
    assert Line.from_text("abc").fill(-4) == Line()
    assert Line.filled(0) == Line() and Line.filled(-4) == Line()
    band = Line.filled(3, SUCCESS)
    assert band.segments == (Segment("   ", SUCCESS),)
    assert styled_line(band) == SUCCESS.prefix() + "   " + RESET


def test_add_concatenates_lines_and_keeps_styles():
    combined = Line.from_text("ab") + Line.from_text("cd")
    assert combined.text == "abcd" and combined.width == 4
    assert Line((Segment("a", ACCENT),)) + Line((Segment("b", MUTED),)) == Line(
        (Segment("a", ACCENT), Segment("b", MUTED))
    )
    with pytest.raises(TypeError):
        Line.from_text("a") + "b"  # type: ignore[operator]


def test_merge_span_restyles_only_intersecting_segments():
    band = Style(reverse=True)
    row = Line(
        [
            Segment("see ", Style()),
            Segment("docs", ACCENT, link="u", action="open"),
            Segment(" now", Style()),
        ]
    )
    merged = row.merge_span(4, 8, band)
    assert merged is not row and merged.text == row.text
    assert merged.segments[0] is row.segments[0]
    assert merged.segments[2] is row.segments[2]
    assert merged.segments[1] == Segment("docs", ACCENT.merge(band), link="u", action="open")
    assert row.merge_span(99, 120, band) is row
    assert row.merge_span(4, 4, band) is row
    assert row.merge_span(-3, 0, band) is row


def test_action_at_reports_the_span_under_a_column():
    row = Line(
        [
            Segment("ab", Style()),
            Segment("\u4e2d\u6587", SUCCESS, action="wide"),
            Segment(" x", Style(), action="tail"),
        ]
    )
    assert row.width == 8
    assert action_at(row, 0) is None
    assert action_at(row, 2) == ("wide", 2, 6)
    assert action_at(row, 5) == ("wide", 2, 6)
    assert action_at(row, 6) == ("tail", 6, 8)
    assert action_at(row, 8) is None
    assert action_at(row, -1) is None
    assert action_at(Line(), 0) is None


def test_fuse_coalesces_runs_with_equal_style_and_payloads():
    link = Segment("link", ACCENT, link="https://example.invalid", action="open")
    assert fuse([link, Segment("link", ACCENT, link="https://example.invalid", action="open")]) == [
        Segment("linklink", ACCENT, link="https://example.invalid", action="open")
    ]
    assert fuse([link, Segment("link", ACCENT)]) == [link, Segment("link", ACCENT)]
    assert fuse([Segment("li", ACCENT, action="a"), Segment("nk", ACCENT, action="b")]) == [
        Segment("li", ACCENT, action="a"),
        Segment("nk", ACCENT, action="b"),
    ]


def test_overlay_applies_the_base_under_attribute_only_runs():
    payload = {"link": "u", "action": "open"}
    assert overlay(NONE, [Segment("t", Style(bold=True), **payload)]) == [
        Segment("t", Style(bold=True), **payload)
    ]
    band = Style(bg="#010203")
    assert overlay(band, [Segment("t", Style(bold=True))]) == [
        Segment("t", band.merge(Style(bold=True)))
    ]
    colored = Style(fg="#abcdef")
    assert overlay(band, [Segment("t", colored)]) == [Segment("t", colored)]


def test_rest_fills_at_the_rows_own_width_with_the_band_underneath():
    painted = rest(Line.from_text("abcdef"), 6, ACCENT)
    assert painted.width == 6 and painted.text == "abcdef"
    assert all(seg.style == ACCENT for seg in painted.segments)
    short = rest(Line.from_text("abc"), 10, ACCENT)
    assert short.width == 3
    truncated = rest(Line.from_text("abcdef"), 4, ACCENT)
    assert truncated.width == 4 and truncated.text.endswith("\u2026")


def test_rest_has_a_none_fast_path():
    row = Line.from_text("abc")
    assert rest(row, 10, NONE) is row
    assert rest(row, 6, NONE).text == "abc"


def test_segment_strips_injected_control_sequences():
    # The door deletes the escape byte itself; the printable characters an
    # injected sequence carried stay behind as inert cells ("[?1000l" cannot
    # drive a terminal).
    assert Segment("a\x1b[?1000lb").text == "a[?1000lb"
    assert "\x1b" not in Segment("\x1b]0;title\x07").text
    # CR/LF are C0 content too: a segment is one row, and the pair is 0-column.
    assert Segment("a\r\nb").text == "ab"
    row = Line.from_text(
        "OUT: \x1b[?1000l\x1b[?1006l\x1b]52;c;base64\x07\x1b]0;title\x07"
    )
    painted = styled_line(row)
    for injected in ("\x1b[?1000l", "\x1b[?1006l", "\x1b]52;", "\x1b]0;"):
        assert injected not in painted, injected
    # Idempotent: the rebuild a restyle makes passes the door again, unchanged.
    assert row.segments[0].with_style(ACCENT).text == row.segments[0].text


def test_segment_normalizes_a_tab_to_one_space():
    # The repo's one tab rule (text._normalize_tabs, TAB_WIDTH == 1), enforced
    # at the door too, so a segment built off the wrap path follows it as
    # well -- a tab counts one column, like the space that replaces it.
    assert Segment("a\tb").text == "a b" and Segment("a\tb").width == 3
    assert styled_line(Line.from_text("a\tb")) == "a b" + RESET


def test_segment_sanitizes_the_link_payload():
    # A link rides inside the OSC 8 pair; stripped of ESC and BEL it can
    # neither close that pair early nor open a new escape of its own.
    assert Segment("x", link="\x1b]8;;evil\x07").link == "]8;;evil"
    # A link that sanitizes away entirely is no link at all.
    assert Segment("x", link="\x1b\x07").link is None


def test_painted_bytes_never_carry_an_injected_sequence():
    # The security report's byte-level reproduction, end to end: a document
    # whose every row is injected content paints through the Painter without
    # one of its sequences reaching the screen's byte stream.
    doc = Document()
    doc.add(Rows("OUT: \x1b[?1000l\x1b[?1006l", "\x1b]52;c;base64\x07\x1b]0;title\x07"))
    screen = HeadlessScreen(width=80, height=6)
    Painter(screen).paint(Viewport(doc).layout(80, 6))
    for injected in ("\x1b[?1000l", "\x1b[?1006l", "\x1b]52;", "\x1b]0;"):
        assert injected not in screen.output, injected


# -- overlay composition -----------------------------------------------------


def test_a_blank_top_row_keeps_the_base_row_unchanged():
    base = Line((Segment("a", ACCENT), Segment("bc", MUTED)))
    assert Line().overlay(base) is base
    assert Line.from_text("   ").overlay(base) == base
    # A wider blank top pads the base rather than replacing anything.
    assert Line.from_text("     ").overlay(base) == base.pad(5)


def test_a_top_glyph_replaces_the_base_cell_and_merges_styles():
    base = Line((Segment("ab", ACCENT),))
    top_style = Style(bg="#000000", underline=True)
    merged = Line((Segment("X", top_style),)).overlay(base)
    assert merged.text == "Xb"
    assert merged.segments == (
        Segment("X", ACCENT.merge(top_style)),
        Segment("b", ACCENT),
    )


def test_a_styled_space_covers_the_glyph_and_keeps_the_band():
    band = Style(bg="#123456")
    merged = Line((Segment(" ", Style(bold=True)),)).overlay(
        Line((Segment("ab", band),))
    )
    assert merged.text == " b"
    assert merged.segments == (
        Segment(" ", band.merge(Style(bold=True))),
        Segment("b", band),
    )


def test_payloads_ride_on_top_cells_and_transparent_cells_keep_the_base():
    base = Line((Segment("ab", Style(), link="base", action="open"),))
    top = Line(
        (Segment("X", Style(), link="top", action="hit"), Segment(" "))
    )
    assert top.overlay(base).segments == (
        Segment("X", Style(), link="top", action="hit"),
        Segment("b", Style(), link="base", action="open"),
    )


def test_overlay_width_is_the_wider_row_and_the_short_side_is_blank():
    assert Line.from_text("abcd").overlay(Line.from_text("X")).text == "abcd"
    wider_base = Line.from_text("X").overlay(Line.from_text("abcd"))
    assert (wider_base.text, wider_base.width) == ("Xbcd", 4)
    wider_top = Line.from_text("abcd").overlay(Line.from_text("X"))
    assert (wider_top.text, wider_top.width) == ("abcd", 4)


def test_wide_characters_are_replaced_or_kept_whole():
    base = Line.from_text("\u4e2d")
    # Covering either half replaces the whole glyph: a blank fills the other
    # column, so no continuation is ever left dangling.
    lead = Line.from_text("X").overlay(base)
    assert (lead.text, lead.width) == ("X ", 2)
    continuation = Line.from_text(" X").overlay(base)
    assert (continuation.text, continuation.width) == (" X", 2)
    # A transparent top keeps the whole base glyph.
    assert Line.from_text("  ").overlay(base) == base
    # A double-wide top cell covers both columns of two narrow base cells.
    assert Line.from_text("\u4e2d").overlay(Line.from_text("ab")).text == "\u4e2d"


def test_surface_overlay_composes_rows_and_takes_the_max_size():
    top = Surface(width=2, rows=(Line.from_text("X"),))
    base = Surface(width=3, rows=(Line.from_text("abc"), Line.from_text("def")))
    merged = top.overlay(base)
    assert (merged.width, merged.height) == (3, 2)
    assert [row.text for row in merged.rows] == ["Xbc", "def"]
    assert all(row.width == 3 for row in merged.rows)
    # Missing top rows are blank: the base shows through, padded to width.
    tall_base = Surface(width=3, rows=(Line.from_text("abc"),))
    blank_top = Surface(width=3, rows=(Line(), Line.from_text("Y")))
    assert [row.text for row in blank_top.overlay(tall_base).rows] == ["abc", "Y  "]
    assert [row.text for row in tall_base.rows] == ["abc"]
