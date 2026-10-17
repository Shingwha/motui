"""The text kernel: the measuring truth, the fit family, and the Line row.

``visible_width`` is the single width truth; ``fit_text``, ``ellipsize_tail``,
``wrap_text`` and ``Line.fit`` build on it, so no row ever exceeds the width.
"""

import itertools

import pytest

from motui.kernel.ansi import ESC
from motui.kernel.lines import (
    Line,
    Segment,
    action_at,
    cut_line,
    fuse,
    overlay,
    slice_line,
    styled_with,
    wrap_line,
)
from motui.kernel.style import (
    ACCENT,
    MUTED,
    NONE,
    RESET,
    SUCCESS,
    Style,
    sgr_prefix,
)
from motui.kernel.text import (
    ellipsize_tail,
    fit_text,
    terminal_size,
    visible_width,
    wrap_text,
)

# Nasty inputs: VS16-widened emoji, a ZWJ family, a combining sequence,
# wide CJK, tabs, and a run that mixes everything above.
NASTY = [
    "\u26a0\ufe0f Blocked",  # VS16: whole 2, per-character sum 1
    "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466",  # ZWJ family: whole 2, per-char 8
    "e\u0301e\u0301e\u0301",  # combining acute accents
    "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8",  # CJK wide
    "a\tb\tc",  # tabs count one column each
    "\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f end",  # stacked VS16 emoji
    "caf\u00e9 \U0001F600 \u4e2d\u6587",  # mixed narrow, emoji, CJK
    "x\U0001F468\u200D\U0001F469\u200dy",  # a family inside plain text
]


# --- measuring truth -----------------------------------------------------------


def test_visible_width_empty_ascii_and_wide():
    assert visible_width("") == 0
    assert visible_width("abc") == 3
    assert visible_width("中文") == 4  # wide characters count two columns
    assert visible_width("a中b") == 4
    assert visible_width("\U0001f389") == 2  # emoji


def test_visible_width_non_printable_and_tab():
    assert visible_width("a\x07b") == 2  # the bell contributes nothing
    assert visible_width(ESC + "[31m") == 4  # escape dropped, "[31m" counted
    assert visible_width("a\tb") == 3  # a tab counts as exactly one column


def test_visible_width_measures_grapheme_clusters():
    # The cluster rules on the fixture's real sequences: a ZWJ run, a
    # skin-tone modifier, a VS16-widened base and a regional-indicator
    # pair each measure the one cell a terminal paints them as.
    assert visible_width("\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466") == 2  # family
    assert visible_width("\U0001F9D1\U0001F3FD\u200D\U0001F4BB") == 2  # technologist
    assert visible_width("\U0001F3F3\uFE0F\u200D\U0001F308") == 2  # rainbow flag
    assert visible_width("\U0001F44B\U0001F3FD") == 2  # wave with a skin tone
    assert visible_width("\U0001F1EF\U0001F1F5") == 2  # two indicators, one flag cell
    assert visible_width("\u2705") == 2  # a plain emoji cell
    assert visible_width("abc") == 3  # plain ASCII
    assert visible_width("\u0301abc") == 3  # a lone combining mark adds 0
    # The fixture's emoji row: 87 columns of text around four two-column
    # clusters -- 87 + 4 * 2 = 95 columns, what a terminal renders -- so at
    # a 78-column pane the row wraps where the terminal breaks it.
    row = (
        "Zero-width and combined: \U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"
        " (family), \U0001F468\u200D\U0001F4BB (man technologist),"
        " \U0001F3F3\uFE0F\u200D\U0001F308 (rainbow flag), \U0001F44D\U0001F3FD (skin tone)."
    )
    assert visible_width(row) == 95
    rows = wrap_text(row, 78)
    assert [visible_width(r) for r in rows] == [72, 22]
    assert rows[0].endswith("(rainbow") and rows[1].startswith("flag),")
    assert " ".join(rows) == row  # the break drops exactly the one space


def test_wrap_text_empty_and_degenerate_widths():
    assert wrap_text("", 10) == [""]
    assert wrap_text("anything", 0) == [""]
    assert wrap_text("anything", -3) == [""]


def test_wrap_text_breaks_at_spaces():
    assert wrap_text("hello world", 5) == ["hello", "world"]
    assert wrap_text("aa bb cc", 5) == ["aa bb", "cc"]
    assert wrap_text("  ab  ", 10) == ["ab"]  # break whitespace is dropped


def test_wrap_text_hard_breaks_over_long_words_and_cjk():
    assert wrap_text("abcdef", 3) == ["abc", "def"]
    assert wrap_text("日本語", 4) == ["日本", "語"]
    # width 1 terminates: a wide character owns its own row.
    assert wrap_text("日本語abc", 1) == ["日", "本", "語", "a", "b", "c"]


def test_wrap_text_tabs_are_one_space_and_breakable():
    assert wrap_text("a\tb", 10) == ["a b"]
    assert wrap_text("ab\tcd", 3) == ["ab", "cd"]


def test_terminal_size_reports_positive_columns_and_rows():
    cols, rows = terminal_size()
    assert isinstance(cols, int) and cols > 0
    assert isinstance(rows, int) and rows > 0


# --- fit_text postconditions ---------------------------------------------------


def test_fit_text_returns_a_prefix_within_budget_for_every_budget():
    for text in NASTY:
        for budget in range(len(text) + 3):
            result = fit_text(text, budget)
            assert text.startswith(result)  # always a prefix
            assert visible_width(result) <= budget  # the hard postcondition


def test_fit_text_cannot_be_extended_by_one_more_character():
    for text in NASTY:
        for budget in range(len(text) + 3):
            result = fit_text(text, budget)
            if len(result) < len(text):
                # The cut is local-greedy: one more character overflows
                # (a later cluster collapse is the documented simplification).
                assert visible_width(text[: len(result) + 1]) > budget


def test_fit_text_returns_whole_text_when_it_fits_and_empty_on_no_budget():
    assert fit_text("abcdef", 6) == "abcdef"
    assert fit_text("abcdef", 99) == "abcdef"
    assert fit_text("\u26a0\ufe0f Blocked", 10) == "\u26a0\ufe0f Blocked"
    assert fit_text("abcdef", 0) == ""
    assert fit_text("abcdef", -3) == ""


def test_ellipsize_tail_postcondition_holds_for_every_budget():
    for text in NASTY:
        for budget in range(len(text) + 3):
            assert visible_width(ellipsize_tail(text, budget)) <= budget


def test_ellipsize_tail_vs16_emoji_stays_within_the_budget():
    # Regression (red before the fix): the old per-character walk measured
    # "\u26a0\ufe0f" as one column while whole-string measurement says two,
    # so the one-column marker pushed the result to five columns at width 4.
    assert visible_width(ellipsize_tail("\u26a0\ufe0f Blocked", 4)) <= 4
    assert ellipsize_tail("\u26a0\ufe0f Blocked", 4) == "\u26a0\ufe0f \u2026"


def test_ellipsize_tail_keeps_its_documented_shape():
    assert ellipsize_tail("abc", 3) == "abc"  # fits: unchanged
    assert ellipsize_tail("abcdef", 4) == "abc\u2026"
    assert ellipsize_tail("abcdef", 1) == "\u2026"
    assert ellipsize_tail("abcdef", 0) == ""
    assert ellipsize_tail("abcdef", -5) == ""
    assert ellipsize_tail("\u65e5\u672c\u8a9e", 4) == "\u65e5\u2026"


def test_line_fit_postcondition_holds_for_every_width():
    # The same nasty inputs as separate segments of one line: Line.fit's
    # inner truncation runs through fit_text now, so the row never
    # overflows -- the second measurement path is gone.
    segments = [Segment(text) for text in NASTY]
    joined = "".join(text for text in NASTY)
    for width in range(len(joined) + 3):
        row = Line(segments).fit(width)
        assert row.width <= width


def test_line_fit_multi_segment_examples():
    row = Line((Segment("ab", ACCENT), Segment("\u26a0\ufe0fx", NONE))).fit(4)
    # Three columns of text survive ("ab" + the bare warning sign, its
    # VS16 selector no longer fits) and the marker takes the fourth.
    assert row.text == "ab\u26a0\u2026" and row.width == 4
    assert row.segments == (Segment("ab", ACCENT), Segment("\u26a0\u2026", NONE))
    # A zero-width run never blocks the marker: the style still fuses.
    assert Line((Segment("\u200d", Style(italic=True)), Segment("abc"))).fit(2).width == 2


# --- the Line row --------------------------------------------------------------


def test_line_views():
    assert Line().segments == ()
    assert Line().text == "" and Line().width == 0 and Line().styled() == ""
    line = Line.from_text("hello")
    assert (line.text, line.width) == ("hello", 5)
    assert line.segments == (Segment("hello", Style()),)
    assert Line((Segment("ab"), Segment("日本"))).width == 6  # wcwidth, not len
    assert Line((Segment("a", ACCENT), Segment("b", MUTED))).styled() == (
        ACCENT.prefix() + "a" + RESET + MUTED.prefix() + "b" + RESET
    )


def test_styled_resets_between_segments_so_no_attribute_crosses_a_boundary():
    # Red before the fix: RESET was inserted only on a styled -> unstyled
    # transition, so between two styled segments the second prefix merely
    # *added* SGR state -- a scrollbar's dim and a separator's bold reached
    # the pane's gold headings, which is the dim right pane of the split.
    track = Style(dim=True)
    divider = Style(fg="#58a6ff", bold=True)
    gold = Style(fg="#e3b341")
    row = Line(
        [
            Segment("x", Style()),
            Segment("░", track),
            Segment(" ", divider),
            Segment("### Escaping", gold),
        ]
    )
    styled = row.styled()
    # Every segment after the first non-empty one is preceded by a RESET, so
    # the heading's gold prefix is the first SGR opened after one and the
    # only ``dim`` in the row sits on the track segment.
    assert styled == (
        "x" + RESET + track.prefix() + "░" + RESET + divider.prefix() + " "
        + RESET + gold.prefix() + "### Escaping" + RESET
    )
    assert styled.count(track.prefix()) == 1
    heading = styled.index("### Escaping")
    assert styled.rindex(RESET, 0, heading) == styled.index(gold.prefix()) - len(RESET)
    # The trailing RESET stays exactly one, whatever the boundaries added.
    assert styled.endswith(RESET) and styled.count(RESET) == 4
    # A zero-width segment paints nothing and opens no reset of its own.
    assert Line((Segment("", track), Segment("a", Style()))).styled() == "a" + RESET


def test_styled_with_downgrades_each_segment_and_never_caches():
    # The same assembly as Line.styled(), with every segment's prefix
    # resolved through sgr_prefix(style, mode) -- the painter's downgrade
    # path.  The row's own cache is untouched: styled() still answers the
    # truecolor bytes afterwards.
    track = Style(dim=True)
    blue = Style(fg="#58a6ff")
    row = Line([Segment("", track), Segment("x", Style()), Segment("y", blue)])
    assert styled_with(row, "256") == (
        "x" + RESET + "\x1b[38;5;75m" + "y" + RESET
    )
    assert styled_with(row, "16") == "x" + RESET + "\x1b[94m" + "y" + RESET
    assert styled_with(row, "none") == "x" + RESET + "y" + RESET
    assert styled_with(Line(), "none") == ""  # an empty line paints nothing
    assert row.styled() == "x" + RESET + blue.prefix() + "y" + RESET


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


def test_a_segment_carries_a_link_and_an_action():
    plain = Segment("t", ACCENT)
    assert (plain.link, plain.action) == (None, None)
    payloads = Segment("t", ACCENT, link="https://example.invalid", action="open")
    assert payloads.text == "t" and payloads.link == "https://example.invalid"
    assert payloads.action == "open" and payloads.width == 1
    assert payloads.with_style(MUTED) == Segment(
        "t", MUTED, link="https://example.invalid", action="open"
    )
    # ``link`` participates in equality (a changed link must repaint the
    # row); ``action`` is metadata and never reaches a byte, so it must not
    # make two visibly identical rows compare different.
    assert Segment("t", ACCENT, link="a") != Segment("t", ACCENT, link="b")
    assert Segment("t", ACCENT, link="a") != plain
    assert Segment("t", ACCENT, action="a") == Segment("t", ACCENT, action="b")
    assert len({Segment("t", ACCENT, action="a"), Segment("t", ACCENT, action="b")}) == 1


def test_styled_wraps_a_link_segment_in_the_osc8_pair_and_leaves_the_rest_alone():
    row = Line(
        [
            Segment("see ", Style()),
            Segment("docs", ACCENT, link="https://example.invalid"),
            Segment(" now", Style()),
        ]
    )
    link = ACCENT.prefix() + "\x1b]8;;https://example.invalid\x1b\\docs\x1b]8;;\x1b\\"
    assert row.styled() == "see " + RESET + link + RESET + " now" + RESET
    # The text still measures as the label alone: the pair is bytes, not cells.
    assert row.text == "see docs now" and row.width == 12
    # A hyperlink is not a color: the downgraded path keeps it in every mode
    # (the SGR prefix around it is the mode's own).
    plain_link = "\x1b]8;;https://example.invalid\x1b\\docs\x1b]8;;\x1b\\"
    assert styled_with(row, "none") == (
        "see " + RESET + sgr_prefix(ACCENT, "none") + plain_link + RESET + " now" + RESET
    )
    assert styled_with(row, "truecolor") == row.styled()
    # A row without a link is byte-for-byte what it always was.
    assert Line((Segment("a", ACCENT), Segment("b"))).styled() == (
        ACCENT.prefix() + "a" + RESET + "b" + RESET
    )


def test_the_cut_fit_overlay_and_fuse_family_carries_the_payloads():
    payload = dict(link="https://example.invalid", action="open")
    link = Segment("link", ACCENT, **payload)
    line = Line([Segment("a "), Segment("link", ACCENT, **payload), Segment(" z")])
    # slice_line (what wrap_line cuts through) and the column cut.
    assert slice_line(line, 2, 6).segments == (Segment("link", ACCENT, **payload),)
    assert cut_line(line, 0, 3).segments == (
        Segment("a ", Style()),
        Segment("l", ACCENT, **payload),
    )
    # fit: the truncated piece keeps the payload, and so does the ellipsis it
    # fuses onto -- a truncated link's cells stay one span.
    fitted = Line([Segment("x "), link]).fit(4)
    assert fitted.segments == (
        Segment("x ", Style()),
        Segment("l…", ACCENT, **payload),
    )
    # overlay (the inline engine's restyle) and with_style.
    assert overlay(NONE, [Segment("link", Style(bold=True), **payload)]) == [
        Segment("link", Style(bold=True), **payload)
    ]
    assert Segment("link", Style(), **payload).with_style(MUTED) == Segment(
        "link", MUTED, **payload
    )
    # fuse merges equal payloads and refuses to merge different ones -- the
    # merged run would otherwise link and answer clicks for the wrong half.
    assert fuse([link, Segment("link", ACCENT, **payload)]) == [
        Segment("linklink", ACCENT, **payload)
    ]
    assert fuse([link, Segment("link", ACCENT)]) == [link, Segment("link", ACCENT)]
    assert fuse([Segment("li", ACCENT, action="a"), Segment("nk", ACCENT, action="b")]) == [
        Segment("li", ACCENT, action="a"),
        Segment("nk", ACCENT, action="b"),
    ]


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
    assert fitted.styled() == ACCENT.prefix() + "abc…" + RESET


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
    assert row.styled() == SUCCESS.prefix() + "   " + RESET


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


# --- the column-space cut --------------------------------------------------------


def test_cut_line_walks_clusters_so_a_window_never_overruns():
    # Red before the fix: the column walk counted characters, so on a cluster
    # that measures wider than its characters the cut came back past the
    # window it was promised -- cut_line("A\u26a0\ufe0fB", 0, 2) was three
    # columns wide.  The walk now runs the same cluster rules visible_width
    # sums, so the boundary snaps to the cluster's edge instead of halving
    # one, and the straddled cluster is attributed whole to the later cut.
    row = Line.from_text("A\u26a0\ufe0fB")
    assert cut_line(row, 0, 2).width == 1  # \u26a0\ufe0f straddles column 2: dropped whole
    # Every prefix cut of a cluster-laden row respects the window it asked
    # for -- the property a splice's left and middle pieces are built on.
    for text in NASTY:
        line = Line.from_text(text)
        for budget in range(line.width + 2):
            assert cut_line(line, 0, budget).width <= budget
    # And the two cuts meeting at one column never lose or duplicate a cell:
    # the floor rule sends the straddling cluster to exactly one of them,
    # so the pieces still tile the row a selection overlay re-concatenates.
    for text in NASTY:
        line = Line.from_text(text)
        # slice_line's documented tab rule turns a kept tab into one space
        plain = text.replace("\t", " ")
        for cut in range(line.width + 1):
            left, right = cut_line(line, 0, cut), cut_line(line, cut, line.width)
            assert left.text + right.text == plain
            assert left.width + right.width == line.width


def test_visible_width_matches_the_direct_wcwidth_measure_of_the_corpus():
    # The memoized per-character width is a cache and not a second opinion:
    # every corpus row still measures what direct wcwidth/wcswidth counting
    # gives, cell by cell, over the scanner's own cells.
    from wcwidth import wcswidth, wcwidth

    from motui.kernel.text import _cell_spans

    def direct_width(cell: str) -> int:
        if "\t" in cell:
            # The documented tab rule: a tab counts as exactly one column,
            # whatever the library says about it.
            return cell.count("\t")
        direct = wcswidth(cell)
        if direct is not None and direct >= 0:
            return direct
        return sum(w for w in map(wcwidth, cell) if w and w > 0)

    for text in NASTY:
        cells = list(_cell_spans(text))
        assert cells  # every corpus row prints something
        # Every cell's width is the one direct wcswidth/wcwidth gives for it,
        # so no memoized answer has drifted from the library's own.
        for start, end, width in cells:
            assert width == direct_width(text[start:end])
        # And those cells, summed, are the measure the toolkit reports.
        assert sum(w for _s, _e, w in cells) == visible_width(text)


def test_index_bounds_at_columns_answers_every_boundary_as_one_walk_would():
    # The N-boundary resolver is the one walk: its answer for any set of
    # columns, in any order and however repeated, is the answer the
    # two-boundary form gives for the same pair.  A run of printable ASCII
    # is skipped arithmetically -- one cell per character, the scanner's own
    # rule -- and every other stretch goes through the scanner itself, so
    # the two shapes agree wherever the fast path and the scanner meet,
    # including where a cluster straddles the seam between them.
    from motui.kernel.text import index_bounds_at_columns, index_pair_at_columns

    for text in NASTY:
        width = visible_width(text)
        for columns in itertools.combinations_with_replacement(
            range(0, width + 3), 3
        ):
            bounds = index_bounds_at_columns(text, *columns)
            by_column = dict(zip(columns, bounds))
            # The pair form is a delegation, not a second answer.
            for first, second in zip(columns, columns[1:]):
                assert index_pair_at_columns(text, first, second) == (
                    by_column[first],
                    by_column[second],
                )
        # A boundary past the last cell is the end of the text, and one at
        # or before column 0 is its start -- the single form and the whole
        # set alike.
        assert index_bounds_at_columns(text, width + 1) == (len(text),)
        assert index_bounds_at_columns(text, 0) == (0,)
        assert index_bounds_at_columns(text, -7) == (0,)
        assert index_bounds_at_columns(text, 0, -7, width + 1) == (
            0,
            0,
            len(text),
        )


# --- the inline-action lookup --------------------------------------------------


def test_action_at_answers_the_span_under_a_column():
    line = Line(
        [
            Segment("ab", Style()),
            Segment("\u4e2d\u6587", SUCCESS, action="wide"),  # columns 2..6
            Segment(" x", Style(), action="tail"),  # columns 6..8
        ]
    )
    assert line.width == 8
    assert action_at(line, 0) is None  # 'a' carries no action
    assert action_at(line, 1) is None
    assert action_at(line, 2) == ("wide", 2, 6)
    assert action_at(line, 3) == ("wide", 2, 6)  # the wide cluster's own cell
    assert action_at(line, 5) == ("wide", 2, 6)  # its last cell, still in range
    assert action_at(line, 6) == ("tail", 6, 8)  # left-closed, right-open
    assert action_at(line, 7) == ("tail", 6, 8)
    assert action_at(line, 8) is None  # one past the end
    assert action_at(line, 99) is None
    assert action_at(line, -1) is None
    assert action_at(Line(), 0) is None
    assert action_at(Line((Segment("\u4e2d", SUCCESS, action="a"),)), 1) == ("a", 0, 2)
    # Pure: nothing on the line is touched, and every call answers the same.
    assert action_at(line, 2) == action_at(line, 2)
    assert line.text == "ab\u4e2d\u6587 x"


# -- the Text component (motui.kernel.lines.Text) ----------------------------
from dataclasses import replace  # noqa: E402

from motui.kernel.style import DIM  # noqa: E402
from motui.kernel.lines import Text  # noqa: E402
from motui.kernel.theme import DEFAULT_THEME  # noqa: E402

def test_verbatim_text_renders_at_the_default_width():
    assert [row.text for row in Text("hello").render(80)] == ["hello"]


def test_blank_lines_survive_as_blank_rows():
    assert [row.text for row in Text("a\n\nb").render(80)] == ["a", "", "b"]


def test_wraps_at_spaces_at_a_narrow_width():
    rows = Text("hello world").render(5)
    assert [row.text for row in rows] == ["hello", "world"]
    assert all(row.width <= 5 for row in rows)


def test_style_applies_to_every_row():
    rows = Text("ab\ncd", style=DIM).render(10)
    assert [row.text for row in rows] == ["ab", "cd"]
    assert all(seg.style == DIM for row in rows for seg in row.segments)


def test_text_is_mutable_for_streaming():
    stream = Text("one ")
    assert stream.render(80) == [Line.from_text("one")]
    stream.text += "two"  # assign one chunk at a time
    assert stream.render(80) == [Line.from_text("one two")]


def test_hard_breaks_at_width_one_and_empties_at_zero():
    # width 1 hard-breaks every character; width 0 yields one empty row.
    assert [row.text for row in Text("hi").render(1)] == ["h", "i"]
    assert Text("hi").render(0) == [Line()]


class SpanText(Text):
    """A ``Text`` whose row carries an inline span (the documented seam).

    The default ``Text`` renders verbatim rows, which carry no payloads; a
    subclass that returns its own ``Line`` values from ``_rows_for`` gets the
    inherited hit testing, hover transform and ``chosen`` for free.
    """

    def _rows_for(self, width: int) -> list[Line]:
        return [
            Line(
                [
                    Segment("see ", Style()),
                    Segment(
                        "docs",
                        ACCENT,
                        link="https://example.invalid",
                        action="open",
                    ),
                    Segment(" now", Style()),
                ]
            ).fit(width)
        ]


def test_text_renders_plain_rows_unchanged_and_the_flag_alone_paints_nothing():
    text = Text("hi\nthere", style=DIM)
    rows = text.render(10)
    assert [row.text for row in rows] == ["hi", "there"]
    assert rows is not text.render(10)  # every hand-out is the caller's own list
    before = [row.styled() for row in rows]
    text.hover = True  # the protocol flag: no visual of its own here
    assert [row.styled() for row in text.render(10)] == before
    # Verbatim rows carry no payload: every hover and click declines, and
    # nothing lands in ``chosen`` (a miss is never a consumption).
    assert text.hover_at(0, 0) is False and text.hover_at(0, 1) is False
    assert text.hover_at(0, 0) is False  # the second call: still nothing changed
    assert text.click(0, 0) is False and text.click(5, 0) is False
    assert text.chosen is None


def test_text_click_takes_a_span_payload_into_chosen_once():
    text = SpanText()
    text.render(40)
    assert text.click(0, 0) is False  # "see " carries no action
    assert text.click(0, 12) is False  # past the row's text
    assert text.click(1, 5) is False  # no such row
    assert text.chosen is None
    assert text.click(0, 5) is True  # inside "docs" (columns 4..8)
    assert text.chosen == "open"
    text.chosen = None  # the host reads a pick exactly once and resets it
    assert text.chosen is None
    assert text.click(0, 4) is True and text.click(0, 7) is True  # the whole span


def test_text_hover_enters_moves_and_leaves_with_zero_bytes_on_exit():
    text = SpanText()
    base = text.render(40)
    base_bytes = base[0].styled()
    # Enter the span: the row repaints with the theme's hover merged on the
    # span's own segment -- the payloads ride along on the restyled copy.
    assert text.hover_at(0, 5) is True
    hovered = text.render(40)
    assert hovered[0] != base[0] and hovered[0].text == base[0].text
    span = hovered[0].segments[1]
    assert span.style == ACCENT.merge(DEFAULT_THEME.hover)
    assert (span.link, span.action) == ("https://example.invalid", "open")
    assert hovered[0].segments[0] == base[0].segments[0]  # runs outside the span
    assert hovered[0].segments[2] == base[0].segments[2]  # keep their own style
    # Moving within the one span changes nothing; leaving it does.
    assert text.hover_at(0, 6) is False and text.render(40)[0] == hovered[0]
    assert text.hover_at(0, 0) is True  # onto the plain "see "
    assert text.render(40)[0] == base[0]
    assert text.hover_at(0, 0) is False  # already off the span
    # The zero-byte proof: the row after the pointer left is the base row,
    # byte for byte, and the span is still clickable.
    assert text.render(40)[0].styled() == base_bytes
    assert text.click(0, 5) is True and text.chosen == "open"
    # ``row < 0`` clears the mark (the pointer left the component).
    assert text.hover_at(0, 5) is True and text.hover_at(-1, -1) is True
    assert text.render(40)[0].styled() == base_bytes
    assert text.hover_at(-1, -1) is False


def test_text_hover_reads_the_themes_hover_band():
    band = Style(fg="#ff00ff", reverse=True)
    text = SpanText(theme=replace(DEFAULT_THEME, hover=band))
    text.render(40)
    text.hover_at(0, 5)
    assert ACCENT.merge(band).prefix() in text.render(40)[0].styled()
    # A theme of its own never mutates the shipped one.
    assert DEFAULT_THEME.hover != band and SpanText()._theme is DEFAULT_THEME


def test_line_merge_span_restyles_only_the_intersecting_segments():
    row = Line(
        [
            Segment("see ", Style()),
            Segment("docs", ACCENT, link="u", action="open"),
            Segment(" now", Style()),
        ]
    )
    merged = row.merge_span(4, 8, DEFAULT_THEME.hover)
    assert merged is not row and merged.text == row.text
    assert merged.segments[0] is row.segments[0]  # untouched: the same object
    assert merged.segments[2] is row.segments[2]
    assert merged.segments[1] == Segment(
        "docs", ACCENT.merge(DEFAULT_THEME.hover), link="u", action="open"
    )
    # A range that meets no non-empty segment answers the row itself: nothing
    # repaints, and every reader keeps one value.
    assert row.merge_span(99, 120, DEFAULT_THEME.hover) is row
    assert row.merge_span(4, 4, DEFAULT_THEME.hover) is row
    assert row.merge_span(-3, 0, DEFAULT_THEME.hover) is row
    # A cut range restyles only what it meets.
    cut = row.merge_span(0, 4, DEFAULT_THEME.hover)
    assert cut.segments[0] != row.segments[0]
    assert cut.segments[1] is row.segments[1]


# --- grapheme corners (D17) ------------------------------------------------------
# The four terminal-relevant cluster classes, each pinned on the rule and on
# its cells: combining marks, variation selectors, the zero-width joiner and
# regional-indicator pairs.  The numbers are the ones the wave's wave-order
# comparison ran -- every one of them was already the answer before the
# compact rule tables landed (``wcwidth`` reports a zero width for every
# assigned mark), and these tests are what makes the rule explicit and keeps
# it from drifting.

from unicodedata import category  # noqa: E402

from motui.kernel.text import (  # noqa: E402
    _MARK_RANGES,
    _VARIATION,
    _VARIATION_SUPPLEMENT,
    _cell_spans,
    _is_mark,
)


def test_combining_marks_merge_into_the_cluster_they_follow():
    # A Mn mark after a narrow base, an Me mark (the enclosing keycap), a
    # mark on a wide base, stacked marks: none adds a column, and each is
    # part of the base's one cell.
    assert visible_width("e\u0301") == 1
    assert list(_cell_spans("e\u0301")) == [(0, 2, 1)]
    assert visible_width("1\u20e3") == 1
    assert list(_cell_spans("1\u20e3")) == [(0, 2, 1)]
    assert visible_width("\u4e2d\u0301") == 2  # the wide base keeps its two
    assert visible_width("e\u0301\u0302\u0303") == 1
    assert list(_cell_spans("e\u0301\u0302\u0303")) == [(0, 4, 1)]
    # A mark with no base at all starts no cell (its width is 0).
    assert visible_width("\u0301") == 0
    assert visible_width("\u0301abc") == 3
    assert list(_cell_spans("\u0301abc")) == [(1, 2, 1), (2, 3, 1), (3, 4, 1)]


def test_the_compact_mark_table_is_sorted_disjoint_and_all_mn_me():
    # The table's hygiene, checked against the interpreter's own category
    # data: sorted, disjoint ranges, and not one code point claimed as a
    # mark that is not Mn/Me.
    assert len(_MARK_RANGES) > 300
    previous = -1
    for start, stop in _MARK_RANGES:
        assert start <= stop and start > previous, (hex(start), hex(stop))
        previous = stop
    wrong = [
        hex(cp)
        for start, stop in _MARK_RANGES
        for cp in range(start, stop + 1)
        if category(chr(cp)) not in ("Mn", "Me")
    ]
    assert wrong == []
    # And in the BMP -- where every composed script's marks live -- the
    # table misses nothing: each Mn/Me code point there is covered.
    covered = set()
    for start, stop in _MARK_RANGES:
        covered.update(range(start, min(stop, 0xFFFF) + 1))
    missing = [
        hex(cp)
        for cp in range(0x10000)
        if category(chr(cp)) in ("Mn", "Me") and cp not in covered
    ]
    assert missing == []
    # The predicate the scanner runs is the table's own answer, for the
    # marks the corpus uses and for the table's first and last entries.
    for ch in ("\u0301", "\u20e3", "\u05b8", "\u064b", chr(_MARK_RANGES[0][0])):
        assert _is_mark(ch) is True
    assert _is_mark(chr(_MARK_RANGES[-1][1])) is True
    for ch in ("a", " ", "\u4e2d", "\U0001F600", "\u200d"):  # the joiner is no mark
        assert _is_mark(ch) is False


def test_variation_selectors_merge_into_their_base_cell():
    # VS1..VS16: VS16 takes the emoji presentation (the base widens to 2),
    # VS15 keeps the text one; the VS17..VS256 supplement is zero width.
    assert visible_width("\u2764\ufe0f") == 2
    assert visible_width("\u2764\ufe0e") == 1
    assert visible_width("\u2764\U000E0100") == 1
    assert list(_cell_spans("\u2764\U000E0100")) == [(0, 2, 1)]
    assert visible_width("\u2764\ufe0f\ufe0f") == 2  # stacked selectors, one cell
    assert list(_cell_spans("\u2764\ufe0f\ufe0f")) == [(0, 3, 2)]
    # A selector with no base starts no cell; one after a mark still merges
    # into the cluster the mark rode in on.
    assert visible_width("\ufe0fabc") == 3
    assert visible_width("\U000E0100") == 0
    assert visible_width("e\u0301\U000E0100") == 1
    assert list(_cell_spans("e\u0301\U000E0100")) == [(0, 3, 1)]
    # The named ranges carry exactly the selectors, and the mark table
    # covers the supplement (its members are Mn).
    assert 0xFE00 in _VARIATION and 0xFE0F in _VARIATION
    assert 0xFE10 not in _VARIATION and 0xFE00 not in _VARIATION_SUPPLEMENT
    assert 0xE0100 in _VARIATION_SUPPLEMENT and 0xE01EF in _VARIATION_SUPPLEMENT
    assert 0xE01F0 not in _VARIATION_SUPPLEMENT
    assert all(_is_mark(chr(cp)) for cp in (0xE0100, 0xE0101, 0xE01EF))


def test_the_joiner_pulls_the_next_cell_into_the_cluster():
    # ZWJ is zero width and the cell it introduces joins the cluster, whose
    # width is the base's alone.
    assert visible_width("a\u200db") == 1
    assert list(_cell_spans("a\u200db")) == [(0, 3, 1)]
    assert visible_width("a\u200d") == 1  # a trailing joiner joins nothing
    assert visible_width("\u200dabc") == 3  # a leading joiner starts no cell
    assert visible_width("a\u200d\u200db") == 1  # the second joins through the first
    assert visible_width("a\u200d\ufe0f") == 1
    # The family sequence of the fixture measures the same as before: one
    # 2-column cluster.
    assert visible_width(
        "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"
    ) == 2


def test_regional_indicators_pair_into_one_flag_cell():
    # Two indicators are one 2-column flag: the second contributes 0 beyond
    # it, the pair's own two columns are the flag.  A lone indicator keeps
    # its 2-column cell (the existing behaviour), and a run pairs left to
    # right.
    assert visible_width("\U0001F1EF") == 2
    assert list(_cell_spans("\U0001F1EF")) == [(0, 1, 2)]
    assert visible_width("\U0001F1EF\U0001F1F5") == 2
    assert list(_cell_spans("\U0001F1EF\U0001F1F5")) == [(0, 2, 2)]
    assert visible_width("\U0001F1EF\U0001F1F5\U0001F1E8") == 4  # pair + single
    assert visible_width("\U0001F1EF\U0001F1F5\U0001F1E8\U0001F1F3") == 4  # two flags
    assert list(_cell_spans("\U0001F1EF\U0001F1F5\U0001F1E8\U0001F1F3")) == [
        (0, 2, 2),
        (2, 4, 2),
    ]


def test_the_cut_family_keeps_a_cluster_together_at_its_boundaries():
    # The mark rides with its base through every column cut: the fit keeps
    # the whole cluster and drops the next character, never half a cluster.
    assert fit_text("e\u0301x", 1) == "e\u0301"
    assert fit_text("e\u0301x", 2) == "e\u0301x"
    assert fit_text("\u4e2d\u0301", 1) == ""  # the two columns do not fit
    assert fit_text("\u4e2d\u0301", 2) == "\u4e2d\u0301"
    # A supplement selectored base is one display column, so a one-column
    # cut takes the whole cluster (chars and selector alike) and the next
    # cut takes the character after it.
    row = Line.from_text("\u2764\U000E0100x")
    assert (row.width, visible_width("\u2764\U000E0100")) == (2, 1)
    assert cut_line(row, 0, 1).text == "\u2764\U000E0100"
    assert cut_line(row, 1, 2).text == "x"
