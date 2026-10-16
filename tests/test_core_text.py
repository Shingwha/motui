"""The text kernel: the measuring truth, the fit family, and the Line row.

``visible_width`` is the single width truth; ``fit_text``, ``ellipsize_tail``,
``wrap_text`` and ``Line.fit`` build on it, so no row ever exceeds the width.
"""

import itertools

import pytest

from mocode_tui.core.ansi import ESC
from mocode_tui.core.lines import Line, Segment, cut_line, styled_with, wrap_line
from mocode_tui.core.style import ACCENT, MUTED, NONE, RESET, SUCCESS, Style
from mocode_tui.core.text import (
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


def test_ellipsize_tail():
    assert ellipsize_tail("abc", 3) == "abc"  # fits: unchanged
    assert ellipsize_tail("", 3) == ""
    result = ellipsize_tail("abcdef", 4)
    assert result == "abc…" and visible_width(result) == 4
    assert ellipsize_tail("abcdef", 1) == "…"
    assert ellipsize_tail("abcdef", 0) == ""
    assert ellipsize_tail("abcdef", -5) == ""
    assert ellipsize_tail("日本語", 4) == "日…"  # wide chars stay within the budget


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


def test_styled_with_matches_styled_on_truecolor():
    row = Line([Segment("a", ACCENT), Segment("b", MUTED)])
    assert styled_with(row, "truecolor") == row.styled()


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

    from mocode_tui.core.text import _cell_spans

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
    from mocode_tui.core.text import index_bounds_at_columns, index_pair_at_columns

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


# -- the Text component (mocode_tui.core.lines.Text) ----------------------------
from mocode_tui.core.style import DIM  # noqa: E402
from mocode_tui.core.lines import Text  # noqa: E402


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
